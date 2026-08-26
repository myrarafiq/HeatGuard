import unittest

from backend.app.normalize import extract_heatmap_stats, extract_tile_temperatures, merge_hour_record


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


if __name__ == "__main__":
    unittest.main()
