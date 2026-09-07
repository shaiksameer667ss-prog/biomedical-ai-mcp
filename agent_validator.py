import json
import logging
import re

from config import (
    DEFAULT_DOCUMENT_ID,
    MAX_QUESTION_LENGTH,
    MCP_SERVER_COMMAND,
    MCP_SERVER_SCRIPT,
    RESEARCH_TOP_K,
)

logger = logging.getLogger("biomedical_research_agent")

from agent_planner import extract_duration_hours

def extract_question_topics(question):
    """
    Extract simple biomedical topics from the user's question.
    This is intentionally deterministic and transparent.
    """

    q = question.lower()

    topics = set()

    topic_patterns = {
        "doxorubicin": [
            "doxorubicin",
        ],
        "copper_nanoparticles": [
            "copper nanoparticle",
            "copper nanoparticles",
            "nano-copper",
            "nanocopper",
            "copper oxide nanoparticle",
            "copper oxide nanoparticles",
        ],
        "liver_cells": [
            "liver cell",
            "liver cells",
            "hepatic",
        ],
        "skin_cells": [
            "skin cell",
            "skin cells",
            "dermal",
        ],
        "bacterial_culture": [
            "bacterial culture",
            "bacterial",
            "bacteria",
        ],
    }

    for topic, patterns in topic_patterns.items():
        if any(pattern in q for pattern in patterns):
            topics.add(topic)

    return topics


def extract_document_topics(evidence_result):
    """
    Infer topics represented by the retrieved research evidence.

    The current DOC001 document is about copper nanoparticles, but
    this function does not hard-code that fact. It examines returned
    evidence text so the validation layer can work as documents grow.
    """

    if not isinstance(evidence_result, dict):
        return set()

    raw_results = (
        evidence_result.get("results")
        or evidence_result.get("evidence")
        or evidence_result.get("matches")
        or []
    )

    combined_text = []

    for item in raw_results:
        if not isinstance(item, dict):
            continue

        content = (
            item.get("content")
            or item.get("text")
            or item.get("snippet")
            or ""
        )

        if content:
            combined_text.append(str(content).lower())

    text = " ".join(combined_text)

    topics = set()

    if (
        "doxorubicin" in text
        or "adriamycin" in text
    ):
        topics.add("doxorubicin")

    if any(
        term in text
        for term in [
            "copper nanoparticle",
            "copper nanoparticles",
            "nano-copper",
            "nanocopper",
            "copper oxide nanoparticle",
            "copper oxide nanoparticles",
        ]
    ):
        topics.add("copper_nanoparticles")

    if (
        "liver cell" in text
        or "liver cells" in text
        or "hepatic" in text
    ):
        topics.add("liver_cells")

    if (
        "skin cell" in text
        or "skin cells" in text
        or "dermal" in text
    ):
        topics.add("skin_cells")

    if (
        "bacterial culture" in text
        or "bacterial" in text
        or "bacteria" in text
    ):
        topics.add("bacterial_culture")

    return topics


