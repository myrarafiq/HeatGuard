import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.app.db import clear_hours, connect, infer_data_source, list_hours, summarize_data_mode, upsert_hour
from backend.app.normalize import env_values_for_hour, extract_env_series, heatmap_mean_c, merge_hour_record
from backend.app.pipeline import fetch_site_hours
from backend.app.safety.planner import build_planner
from backend.app.sites import Site
from backend.app.time_windows import hour_range


TZ = ZoneInfo("America/New_York")
SITE = Site(
    id="brickell",
    name="Brickell Tower Site",
    city="Miami",
    surface="urban",
    lat=25.7617,
    lon=-80.1918,
    half_deg=0.0014,
)


def _heatmap(mean=31.26):
    return {
        "data": {
            "result": {
                "map_data": {
                    "type": "FeatureCollection",
                    "features": [
                        {"type": "Feature", "properties": {"average_temperature": mean}},
                    ],
                },
                "stats_data": {
                    "temperature_stats": {
                        "minimum": mean - 0.1,
                        "maximum": mean + 0.1,
                        "mean": mean,
                        "standard_deviation": 0.07,
                    }
                },
            }
        }
    }


def _env_series():
    return {
        "data": {
            "result": {
                "metadata": {
                    "timestamps": [
                        "2024-07-15T06:00:00-04:00",
                        "2024-07-15T14:00:00-04:00",
                    ]
                },
                "locations": [
                    {
                        "parameters": {
                            "wet_bulb_temperature_celsius": [22.0, 26.4],
                            "relative_humidity_percent": [70.0, 76.3],
                            "apparent_temperature_celsius": [30.0, 34.2],
                        },
                        "solar_irradiance": {"clear_sky": {"ghi": [120.0, 844.0]}},
                    }
                ],
            }
        }
    }


class FakeClient:
    def __init__(self, heatmap=None, env=None, heatmap_error=None):
        self.heatmap = heatmap if heatmap is not None else _heatmap()
        self.env = env if env is not None else _env_series()
        self.heatmap_error = heatmap_error
        self.heatmap_calls = []
        self.env_calls = []

    def submit_heatmap(self, polygon, date_time, **kwargs):
        self.heatmap_calls.append(date_time)
        if self.heatmap_error:
            raise RuntimeError(self.heatmap_error)
        return "hm"

    def submit_env_params(self, lat, lon, temperature, date_time, **kwargs):
        self.env_calls.append({"temperature": temperature, "date_time": date_time, "lat": lat, "lon": lon})
        return "env"

    def wait_for_result(self, activity_id):
        if activity_id == "hm":
            return self.heatmap
        return self.env


class EnvAlignTests(unittest.TestCase):
    def test_picks_matching_hour_not_index_zero(self):
        series = extract_env_series(_env_series())
        six = env_values_for_hour(series, "2024-07-15T06:00:00-04:00")
        two = env_values_for_hour(series, "2024-07-15T14:00:00-04:00")
        self.assertEqual(six["wet_bulb_temperature_celsius"], 22.0)
        self.assertEqual(two["wet_bulb_temperature_celsius"], 26.4)
        self.assertEqual(two["solar_ghi"], 844.0)

    def test_unaligned_hour_is_missing_not_first_step(self):
        series = extract_env_series(_env_series())
        vals = env_values_for_hour(series, "2024-07-15T11:00:00-04:00")
        self.assertIsNone(vals["wet_bulb_temperature_celsius"])
        self.assertTrue(vals.get("env_hour_unaligned"))

    def test_merge_uses_aligned_wet_bulb(self):
        record = merge_hour_record(
            site_id="brickell",
            hour_local="2024-07-15T14:00:00-04:00",
            heatmap=_heatmap(),
            env=_env_series(),
            heatmap_activity_id="hm",
            env_activity_id="env",
            data_source="live",
        )
        self.assertEqual(record["wet_bulb_temperature_celsius"], 26.4)
        self.assertEqual(record["data_source"], "live")
        self.assertNotIn("env_timestamp_match", record["missing_fields"])


