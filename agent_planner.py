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

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


class AgentInputError(ValueError):
    """Raised when a user question is invalid for agent processing."""


def validate_question(question):
    """
    Validate and normalize a user question before tool planning.

    Returns the stripped question.
    Raises AgentInputError for invalid input.
    """
    if question is None:
        raise AgentInputError("Question cannot be empty.")

    if not isinstance(question, str):
        raise AgentInputError("Question must be text.")

    normalized = question.strip()

    if not normalized:
        raise AgentInputError("Question cannot be empty.")

    if len(normalized) > MAX_QUESTION_LENGTH:
        raise AgentInputError(
            f"Question is too long. Please keep it under {MAX_QUESTION_LENGTH} characters."
        )

    return normalized


def validate_numeric_dilution_values(stock, desired, final_volume):
    """Validate numeric dilution inputs before sending them to the MCP server."""
    values = {
        "stock concentration": stock,
        "desired concentration": desired,
        "final volume": final_volume,
    }

    for label, value in values.items():
        if isinstance(value, bool):
            raise AgentInputError(f"{label} must be numeric.")

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise AgentInputError(f"{label} must be numeric.")

        if numeric <= 0:
            raise AgentInputError(f"{label} must be greater than zero.")

    if float(desired) > float(stock):
        raise AgentInputError(
            "Desired concentration cannot be greater than stock concentration."
        )

    return (
        float(stock),
        float(desired),
        float(final_volume),
    )


def word_to_number(text):
    text = text.lower().strip()

    if text in NUMBER_WORDS:
        return NUMBER_WORDS[text]

    parts = text.split()
    total = 0

    for part in parts:
        if part in NUMBER_WORDS:
            total += NUMBER_WORDS[part]

    return total if total > 0 else None


def extract_duration_hours(question):
    q = question.lower()

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b",
        q,
    )

    if match:
        return float(match.group(1))

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:days?|day)\b",
        q,
    )

    if match:
        return float(match.group(1)) * 24

    match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:weeks?|week)\b",
        q,
    )

    if match:
        return float(match.group(1)) * 24 * 7

    for word, number in NUMBER_WORDS.items():
        if re.search(
            rf"\b{word}\s*(?:hours?|hrs?)\b",
            q,
        ):
            return number

    for word, number in NUMBER_WORDS.items():
        if re.search(
            rf"\b{word}\s*(?:days?|day)\b",
            q,
        ):
            return number * 24

    for word, number in NUMBER_WORDS.items():
        if re.search(
            rf"\b{word}\s*(?:weeks?|week)\b",
            q,
        ):
            return number * 24 * 7

    return None


def parse_experiment_filters(question):
    q = question.lower()

    filters = {}

    # Cell type
    if "liver cell" in q or "liver cells" in q or "hepatic" in q:
        filters["cell_type"] = "Liver Cells"

    elif "skin cell" in q or "skin cells" in q or "dermal" in q:
        filters["cell_type"] = "Skin Cells"

    # Treatment
    if "doxorubicin" in q:
        filters["treatment"] = "Doxorubicin"

    elif (
        "copper nanoparticle" in q
        or "copper nanoparticles" in q
        or "nano-copper" in q
        or "nanocopper" in q
    ):
        filters["treatment"] = "Copper Nanoparticles"

    # Organism
    if (
        "bacterial culture" in q
        or "bacterial" in q
        or "bacteria" in q
    ):
        filters["organism"] = "Bacterial Culture"

    # Test
    if "antimicrobial" in q:
        filters["test"] = "Antimicrobial Susceptibility"

    elif (
        "cell viability" in q
        or "viability assay" in q
        or "viability" in q
    ):
        filters["test"] = "Cell Viability Assay"

    # Duration
    duration = extract_duration_hours(question)

    if duration is not None:
        filters["duration_hours"] = duration

    return filters


def extract_experiment_search_query(question):
    q = question.strip()
    lower_q = q.lower()

    prefixes = [
        "find experiments that",
        "find experiments",
        "show experiments that",
        "show experiments",
        "list experiments that",
        "list experiments",
        "search experiments that",
        "search experiments",
        "find me experiments that",
        "find me experiments",
    ]

    for prefix in prefixes:
        if lower_q.startswith(prefix):
            q = q[len(prefix):].strip()
            break

    patterns = [
        r"^which experiments (?:are|were)\s+",
        r"^what experiments (?:are|were)\s+",
        r"^which experiments\s+",
    ]

    for pattern in patterns:
        q = re.sub(
            pattern,
            "",
            q,
            flags=re.IGNORECASE,
        )

    remove_phrases = [
        "performed",
        "conducted",
        "carried out",
        "using",
        "with",
        "that lasted",
        "lasting",
    ]

    for phrase in remove_phrases:
        q = re.sub(
            rf"\b{re.escape(phrase)}\b",
            " ",
            q,
            flags=re.IGNORECASE,
        )

    q = re.sub(r"\s+", " ", q).strip()

    return q


