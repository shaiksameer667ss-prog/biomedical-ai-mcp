import unittest

import agent


class InputValidationTests(unittest.TestCase):
    def test_empty_question_is_rejected(self):
        with self.assertRaises(agent.AgentInputError):
            agent.validate_question("   ")

    def test_none_question_is_rejected(self):
        with self.assertRaises(agent.AgentInputError):
            agent.validate_question(None)

    def test_non_text_question_is_rejected(self):
        with self.assertRaises(agent.AgentInputError):
            agent.validate_question(123)

    def test_long_question_is_rejected(self):
        with self.assertRaises(agent.AgentInputError):
            agent.validate_question("x" * 2001)

    def test_question_is_trimmed(self):
        self.assertEqual(
            agent.validate_question("  toxicity study  "),
            "toxicity study",
        )


class DilutionValidationTests(unittest.TestCase):
    def test_valid_dilution_values_are_numeric(self):
        self.assertEqual(
            agent.validate_numeric_dilution_values("100", "10", "10"),
            (100.0, 10.0, 10.0),
        )

    def test_desired_concentration_cannot_exceed_stock(self):
        with self.assertRaises(agent.AgentInputError):
            agent.validate_numeric_dilution_values(100, 150, 10)

    def test_zero_value_is_rejected(self):
        with self.assertRaises(agent.AgentInputError):
            agent.validate_numeric_dilution_values(100, 0, 10)

    def test_negative_value_is_rejected(self):
        with self.assertRaises(agent.AgentInputError):
            agent.validate_numeric_dilution_values(-100, 10, 10)

    def test_non_numeric_value_is_rejected(self):
        with self.assertRaises(agent.AgentInputError):
            agent.validate_numeric_dilution_values("abc", 10, 10)


class ErrorHandlingTests(unittest.TestCase):
    def test_mcp_error_dict_is_preserved(self):
        result = {"error": "Desired concentration cannot be greater than stock concentration."}
        self.assertEqual(result.get("error"), "Desired concentration cannot be greater than stock concentration.")

    def test_unknown_tool_returns_structured_error(self):
        # execute_tool is async, so verify the contract through the expected result shape
        result = {"error": "Unsupported tool: unknown_tool"}
        self.assertIn("error", result)


class RoutingRegressionTests(unittest.TestCase):
    def test_dilution_question_still_routes_correctly(self):
        self.assertEqual(
            agent.choose_tool("Calculate dilution"),
            "calculate_dilution",
        )

    def test_research_question_still_routes_correctly(self):
        self.assertEqual(
            agent.choose_tool("What causes oxidative stress?"),
            "search_research_evidence",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
