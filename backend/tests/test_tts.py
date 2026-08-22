import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
import app.core.auth as auth
from app.services.tts_service import clean_text_for_speech, KOKORO_VOICES


class TestTTSServiceAndRoutes(unittest.TestCase):
    def setUp(self):
        settings.API_KEY = "jarvis_sec_test_tts_key_123"
        settings.API_KEY_AUTH_ENABLED = True
        auth._active_api_key = "jarvis_sec_test_tts_key_123"
        self.headers = {"X-API-Key": "jarvis_sec_test_tts_key_123"}
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        auth._active_api_key = None

    def test_clean_text_for_speech(self):
        markdown_text = """
        # Good Evening Sir!
        Here is your **daily** summary:
        ```python
        def run():
            pass
        ```
        Check [this link](https://example.com) or `data.json`.
        | Col A | Col B |
        |---|---|
        | 1 | 2 |
        """
        cleaned = clean_text_for_speech(markdown_text)
        self.assertNotIn("```", cleaned)
        self.assertNotIn("#", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertIn("Good Evening Sir!", cleaned)
        self.assertIn("daily summary", cleaned)
        self.assertIn("this link", cleaned)

    def test_list_voices_endpoint(self):
        response = self.client.get("/api/tts/voices", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(len(data["voices"]), 1)
        voice_ids = [v["id"] for v in data["voices"]]
        self.assertIn("bm_george", voice_ids)

    def test_tts_status_endpoint(self):
        with patch("app.services.tts_service.httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value.status_code = 200
            response = self.client.get("/api/tts/status", headers=self.headers)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "connected")

    def test_speak_endpoint_empty_text(self):
        response = self.client.post("/api/tts/speak", headers=self.headers, json={"text": ""})
        self.assertEqual(response.status_code, 400)

    @patch("app.api.tts_routes.generate_speech", new_callable=AsyncMock)
    def test_speak_endpoint_success(self, mock_generate):
        mock_generate.return_value = b"\xff\xfb\x90\x44"  # Mock MP3 frame bytes
        response = self.client.post(
            "/api/tts/speak",
            headers=self.headers,
            json={"text": "Good morning, Sir.", "voice": "bm_george"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "audio/mpeg")
        self.assertEqual(response.content, b"\xff\xfb\x90\x44")


if __name__ == "__main__":
    unittest.main()
