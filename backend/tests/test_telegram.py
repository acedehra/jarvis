import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.core.config import settings
import app.core.auth as auth
from app.main import app
from app.services.telegram_service import TelegramBotService, is_valid_chat_id, telegram_bot


class TestTelegramSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_key = "jarvis_sec_test_telegram_key_12345"
        auth._active_api_key = cls.test_key
        settings.API_KEY = cls.test_key
        settings.API_KEY_AUTH_ENABLED = True
        cls.client = TestClient(app, headers={"X-API-Key": cls.test_key})

    def test_is_valid_chat_id(self):
        """Test chat ID validation helper with various inputs."""
        # Valid chat IDs
        self.assertTrue(is_valid_chat_id("123456789"))
        self.assertTrue(is_valid_chat_id("-100123456789"))
        self.assertTrue(is_valid_chat_id("  987654321  "))
        self.assertTrue(is_valid_chat_id(12345))

        # Invalid chat IDs
        self.assertFalse(is_valid_chat_id(None))
        self.assertFalse(is_valid_chat_id(""))
        self.assertFalse(is_valid_chat_id("   "))
        self.assertFalse(is_valid_chat_id("your_telegram_chat_id_here"))
        self.assertFalse(is_valid_chat_id("your_chat_id"))
        self.assertFalse(is_valid_chat_id("abc12345"))
        self.assertFalse(is_valid_chat_id("invalid"))
        self.assertFalse(is_valid_chat_id("123.456"))

    def test_is_authorized(self):
        """Verify is_authorized strictly rejects unauthorized/missing/invalid chat IDs."""
        svc = TelegramBotService()

        # Chat ID not configured -> must be denied
        with patch.object(settings, "TELEGRAM_CHAT_ID", None):
            self.assertFalse(svc.is_authorized(123456))

        with patch.object(settings, "TELEGRAM_CHAT_ID", ""):
            self.assertFalse(svc.is_authorized(123456))

        with patch.object(settings, "TELEGRAM_CHAT_ID", "your_telegram_chat_id_here"):
            self.assertFalse(svc.is_authorized(123456))

        with patch.object(settings, "TELEGRAM_CHAT_ID", "not_a_number"):
            self.assertFalse(svc.is_authorized(123456))

        # Chat ID configured properly
        with patch.object(settings, "TELEGRAM_CHAT_ID", "987654321"):
            # Matching chat ID -> Authorized
            self.assertTrue(svc.is_authorized(987654321))
            self.assertTrue(svc.is_authorized("987654321"))
            # Different chat ID -> Rejected
            self.assertFalse(svc.is_authorized(111222333))
            self.assertFalse(svc.is_authorized("111222333"))

    async def _async_start_no_chat_id(self):
        svc = TelegramBotService()
        with patch.object(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"), \
             patch.object(settings, "TELEGRAM_CHAT_ID", None):
            await svc.start()
            self.assertFalse(svc._is_running)
            self.assertIsNotNone(svc.last_error)
            self.assertIn("TELEGRAM_CHAT_ID is missing or invalid", svc.last_error)

    def test_bot_does_not_start_polling_without_chat_id(self):
        """Verify bot does not start polling if TELEGRAM_CHAT_ID is missing."""
        import asyncio
        asyncio.run(self._async_start_no_chat_id())

    async def _async_start_with_invalid_chat_id(self):
        svc = TelegramBotService()
        with patch.object(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"), \
             patch.object(settings, "TELEGRAM_CHAT_ID", "your_telegram_chat_id_here"):
            await svc.start()
            self.assertFalse(svc._is_running)
            self.assertIsNotNone(svc.last_error)
            self.assertIn("TELEGRAM_CHAT_ID is missing or invalid", svc.last_error)

    def test_bot_does_not_start_polling_with_invalid_chat_id(self):
        """Verify bot does not start polling if TELEGRAM_CHAT_ID is a placeholder or invalid."""
        import asyncio
        asyncio.run(self._async_start_with_invalid_chat_id())

    async def _async_start_successful(self):
        svc = TelegramBotService()
        mock_app = MagicMock()
        mock_app.initialize = AsyncMock()
        mock_app.start = AsyncMock()
        mock_app.updater.start_polling = AsyncMock()
        mock_bot = MagicMock()
        mock_bot.get_me = AsyncMock(return_value=MagicMock(username="JarvisBot", id=123456))
        mock_app.bot = mock_bot

        with patch.object(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"), \
             patch.object(settings, "TELEGRAM_CHAT_ID", "987654321"), \
             patch("app.services.telegram_service.Application.builder") as mock_builder:
            mock_builder_instance = MagicMock()
            mock_builder_instance.token.return_value = mock_builder_instance
            mock_builder_instance.build.return_value = mock_app
            mock_builder.return_value = mock_builder_instance

            await svc.start()
            self.assertTrue(svc._is_running)
            self.assertIsNone(svc.last_error)

    def test_bot_starts_polling_with_valid_token_and_chat_id(self):
        """Verify bot starts polling successfully when both valid token and chat ID are provided."""
        import asyncio
        asyncio.run(self._async_start_successful())

    def test_telegram_status_endpoint(self):
        """Verify /api/telegram/status returns validation flags and error details."""
        with patch.object(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF"), \
             patch.object(settings, "TELEGRAM_CHAT_ID", "your_telegram_chat_id_here"), \
             patch.object(telegram_bot, "_is_running", False), \
             patch.object(telegram_bot, "last_error", "TELEGRAM_CHAT_ID is missing or invalid."):
            res = self.client.get("/api/telegram/status")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertTrue(data["has_token_configured"])
            self.assertTrue(data["chat_id_configured"])
            self.assertFalse(data["is_chat_id_valid"])
            self.assertFalse(data["is_active"])
            self.assertEqual(data["error"], "TELEGRAM_CHAT_ID is missing or invalid.")

    def test_health_endpoint_reports_missing_chat_id(self):
        """Verify /api/health returns missing_chat_id status when token exists without valid chat ID."""
        with patch("app.main.check_database_health", new_callable=AsyncMock) as mock_db, \
             patch.object(settings, "TELEGRAM_BOT_TOKEN", "123456:ABC-DEF"), \
             patch.object(settings, "TELEGRAM_CHAT_ID", None), \
             patch.object(telegram_bot, "_is_running", False):
            mock_db.return_value = {"status": "connected", "latency_ms": 0.5, "error": None}
            res = self.client.get("/api/health")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["services"]["telegram"]["status"], "missing_chat_id")
            self.assertFalse(data["services"]["telegram"]["chat_id_valid"])
