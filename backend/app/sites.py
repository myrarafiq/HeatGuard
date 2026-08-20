from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import SITES_PATH


def square_polygon(lon: float, lat: float, half_deg: float) -> dict[str, Any]:
    coords = [
        [lon - half_deg, lat - half_deg],
        [lon + half_deg, lat - half_deg],
        [lon + half_deg, lat + half_deg],
        [lon - half_deg, lat + half_deg],
        [lon - half_deg, lat - half_deg],
    ]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [coords]},
            }
        ],
    }


@dataclass(frozen=True)
class Site:
    id: str
    name: str
    city: str
    surface: str
    lat: float
    lon: float
    half_deg: float

    @property
    def polygon_aoi(self) -> dict[str, Any]:
        return square_polygon(self.lon, self.lat, self.half_deg)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "surface": self.surface,
            "lat": self.lat,
            "lon": self.lon,
            "polygon_aoi": self.polygon_aoi,
        }


def load_sites(path: Path | None = None) -> list[Site]:
    data = json.loads((path or SITES_PATH).read_text())
    return [Site(**row) for row in data["sites"]]


def get_site(site_id: str) -> Site:
    for site in load_sites():
        if site.id == site_id:
            return site
    raise KeyError(f"Unknown site_id: {site_id}")
