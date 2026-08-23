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
            },
            {
                "site_id": "doral",
                "hour_local": "2024-07-15T10:00:00-04:00",
                "temp_c_mean": 32.0,
                "wet_bulb_temperature_celsius": 26.5,
                "solar_ghi": 700,
            },
        ]
        plan = build_planner(sites, hours, "heavy")
        self.assertIsNotNone(plan["comparison_at_10am"]["best_site_id"])
        ans = answer_from_facts(
            "Which site has the best conditions for heavy outdoor work at 10 AM?",
            plan,
        )
        self.assertIn("brickell", ans.lower())
        brief = render_brief_template(plan)
        self.assertIn("Heat Operations Brief", brief)


if __name__ == "__main__":
    unittest.main()
