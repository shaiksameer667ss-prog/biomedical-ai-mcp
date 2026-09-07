import importlib
import sys
import types
import unittest


# The production project already contains config.py. This lightweight stub
# keeps these planner-only tests self-contained in the build environment.
config = types.ModuleType("config")
config.DEFAULT_DOCUMENT_ID = "DOC001"
config.LOG_LEVEL = "INFO"
config.MAX_QUESTION_LENGTH = 1000
config.MCP_SERVER_COMMAND = "python"
config.MCP_SERVER_SCRIPT = "server.py"
config.RESEARCH_TOP_K = 5
sys.modules.setdefault("config", config)

planner = importlib.import_module("agent_planner")


class Phase94PlannerTests(unittest.TestCase):
    def assert_plan(self, question, expected):
        self.assertEqual(planner.plan_tools(question), expected)

    def test_mechanism_question_uses_evidence_only(self):
        self.assert_plan(
            "What mechanisms are involved in copper nanoparticle toxicity?",
            ["search_research_evidence"],
        )

    def test_experiment_question_uses_experiment_search(self):
        self.assert_plan(
            "Find experiments involving copper nanoparticles",
            ["search_experiments"],
        )

    def test_combined_evidence_and_experiment_question_uses_two_tools(self):
        self.assert_plan(
            "What mechanisms are involved in copper nanoparticle toxicity, and what related experiments are in the database?",
            ["search_research_evidence", "search_experiments"],
        )

    def test_show_paper_and_mechanism_uses_document_and_evidence(self):
        self.assert_plan(
            "Show me the paper and tell me what it says about apoptosis.",
            ["search_research_evidence", "get_research_document"],
        )

    def test_paper_mechanism_question_stays_evidence_only(self):
        self.assert_plan(
            "What does the paper say about apoptosis?",
            ["search_research_evidence"],
        )

    def test_document_only_question_uses_document_tool(self):
        self.assert_plan(
            "Show me the research document",
            ["get_research_document"],
        )

    def test_experiment_and_document_question_uses_both(self):
        self.assert_plan(
            "Show me the paper and the experiments involving copper nanoparticles.",
            ["search_experiments", "get_research_document"],
        )

    def test_document_metadata_phrase_is_not_evidence_only(self):
        self.assert_plan(
            "Show the paper details",
            ["get_research_document"],
        )

    def test_experimental_attributes_trigger_database_search(self):
        self.assert_plan(
            "Which studies used copper nanoparticles for 24 hours?",
            ["search_experiments"],
        )

    def test_dilution_remains_dedicated_workflow(self):
        self.assert_plan(
            "Calculate the dilution from 100 to 10 mg/mL.",
            ["calculate_dilution"],
        )

    def test_multiple_domain_helper_reports_intents(self):
        result = planner.question_requests_multiple_domains(
            "What mechanisms are involved, and what related experiments are in the database?"
        )
        self.assertTrue(result["evidence"])
        self.assertTrue(result["experiments"])

    def test_plan_has_no_duplicate_tools(self):
        plan = planner.plan_tools(
            "Show me the paper and tell me what it says about apoptosis, and show me the experiments."
        )
        self.assertEqual(plan, [
            "search_research_evidence",
            "search_experiments",
            "get_research_document",
        ])


if __name__ == "__main__":
    unittest.main()
