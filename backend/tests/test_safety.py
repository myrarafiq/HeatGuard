import unittest

from backend.app.safety.recommend import compare_sites_at_hour, in_midday_break, recommend_for_hour
from backend.app.safety.risk import assess_hour, risk_for_wbgt, screening_wbgt_c
from backend.app.safety.planner import build_planner
from backend.app.safety.ai import answer_from_facts, render_brief_template


class RiskTests(unittest.TestCase):
    def test_screening_formula(self) -> None:
        # 0.7*26 + 0.3*32 = 18.2 + 9.6 = 27.8
        self.assertEqual(screening_wbgt_c(wet_bulb_c=26.0, air_temp_c=32.0), 27.8)

    def test_solar_bump(self) -> None:
        self.assertEqual(
            screening_wbgt_c(wet_bulb_c=26.0, air_temp_c=32.0, solar_ghi=800),
            28.3,
        )

    def test_missing_is_unknown_not_green(self) -> None:
        risk = risk_for_wbgt(None, "heavy")
        self.assertEqual(risk["level"], "unknown")

    def test_heavy_bands_use_osha_table(self) -> None:
        # heavy AL=23 TLV=26
        self.assertEqual(risk_for_wbgt(22.0, "heavy")["level"], "green")
        self.assertEqual(risk_for_wbgt(24.0, "heavy")["level"], "amber")
        self.assertEqual(risk_for_wbgt(26.0, "heavy")["level"], "red")

    def test_heavy_vs_light(self) -> None:
        hour = {
            "site_id": "doral",
            "hour_local": "2024-07-15T14:00:00-04:00",
            "temp_c_mean": 32.11,
            "wet_bulb_temperature_celsius": 26.4,
            "solar_ghi": 100,
        }
        heavy = assess_hour(hour, "heavy")
        light = assess_hour(hour, "light")
        self.assertNotEqual(heavy["level"], light["level"])
        self.assertEqual(heavy["level"], "red")
        self.assertIn(light["level"], {"amber", "green", "red"})

    def test_hotspot_preferred_over_mean(self) -> None:
        from backend.app.safety.risk import screening_air_temp_c

        hour = {
            "temp_c_mean": 29.0,
            "temp_c_max": 33.0,
            "temp_c_p90": 32.4,
        }
        value, source = screening_air_temp_c(hour)
        self.assertEqual(source, "temp_c_p90")
        self.assertEqual(value, 32.4)
        value_max, source_max = screening_air_temp_c({"temp_c_mean": 29.0, "temp_c_max": 33.0})
        self.assertEqual(source_max, "temp_c_max")
        value_mean, source_mean = screening_air_temp_c({"temp_c_mean": 29.0})
        self.assertEqual(source_mean, "temp_c_mean")
        self.assertEqual(value_mean, 29.0)

        cooler_mean = {
            "site_id": "doral",
            "hour_local": "2024-07-15T10:00:00-04:00",
            "temp_c_mean": 29.0,
            "temp_c_max": 34.0,
            "wet_bulb_temperature_celsius": 24.0,
            "solar_ghi": 100,
        }
        mean_only = assess_hour({**cooler_mean, "temp_c_max": None}, "heavy")
        hotspot = assess_hour(cooler_mean, "heavy")
        self.assertEqual(mean_only["screening_air_temp_source"], "temp_c_mean")
        self.assertEqual(hotspot["screening_air_temp_source"], "temp_c_max")
        self.assertGreater(hotspot["effective_wbgt_c"], mean_only["effective_wbgt_c"])
        self.assertIsNotNone(hotspot["screening_wbgt_from_mean_c"])

    def test_acclimatized_uses_tlv_as_red_line(self) -> None:
        # heavy AL=23 TLV=26. 24°C is amber unacclimatized, green acclimatized.
        self.assertEqual(risk_for_wbgt(24.0, "heavy", acclimatized=False)["level"], "amber")
        self.assertEqual(risk_for_wbgt(24.0, "heavy", acclimatized=True)["level"], "green")
        self.assertEqual(risk_for_wbgt(26.0, "heavy", acclimatized=True)["level"], "red")

    def test_work_rest_uses_acgih_table(self) -> None:
        from backend.app.safety.thresholds import work_rest_for

        # Unacclimatized heavy: no 45/15 row; 22°C ≤ 24 → 30/30
        cycle = work_rest_for(22.0, "heavy", acclimatized=False)
        self.assertEqual(cycle["code"], "30/30")
        self.assertEqual(cycle["work_min"], 30)
        self.assertEqual(cycle["rest_min"], 30)
        stop = work_rest_for(29.0, "heavy", acclimatized=False)
        self.assertEqual(stop["code"], "stop")

    def test_clothing_caf_raises_effective_wbgt(self) -> None:
        hour = {
            "site_id": "doral",
            "hour_local": "2024-07-15T10:00:00-04:00",
            "temp_c_mean": 29.0,
            "wet_bulb_temperature_celsius": 24.0,
            "solar_ghi": 100,
        }
        baseline = assess_hour(hour, "heavy", clothing="work_clothes")
        ppe = assess_hour(hour, "heavy", clothing="double_layer")
        self.assertEqual(ppe["clothing_adjustment_c"], 3.0)
        self.assertAlmostEqual(
            ppe["effective_wbgt_c"],
            baseline["effective_wbgt_c"] + 3.0,
        )

    def test_heat_index_not_used_as_air_temp(self) -> None:
        hour = {
            "temp_c_mean": 29.0,
            "heat_index_celsius": 45.0,
            "apparent_temperature_celsius": 40.0,
            "wet_bulb_temperature_celsius": 24.0,
        }
        assessed = assess_hour(hour, "heavy")
        self.assertEqual(assessed["screening_air_temp_c"], 29.0)
        self.assertEqual(assessed["heat_index_celsius"], 45.0)

    def test_recommendation_uses_work_rest_code(self) -> None:
        hour = {
            "site_id": "doral",
            "hour_local": "2024-07-15T10:00:00-04:00",
            "temp_c_mean": 26.0,
            "wet_bulb_temperature_celsius": 20.0,
            "solar_ghi": 50,
        }
        assessed = assess_hour(hour, "heavy")
        rec = recommend_for_hour(assessed)
        self.assertEqual(assessed["work_rest"]["code"], "30/30")
        self.assertIn("30/30", rec["primary_action"])
        self.assertIn("work_rest_30_30", rec["action_codes"])


