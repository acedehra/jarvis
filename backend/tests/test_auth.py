import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient

from app.core.config import settings
import app.core.auth as auth
from app.core.auth import (
    init_api_key,
    get_active_api_key,
    is_valid_api_key,
    get_api_key,
    verify_ws_auth,
    APIKeyAuthMiddleware,
)


class TestKeyLifecycle(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for isolated file operations
        self.test_dir = tempfile.mkdtemp()
        self.key_file = Path(self.test_dir) / ".test_api_key"
        
        # Reset auth module state
        auth._active_api_key = None
        auth._is_first_run = False

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)
        auth._active_api_key = None
        auth._is_first_run = False

    def test_first_run_generates_key_and_creates_file(self):
        """Test that first run generates a secure random key and saves to file."""
        with patch.object(settings, "API_KEY", None), \
             patch.object(settings, "API_KEY_FILE_PATH", str(self.key_file)), \
             patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            
            self.assertFalse(self.key_file.exists())
            
            key = init_api_key()
            
            self.assertIsNotNone(key)
            self.assertTrue(key.startswith("jarvis_sec_"))
            self.assertTrue(self.key_file.exists())
            self.assertEqual(self.key_file.read_text(encoding="utf-8").strip(), key)
            self.assertTrue(auth._is_first_run)

    def test_subsequent_run_loads_existing_key_without_recreation(self):
        """Test that subsequent run loads existing key from file without re-generating."""
        # Pre-seed the key file
        existing_key = "jarvis_sec_existing_test_key_12345"
        self.key_file.write_text(existing_key, encoding="utf-8")

        with patch.object(settings, "API_KEY", None), \
             patch.object(settings, "API_KEY_FILE_PATH", str(self.key_file)), \
             patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            
            key = init_api_key()
            
            self.assertEqual(key, existing_key)
            self.assertEqual(self.key_file.read_text(encoding="utf-8").strip(), existing_key)
            self.assertFalse(auth._is_first_run)

    def test_environment_api_key_takes_precedence(self):
        """Test that API_KEY set in settings/environment takes precedence over file."""
        env_key = "my_custom_env_api_key_98765"
        self.key_file.write_text("file_key_to_ignore", encoding="utf-8")

        with patch.object(settings, "API_KEY", env_key), \
             patch.object(settings, "API_KEY_FILE_PATH", str(self.key_file)), \
             patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            
            key = init_api_key()
            
            self.assertEqual(key, env_key)
            self.assertFalse(auth._is_first_run)

    def test_is_valid_api_key(self):
        """Test constant-time validation function."""
        test_key = "jarvis_sec_secret_key_abcdef"
        auth._active_api_key = test_key

        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            self.assertTrue(is_valid_api_key(test_key))
            self.assertTrue(is_valid_api_key(f"  {test_key}  "))  # strip whitespace
            self.assertFalse(is_valid_api_key("wrong_key"))
            self.assertFalse(is_valid_api_key(""))
            self.assertFalse(is_valid_api_key(None))


class TestAPIAuthenticationEnforcement(unittest.TestCase):
    def setUp(self):
        self.valid_key = "jarvis_sec_valid_test_key_777"
        auth._active_api_key = self.valid_key

        # Create a test FastAPI app mimicking the production app structure
        self.app = FastAPI(title="Test App")
        self.app.add_middleware(APIKeyAuthMiddleware)

        @self.app.get("/api/auth/verify", dependencies=[Depends(get_api_key)])
        def verify():
            return {"status": "authenticated"}

        @self.app.get("/api/tracker/records", dependencies=[Depends(get_api_key)])
        def tracker_records():
            return {"records": []}

        @self.app.get("/docs")
        def docs():
            return {"docs": "public"}

        @self.app.websocket("/api/chat")
        async def chat_ws(websocket: WebSocket, api_key: str = None):
            if not await verify_ws_auth(websocket, query_api_key=api_key):
                await websocket.close(code=1008, reason="Invalid or missing API key")
                return
            await websocket.accept()
            await websocket.send_text("connected")
            await websocket.close()

        self.client = TestClient(self.app)

    def test_unauthenticated_request_to_protected_route_returns_401(self):
        """Test unauthenticated request to /api/auth/verify returns 401."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            response = self.client.get("/api/auth/verify")
            self.assertEqual(response.status_code, 401)
            self.assertIn("Invalid or missing API key", response.json()["detail"])

    def test_authenticated_with_x_api_key_header(self):
        """Test request with X-API-Key header succeeds with 200."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            response = self.client.get("/api/auth/verify", headers={"X-API-Key": self.valid_key})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "authenticated"})

    def test_authenticated_with_bearer_token(self):
        """Test request with Authorization: Bearer <key> succeeds with 200."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            response = self.client.get("/api/auth/verify", headers={"Authorization": f"Bearer {self.valid_key}"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "authenticated"})

    def test_query_parameter_rejected_for_http(self):
        """Test request with ?api_key=<key> query parameter is rejected with 401 for HTTP endpoints."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            response = self.client.get(f"/api/auth/verify?api_key={self.valid_key}")
            self.assertEqual(response.status_code, 401)

    def test_invalid_key_returns_401(self):
        """Test request with invalid key returns 401."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            response = self.client.get("/api/auth/verify", headers={"X-API-Key": "invalid_key_value"})
            self.assertEqual(response.status_code, 401)

    def test_public_docs_accessible_without_key(self):
        """Test that /docs remains accessible without authentication."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            response = self.client.get("/docs")
            self.assertEqual(response.status_code, 200)

    def test_websocket_without_key_is_rejected(self):
        """Test WebSocket connection without key is closed with 1008."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            with self.assertRaises(WebSocketDisconnect) as cm:
                with self.client.websocket_connect("/api/chat"):
                    pass
            self.assertEqual(cm.exception.code, 1008)

    def test_websocket_with_valid_key_is_accepted(self):
        """Test WebSocket connection with valid key connects successfully."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            with self.client.websocket_connect(f"/api/chat?api_key={self.valid_key}") as ws:
                data = ws.receive_text()
                self.assertEqual(data, "connected")


class TestMainAppIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.main import app
        cls.main_app = app
        cls.test_key = "jarvis_sec_main_app_integration_key_999"
        auth._active_api_key = cls.test_key
        cls.client = TestClient(cls.main_app, raise_server_exceptions=False)

    def test_main_app_health_unauthenticated_healthy(self):
        """Verify real app /api/health is accessible without auth and returns 200 when DB is connected."""
        with patch("app.main.check_database_health", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = {"status": "connected", "latency_ms": 1.2, "error": None}
            res = self.client.get("/api/health")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "healthy")
            self.assertIn("services", data)
            self.assertEqual(data["services"]["database"]["status"], "connected")
            self.assertIn("telegram", data["services"])
            self.assertIn("mcp", data["services"])
            self.assertIn("authentication", data["services"])
            self.assertIn("llm_providers", data["services"])

    def test_main_app_health_fails_when_database_disconnected(self):
        """Verify real app /api/health returns 503 and unhealthy status when database connectivity check fails."""
        with patch("app.main.check_database_health", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = {"status": "disconnected", "latency_ms": None, "error": "Connection refused"}
            res = self.client.get("/api/health")
            self.assertEqual(res.status_code, 503)
            data = res.json()
            self.assertEqual(data["status"], "unhealthy")
            self.assertEqual(data["services"]["database"]["status"], "disconnected")

    def test_main_app_health_no_secrets_leaked(self):
        """Verify /api/health does NOT expose any raw secret keys, bot tokens, or passwords."""
        with patch("app.main.check_database_health", new_callable=AsyncMock) as mock_db, \
             patch.object(settings, "TELEGRAM_BOT_TOKEN", "super_secret_telegram_token_123"), \
             patch.object(settings, "GEMINI_API_KEY", "super_secret_gemini_key_456"):
            mock_db.return_value = {"status": "connected", "latency_ms": 0.8, "error": None}
            res = self.client.get("/api/health")
            self.assertEqual(res.status_code, 200)
            raw_text = res.text
            self.assertNotIn("super_secret_telegram_token_123", raw_text)
            self.assertNotIn("super_secret_gemini_key_456", raw_text)
            self.assertNotIn(self.test_key, raw_text)

    def test_main_app_health_informational_services_do_not_fail_health(self):
        """Verify telegram/mcp issues do not fail /api/health as long as database is connected."""
        with patch("app.main.check_database_health", new_callable=AsyncMock) as mock_db, \
             patch.object(settings, "TELEGRAM_BOT_TOKEN", None):
            mock_db.return_value = {"status": "connected", "latency_ms": 1.0, "error": None}
            res = self.client.get("/api/health")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["services"]["telegram"]["status"], "not_configured")

    def test_main_app_auth_verify_unauthorized(self):
        """Verify /api/auth/verify rejects unauthenticated requests with 401."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            res = self.client.get("/api/auth/verify")
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.json(), {"detail": "Invalid or missing API key"})

    def test_main_app_auth_verify_authorized(self):
        """Verify /api/auth/verify accepts valid X-API-Key with 200."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            res = self.client.get("/api/auth/verify", headers={"X-API-Key": self.test_key})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json(), {"status": "authenticated", "valid": True})

    def test_main_app_docs_and_openapi_accessible(self):
        """Verify real app /docs and /openapi.json are accessible without key."""
        with patch.object(settings, "API_KEY_AUTH_ENABLED", True):
            docs_res = self.client.get("/docs")
            self.assertEqual(docs_res.status_code, 200)

            openapi_res = self.client.get("/openapi.json")
            self.assertEqual(openapi_res.status_code, 200)
            schema = openapi_res.json()
            self.assertIn("paths", schema)
            self.assertIn("components", schema)
            self.assertIn("securitySchemes", schema["components"])


if __name__ == "__main__":
    unittest.main()
