import io
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from autoe2e.remote.intervention import wait_for_startup_intervention
from autoe2e.remote.session import RemoteSession, _find_novnc_root, _require_executable


class StartupInterventionTests(unittest.TestCase):
    @patch("autoe2e.remote.intervention.input", return_value="")
    @patch("autoe2e.remote.intervention.sys.stdin.isatty", return_value=True)
    def test_navigates_and_waits_for_confirmation(self, _isatty, prompt):
        page = Mock()

        wait_for_startup_intervention(page, "https://example.test")

        page.goto.assert_called_once_with("https://example.test", wait_until="domcontentloaded")
        prompt.assert_called_once()

    @patch("autoe2e.remote.intervention.sys.stdin.isatty", return_value=False)
    def test_rejects_noninteractive_input(self, _isatty):
        with self.assertRaisesRegex(RuntimeError, "interactive terminal"):
            wait_for_startup_intervention(Mock(), "https://example.test")


class RemoteSessionTests(unittest.TestCase):
    @patch("autoe2e.remote.session.shutil.which", return_value=None)
    def test_missing_executable_has_actionable_error(self, _which):
        with self.assertRaisesRegex(RuntimeError, "Docker image or install"):
            _require_executable("websockify")

    def test_finds_novnc_web_root(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "vnc.html").touch()
            with patch("autoe2e.remote.session.NOVNC_WEB_ROOTS", (root,)):
                self.assertEqual(_find_novnc_root(), root)

    def test_close_terminates_processes_in_reverse_order(self):
        session = RemoteSession(Path("remote-logs"), "127.0.0.1")
        first = Mock(spec=subprocess.Popen)
        second = Mock(spec=subprocess.Popen)
        first.poll.return_value = None
        second.poll.return_value = None
        first.wait.return_value = 0
        second.wait.return_value = 0
        calls = []
        first.terminate.side_effect = lambda: calls.append("first")
        second.terminate.side_effect = lambda: calls.append("second")
        session._processes = [first, second]
        session._logs = [io.BytesIO()]

        session.close()
        session.close()

        self.assertEqual(calls, ["second", "first"])
        self.assertTrue(session._logs[0].closed)

    @patch.dict(os.environ, {"AUTOE2E_CONTAINER": "1"})
    @patch.object(RemoteSession, "_start")
    def test_container_session_listens_on_all_container_interfaces(self, _start):
        session = RemoteSession.start(Path("remote-logs"))
        self.assertEqual(session.bind_host, "0.0.0.0")
        session.close()


if __name__ == "__main__":
    unittest.main()