class PipelineFetchTests(unittest.TestCase):
    def test_range_fetch_is_one_heatmap_and_one_env(self):
        client = FakeClient()
        start = datetime(2024, 7, 15, 6, 0, tzinfo=TZ)
        rows = fetch_site_hours(client, SITE, start, hours=12, persist=False, save_raw=False)
        self.assertEqual(len(client.heatmap_calls), 1)
        self.assertEqual(len(client.env_calls), 1)
        self.assertEqual(client.heatmap_calls[0]["filter_type"], 2)
        self.assertEqual(client.heatmap_calls[0]["start_time"], "06:00")
        self.assertEqual(client.heatmap_calls[0]["end_time"], "17:00")
        self.assertEqual(client.env_calls[0]["date_time"]["filter_type"], 2)
        self.assertEqual(len(rows), 12)
        two_pm = next(r for r in rows if "T14:" in r["hour_local"])
        six_am = next(r for r in rows if "T06:" in r["hour_local"])
        self.assertEqual(two_pm["wet_bulb_temperature_celsius"], 26.4)
        self.assertEqual(six_am["wet_bulb_temperature_celsius"], 22.0)
        self.assertEqual(two_pm["data_source"], "live")
        self.assertNotEqual(client.env_calls[0]["temperature"], 32.0)

    def test_missing_heatmap_temp_skips_env_and_does_not_invent_32(self):
        empty = {"data": {"result": {"stats_data": {}, "map_data": {"features": []}}}}
        client = FakeClient(heatmap=empty)
        start = datetime(2024, 7, 15, 14, 0, tzinfo=TZ)
        rows = fetch_site_hours(client, SITE, start, hours=1, persist=False, save_raw=False)
        self.assertEqual(client.env_calls, [])
        self.assertIsNone(rows[0]["temp_c_mean"])
        self.assertIsNone(rows[0]["wet_bulb_temperature_celsius"])
        self.assertIn("temp_c_mean", rows[0]["missing_fields"])
        self.assertEqual(rows[0]["env_skipped"], "missing_heatmap_temperature")
        self.assertIsNone(heatmap_mean_c(empty))

    def test_heatmap_failure_skips_env(self):
        client = FakeClient(heatmap_error="timeout")
        start = datetime(2024, 7, 15, 14, 0, tzinfo=TZ)
        rows = fetch_site_hours(client, SITE, start, hours=1, persist=False, save_raw=False)
        self.assertEqual(client.env_calls, [])
        self.assertIsNone(rows[0]["temp_c_mean"])
        self.assertIn("timeout", rows[0]["error"])


class DataSourceTests(unittest.TestCase):
    def test_hour_range_inclusive_window(self):
        start = datetime(2024, 7, 15, 6, 0, tzinfo=TZ)
        payload = hour_range(start, 12)
        self.assertEqual(payload["filter_type"], 2)
        self.assertEqual(payload["end_time"], "17:00")

    def test_summarize_detects_mixed(self):
        hours = [
            {"data_source": "live", "heatmap_activity_id": "abc"},
            {"data_source": "fixture", "heatmap_activity_id": "fixture"},
        ]
        summary = summarize_data_mode(hours)
        self.assertEqual(summary["mode"], "mixed")
        self.assertTrue(summary["mixed"])

    def test_infer_fixture_from_legacy_source_field(self):
        self.assertEqual(
            infer_data_source({"source": "demo_fixture_from_live_1400_anchors", "heatmap_activity_id": "fixture"}),
            "fixture",
        )

    def test_replace_does_not_leave_live_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with connect(db_path) as conn:
                upsert_hour(
                    conn,
                    {
                        "site_id": "brickell",
                        "hour_local": "2024-07-15T10:00:00-04:00",
                        "temp_c_mean": 31.0,
                        "heatmap_activity_id": "live-activity",
                        "data_source": "live",
                    },
                )
                self.assertEqual(summarize_data_mode(list_hours(conn))["mode"], "live")
                clear_hours(conn)
                upsert_hour(
                    conn,
                    {
                        "site_id": "brickell",
                        "hour_local": "2024-07-15T06:00:00-04:00",
                        "temp_c_mean": 28.0,
                        "heatmap_activity_id": "fixture",
                        "data_source": "fixture",
                    },
                )
                rows = list_hours(conn)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["data_source"], "fixture")
                self.assertEqual(summarize_data_mode(rows)["mode"], "fixture")


class PlannerRiskSplitTests(unittest.TestCase):
    def test_now_risk_is_first_hour_peak_is_worst(self):
        sites = [{"id": "doral", "name": "Doral", "city": "Doral", "surface": "asphalt", "lat": 1, "lon": 2}]
        hours = [
            {
                "site_id": "doral",
                "hour_local": "2024-07-15T06:00:00-04:00",
                "temp_c_mean": 26.0,
                "wet_bulb_temperature_celsius": 20.0,
                "solar_ghi": 50,
                "data_source": "fixture",
            },
            {
                "site_id": "doral",
                "hour_local": "2024-07-15T14:00:00-04:00",
                "temp_c_mean": 32.11,
                "wet_bulb_temperature_celsius": 26.4,
                "solar_ghi": 100,
                "data_source": "fixture",
            },
        ]
        plan = build_planner(sites, hours, "heavy")
        site = plan["sites"][0]
        self.assertEqual(site["now_risk"], "green")
        self.assertEqual(site["peak_risk"], "red")
        self.assertEqual(site["current_risk"], "green")
        self.assertEqual(plan["data"]["mode"], "fixture")
        self.assertFalse(plan["assumption"]["acclimatized"])
        self.assertIn("unacclimatized", plan["assumption"]["label"].lower())

        selected = build_planner(
            sites, hours, "heavy", hour_local="2024-07-15T14:00:00-04:00"
        )
        self.assertEqual(selected["sites"][0]["now_risk"], "red")
        self.assertEqual(selected["sites"][0]["peak_risk"], "red")

        acclim = build_planner(sites, hours, "heavy", acclimatized=True)
        self.assertTrue(acclim["assumption"]["acclimatized"])
        self.assertIn("tlv is the red line", acclim["assumption"]["label"].lower())


if __name__ == "__main__":
    unittest.main()
