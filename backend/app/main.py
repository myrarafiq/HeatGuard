from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import connect, list_hours
from .fixtures import load_fixtures_into_db
from .safety.ai import maybe_llm_explain, render_brief_template
from .safety.planner import build_planner
from .safety.thresholds import WORKLOAD_DEFINITIONS
from .sites import get_site, load_sites

WorkloadParam = Literal["light", "moderate", "heavy", "very_heavy"]

app = FastAPI(
    title="HeatGuard API",
    description=(
        "Person 1+2 backend for the FortyGuard Hackathon: FortyGuard forecasts → "
        "OSHA/NIOSH screening risk → recommendations → AI explanation. No frontend."
    ),
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskBody(BaseModel):
    question: str = Field(..., min_length=1)
    workload: WorkloadParam = "heavy"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "heatguard"}


@app.get("/sites")
def sites() -> dict:
    return {"sites": [site.to_public_dict() for site in load_sites()]}


@app.get("/sites/{site_id}")
def site_detail(site_id: str) -> dict:
    try:
        return get_site(site_id).to_public_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/workloads")
def workloads() -> dict:
    return {"workloads": WORKLOAD_DEFINITIONS}


@app.get("/hours")
def hours(site_id: str | None = None) -> dict:
    with connect() as conn:
        return {"hours": list_hours(conn, site_id)}


@app.post("/demo/load-fixtures")
def demo_load_fixtures() -> dict:
    """Load backup demo day into SQLite (for judging if live API is down)."""
    n = load_fixtures_into_db()
    return {"loaded": n}


@app.get("/planner")
def planner(workload: WorkloadParam = Query(default="heavy")) -> dict:
    site_rows = [site.to_public_dict() for site in load_sites()]
    with connect() as conn:
        hour_rows = list_hours(conn)
    if not hour_rows:
        # Auto-load demo fixtures so frontend always has something to render.
        load_fixtures_into_db()
        with connect() as conn:
            hour_rows = list_hours(conn)
    return build_planner(site_rows, hour_rows, workload)


@app.get("/planner/snapshot")
def planner_snapshot(workload: WorkloadParam = Query(default="heavy")) -> dict:
    """Backward-compatible alias used earlier by Person 1."""
    return planner(workload)


@app.get("/planner/compare")
def planner_compare(
    workload: WorkloadParam = Query(default="heavy"),
    hour_local: str | None = None,
) -> dict:
    data = planner(workload)
    if hour_local:
        from .safety.recommend import compare_sites_at_hour

        assessments = [h for s in data["sites"] for h in s["hours"]]
        return compare_sites_at_hour(assessments, hour_local=hour_local)
    return data.get("comparison_at_10am") or data["comparison"]


@app.get("/planner/brief")
def planner_brief(workload: WorkloadParam = Query(default="heavy")) -> dict:
    data = planner(workload)
    return {"brief": render_brief_template(data), "workload": workload}


@app.post("/planner/ask")
def planner_ask(body: AskBody) -> dict:
    data = planner(body.workload)
    result = maybe_llm_explain(body.question, data)
    return {"question": body.question, "workload": body.workload, **result}
