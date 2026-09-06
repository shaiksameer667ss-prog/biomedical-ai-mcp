import unittest

import test_agent_alignment
import test_production_hardening
import test_config
import test_config_integration
import test_security
import test_security_mcp
import test_sql_security
import test_error_safety
import test_tool_limits
import test_pdf_limits


def build_test_suite():
    suite = unittest.TestSuite()

    test_modules = [
        test_agent_alignment,
        test_production_hardening,
        test_config,
        test_config_integration,
        test_security,
        test_security_mcp,
        test_sql_security,
        test_error_safety,
        test_tool_limits,
        test_pdf_limits,
    ]

    loader = unittest.TestLoader()

    for module in test_modules:
        suite.addTests(
            loader.loadTestsFromModule(module)
        )

    return suite


if __name__ == "__main__":
    suite = build_test_suite()

    runner = unittest.TextTestRunner(
        verbosity=2
    )

    result = runner.run(suite)

    if not result.wasSuccessful():
        raise SystemExit(1)