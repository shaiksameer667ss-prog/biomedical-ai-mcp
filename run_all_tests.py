"""
Run the complete Biomedical AI MCP test suite.

The test database is prepared before importing the test modules so that
server.py can connect to a valid SQLite schema in a clean environment,
including GitHub Actions CI.
"""

import unittest


# ============================================================
# PREPARE TEST DATABASE
# ============================================================

from test_database_setup import ensure_test_database

ensure_test_database()


# ============================================================
# IMPORT TEST MODULES
# ============================================================

import test_agent_alignment
import test_config
import test_config_integration
import test_error_safety
import test_pdf_limits
import test_security
import test_security_mcp
import test_sql_security
import test_tool_limits
import test_production_hardening


# ============================================================
# TEST MODULE LIST
# ============================================================

TEST_MODULES = [
    test_agent_alignment,
    test_config,
    test_config_integration,
    test_error_safety,
    test_pdf_limits,
    test_security,
    test_security_mcp,
    test_sql_security,
    test_tool_limits,
    test_production_hardening,
]


# ============================================================
# BUILD TEST SUITE
# ============================================================

def build_test_suite():
    """
    Build one unittest suite containing every project test module.
    """

    loader = unittest.TestLoader()

    suite = unittest.TestSuite()

    for module in TEST_MODULES:
        suite.addTests(
            loader.loadTestsFromModule(module)
        )

    return suite


# ============================================================
# RUN TESTS
# ============================================================

def main():
    """
    Run the complete test suite.

    Returns:
        0 when every test passes.
        1 when one or more tests fail.
    """

    suite = build_test_suite()

    runner = unittest.TextTestRunner(
        verbosity=2
    )

    result = runner.run(suite)

    if result.wasSuccessful():
        return 0

    return 1


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    raise SystemExit(main())