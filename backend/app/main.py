from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT
from .db import connect, list_hours, summarize_data_mode
from .fixtures import build_demo_day, load_fixtures_into_db
from .fortyguard_client import FortyGuardClient
from .safety.ai import maybe_llm_explain, render_brief_template
from .safety.planner import build_planner
from .safety.thresholds import (
    CLOTHING_ADJUSTMENT_C,
    DEFAULT_ACCLIMATIZED,
    DEFAULT_CLOTHING,
    EXTRA_PPE_CLOTHING,
    WORKLOAD_DEFINITIONS,
    ClothingId,
    planning_assumption,
    resolve_clothing,
)
from .sites import get_site, load_sites

WorkloadParam = Literal["light", "moderate", "heavy", "very_heavy"]
DASHBOARD_DIR = ROOT / "frontend" / "dashboard"
ON_VERCEL = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))

app = FastAPI(
    title="HeatGuard API",
    description=(
        "FortyGuard Hackathon submission: hyperlocal forecasts → OSHA/NIOSH screening risk "
        "→ recommendations → manager dashboard."
    ),
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _planner_hours() -> list:
    """Hours for the planner. Never 500 on a read-only filesystem — fixtures are the demo fallback."""
    try:
        with connect() as conn:
            hour_rows = list_hours(conn)
        if not hour_rows:
            load_fixtures_into_db()
            with connect() as conn:
                hour_rows = list_hours(conn)
        if hour_rows:
            return hour_rows
    except Exception:
        pass
    rows = build_demo_day()
    for row in rows:
        row["data_source"] = "fixture"
    return rows


class AskBody(BaseModel):
    question: str = Field(..., min_length=1)
    workload: WorkloadParam = "heavy"
    acclimatized: bool = DEFAULT_ACCLIMATIZED
    extra_ppe: bool = False
    clothing: ClothingId = DEFAULT_CLOTHING
    hour_local: str | None = None


@app.get("/health")
def health() -> dict:
    db_error = None
    try:
        hour_rows = _planner_hours()
        summary = summarize_data_mode(hour_rows)
    except Exception as exc:  # noqa: BLE001
        db_error = str(exc)
        hour_rows = []
        summary = summarize_data_mode([])
    credits = {"credits_remaining": None, "credits_status": "skipped"}
    if not ON_VERCEL:
        try:
            with FortyGuardClient() as client:
                credits = client.credits_remaining()
        except Exception as exc:  # noqa: BLE001
            credits = {"credits_remaining": None, "credits_status": "error", "credits_error": str(exc)}
    return {
        "status": "ok",
        "service": "heatguard",
        "data_mode": summary.get("mode"),
        "last_successful_pull": summary.get("last_successful_pull"),
        **summary,
        **credits,
        **({"db_error": db_error} if db_error else {}),
    }


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
    return {
        "workloads": WORKLOAD_DEFINITIONS,
        "clothing": CLOTHING_ADJUSTMENT_C,
        "extra_ppe_flag": {
            "clothing": EXTRA_PPE_CLOTHING,
            **CLOTHING_ADJUSTMENT_C[EXTRA_PPE_CLOTHING],
            "source": "OSHA Heat Hazard Recognition clothing adjustment table",
        },
        "default_assumption": planning_assumption(
            acclimatized=DEFAULT_ACCLIMATIZED,
            clothing=DEFAULT_CLOTHING,
        ),
    }


@app.get("/hours")
def hours(site_id: str | None = None) -> dict:
    rows = _planner_hours()
    if site_id:
        rows = [row for row in rows if row.get("site_id") == site_id]
    return {"hours": rows}


@app.post("/demo/load-fixtures")
def demo_load_fixtures() -> dict:
    """Replace DB contents with the backup demo day (never mixed with live rows)."""
    try:
        n = load_fixtures_into_db(replace=True)
        return {"loaded": n, "data_source": "fixture", "replaced": True}
    except Exception as exc:  # noqa: BLE001 — serverless may not persist SQLite
        rows = build_demo_day()
        return {
            "loaded": len(rows),
            "data_source": "fixture",
            "replaced": False,
            "persisted": False,
            "error": str(exc),
        }


@app.get("/planner")
def planner(
    workload: WorkloadParam = Query(default="heavy"),
    acclimatized: bool = Query(default=DEFAULT_ACCLIMATIZED),
    clothing: ClothingId = Query(default=DEFAULT_CLOTHING),
    extra_ppe: bool = Query(default=False),
    hour_local: str | None = Query(default=None),
) -> dict:
    site_rows = [site.to_public_dict() for site in load_sites()]
    hour_rows = _planner_hours()
    return build_planner(
        site_rows,
        hour_rows,
        workload,
        acclimatized=acclimatized,
        clothing=resolve_clothing(clothing, extra_ppe),
        hour_local=hour_local,
    )


@app.get("/planner/snapshot")
def planner_snapshot(
    workload: WorkloadParam = Query(default="heavy"),
    acclimatized: bool = Query(default=DEFAULT_ACCLIMATIZED),
    clothing: ClothingId = Query(default=DEFAULT_CLOTHING),
    extra_ppe: bool = Query(default=False),
    hour_local: str | None = Query(default=None),
) -> dict:
    """Alias for /planner (used by dashboard docs)."""
    return planner(workload, acclimatized, clothing, extra_ppe, hour_local)


@app.get("/planner/compare")
def planner_compare(
    workload: WorkloadParam = Query(default="heavy"),
    acclimatized: bool = Query(default=DEFAULT_ACCLIMATIZED),
    clothing: ClothingId = Query(default=DEFAULT_CLOTHING),
    extra_ppe: bool = Query(default=False),
    hour_local: str | None = None,
) -> dict:
    data = planner(
        workload,
        acclimatized,
        clothing,
        extra_ppe,
        hour_local,
    )
    if hour_local:
        from .safety.recommend import compare_sites_at_hour

        assessments = [h for s in data["sites"] for h in s["hours"]]
        return compare_sites_at_hour(assessments, hour_local=hour_local)
    return data.get("comparison_at_10am") or data["comparison"]


@app.get("/planner/brief")
def planner_brief(
    workload: WorkloadParam = Query(default="heavy"),
    acclimatized: bool = Query(default=DEFAULT_ACCLIMATIZED),
    clothing: ClothingId = Query(default=DEFAULT_CLOTHING),
    extra_ppe: bool = Query(default=False),
    hour_local: str | None = Query(default=None),
) -> dict:
    data = planner(workload, acclimatized, clothing, extra_ppe, hour_local)
    return {"brief": render_brief_template(data), "workload": workload, "assumption": data.get("assumption")}


@app.post("/planner/ask")
def planner_ask(body: AskBody) -> dict:
    data = planner(
        body.workload,
        body.acclimatized,
        body.clothing,
        body.extra_ppe,
        body.hour_local,
    )
    result = maybe_llm_explain(body.question, data)
    return {"question": body.question, "workload": body.workload, **result}


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "index.html")


if DASHBOARD_DIR.is_dir() and not ON_VERCEL:
    app.mount("/assets", StaticFiles(directory=str(DASHBOARD_DIR)), name="dashboard-assets")
