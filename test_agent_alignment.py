import unittest
import agent


class CrossToolAlignmentTests(unittest.TestCase):

    def alignment(self, question, experiment, evidence):
        result = agent.validate_cross_tool_alignment(
            question,
            {"results": [experiment]},
            {"results": evidence},
        )
        return result

    def test_copper_experiment_copper_evidence_is_partial(self):
        result = self.alignment(
            "What does the research document say about copper nanoparticle toxicity, "
            "and which experiments involve copper nanoparticles?",
            {
                "experiment_id": "EXP001",
                "name": "Cytotoxicity Study",
                "cell_type": "Skin Cells",
                "treatment": "Copper Nanoparticles",
                "duration_hours": 24,
            },
            [{
                "page_number": 6,
                "text": (
                    "Copper nanoparticles cause ROS generation and mitochondrial "
                    "effects in neurons."
                ),
            }],
        )
        self.assertEqual(result["overall"], "PARTIALLY ALIGNED")

    def test_doxorubicin_experiment_copper_evidence_is_not_aligned(self):
        result = self.alignment(
            "Which experiment tested doxorubicin on liver cells for two days, "
            "and what does the research document say about copper nanoparticle toxicity?",
            {
                "experiment_id": "EXP003",
                "name": "Drug Cytotoxicity Study",
                "cell_type": "Liver Cells",
                "treatment": "Doxorubicin",
                "duration_hours": 48,
            },
            [{
                "page_number": 6,
                "text": (
                    "Copper nanoparticles cause ROS generation and mitochondrial "
                    "effects in neurons."
                ),
            }],
        )
        self.assertEqual(result["overall"], "NOT ALIGNED")
        self.assertEqual(result["treatment"]["status"], "DIFFERENT")

    def test_matching_context_is_matched(self):
        result = self.alignment(
            "What does the copper nanoparticle experiment show about toxicity after 24 hours?",
            {
                "experiment_id": "EXP001",
                "name": "Cytotoxicity Study",
                "cell_type": "Skin Cells",
                "treatment": "Copper Nanoparticles",
                "duration_hours": 24,
            },
            [{
                "page_number": 4,
                "text": (
                    "Copper nanoparticles were exposed to skin cells for 24 hours. "
                    "This caused cytotoxic effects and reduced cell viability."
                ),
            }],
        )
        self.assertEqual(result["overall"], "MATCHED")

    def test_conflicting_duration_is_not_aligned(self):
        result = self.alignment(
            "What happened after two days of copper nanoparticle exposure?",
            {
                "experiment_id": "EXP001",
                "name": "Cytotoxicity Study",
                "cell_type": "Skin Cells",
                "treatment": "Copper Nanoparticles",
                "duration_hours": 24,
            },
            [{
                "page_number": 4,
                "text": (
                    "Copper nanoparticles were studied in skin cells for 48 hours "
                    "and produced cytotoxic effects."
                ),
            }],
        )
        self.assertEqual(result["overall"], "NOT ALIGNED")
        self.assertEqual(result["duration"]["status"], "DIFFERENT")

    def test_unknown_document_duration_does_not_create_false_mismatch(self):
        result = self.alignment(
            "What does the copper nanoparticle experiment show?",
            {
                "experiment_id": "EXP001",
                "name": "Cytotoxicity Study",
                "cell_type": "Skin Cells",
                "treatment": "Copper Nanoparticles",
                "duration_hours": 24,
            },
            [{
                "page_number": 6,
                "text": (
                    "Copper nanoparticles cause ROS generation and mitochondrial "
                    "effects in neurons."
                ),
            }],
        )
        self.assertEqual(result["duration"]["status"], "UNKNOWN")

    def test_topic_level_copper_match_is_explicit(self):
        result = self.alignment(
            "What does the copper nanoparticle experiment show?",
            {
                "experiment_id": "EXP001",
                "name": "Cytotoxicity Study",
                "cell_type": "Skin Cells",
                "treatment": "Copper Nanoparticles",
                "duration_hours": 24,
            },
            [{
                "page_number": 6,
                "text": (
                    "Copper oxide nanoparticles cause ROS generation and "
                    "mitochondrial effects."
                ),
            }],
        )
        self.assertEqual(result["treatment"]["status"], "MATCH (topic-level)")


class RegressionTests(unittest.TestCase):

    def test_dilution_question_routes_to_calculator(self):
        question = "Calculate dilution from a 10 mg/mL stock to 2 mg/mL, final volume 5 mL."

        if callable(getattr(agent, "choose_tool", None)):
            selected = agent.choose_tool(question)
            if isinstance(selected, (list, tuple)):
                selected = list(selected)
                self.assertIn("calculate_dilution", selected)
            else:
                self.assertEqual(selected, "calculate_dilution")
        else:
            self.skipTest("Agent does not expose choose_tool().")

    def test_experiment_search_helper_exists(self):
        self.assertTrue(callable(getattr(agent, "parse_experiment_filters", None)))

    def test_tool_planner_exists(self):
        self.assertTrue(callable(getattr(agent, "plan_tools", None)))

    def test_cross_tool_validation_exists(self):
        self.assertTrue(
            callable(getattr(agent, "validate_cross_tool_relevance", None))
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
