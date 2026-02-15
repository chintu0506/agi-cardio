import json
import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import app  # noqa: E402


class ApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_root_endpoint_reports_ok(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data)
        self.assertEqual(payload.get('status'), 'ok')
        self.assertIn('/api/health', payload.get('endpoints', []))

    def test_health_endpoint_has_core_fields(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data)
        self.assertEqual(payload.get('status'), 'ok')
        self.assertIn('version', payload)
        self.assertIn('models', payload)
        self.assertIn('accuracy', payload)
        self.assertIn('auc', payload)


if __name__ == '__main__':
    unittest.main()
