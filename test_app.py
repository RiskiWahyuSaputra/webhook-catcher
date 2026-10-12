#!/usr/bin/env python3
import unittest
import urllib.request
import urllib.parse
import json
import subprocess
import time
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_PY = os.path.join(BASE_DIR, "app.py")
TEST_PORT = 4999

class TestWebhookCatcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.process = subprocess.Popen([sys.executable, APP_PY, str(TEST_PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.2)

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait()

    def test_capture_and_inspect_request(self):
        # 1. Send webhook
        hook_url = f"http://127.0.0.1:{TEST_PORT}/hook/github-test"
        payload = json.dumps({"event": "push", "ref": "refs/heads/main"}).encode("utf-8")
        req = urllib.request.Request(hook_url, data=payload, headers={"Content-Type": "application/json", "X-Custom-Token": "secret123"})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res_data = json.loads(resp.read().decode())
            self.assertTrue(res_data.get("ok"))
            self.assertEqual(res_data.get("endpoint"), "github-test")

        # 2. Verify captured via API
        api_url = f"http://127.0.0.1:{TEST_PORT}/api/requests?endpoint=github-test"
        with urllib.request.urlopen(api_url) as resp:
            self.assertEqual(resp.status, 200)
            api_data = json.loads(resp.read().decode())
            self.assertTrue(api_data.get("ok"))
            items = api_data.get("data", [])
            self.assertGreater(len(items), 0)
            latest = items[0]
            self.assertEqual(latest["endpoint"], "github-test")
            self.assertIn("secret123", latest["headers"].get("X-Custom-Token", ""))

if __name__ == "__main__":
    unittest.main()
