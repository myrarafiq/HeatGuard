from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import main


class RefreshLiveTests(unittest.TestCase):
    def test_hosted_demo_does_not_start_a_live_pull(self) -> None:
        with patch.object(main, "ON_VERCEL", True):
            client = TestClient(main.app)
            response = client.post("/demo/refresh-live")
        self.assertEqual(response.status_code, 503)
        self.assertIn("backup day", response.json()["detail"].lower())

    def test_live_pull_requires_api_key(self) -> None:
        with patch.object(main, "ON_VERCEL", False), patch.object(main, "FORTYGUARD_API_KEY", ""):
            client = TestClient(main.app)
            response = client.post("/demo/refresh-live")
        self.assertEqual(response.status_code, 400)
        self.assertIn("FORTYGUARD_API_KEY", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