def validate_cross_tool_relevance(question, experiment_result, evidence_result):
    """
    Compare the topic of the experiment result with the topic of
    the retrieved research evidence.

    Returns a transparent validation record.
    """

    question_topics = extract_question_topics(question)
    evidence_topics = extract_document_topics(evidence_result)

    experiment_topics = set()

    experiments = []

    if isinstance(experiment_result, dict):
        experiments = (
            experiment_result.get("experiments")
            or experiment_result.get("results")
            or []
        )

    for experiment in experiments:
        if not isinstance(experiment, dict):
            continue

        treatment = str(
            experiment.get("treatment") or ""
        ).lower()

        cell_type = str(
            experiment.get("cell_type") or ""
        ).lower()

        organism = str(
            experiment.get("organism") or ""
        ).lower()

        if "doxorubicin" in treatment:
            experiment_topics.add("doxorubicin")

        if "copper nanoparticle" in treatment:
            experiment_topics.add("copper_nanoparticles")

        if "liver" in cell_type:
            experiment_topics.add("liver_cells")

        if "skin" in cell_type:
            experiment_topics.add("skin_cells")

        if "bacterial" in organism:
            experiment_topics.add("bacterial_culture")

    # Topics that are actually present in both sources.
    shared_topics = (
        experiment_topics & evidence_topics
    )

    # If the user explicitly requested a treatment/topic and that
    # topic is absent from the research evidence, it is unsafe to
    # present the evidence as directly supporting the experiment.
    requested_treatment_topics = (
        question_topics
        & {
            "doxorubicin",
            "copper_nanoparticles",
        }
    )

    missing_requested_topics = (
        requested_treatment_topics - evidence_topics
    )

    if requested_treatment_topics:
        relevant = len(missing_requested_topics) == 0
    else:
        relevant = len(shared_topics) > 0

    return {
        "question_topics": sorted(question_topics),
        "experiment_topics": sorted(experiment_topics),
        "evidence_topics": sorted(evidence_topics),
        "shared_topics": sorted(shared_topics),
        "missing_requested_topics": sorted(
            missing_requested_topics
        ),
        "relevant": relevant,
    }


def format_cross_tool_validation(validation):
    """Create a human-readable cross-tool validation summary."""

    if validation["relevant"]:
        return (
            "Cross-tool relevance check: PASS\n"
            "The retrieved research evidence matches the "
            "requested experiment topic."
        )

    missing = validation[
        "missing_requested_topics"
    ]

    if missing:
        readable = ", ".join(
            missing
        ).replace(
            "doxorubicin",
            "doxorubicin",
        ).replace(
            "copper_nanoparticles",
            "copper nanoparticles",
        )

        return (
            "Cross-tool relevance check: NOT SUPPORTED\n"
            f"The available research evidence does not contain "
            f"the requested treatment/topic ({readable}). "
            "Therefore, the retrieved mechanism evidence should "
            "not be presented as evidence about the selected experiment."
        )

    return (
        "Cross-tool relevance check: NOT CONFIRMED\n"
        "The experiment record and retrieved research evidence "
        "do not share a sufficiently clear biomedical topic."
    )


def _extract_experiment_records(experiment_result):
    if not isinstance(experiment_result, dict):
        return []
    return (
        experiment_result.get("experiments")
        or experiment_result.get("results")
        or []
    )


def _extract_evidence_text(evidence_result):
    if not isinstance(evidence_result, dict):
        return ""
    raw_results = (
        evidence_result.get("results")
        or evidence_result.get("evidence")
        or evidence_result.get("matches")
        or []
    )
    parts = []
    for item in raw_results:
        if isinstance(item, dict):
            content = (
                item.get("content")
                or item.get("text")
                or item.get("snippet")
                or ""
            )
            if content:
                parts.append(str(content).lower())
    return " ".join(parts)


def _requested_mechanism(question):
    q = question.lower()
    mechanism_terms = [
        "mechanism", "mechanisms", "toxicity", "cytotoxicity",
        "oxidative stress", "reactive oxygen", "ros",
        "apoptosis", "mitochondrial", "dna damage",
        "genotoxicity", "lipid peroxidation", "cell death",
        "membrane damage", "membrane disruption", "cell viability",
    ]
    return any(term in q for term in mechanism_terms)


def _infer_evidence_cell_models(evidence_text):
    models = set()
    patterns = {
        "liver_cells": ["liver cell", "liver cells", "hepatic"],
        "skin_cells": ["skin cell", "skin cells", "dermal"],
        "bacterial_culture": ["bacterial culture", "bacterial", "bacteria"],
        "podocytes": ["podocyte", "podocytes"],
        "neurons": ["neuron", "neurons"],
        "epithelial_cells": ["epithelial cell", "epithelial cells"],
        "cancer_cells": ["cancer cell", "cancer cells"],
    }
    for model, terms in patterns.items():
        if any(term in evidence_text for term in terms):
            models.add(model)
    return models


