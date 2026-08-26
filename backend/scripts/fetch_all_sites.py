from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.pipeline import fetch_sites_parallel
from backend.app.sites import load_sites
from backend.app.time_windows import parse_local_hour


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch forecasts for multiple sites.")
    parser.add_argument("--when", help="Start hour local Florida time")
    parser.add_argument("--hours", type=int, default=12)
    parser.add_argument(
        "--sites",
        default="all",
        help="Comma-separated site ids, or 'all'",
    )
    parser.add_argument("--workers", type=int, default=None, help="Parallel site fetches (default 2).")
    args = parser.parse_args()

    start = parse_local_hour(args.when)
    sites = load_sites()
    if args.sites != "all":
        wanted = {s.strip() for s in args.sites.split(",") if s.strip()}
        sites = [s for s in sites if s.id in wanted]

    by_site = fetch_sites_parallel(sites, start, hours=args.hours, max_workers=args.workers)
    for site in sites:
        rows = by_site.get(site.id) or []
        print(f"=== {site.id} ({len(rows)}h from {start.isoformat()}) ===")
        for row in rows:
            print(
                f"  {row['hour_local']} mean={row.get('temp_c_mean')} "
                f"hotspot={row.get('temp_c_p90') or row.get('temp_c_max')} "
                f"spread={row.get('tile_spread_c')} "
                f"city={row.get('city_temp_c')} "
                f"Tw={row.get('wet_bulb_temperature_celsius')}"
            )


if __name__ == "__main__":
    main()
