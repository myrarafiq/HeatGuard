from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.fortyguard_client import FortyGuardClient
from backend.app.pipeline import fetch_site_hours
from backend.app.sites import get_site
from backend.app.time_windows import parse_local_hour


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a 12-hour FortyGuard series for one site.")
    parser.add_argument("site_id")
    parser.add_argument("--when")
    parser.add_argument("--hours", type=int, default=12)
    args = parser.parse_args()

    site = get_site(args.site_id)
    start = parse_local_hour(args.when)
    with FortyGuardClient() as client:
        rows = fetch_site_hours(client, site, start, hours=args.hours)
    for row in rows:
        print(
            f"{row['hour_local']} mean={row.get('temp_c_mean')} "
            f"Tw={row.get('wet_bulb_temperature_celsius')} RH={row.get('relative_humidity_percent')}"
        )


if __name__ == "__main__":
    main()
