import os
import unittest
from unittest.mock import patch

from autoe2e.settings import Settings

REQUIRED_ENVIRONMENT = {
    "BASE_URL": "https://example.test",
    "LLM_MODEL": "chat-model",
    "EMBEDDING_MODEL": "embedding-model",
}


class SettingsTests(unittest.TestCase):
    @patch.dict(os.environ, REQUIRED_ENVIRONMENT, clear=True)
    def test_remote_flags_default_to_disabled(self):
        settings = Settings.from_env()
        self.assertFalse(settings.remote_view_enabled)
        self.assertFalse(settings.remote_startup_intervention)
        self.assertTrue(settings.headless)

    @patch.dict(
        os.environ,
        {
            **REQUIRED_ENVIRONMENT,
            "REMOTE_VIEW_ENABLED": "yes",
            "REMOTE_STARTUP_INTERVENTION": "1",
        },
        clear=True,
    )
    def test_remote_flags_enable_headed_intervention(self):
        settings = Settings.from_env()
        self.assertTrue(settings.remote_view_enabled)
        self.assertTrue(settings.remote_startup_intervention)
        self.assertFalse(settings.headless)

    @patch.dict(
        os.environ,
        {**REQUIRED_ENVIRONMENT, "REMOTE_STARTUP_INTERVENTION": "true"},
        clear=True,
    )
    def test_intervention_requires_remote_view(self):
        with self.assertRaisesRegex(ValueError, "requires REMOTE_VIEW_ENABLED"):
            Settings.from_env()

    @patch.dict(
        os.environ,
        {**REQUIRED_ENVIRONMENT, "REMOTE_VIEW_ENABLED": "sometimes"},
        clear=True,
    )
    def test_invalid_boolean_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "REMOTE_VIEW_ENABLED must be one of"):
            Settings.from_env()


if __name__ == "__main__":
    unittest.main()
