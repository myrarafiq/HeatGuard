from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.fortyguard_client import FortyGuardClient
from backend.app.pipeline import fetch_site_hours
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
    args = parser.parse_args()

    start = parse_local_hour(args.when)
    sites = load_sites()
    if args.sites != "all":
        wanted = {s.strip() for s in args.sites.split(",") if s.strip()}
        sites = [s for s in sites if s.id in wanted]

    with FortyGuardClient() as client:
        for site in sites:
            print(f"=== {site.id} ({args.hours}h from {start.isoformat()}) ===")
            rows = fetch_site_hours(client, site, start, hours=args.hours)
            for row in rows:
                print(
                    f"  {row['hour_local']} mean={row.get('temp_c_mean')} "
                    f"Tw={row.get('wet_bulb_temperature_celsius')}"
                )


if __name__ == "__main__":
    main()
