from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.fortyguard_client import FortyGuardClient
from backend.app.pipeline import fetch_site_hour, fetch_site_hours
from backend.app.sites import load_sites
from backend.app.time_windows import parse_local_hour


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull live FortyGuard snapshots for Miami test sites.")
    parser.add_argument("--when", help="Local Florida datetime, e.g. 2026-08-26T14:00. Default: current hour.")
    parser.add_argument("--sites", default="brickell,miami_beach,doral", help="Comma-separated site ids.")
    parser.add_argument("--hours", type=int, default=1, help="Number of consecutive hours starting at --when.")
    args = parser.parse_args()

    start = parse_local_hour(args.when)
    wanted = {s.strip() for s in args.sites.split(",") if s.strip()}
    sites = [site for site in load_sites() if site.id in wanted]
    if not sites:
        raise SystemExit(f"No matching sites. Available: {[s.id for s in load_sites()]}")

    rows = []
    with FortyGuardClient() as client:
        try:
            print("credits:", json.dumps(client.credits(), indent=2)[:1000])
        except Exception as exc:
            print(f"(credits lookup skipped: {exc})")
        for site in sites:
            print(f"Fetching {site.id} ({args.hours}h from {start.isoformat()}) ...")
            if args.hours == 1:
                batch = [fetch_site_hour(client, site, start)]
            else:
                batch = fetch_site_hours(client, site, start, hours=args.hours)
            rows.extend(batch)
            for record in batch:
                print(
                    f"  {record.get('hour_local')} mean={record.get('temp_c_mean')} "
                    f"min={record.get('temp_c_min')} max={record.get('temp_c_max')} "
                    f"tiles={record.get('tile_count')} "
                    f"Tw={record.get('wet_bulb_temperature_celsius')} "
                    f"RH={record.get('relative_humidity_percent')} "
                    f"src={record.get('data_source')}"
                )

    print("\nGO/NO-GO comparison (same hour, different sites)")
    print(f"{'site':16} {'mean°C':>8} {'min°C':>8} {'max°C':>8} {'Tw°C':>8} {'RH%':>8}")
    for row in rows:
        print(
            f"{row['site_id']:16} "
            f"{_fmt(row.get('temp_c_mean')):>8} "
            f"{_fmt(row.get('temp_c_min')):>8} "
            f"{_fmt(row.get('temp_c_max')):>8} "
            f"{_fmt(row.get('wet_bulb_temperature_celsius')):>8} "
            f"{_fmt(row.get('relative_humidity_percent')):>8}"
        )

    means = [r["temp_c_mean"] for r in rows if r.get("temp_c_mean") is not None]
    if len(means) >= 2:
        spread = max(means) - min(means)
        print(f"\nMean temperature spread across sites: {spread:.2f} °C")
        if spread >= 1.0:
            print("PROVISIONAL GO: sites differ by ≥ 1°C at the same time.")
        else:
            print("Needs more hours/sites: spread < 1°C for this snapshot.")


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    return f"{float(value):.2f}"


if __name__ == "__main__":
    main()
