from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import HEATMAP_GRANULARITY_M, SITES_PATH


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

    def approx_side_m(self) -> float:
        """half_deg is degrees of latitude/longitude; 1° lat ≈ 111 km."""
        return round(self.half_deg * 2 * 111_000, 0)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "surface": self.surface,
            "lat": self.lat,
            "lon": self.lon,
            "half_deg": self.half_deg,
            "approx_side_m": self.approx_side_m(),
            "heatmap_granularity_m": HEATMAP_GRANULARITY_M,
            "polygon_aoi": self.polygon_aoi,
        }


def load_sites(path: Path | None = None) -> list[Site]:
    data = json.loads((path or SITES_PATH).read_text())
    rows = data["sites"]
    allowed = {"id", "name", "city", "surface", "lat", "lon", "half_deg"}
    return [Site(**{k: v for k, v in row.items() if k in allowed}) for row in rows]


def get_site(site_id: str) -> Site:
    for site in load_sites():
        if site.id == site_id:
            return site
    raise KeyError(f"Unknown site_id: {site_id}")
