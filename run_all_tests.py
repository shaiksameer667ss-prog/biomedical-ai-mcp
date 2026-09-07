"""Run the complete Biomedical AI MCP test suite."""

import sys
import unittest


TEST_MODULES = [
    "tests.test_database_setup",
    "tests.test_agent_alignment",
    "tests.test_config",
    "tests.test_config_integration",
    "tests.test_error_safety",
    "tests.test_pdf_limits",
    "tests.test_security",
    "tests.test_security_mcp",
    "tests.test_sql_security",
    "tests.test_tool_limits",
    "tests.test_production_hardening",
    "tests.test_phase9_planner",
    "tests.test_phase9_2_executor",
    "tests.test_phase9_3_failure_paths",
    "tests.test_phase9_4_planner",
    "tests.test_phase9_5_answer",
    "tests.test_phase10_4_logging_config",
    "tests.test_phase10_5_logging_cleanup",
    "tests.test_phase10_6_observability",
]


def main():
    """Run all registered project tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for module_name in TEST_MODULES:
        suite.addTests(loader.loadTestsFromName(module_name))

    runner = unittest.TextTestRunner(
        verbosity=2,
    )

    result = runner.run(suite)

    print()
    print("=" * 70)

    if result.wasSuccessful():
        print("ALL TESTS PASSED")
    else:
        print("TEST SUITE FAILED")

    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures:  {len(result.failures)}")
    print(f"Errors:    {len(result.errors)}")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
