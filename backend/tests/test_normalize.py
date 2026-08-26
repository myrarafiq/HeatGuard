import unittest

from backend.app.normalize import (
    extract_duration_hours,
    extract_heatmap_stats,
    extract_tile_temperatures,
    merge_hour_record,
)


class NormalizeTests(unittest.TestCase):
    def test_heatmap_stats_and_tiles(self) -> None:
        payload = {
            "data": {
                "result": {
                    "map_data": {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {
                                    "tile_id": 0,
                                    "average_temperature": 31.34,
                                    "min_temperature": 31.34,
                                    "max_temperature": 31.34,
                                },
                            }
                        ],
                    },
                    "stats_data": {
                        "temperature_stats": {
                            "minimum": 31.18,
                            "maximum": 31.34,
                            "mean": 31.26,
                            "standard_deviation": 0.07,
                        }
                    },
                }
            }
        }
        stats = extract_heatmap_stats(payload)
        self.assertEqual(stats["temp_c_mean"], 31.26)
        self.assertEqual(extract_tile_temperatures(payload), [31.34])

    def test_merge_hour_skips_missing_as_zero(self) -> None:
        record = merge_hour_record(
            site_id="brickell",
            hour_local="2024-07-15T14:00:00-04:00",
            heatmap=None,
            env=None,
            heatmap_activity_id=None,
            env_activity_id=None,
        )
        self.assertIsNone(record["temp_c_mean"])
        self.assertIn("temp_c_mean", record["missing_fields"])
        self.assertEqual(record["data_source"], "live")

    def test_merge_persists_mean_max_p90_and_spread(self) -> None:
        payload = {
            "data": {
                "result": {
                    "map_data": {
                        "type": "FeatureCollection",
                        "features": [
                            {"type": "Feature", "properties": {"average_temperature": 31.0}},
                            {"type": "Feature", "properties": {"average_temperature": 32.0}},
                            {"type": "Feature", "properties": {"average_temperature": 34.0}},
                        ],
                    },
                    "stats_data": {
                        "temperature_stats": {
                            "minimum": 31.0,
                            "maximum": 34.0,
                            "mean": 32.2,
                            "standard_deviation": 1.2,
                        }
                    },
                }
            }
        }
        record = merge_hour_record(
            site_id="doral",
            hour_local="2024-07-15T14:00:00-04:00",
            heatmap=payload,
            env=None,
            heatmap_activity_id="hm",
            env_activity_id=None,
        )
        self.assertEqual(record["temp_c_mean"], 32.2)
        self.assertEqual(record["temp_c_max"], 34.0)
        self.assertEqual(record["temp_c_min"], 31.0)
        self.assertEqual(record["tile_spread_c"], 3.0)
        self.assertEqual(record["temp_c_p90"], 33.6)
        self.assertEqual(record["tile_count"], 3)

    def test_extract_duration_hours_are_hours_not_osha_temps(self) -> None:
        payload = {
            "data": {
                "result": {
                    "stats_data": {
                        "temperature_stats": {"minimum": 3.0, "maximum": 8.0, "mean": 6.5}
                    }
                }
            }
        }
        hours = extract_duration_hours(payload)
        self.assertEqual(hours["hours_mean"], 6.5)
        self.assertEqual(hours["hours_max"], 8.0)
        self.assertNotEqual(hours["hours_mean"], 32.0)


if __name__ == "__main__":
    unittest.main()