def _infer_evidence_treatments(evidence_text):
    treatments = set()
    if "doxorubicin" in evidence_text or "adriamycin" in evidence_text:
        treatments.add("doxorubicin")
    if any(term in evidence_text for term in [
        "copper nanoparticle",
        "copper nanoparticles",
        "nano-copper",
        "nanocopper",
        "copper oxide nanoparticle",
        "copper oxide nanoparticles",
    ]):
        treatments.add("copper_nanoparticles")
    return treatments


def _infer_evidence_duration(evidence_text):
    durations = set()
    patterns = [
        (r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", 1),
        (r"\b(\d+(?:\.\d+)?)\s*(?:days?|day)\b", 24),
        (r"\b(\d+(?:\.\d+)?)\s*(?:weeks?|week)\b", 24 * 7),
    ]
    for pattern, multiplier in patterns:
        for match in re.finditer(pattern, evidence_text):
            try:
                durations.add(float(match.group(1)) * multiplier)
            except ValueError:
                pass
    return durations


def _format_alignment_dimension(label, status, detail):
    return f"{label:<18} {status:<10} {detail}"


def validate_cross_tool_alignment(question, experiment_result, evidence_result):
    """
    Compare experiment and literature evidence across multiple dimensions.

    This is a conservative alignment check, not scientific validation.
    """
    experiments = _extract_experiment_records(experiment_result)
    evidence_text = _extract_evidence_text(evidence_result)
    question_topics = extract_question_topics(question)
    requested_duration = extract_duration_hours(question)
    evidence_treatments = _infer_evidence_treatments(evidence_text)
    evidence_models = _infer_evidence_cell_models(evidence_text)
    evidence_durations = _infer_evidence_duration(evidence_text)

    first = experiments[0] if experiments and isinstance(experiments[0], dict) else {}

    experiment_treatment = str(first.get("treatment") or "").lower()
    experiment_cell = str(first.get("cell_type") or "").lower()
    experiment_duration = first.get("duration_hours")

    requested_treatments = question_topics & {
        "doxorubicin",
        "copper_nanoparticles",
    }

    # Treatment alignment
    if requested_treatments:
        if "doxorubicin" in requested_treatments:
            treatment_status = (
                "MATCH" if "doxorubicin" in evidence_treatments
                else "DIFFERENT"
            )
        elif "copper_nanoparticles" in requested_treatments:
            if "copper_nanoparticles" in evidence_treatments:
                # Copper oxide is treated as topic-level compatibility,
                # not proof of identical material/specification.
                treatment_status = "MATCH (topic-level)"
            else:
                treatment_status = "DIFFERENT"
    elif experiment_treatment:
        treatment_status = "MATCH" if evidence_treatments else "UNKNOWN"
    else:
        treatment_status = "UNKNOWN"

    # Cell/model alignment
    experiment_model = None
    if "liver" in experiment_cell:
        experiment_model = "liver_cells"
    elif "skin" in experiment_cell:
        experiment_model = "skin_cells"
    elif "bacterial" in experiment_cell:
        experiment_model = "bacterial_culture"

    if experiment_model and evidence_models:
        cell_status = (
            "MATCH" if experiment_model in evidence_models
            else "DIFFERENT"
        )
    else:
        cell_status = "UNKNOWN"

    # Duration alignment
    if requested_duration is not None and experiment_duration is not None:
        experiment_duration_match = (
            float(experiment_duration) == float(requested_duration)
        )
        duration_detail = (
            f"experiment={experiment_duration:g}h, "
            f"question={requested_duration:g}h"
        )
        if evidence_durations:
            if float(requested_duration) in evidence_durations:
                duration_status = "MATCH"
            else:
                duration_status = "UNKNOWN"
                duration_detail += "; document duration not established"
        else:
            duration_status = "UNKNOWN"
            duration_detail += "; document duration not established"
        if not experiment_duration_match:
            duration_status = "DIFFERENT"
    elif experiment_duration is not None:
        duration_status = "UNKNOWN"
        duration_detail = "experiment duration known; question/document duration not established"
    else:
        duration_status = "UNKNOWN"
        duration_detail = "duration not established across sources"

    # Mechanism alignment
    if _requested_mechanism(question):
        mechanism_terms = [
            "oxidative stress", "reactive oxygen species", "ros",
            "mitochondrial", "lipid peroxidation", "dna damage",
            "genotoxicity", "apoptosis", "caspase", "cell death",
            "cytotoxicity", "membrane damage", "cell viability",
        ]
        mechanism_hits = [term for term in mechanism_terms if term in evidence_text]
        mechanism_status = "MATCH" if mechanism_hits else "UNKNOWN"
        mechanism_detail = (
            "mechanism-specific evidence retrieved"
            if mechanism_hits
            else "no mechanism-specific evidence established"
        )
    else:
        mechanism_status = "UNKNOWN"
        mechanism_detail = "mechanism was not explicitly requested"

    statuses = [
        treatment_status,
        cell_status,
        duration_status,
        mechanism_status,
    ]

    # Overall alignment is intentionally asymmetric:
    # - A treatment mismatch is a hard incompatibility.
    # - A conflicting duration is also a hard incompatibility.
    # - A different cell/model is important, but does not make the
    #   sources unrelated; it produces PARTIALLY ALIGNED.
    # - UNKNOWN dimensions should not be treated as mismatches.
    hard_mismatches = {
        "DIFFERENT" for status in (treatment_status, duration_status)
        if status == "DIFFERENT"
    }

    if hard_mismatches:
        overall = "NOT ALIGNED"
    elif all(
        status in {"MATCH", "MATCH (topic-level)"}
        for status in statuses
    ):
        overall = "MATCHED"
    elif any(
        status in {"MATCH", "MATCH (topic-level)"}
        for status in statuses
    ):
        overall = "PARTIALLY ALIGNED"
    else:
        overall = "NOT CONFIRMED"

    return {
        "overall": overall,
        "treatment": {
            "status": treatment_status,
            "detail": (
                f"experiment={experiment_treatment or 'unknown'}; "
                f"document={', '.join(sorted(evidence_treatments)) or 'not established'}"
            ),
        },
        "cell_model": {
            "status": cell_status,
            "detail": (
                f"experiment={experiment_model or 'unknown'}; "
                f"document={', '.join(sorted(evidence_models)) or 'not established'}"
            ),
        },
        "duration": {
            "status": duration_status,
            "detail": duration_detail,
        },
        "mechanism": {
            "status": mechanism_status,
            "detail": mechanism_detail,
        },
    }


def format_cross_tool_alignment(alignment):
    """Render multi-dimensional alignment without implying scientific validation."""
    lines = [
        "Cross-Tool Evidence Alignment",
        "-----------------------------",
        _format_alignment_dimension(
            "Treatment:", alignment["treatment"]["status"],
            alignment["treatment"]["detail"],
        ),
        _format_alignment_dimension(
            "Cell model:", alignment["cell_model"]["status"],
            alignment["cell_model"]["detail"],
        ),
        _format_alignment_dimension(
            "Duration:", alignment["duration"]["status"],
            alignment["duration"]["detail"],
        ),
        _format_alignment_dimension(
            "Mechanism:", alignment["mechanism"]["status"],
            alignment["mechanism"]["detail"],
        ),
        "",
        f"Overall alignment: {alignment['overall']}",
    ]

    if alignment["overall"] == "MATCHED":
        lines.append(
            "Interpretation: The retrieved evidence is aligned with "
            "the requested treatment/model context at the dimensions checked."
        )
    elif alignment["overall"] == "PARTIALLY ALIGNED":
        lines.append(
            "Interpretation: Some dimensions align, but the document "
            "does not establish the same complete experimental context."
        )
    elif alignment["overall"] == "NOT ALIGNED":
        lines.append(
            "Interpretation: At least one key dimension differs. "
            "The document evidence should not be presented as direct "
            "evidence for the selected experiment."
        )
    else:
        lines.append(
            "Interpretation: The available evidence is insufficient "
            "to establish cross-tool alignment."
        )

    lines.append(
        "This alignment is a rule-based consistency check, not "
        "independent scientific validation."
    )
    return "\n".join(lines)


