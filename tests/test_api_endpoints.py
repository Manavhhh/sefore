"""
API Endpoints Automated Test Suite.
Verifies FastAPI endpoints: /health, /validation/samples, /validation/summary, /validation/evaluate.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from fastapi.testclient import TestClient
from api import app

class TestAPIEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "SIH26143-OilSpillDetector")

    def test_validation_samples_list(self):
        response = self.client.get("/validation/samples")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("samples", data)
        self.assertGreaterEqual(len(data["samples"]), 10)

    def test_validation_summary(self):
        response = self.client.get("/validation/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("aggregate_metrics", data)
        agg = data["aggregate_metrics"]
        self.assertIn("mean_iou", agg)
        self.assertIn("mean_dice", agg)
        self.assertIn("mean_precision", agg)
        self.assertIn("mean_recall", agg)

    def test_validation_evaluate_sample(self):
        response = self.client.get("/validation/evaluate/00000.tif")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("ground_truth_metrics", data)
        m = data["ground_truth_metrics"]
        self.assertIn("iou", m)
        self.assertIn("dice", m)
        self.assertIn("precision", m)
        self.assertIn("recall", m)
        self.assertIn("features", data)
        self.assertGreater(len(data["features"]), 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
