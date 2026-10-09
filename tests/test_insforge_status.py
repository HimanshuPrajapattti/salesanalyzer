import unittest

from app import app, get_insforge_status


class InsForgeStatusTests(unittest.TestCase):
    def test_get_insforge_status_contains_connection_metadata(self):
        status = get_insforge_status()

        self.assertIn('project_id', status)
        self.assertIn('project_name', status)
        self.assertIn('host', status)
        self.assertIn('reachable', status)
        self.assertIn('connected', status)
        self.assertEqual(status['project_name'], 'sales analyzer')

    def test_status_endpoint_returns_json(self):
        client = app.test_client()
        response = client.get('/api/insforge/status')

        self.assertEqual(response.status_code, 200)
        self.assertIn('project_id', response.get_json())
        self.assertIn('reachable', response.get_json())


if __name__ == '__main__':
    unittest.main()
