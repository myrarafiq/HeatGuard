from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .db import connect, list_hours
from .sites import get_site, load_sites

app = FastAPI(
    title="Heat Safety Planner API",
    description="Person 1 backend: FortyGuard site forecasts as clean hourly JSON. No risk math.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sites")
def sites() -> dict:
    return {"sites": [site.to_public_dict() for site in load_sites()]}


@app.get("/sites/{site_id}")
def site_detail(site_id: str) -> dict:
    try:
        return get_site(site_id).to_public_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/hours")
def hours(site_id: str | None = None) -> dict:
    with connect() as conn:
        return {"hours": list_hours(conn, site_id)}


@app.get("/planner/snapshot")
def planner_snapshot() -> dict:
    """Structured payload for Person 2 (risk engine) and Person 3 (dashboard)."""
    sites = [site.to_public_dict() for site in load_sites()]
    with connect() as conn:
        rows = list_hours(conn)
    by_site: dict[str, list] = {}
    for row in rows:
        by_site.setdefault(row["site_id"], []).append(row)
    for site in sites:
        site["hours"] = by_site.get(site["id"], [])
    return {"sites": sites}