def choose_tool(question):
    question = validate_question(question)
    q = question.lower()

    # Dilution
    if (
        "dilution" in q
        or "stock concentration" in q
        or "final concentration" in q
    ):
        return "calculate_dilution"

    # Research evidence
    research_terms = [
        "mechanism",
        "mechanisms",
        "toxicity",
        "cytotoxicity",
        "oxidative stress",
        "reactive oxygen",
        "ros",
        "apoptosis",
        "mitochondrial",
        "dna damage",
        "lipid peroxidation",
        "cell death",
        "membrane damage",
        "how does",
        "why does",
    ]

    if any(term in q for term in research_terms):
        return "search_research_evidence"

    # Documents
    document_terms = [
        "document",
        "paper",
        "research paper",
        "pdf",
        "publication",
        "article",
    ]

    if any(term in q for term in document_terms):
        return "get_research_document"

    # Experiments
    experiment_terms = [
        "experiment",
        "experiments",
        "study",
        "studies",
    ]

    if any(term in q for term in experiment_terms):
        return "search_experiments"

    return "search_research_evidence"


def question_needs_research_evidence(question):
    q = question.lower()

    research_terms = [
        "mechanism",
        "mechanisms",
        "toxicity",
        "cytotoxicity",
        "oxidative stress",
        "reactive oxygen",
        "reactive oxygen species",
        "ros",
        "apoptosis",
        "mitochondrial",
        "dna damage",
        "genotoxicity",
        "lipid peroxidation",
        "cell death",
        "membrane damage",
        "membrane disruption",
        "cell viability",
        "how does",
        "why does",
        "evidence",
    ]

    return any(term in q for term in research_terms)


def question_needs_experiments(question):
    """
    Decide whether the question asks for experiment/database information.

    The planner is intentionally conservative when a question is already a
    research-evidence question. Words such as "study" or "test" can occur in
    scientific prose without meaning that the user wants database records.
    Explicit experiment language, database-style requests, or experimental
    attributes are therefore given more weight.
    """
    q = question.lower()

    explicit_experiment_phrases = [
        "experiment",
        "experiments",
        "which study",
        "which studies",
        "what study",
        "what studies",
        "find study",
        "find studies",
        "find experiment",
        "find experiments",
        "show study",
        "show studies",
        "show experiment",
        "show experiments",
        "list study",
        "list studies",
        "list experiment",
        "list experiments",
        "database experiment",
        "database experiments",
        "experimental record",
        "experimental records",
    ]

    experimental_attribute_phrases = [
        "cell type",
        "cell types",
        "treatment",
        "organism",
        "duration",
        "lasted",
        "hours",
        "days",
        "test used",
        "assay",
        "performed",
        "conducted",
        "carried out",
        "tested",
        "was tested",
        "were tested",
    ]

    if any(term in q for term in explicit_experiment_phrases):
        return True

    if any(term in q for term in experimental_attribute_phrases):
        return True

    # In an evidence question, generic words such as "study" and "test"
    # are not enough to trigger the experiment database tool.
    if question_needs_research_evidence(question):
        return False

    generic_experiment_terms = [
        "study",
        "studies",
        "tested",
        "test",
        "performed",
        "conducted",
        "carried out",
    ]

    return any(term in q for term in generic_experiment_terms)


def question_needs_document(question):
    q = question.lower()

    document_terms = [
        "document",
        "paper",
        "research paper",
        "pdf",
        "publication",
        "article",
    ]

    return any(term in q for term in document_terms)


def question_requests_multiple_domains(question):
    """Return True when the wording explicitly combines research domains."""
    q = question.lower()

    experiment_request = any(
        phrase in q
        for phrase in [
            "related experiments",
            "related studies",
            "matching experiments",
            "matching studies",
            "experiments in the database",
            "studies in the database",
            "experiment and",
            "experiments and",
            "study and",
            "studies and",
            "along with experiments",
            "along with studies",
            "as well as experiments",
            "as well as studies",
        ]
    )

    document_request = question_needs_document(question)
    evidence_request = question_needs_research_evidence(question)

    return {
        "evidence": evidence_request,
        "experiments": experiment_request,
        "document": document_request,
    }