class RecommendTests(unittest.TestCase):
    def test_midday_window(self) -> None:
        self.assertTrue(in_midday_break("2024-07-15T13:00:00-04:00"))
        self.assertFalse(in_midday_break("2024-07-15T10:00:00-04:00"))

    def test_midday_action_code(self) -> None:
        assessment = {
            "level": "red",
            "workload": "heavy",
            "hour_local": "2024-07-15T13:00:00-04:00",
            "reason": "test",
            "screening_wbgt_c": 28.0,
        }
        rec = recommend_for_hour(assessment)
        self.assertIn("midday_break", rec["action_codes"])

    def test_compare_picks_coolest(self) -> None:
        rows = [
            {
                "site_id": "doral",
                "hour_local": "2024-07-15T10:00:00-04:00",
                "level": "red",
                "screening_wbgt_c": 28.0,
                "workload": "heavy",
                "reason": "hot",
            },
            {
                "site_id": "miami_beach",
                "hour_local": "2024-07-15T10:00:00-04:00",
                "level": "amber",
                "screening_wbgt_c": 24.5,
                "workload": "heavy",
                "reason": "cooler",
            },
        ]
        result = compare_sites_at_hour(rows, hour_local="2024-07-15T10:00:00-04:00")
        self.assertEqual(result["best_site_id"], "miami_beach")
        self.assertEqual(result["worst_site_id"], "doral")


class PlannerAiTests(unittest.TestCase):
    def test_planner_answers_10am_question(self) -> None:
        sites = [
            {
                "id": "brickell",
                "name": "Brickell",
                "city": "Miami",
                "surface": "urban",
                "lat": 1,
                "lon": 2,
            },
            {
                "id": "doral",
                "name": "Doral",
                "city": "Doral",
                "surface": "asphalt",
                "lat": 3,
                "lon": 4,
            },
        ]
        hours = [
            {
                "site_id": "brickell",
                "hour_local": "2024-07-15T10:00:00-04:00",
                "temp_c_mean": 29.0,
                "wet_bulb_temperature_celsius": 24.0,
                "solar_ghi": 500,
                "data_source": "live",
            },
            {
                "site_id": "doral",
                "hour_local": "2024-07-15T10:00:00-04:00",
                "temp_c_mean": 32.0,
                "wet_bulb_temperature_celsius": 26.5,
                "solar_ghi": 700,
                "data_source": "live",
            },
        ]
        plan = build_planner(sites, hours, "heavy")
        self.assertIsNotNone(plan["comparison_at_10am"]["best_site_id"])
        self.assertEqual(plan["data"]["mode"], "live")
        ans = answer_from_facts(
            "Which site has the best conditions for heavy outdoor work at 10 AM?",
            plan,
        )
        self.assertIn("brickell", ans.lower())
        brief = render_brief_template(plan)
        self.assertIn("Heat Operations Brief", brief)
        self.assertIn("live FortyGuard", brief)


if __name__ == "__main__":
    unittest.main()
