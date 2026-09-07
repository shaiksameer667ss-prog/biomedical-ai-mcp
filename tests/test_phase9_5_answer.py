import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLANNER_DIR = ROOT.parent / "phase9_4_smarter_planning"
if str(PLANNER_DIR) not in sys.path:
    sys.path.insert(0, str(PLANNER_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The production project already has config.py. This lightweight test stub
# only makes the formatter testable in the build environment used to create
# this package.
if "config" not in sys.modules:
    config = types.ModuleType("config")
    config.DEFAULT_DOCUMENT_ID = "DOC001"
    config.LOG_LEVEL = "INFO"
    config.MAX_QUESTION_LENGTH = 2000
    config.MCP_SERVER_COMMAND = "python"
    config.MCP_SERVER_SCRIPT = "server.py"
    config.RESEARCH_TOP_K = 5
    sys.modules["config"] = config

import agent_answer


class Phase95AnswerTests(unittest.TestCase):
    def setUp(self):
        self.experiment = {
            "experiments": [
                {
                    "experiment_id": "EXP001",
                    "name": "Cytotoxicity Study",
                    "cell_type": "Skin Cells",
                    "treatment": "Copper Nanoparticles",
                    "duration_hours": 24,
                }
            ]
        }
        self.evidence = {
            "document_id": "DOC001",
            "document_title": "Copper Nanoparticle Cytotoxicity Study",
            "results": [{"content": "Copper nanoparticles can cause oxidative stress and apoptosis."}],
            "mechanisms": [
                {
                    "mechanism": "Apoptosis",
                    "summary": "Nano-copper exposure is associated with apoptotic signaling.",
                    "evidence": "Nano-copper poisoning leads to high levels of cytosolic cytochrome c.",
                    "page": 7,
                    "evidence_strength": "DIRECT",
                }
            ],
        }
        self.document = {
            "document_id": "DOC001",
            "title": "Copper Nanoparticle Cytotoxicity Study",
            "file_name": "copper_nanoparticle_study.pdf",
            "document_type": "PDF",
            "description": "Research document related to copper nanoparticle cytotoxicity.",
        }

    def test_combined_answer_has_research_question(self):
        answer = agent_answer.build_combined_research_answer(
            "What mechanisms cause copper nanoparticle toxicity?",
            {"search_research_evidence": self.evidence},
        )
        self.assertIn("Research Question", answer)
        self.assertIn("Mechanistic Evidence", answer)

    def test_experiment_section_is_named_relevant_experiments(self):
        answer = agent_answer.build_combined_research_answer(
            "What mechanisms cause copper nanoparticle toxicity and what experiments exist?",
            {"search_experiments": self.experiment},
        )
        self.assertIn("Relevant Experiments", answer)
        self.assertIn("EXP001", answer)

    def test_document_metadata_is_preserved(self):
        answer = agent_answer.build_combined_research_answer(
            "Show me the paper and its mechanisms.",
            {
                "search_research_evidence": self.evidence,
                "get_research_document": self.document,
            },
        )
        self.assertIn("Research Document", answer)
        self.assertIn("DOC001", answer)
        self.assertIn("copper_nanoparticle_study.pdf", answer)

    def test_cross_tool_interpretation_is_explicit(self):
        answer = agent_answer.build_combined_research_answer(
            "What mechanisms cause copper nanoparticle toxicity and what experiments investigate them?",
            {
                "search_research_evidence": self.evidence,
                "search_experiments": self.experiment,
            },
        )
        self.assertIn("Cross-Tool Interpretation", answer)
        self.assertIn("EXP001 (Cytotoxicity Study)", answer)
        self.assertIn("Overall cross-tool alignment:", answer)

    def test_alignment_details_are_not_hidden(self):
        answer = agent_answer.build_combined_research_answer(
            "What mechanisms cause copper nanoparticle toxicity and what experiments investigate them?",
            {
                "search_research_evidence": self.evidence,
                "search_experiments": self.experiment,
            },
        )
        self.assertIn("Treatment:", answer)
        self.assertIn("Cell model:", answer)
        self.assertIn("Mechanism:", answer)

    def test_provenance_section_identifies_sources(self):
        answer = agent_answer.build_combined_research_answer(
            "What mechanisms cause copper nanoparticle toxicity and what experiments investigate them?",
            {
                "search_research_evidence": self.evidence,
                "search_experiments": self.experiment,
                "get_research_document": self.document,
            },
        )
        self.assertIn("Evidence & Provenance", answer)
        self.assertIn("SQLite research database", answer)
        self.assertIn("retrieved research-document evidence", answer)

    def test_unrelated_experiment_and_evidence_are_not_claimed_as_same_context(self):
        unrelated = dict(self.experiment)
        unrelated["experiments"] = [dict(self.experiment["experiments"][0], treatment="Doxorubicin")]
        answer = agent_answer.build_combined_research_answer(
            "What mechanisms cause copper nanoparticle toxicity and what experiments investigate them?",
            {
                "search_research_evidence": self.evidence,
                "search_experiments": unrelated,
            },
        )
        self.assertIn("does not establish the same complete experimental context", answer)
        self.assertIn("Treatment:", answer)

    def test_empty_tool_result_does_not_crash(self):
        answer = agent_answer.build_combined_research_answer(
            "Find experiments involving copper nanoparticles.",
            {"search_experiments": {"experiments": []}},
        )
        self.assertIn("Relevant Experiments", answer)
        self.assertIn("Evidence & Provenance", answer)


if __name__ == "__main__":
    unittest.main()