def question_needs_document_metadata(question):
    """Return True when the user explicitly wants document-level information."""
    q = question.lower()

    metadata_phrases = [
        "show me the document",
        "show me the paper",
        "show me the pdf",
        "show the document",
        "show the paper",
        "show the pdf",
        "get the document",
        "get the paper",
        "document metadata",
        "document details",
        "paper details",
        "paper metadata",
        "publication details",
        "article details",
        "pdf details",
        "what paper",
        "which paper",
    ]

    return any(term in q for term in metadata_phrases)


def question_needs_document_content(question):
    """Return True when the user asks what the document/paper contains."""
    q = question.lower()

    content_phrases = [
        "what does the paper say",
        "what does the paper show",
        "what does the paper report",
        "what does the paper discuss",
        "what does the document say",
        "what does the document show",
        "what does the document report",
        "what does the article say",
        "what does the article show",
        "according to the paper",
        "according to the document",
        "according to the article",
        "in the paper",
        "in the document",
        "in this paper",
        "in this document",
    ]

    return any(term in q for term in content_phrases)


def question_needs_experiment_metadata(question):
    """Return True when the question asks for experiment records or attributes."""
    q = question.lower()

    explicit_phrases = [
        "experiment",
        "experiments",
        "which study",
        "which studies",
        "what study",
        "what studies",
        "find study",
        "find studies",
        "find experiment",
        "find experiments",
        "show study",
        "show studies",
        "show experiment",
        "show experiments",
        "list study",
        "list studies",
        "list experiment",
        "list experiments",
        "database experiment",
        "database experiments",
        "experimental record",
        "experimental records",
    ]

    attributes = [
        "cell type",
        "cell types",
        "treatment",
        "organism",
        "duration",
        "lasted",
        "hours",
        "days",
        "test used",
        "assay",
        "experimental design",
        "experimental conditions",
    ]

    return any(term in q for term in explicit_phrases + attributes)


def question_needs_experiments(question):
    """Decide whether the question asks for experiment/database information."""
    q = question.lower()

    if question_needs_experiment_metadata(question):
        return True

    # Generic scientific wording should not trigger database search when the
    # user is asking for evidence or document content.
    if question_needs_research_evidence(question):
        return False

    generic_terms = ["study", "studies", "tested", "test", "performed", "conducted"]
    return any(term in q for term in generic_terms)

def plan_tools(question):
    """
    Determine the smallest useful MCP tool plan for a question.

    The planner separates four user intents:

    - research evidence: search_research_evidence
    - experiment records: search_experiments
    - document metadata: get_research_document
    - dilution calculation: calculate_dilution

    Multiple intents can produce a multi-tool plan. The order is deterministic:
    evidence first, experiment records second, and document metadata third.
    """
    question = validate_question(question)
    q = question.lower()

    # Dilution is a dedicated workflow and should not be mixed with research
    # tools in the current portfolio version.
    if (
        "dilution" in q
        or "stock concentration" in q
        or "final concentration" in q
    ):
        return ["calculate_dilution"]

    wants_evidence = question_needs_research_evidence(question)
    wants_experiments = question_needs_experiments(question)
    wants_document = question_needs_document(question)
    wants_document_metadata = question_needs_document_metadata(question)
    wants_document_content = question_needs_document_content(question)

    tools = []

    # Mechanism/toxicity/evidence questions use the research retriever.
    if wants_evidence:
        tools.append("search_research_evidence")

    # Explicit experiment/database requests use the experiment search tool.
    if wants_experiments:
        tools.append("search_experiments")

    # A document-focused question needs metadata when it explicitly asks for
    # the document itself/details. If the user asks what the paper says,
    # evidence retrieval is more useful than metadata alone, but metadata is
    # still added when the wording explicitly asks for both.
    if wants_document_metadata:
        tools.append("get_research_document")
    elif wants_document and not wants_evidence and not wants_experiments:
        tools.append("get_research_document")
    elif wants_document_content and not wants_evidence:
        # Content-only wording without a mechanism/evidence term still needs
        # the document metadata tool as the safest available document route.
        tools.append("get_research_document")

    if not tools:
        tools.append(choose_tool(question))

    # Preserve deterministic ordering and prevent duplicate tools.
    return list(dict.fromkeys(tools))

