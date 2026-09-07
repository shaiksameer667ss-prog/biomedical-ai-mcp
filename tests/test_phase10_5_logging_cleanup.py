"""
Phase 10.5 tests: centralized logging cleanup and observability ownership.
"""

import logging
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Phase105LoggingCleanupTests(unittest.TestCase):
    AGENT_MODULES = (
        "agent_planner.py",
        "agent_validator.py",
        "agent_answer.py",
    )

    def test_agent_modules_do_not_configure_logging(self):
        for filename in self.AGENT_MODULES:
            source = (PROJECT_ROOT / filename).read_text(encoding="utf-8")
            self.assertNotIn("logging.basicConfig(", source)
            self.assertNotIn("if not logger.handlers:", source)

    def test_server_does_not_use_local_basic_config(self):
        source = (PROJECT_ROOT / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("logging.basicConfig(", source)
        self.assertNotIn("if not logger.handlers:", source)

    def test_server_uses_centralized_logging(self):
        source = (PROJECT_ROOT / "server.py").read_text(encoding="utf-8")
        self.assertIn("configure_logging", source)
        self.assertIn("configure_logging()", source)

    def test_agent_app_uses_centralized_logging(self):
        source = (PROJECT_ROOT / "agent_app.py").read_text(encoding="utf-8")
        self.assertIn("configure_logging", source)
        self.assertIn("configure_logging()", source)

    def test_logging_setup_exists_only_in_config(self):
        config_source = (PROJECT_ROOT / "config.py").read_text(encoding="utf-8")
        self.assertIn("def configure_logging", config_source)

        for filename in (
            "server.py",
            "agent_app.py",
            "agent_planner.py",
            "agent_validator.py",
            "agent_answer.py",
        ):
            source = (PROJECT_ROOT / filename).read_text(encoding="utf-8")
            self.assertNotIn(
                "def configure_logging",
                source,
                msg=f"{filename} contains a duplicate logging setup function.",
            )

    def test_configure_logging_is_idempotent(self):
        import config

        root_logger = logging.getLogger()

        for handler in list(root_logger.handlers):
            if getattr(handler, "_biomed_mcp_handler", False):
                root_logger.removeHandler(handler)
                handler.close()

        def owned_count():
            return sum(
                1
                for handler in root_logger.handlers
                if getattr(handler, "_biomed_mcp_handler", False)
            )

        before = owned_count()
        config.configure_logging()
        after_first = owned_count()
        config.configure_logging()
        after_second = owned_count()

        self.assertEqual(after_first, before + 1)
        self.assertEqual(after_second, after_first)


if __name__ == "__main__":
    unittest.main()
