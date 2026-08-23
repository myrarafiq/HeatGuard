from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.fixtures import load_fixtures_into_db, write_fixtures


def main() -> None:
    parser = argparse.ArgumentParser(description="Write/load demo backup fixtures into SQLite.")
    parser.add_argument("--write-only", action="store_true")
    args = parser.parse_args()
    path = write_fixtures()
    print(f"Wrote {path}")
    if not args.write_only:
        n = load_fixtures_into_db(path)
        print(f"Loaded {n} hour rows into the database.")


if __name__ == "__main__":
    main()
