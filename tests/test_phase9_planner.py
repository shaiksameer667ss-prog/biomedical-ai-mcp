import sys
import types
import unittest

# Allow the planner to be tested as a standalone file in the generated
# portfolio package when the project's real config.py is not mounted here.
if "config" not in sys.modules:
    config = types.ModuleType("config")
    config.DEFAULT_DOCUMENT_ID = "DOC001"
    config.LOG_LEVEL = "INFO"
    config.MAX_QUESTION_LENGTH = 1000
    config.MCP_SERVER_COMMAND = "python"
    config.MCP_SERVER_SCRIPT = "server.py"
    config.RESEARCH_TOP_K = 5
    sys.modules["config"] = config

from agent_planner import plan_tools


class Phase9PlannerTests(unittest.TestCase):
    def test_research_question_uses_evidence_only(self):
        question = "What mechanisms are involved in copper nanoparticle toxicity?"
        self.assertEqual(plan_tools(question), ["search_research_evidence"])

    def test_combined_research_and_experiment_question_uses_two_tools(self):
        question = (
            "What mechanisms are involved in copper nanoparticle toxicity, "
            "and what related experiments are in the database?"
        )
        self.assertEqual(
            plan_tools(question),
            ["search_research_evidence", "search_experiments"],
        )

    def test_experiment_question_uses_experiment_search(self):
        question = "Find experiments involving copper nanoparticles"
        self.assertEqual(plan_tools(question), ["search_experiments"])

    def test_doxorubicin_question_uses_experiment_search(self):
        question = "Which experiments use doxorubicin?"
        self.assertEqual(plan_tools(question), ["search_experiments"])

    def test_document_question_uses_document_tool(self):
        question = "Show me the research document"
        self.assertEqual(plan_tools(question), ["get_research_document"])

    def test_paper_mechanism_question_stays_evidence_only(self):
        question = "What does the paper say about apoptosis?"
        self.assertEqual(plan_tools(question), ["search_research_evidence"])

    def test_experiment_attributes_trigger_experiment_search(self):
        question = "What studies tested copper nanoparticles for 24 hours?"
        self.assertEqual(plan_tools(question), ["search_experiments"])


if __name__ == "__main__":
    unittest.main()
