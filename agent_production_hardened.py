import asyncio
import json
import logging
import re

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ============================================================
# PRODUCTION HARDENING: LOGGING + INPUT VALIDATION
# ============================================================

logger = logging.getLogger("biomedical_research_agent")

if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


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

    if len(normalized) > 2000:
        raise AgentInputError(
            "Question is too long. Please keep it under 2000 characters."
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


# ============================================================
# MCP SERVER CONFIGURATION
# ============================================================

server_params = StdioServerParameters(
    command="python",
    args=["server.py"],
)


# ============================================================
# NUMBER WORDS
# ============================================================

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


# ============================================================
# DURATION EXTRACTION
# ============================================================

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


# ============================================================
# EXPERIMENT FILTER PARSING
# ============================================================

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


# ============================================================
# EXPERIMENT SEARCH QUERY EXTRACTION
# ============================================================

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


# ============================================================
# TOOL SELECTION
# ============================================================

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


# ============================================================
# MCP RESULT PARSING
# ============================================================

def parse_mcp_result(result):
    if result is None:
        logger.warning("MCP returned no result.")
        return None

    if hasattr(result, "content"):
        content = result.content

        if isinstance(content, list):
            texts = []

            for item in content:
                if hasattr(item, "text"):
                    texts.append(item.text)

            if texts:
                text = "\n".join(texts)

                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text

        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content

    if isinstance(result, dict):
        return result

    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result

    return result


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_evidence_text(text):
    if not text:
        return ""

    text = str(text)

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    text = re.sub(
        r"\bpage\s*\d+\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip(" \t\n\r-–—:;")


# ============================================================
# SENTENCE SPLITTING
# ============================================================

def split_into_sentences(text):
    text = clean_evidence_text(text)

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+(?=[A-Z0-9])",
        text,
    )

    cleaned = []

    for sentence in sentences:
        sentence = sentence.strip()

        if len(sentence) >= 25:
            cleaned.append(sentence)

    return cleaned


# ============================================================
# FIGURE / CAPTION FILTER
# ============================================================

def is_caption_or_fragment(sentence):
    text = sentence.lower().strip()

    bad_starts = [
        "schematic diagram",
        "figure ",
        "fig. ",
        "fig ",
        "table ",
        "graph ",
        "illustration ",
        "model of ",
    ]

    for start in bad_starts:
        if text.startswith(start):
            return True

    # Very short fragments are usually not useful evidence.
    words = text.split()

    if len(words) < 7:
        return True

    return False


# ============================================================
# TOPIC RULES
# ============================================================

TOPIC_RULES = {
    "copper_nanoparticle": [
        "copper nanoparticle",
        "copper nanoparticles",
        "nano-copper",
        "nanocopper",
        "copper oxide nanoparticle",
        "copper oxide nanoparticles",
        "copper oxide np",
        "copper oxide nps",
        "copper np",
        "copper nps",
        "cu nanoparticle",
        "cu nanoparticles",
    ],

    "nanoparticle": [
        "nanoparticle",
        "nanoparticles",
        "nano particle",
        "nano-particle",
        "nano-sized",
        "nanoscale",
    ],

    "copper": [
        "copper",
        "cu2+",
        "cu+",
    ],
}


# ============================================================
# PAGE-LEVEL TOPIC RELEVANCE
# ============================================================

def score_page_topic_relevance(page_text, question):
    """
    Score the entire retrieved page for topic relevance.

    This is different from sentence-level relevance.

    A scientific paper may establish the topic once and then
    use phrases such as 'these NPs', 'these particles', or
    'exposure' later in the section.
    """

    text = page_text.lower()
    q = question.lower()

    score = 0

    # Explicit copper nanoparticle references
    for term in TOPIC_RULES["copper_nanoparticle"]:
        count = text.count(term)
        score += min(count, 5) * 15

    # Copper + nanoparticle independently
    has_copper = "copper" in text or "cu2+" in text or "cu+" in text

    has_nanoparticle = any(
        term in text
        for term in TOPIC_RULES["nanoparticle"]
    )

    if has_copper and has_nanoparticle:
        score += 25

    # Toxicity context
    toxicity_terms = [
        "toxicity",
        "cytotoxicity",
        "toxic effect",
        "cell death",
        "cell viability",
    ]

    for term in toxicity_terms:
        if term in text:
            score += 3

    # Question topic specificity
    question_is_copper_nanoparticle = (
        "copper nanoparticle" in q
        or "copper nanoparticles" in q
        or "nano-copper" in q
        or "nanocopper" in q
        or "copper oxide" in q
    )

    if question_is_copper_nanoparticle:

        if has_copper and has_nanoparticle:
            score += 30

        elif has_copper:
            score += 8

        elif has_nanoparticle:
            score += 5

    return score


# ============================================================
# TOPIC RELEVANCE WITH PAGE CONTEXT
# ============================================================

def score_sentence_topic_relevance(
    sentence,
    page_text,
    question,
):
    """
    Combine:

    1. sentence-level topic evidence
    2. page-level topic context

    This allows sentences such as:

        'These NPs inhibit mitochondrial dehydrogenases...'

    to be accepted when the surrounding retrieved page clearly
    establishes that NPs = copper nanoparticles.
    """

    sentence_lower = sentence.lower()

    sentence_score = 0

    # Direct topic references
    for term in TOPIC_RULES["copper_nanoparticle"]:
        if term in sentence_lower:
            sentence_score += 35

    # Copper + nanoparticle in same sentence
    has_copper = "copper" in sentence_lower
    has_nanoparticle = any(
        term in sentence_lower
        for term in TOPIC_RULES["nanoparticle"]
    )

    if has_copper and has_nanoparticle:
        sentence_score += 25

    # Indirect references commonly used in papers
    indirect_topic_terms = [
        "these nps",
        "these nanoparticles",
        "these particles",
        "nano-copper",
        "nanocopper",
        "copper oxide",
        "cuo",
        "cu nanoparticles",
    ]

    for term in indirect_topic_terms:
        if term in sentence_lower:
            sentence_score += 15

    # Page context
    page_score = score_page_topic_relevance(
        page_text,
        question,
    )

    # Convert page context into a confidence contribution.
    #
    # We don't let page context completely override the sentence.
    page_context_bonus = min(
        page_score // 10,
        25,
    )

    total = sentence_score + page_context_bonus

    return {
        "sentence_score": sentence_score,
        "page_score": page_score,
        "page_context_bonus": page_context_bonus,
        "total": total,
    }


# ============================================================
# TOPIC RELEVANCE CHECK
# ============================================================

def is_topic_relevant(
    sentence,
    page_text,
    question,
):
    result = score_sentence_topic_relevance(
        sentence,
        page_text,
        question,
    )

    # Direct topic sentence
    if result["sentence_score"] >= 20:
        return True

    # Indirect sentence supported by a strongly topic-relevant page
    if (
        result["page_score"] >= 40
        and result["sentence_score"] >= 5
    ):
        return True

    return False


# ============================================================
# MECHANISM RULES
# ============================================================

MECHANISM_RULES = {
    "Oxidative stress": {
        "strong": [
            "oxidative stress",
            "oxidative damage",
            "reactive oxygen species",
            "ros generation",
            "ros level",
            "reactive oxygen",
        ],
        "supporting": [
            "oxidative",
            "free radicals",
            "redox",
        ],
    },

    "Mitochondrial damage": {
        "strong": [
            "mitochondrial damage",
            "mitochondrial dysfunction",
            "mitochondrial membrane potential",
            "mitochondrial dehydrogenase",
            "mitochondrial dehydrogenases",
            "mitochondrial pathway",
            "mitochondrial pathways",
            "mitochondria",
        ],
        "supporting": [
            "cytochrome c",
            "mitochondrial membrane",
            "membrane potential",
        ],
    },

    "Lipid peroxidation": {
        "strong": [
            "lipid peroxidation",
            "lipid oxidation",
            "peroxidation of lipids",
        ],
        "supporting": [
            "lipid",
            "peroxidative",
        ],
    },

    "DNA damage": {
        "strong": [
            "dna damage",
            "genotoxicity",
            "genotoxic",
            "dna fragmentation",
            "dna strand break",
        ],
        "supporting": [
            "dna",
            "genome",
            "chromosomal damage",
        ],
    },

    "Apoptosis": {
        "strong": [
            "apoptosis",
            "apoptotic",
            "caspase",
            "caspase-3",
            "caspase 3",
            "caspase-8",
            "caspase 8",
            "caspase-9",
            "caspase 9",
            "cytochrome c",
            "apaf",
            "tbid",
            "fas",
        ],
        "supporting": [
            "programmed cell death",
        ],
    },

    "Cell membrane damage": {
        "strong": [
            "membrane damage",
            "cell membrane damage",
            "membrane disruption",
            "membrane integrity",
            "membrane permeability",
        ],
        "supporting": [
            "membrane",
            "permeability",
        ],
    },

    "Cell death / reduced viability": {
        "strong": [
            "cell death",
            "cell viability",
            "reduced viability",
            "decreased viability",
            "loss of viability",
            "cytotoxicity",
            "cytotoxic",
        ],
        "supporting": [
            "cell survival",
            "cell proliferation",
        ],
    },
}


# ============================================================
# MECHANISM SENTENCE SCORING
# ============================================================

def score_mechanism_sentence(
    sentence,
    page_text,
    mechanism,
    question,
):
    text = sentence.lower()

    rules = MECHANISM_RULES.get(
        mechanism,
        {},
    )

    strong_terms = rules.get(
        "strong",
        [],
    )

    supporting_terms = rules.get(
        "supporting",
        [],
    )

    score = 0
    strong_matches = 0
    supporting_matches = 0

    # --------------------------------------------------------
    # Strong mechanism terms
    # --------------------------------------------------------

    for term in strong_terms:
        if term in text:
            score += 15
            strong_matches += 1

    # --------------------------------------------------------
    # Supporting terms
    # --------------------------------------------------------

    for term in supporting_terms:
        if term in text:
            score += 4
            supporting_matches += 1

    # --------------------------------------------------------
    # Topic relevance
    # --------------------------------------------------------

    topic = score_sentence_topic_relevance(
        sentence,
        page_text,
        question,
    )

    score += topic["total"]

    # --------------------------------------------------------
    # Scientific specificity
    # --------------------------------------------------------

    specificity_terms = [
        "increase",
        "increased",
        "decrease",
        "decreased",
        "inhibit",
        "inhibition",
        "induce",
        "induced",
        "activate",
        "activation",
        "lead to",
        "result in",
        "cause",
        "caused",
        "mediated",
        "pathway",
        "mechanism",
    ]

    specificity_matches = 0

    for term in specificity_terms:
        if term in text:
            specificity_matches += 1

    score += min(
        specificity_matches,
        4,
    ) * 3

    # --------------------------------------------------------
    # Experimental language
    # --------------------------------------------------------

    experimental_terms = [
        "study",
        "studies",
        "observed",
        "showed",
        "demonstrated",
        "reported",
        "analysis",
        "exposure",
        "treated",
        "treatment",
    ]

    experimental_matches = 0

    for term in experimental_terms:
        if term in text:
            experimental_matches += 1

    score += min(
        experimental_matches,
        3,
    ) * 2

    # --------------------------------------------------------
    # Length
    # --------------------------------------------------------

    if len(sentence) >= 80:
        score += 3

    if len(sentence) >= 150:
        score += 3

    return {
        "score": score,
        "strong_matches": strong_matches,
        "supporting_matches": supporting_matches,
        "topic_score": topic["total"],
        "page_topic_score": topic["page_score"],
    }


# ============================================================
# BEST MECHANISM EVIDENCE
# ============================================================

def extract_best_mechanism_evidence(
    pages,
    mechanism,
    question,
    max_sentences=2,
):
    candidates = []

    for page in pages:

        page_number = page.get(
            "page_number"
        )

        content = (
            page.get("content")
            or page.get("text")
            or page.get("snippet")
            or ""
        )

        content = clean_evidence_text(
            content
        )

        if not content:
            continue

        sentences = split_into_sentences(
            content
        )

        # ----------------------------------------------------
        # Calculate page-level topic relevance once
        # ----------------------------------------------------

        page_topic_score = score_page_topic_relevance(
            content,
            question,
        )

        for sentence in sentences:

            # ------------------------------------------------
            # Reject captions / fragments
            # ------------------------------------------------

            if is_caption_or_fragment(
                sentence
            ):
                continue

            # ------------------------------------------------
            # Score mechanism + topic
            # ------------------------------------------------

            result = score_mechanism_sentence(
                sentence=sentence,
                page_text=content,
                mechanism=mechanism,
                question=question,
            )

            # Must contain strong mechanism evidence.
            if result["strong_matches"] == 0:
                continue

            # ------------------------------------------------
            # IMPORTANT:
            # Require either direct topic evidence OR
            # strong page-level topic context.
            # ------------------------------------------------

            direct_topic = (
                result["topic_score"] >= 20
            )

            strong_page_context = (
                page_topic_score >= 40
                and result["topic_score"] >= 5
            )

            if not direct_topic and not strong_page_context:
                continue

            # Minimum total score
            if result["score"] < 35:
                continue

            candidates.append(
                {
                    "page_number": page_number,
                    "sentence": sentence,
                    "score": result["score"],
                    "topic_score": result["topic_score"],
                    "page_topic_score": page_topic_score,
                    "strong_matches": result[
                        "strong_matches"
                    ],
                }
            )

    # --------------------------------------------------------
    # Rank evidence
    # --------------------------------------------------------

    candidates.sort(
        key=lambda x: (
            x["score"],
            x["topic_score"],
            x["page_topic_score"],
            x["strong_matches"],
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # Remove duplicate sentences
    # --------------------------------------------------------

    selected = []
    seen = set()

    for candidate in candidates:

        normalized = re.sub(
            r"\s+",
            " ",
            candidate["sentence"].lower(),
        ).strip()

        if normalized in seen:
            continue

        seen.add(normalized)

        selected.append(
            candidate
        )

        if len(selected) >= max_sentences:
            break

    return selected


# ============================================================
# PAGE NUMBER EXTRACTION
# ============================================================

def get_result_page(item):
    if not isinstance(item, dict):
        return None

    return (
        item.get("page_number")
        or item.get("page")
        or item.get("page_num")
    )


# ============================================================
# RESEARCH ANSWER
# ============================================================

def infer_evidence_context(sentence, page_text):
    """Separate direct sentence context from broader page context.

    Direct context is reported only when the term appears in the
    evidence sentence itself. Page context is reported separately when
    the term appears elsewhere on the retrieved page. This avoids
    implying that every concept on a page is present in every sentence.
    """
    sentence_text = sentence.lower()
    page_lower = page_text.lower()
    direct = []
    page_only = []

    def add_context(label, terms, direct_label=None):
        direct_label = direct_label or label
        if any(term in sentence_text for term in terms):
            direct.append(direct_label)
        elif any(term in page_lower for term in terms):
            page_only.append(label)

    cell_models = [
        ("podocyte", ["podocyte", "podocytes"]),
        ("neuron", ["neuron", "neurons"]),
        ("epithelial cell", ["epithelial cell", "epithelial cells"]),
        ("skin cell", ["skin cell", "skin cells"]),
        ("liver cell", ["liver cell", "liver cells"]),
        ("cancer cell", ["cancer cell", "cancer cells"]),
    ]

    for label, terms in cell_models:
        if any(term in sentence_text for term in terms):
            direct.append(f"Model/cell context: {label}")
            break
    else:
        for label, terms in cell_models:
            if any(term in page_lower for term in terms):
                page_only.append(f"Model/cell context: {label}")
                break

    add_context(
        "Mechanistic context: mitochondrial effects",
        ["mitochondrial membrane", "mitochondrial", "mitochondria"],
    )
    add_context(
        "Mechanistic context: ROS/oxidative stress",
        ["reactive oxygen species", "ros", "oxidative stress", "oxidative damage"],
    )
    add_context(
        "Mechanistic context: lipid peroxidation",
        ["lipid peroxidation"],
    )
    add_context(
        "Mechanistic context: apoptotic signaling",
        ["cytochrome c", "caspase", "apoptosis", "apoptotic"],
    )
    add_context(
        "Mechanistic context: DNA damage/genotoxicity",
        ["dna damage", "genotoxic", "genotoxicity"],
    )
    add_context(
        "Exposure/topic context: copper nanoparticles",
        ["nano-copper", "nanocopper", "copper nanoparticle", "copper nanoparticles"],
    )
    add_context(
        "Exposure/topic context: copper oxide",
        ["copper oxide"],
    )
    add_context(
        "Outcome context: toxicity/cell response",
        ["cytotoxic", "cytotoxicity", "cell death", "cell viability", "toxic", "toxicity"],
    )
    add_context(
        "Study context: exposure/treatment evidence",
        ["exposure", "treated", "treatment", "concentration", "dose", "poisoning"],
    )

    return {
        "direct": direct,
        "page_only": page_only,
    }


def classify_evidence_strength(sentence, page_text, mechanism, question):
    """Conservatively classify the selected evidence sentence."""
    result = score_mechanism_sentence(sentence=sentence, page_text=page_text, mechanism=mechanism, question=question)
    direct_mechanism = result.get("strong_matches", 0) > 0
    direct_topic = result.get("topic_score", 0) >= 20
    page_topic = result.get("page_topic_score", 0)
    if direct_mechanism and direct_topic:
        level = "DIRECT"
        explanation = "Mechanism and topic are explicitly supported by the evidence sentence."
    elif direct_mechanism and page_topic >= 40:
        level = "SUPPORTING"
        explanation = "Mechanism is explicit; broader topic linkage is partly page-level."
    elif direct_mechanism:
        level = "WEAK/INDIRECT"
        explanation = "Mechanism is explicit, but topic linkage is limited."
    else:
        level = "WEAK/INDIRECT"
        explanation = "The sentence provides only indirect support."
    return {"level": level, "score": result.get("score", 0), "topic_score": result.get("topic_score", 0), "page_topic_score": page_topic, "strong_matches": result.get("strong_matches", 0), "explanation": explanation}


def format_evidence_provenance(provenance):
    """Render evidence strength and transparent retrieval scores."""
    if not provenance:
        return ""
    return (
        f"   Evidence strength: {provenance.get('level', 'UNKNOWN')}\n"
        f"   Retrieval score: {provenance.get('score', 0)} | "
        f"Direct topic score: {provenance.get('topic_score', 0)} | "
        f"Page topic score: {provenance.get('page_topic_score', 0)}\n"
        f"   Basis: {provenance.get('explanation', '')}"
    )


def format_provenance_chain(
    document_id,
    document_title,
    page_number,
    sentence,
    mechanism,
    provenance,
):
    """Render a traceable document -> page -> sentence -> mechanism chain."""
    doc_label = document_id or "Unknown document"
    if document_title:
        doc_label = f"{doc_label} ({document_title})"

    page_label = (
        f"Page {page_number}"
        if page_number is not None
        else "Page unknown"
    )

    lines = [
        "   Provenance chain:",
        f"   Document: {doc_label}",
        f"   Page: {page_label}",
        f"   Evidence sentence: {sentence}",
        f"   Mechanism: {mechanism}",
        f"   Evidence strength: {provenance.get('level', 'UNKNOWN')}",
        (
            "   Scores: "
            f"retrieval={provenance.get('score', 0)}, "
            f"direct_topic={provenance.get('topic_score', 0)}, "
            f"page_topic={provenance.get('page_topic_score', 0)}"
        ),
    ]
    return "\n".join(lines)


def format_evidence_context(context):
    """Format direct and page-level context distinctly."""
    if isinstance(context, dict):
        direct = context.get("direct") or []
        page_only = context.get("page_only") or []
    else:
        direct = context or []
        page_only = []

    if not direct and not page_only:
        return "   Context: No additional explicit context identified."

    lines = []

    if direct:
        lines.append("   Direct context:")
        for item in direct:
            lines.append(f"   - {item}")

    if page_only:
        lines.append("   Page context (not necessarily stated in this sentence):")
        for item in page_only:
            lines.append(f"   - {item}")

    return "\n".join(lines)

def generate_research_answer(
    question,
    result,
):
    if not isinstance(result, dict):
        return (
            "The research retrieval tool returned "
            "an unexpected result."
        )

    raw_results = (
        result.get("results")
        or result.get("evidence")
        or result.get("matches")
        or []
    )

    if not raw_results:
        return (
            "No sufficiently relevant research "
            "evidence was retrieved."
        )

    # --------------------------------------------------------
    # Normalize retrieved pages
    # --------------------------------------------------------

    pages = []

    for item in raw_results:

        if not isinstance(item, dict):
            continue

        page_number = get_result_page(
            item
        )

        content = (
            item.get("content")
            or item.get("text")
            or item.get("snippet")
            or ""
        )

        if not content:
            continue

        pages.append(
            {
                "page_number": page_number,
                "content": content,
            }
        )

    if not pages:
        return (
            "No usable research evidence was returned."
        )

    # --------------------------------------------------------
    # Source metadata for provenance
    # --------------------------------------------------------

    document_id = (
        result.get("document_id")
        or result.get("source_document_id")
        or result.get("doc_id")
        or ""
    )

    document_title = (
        result.get("document_title")
        or result.get("source_document_title")
        or result.get("title")
        or ""
    )

    if not document_id:
        for item in raw_results:
            if isinstance(item, dict):
                document_id = (
                    item.get("document_id")
                    or item.get("source_document_id")
                    or item.get("doc_id")
                    or ""
                )
                if document_id:
                    break

    if not document_title:
        for item in raw_results:
            if isinstance(item, dict):
                document_title = (
                    item.get("document_title")
                    or item.get("source_document_title")
                    or ""
                )
                if document_title:
                    break

    # --------------------------------------------------------
    # Mechanisms
    # --------------------------------------------------------

    mechanisms = [
        "Oxidative stress",
        "Mitochondrial damage",
        "Lipid peroxidation",
        "DNA damage",
        "Apoptosis",
        "Cell membrane damage",
        "Cell death / reduced viability",
    ]

    mechanism_results = []

    for mechanism in mechanisms:

        evidence = extract_best_mechanism_evidence(
            pages=pages,
            mechanism=mechanism,
            question=question,
            max_sentences=2,
        )

        if evidence:
            mechanism_results.append(
                {
                    "mechanism": mechanism,
                    "evidence": evidence,
                }
            )

    # --------------------------------------------------------
    # Build answer
    # --------------------------------------------------------

    lines = []

    lines.append(
        "The retrieved evidence indicates that "
        "copper nanoparticle toxicity involves "
        "several cellular mechanisms."
    )

    lines.append("")

    if not mechanism_results:
        lines.append(
            "No mechanism-specific evidence met "
            "the topic-relevance and evidence-quality "
            "thresholds."
        )

    for index, mechanism_data in enumerate(
        mechanism_results,
        start=1,
    ):

        mechanism = mechanism_data[
            "mechanism"
        ]

        evidence = mechanism_data[
            "evidence"
        ]

        pages_used = sorted(
            {
                item["page_number"]
                for item in evidence
                if item["page_number"] is not None
            }
        )

        if pages_used:

            page_text = ", ".join(
                str(page)
                for page in pages_used
            )

            lines.append(
                f"{index}. {mechanism} — "
                f"supporting pages: {page_text}"
            )

        else:
            lines.append(
                f"{index}. {mechanism}"
            )

        for item in evidence:

            sentence = item[
                "sentence"
            ]

            page_number = item[
                "page_number"
            ]

            if page_number is not None:
                lines.append(
                    f"   Evidence (Page {page_number}): "
                    f"{sentence}"
                )
            else:
                lines.append(
                    f"   Evidence: {sentence}"
                )

            page_context = ""
            for page in pages:
                if page["page_number"] == page_number:
                    page_context = page["content"]
                    break

            context = infer_evidence_context(
                sentence,
                page_context,
            )

            lines.append(
                format_evidence_context(context)
            )

            provenance = classify_evidence_strength(
                sentence=sentence,
                page_text=page_context,
                mechanism=mechanism,
                question=question,
            )
            lines.append(format_evidence_provenance(provenance))

            lines.append(
                format_provenance_chain(
                    document_id=document_id,
                    document_title=document_title,
                    page_number=page_number,
                    sentence=sentence,
                    mechanism=mechanism,
                    provenance=provenance,
                )
            )

        lines.append("")

    # --------------------------------------------------------
    # Evidence strength summary
    # --------------------------------------------------------

    strength_counts = {}
    for mechanism_data in mechanism_results:
        mechanism = mechanism_data["mechanism"]
        for item in mechanism_data["evidence"]:
            page_context = next((p["content"] for p in pages if p["page_number"] == item["page_number"]), "")
            provenance = classify_evidence_strength(item["sentence"], page_context, mechanism, question)
            level = provenance["level"]
            strength_counts[level] = strength_counts.get(level, 0) + 1

    lines.append("Evidence Strength Summary")
    lines.append("-------------------------")
    for level in ("DIRECT", "SUPPORTING", "PAGE CONTEXT", "WEAK/INDIRECT"):
        if strength_counts.get(level):
            lines.append(f"- {level}: {strength_counts[level]}")
    lines.append("")

    # --------------------------------------------------------
    # Supporting sources
    # --------------------------------------------------------

    source_pages = []

    for item in pages:

        page_number = item[
            "page_number"
        ]

        if page_number is not None:
            source_pages.append(
                page_number
            )

    source_pages = list(
        dict.fromkeys(
            source_pages
        )
    )

    if source_pages:

        lines.append(
            "Supporting Sources"
        )

        lines.append(
            "-------------------"
        )

        for page in source_pages:
            lines.append(
                f"- Page {page}"
            )

        lines.append("")

    lines.append(
        "Note: Direct context labels come from the evidence sentence; "
        "page-context labels come from the broader retrieved page. "
        "These are rule-based annotations and do not establish causality "
        "or generalizability. "
        "This answer is generated only from the retrieved "
        "document evidence and is not an independent scientific "
        "conclusion. Check the original paper before using the "
        "information for research decisions."
    )

    return "\n".join(lines)


# ============================================================
# EXPERIMENT ANSWER
# ============================================================

def format_experiment_answer(result):
    if not isinstance(result, dict):
        return str(result)

    experiments = (
        result.get("experiments")
        or result.get("results")
        or []
    )

    if not experiments:
        return (
            "No matching experiments were found."
        )

    lines = []

    lines.append(
        f"Found {len(experiments)} "
        f"matching experiment(s):"
    )

    lines.append("")

    for experiment in experiments:

        experiment_id = experiment.get(
            "experiment_id",
            "Unknown",
        )

        name = experiment.get(
            "name",
            "Unnamed experiment",
        )

        lines.append(
            f"- {experiment_id}: {name}"
        )

        details = []

        if experiment.get("cell_type"):
            details.append(
                f"Cell type: "
                f"{experiment['cell_type']}"
            )

        if experiment.get("treatment"):
            details.append(
                f"Treatment: "
                f"{experiment['treatment']}"
            )

        if experiment.get("organism"):
            details.append(
                f"Organism: "
                f"{experiment['organism']}"
            )

        if experiment.get("test"):
            details.append(
                f"Test: "
                f"{experiment['test']}"
            )

        if experiment.get(
            "duration_hours"
        ) is not None:

            details.append(
                f"Duration: "
                f"{experiment['duration_hours']} hours"
            )

        for detail in details:
            lines.append(
                f"  {detail}"
            )

        lines.append("")

    return "\n".join(lines)


# ============================================================
# DOCUMENT ANSWER
# ============================================================

def format_document_answer(result):
    if not isinstance(result, dict):
        return str(result)

    document = result.get(
        "document"
    ) or result

    document_id = document.get(
        "document_id",
        "Unknown",
    )

    title = document.get(
        "title",
        "Untitled",
    )

    file_name = document.get(
        "file_name",
        "",
    )

    document_type = document.get(
        "document_type",
        "",
    )

    description = document.get(
        "description",
        "",
    )

    lines = [
        "Research Document",
        "-----------------",
        f"Document ID: {document_id}",
        f"Title: {title}",
    ]

    if file_name:
        lines.append(
            f"File: {file_name}"
        )

    if document_type:
        lines.append(
            f"Type: {document_type}"
        )

    if description:
        lines.append(
            f"Description: {description}"
        )

    return "\n".join(lines)


# ============================================================
# DILUTION ANSWER
# ============================================================

def format_dilution_answer(result):
    if not isinstance(result, dict):
        return str(result)

    stock_volume = result.get(
        "stock_volume",
        result.get("stock_ml"),
    )

    diluent_volume = result.get(
        "diluent_volume",
        result.get("diluent_ml"),
    )

    final_volume = result.get(
        "final_volume",
        result.get("final_volume_ml"),
    )

    lines = [
        "Dilution Calculation",
        "--------------------",
    ]

    if stock_volume is not None:
        lines.append(
            f"Stock solution: {stock_volume}"
        )

    if diluent_volume is not None:
        lines.append(
            f"Diluent: {diluent_volume}"
        )

    if final_volume is not None:
        lines.append(
            f"Final volume: {final_volume}"
        )

    return "\n".join(lines)



# ============================================================
# MULTI-TOOL PLANNING
# ============================================================

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
    q = question.lower()

    experiment_terms = [
        "experiment",
        "experiments",
        "study",
        "studies",
        "tested",
        "test",
        "performed",
        "conducted",
        "carried out",
        "duration",
        "lasted",
    ]

    # If the question is also asking for research evidence,
    # require stronger experiment-specific context.
    if question_needs_research_evidence(question):
        experiment_context_terms = [
            "which experiment",
            "which experiments",
            "what experiment",
            "what experiments",
            "find experiment",
            "find experiments",
            "show experiment",
            "show experiments",
            "list experiment",
            "list experiments",
            "tested",
            "performed",
            "conducted",
            "duration",
            "lasted",
            "two days",
            "three days",
            "24 hours",
            "48 hours",
            "72 hours",
            "doxorubicin",
            "liver cells",
            "skin cells",
            "bacterial culture",
        ]
        return any(term in q for term in experiment_context_terms)

    return any(term in q for term in experiment_terms)


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


def plan_tools(question):
    """
    Determine whether one or multiple MCP tools are required.
    This is a deterministic planner for the current portfolio version.
    """

    q = question.lower()

    # Dilution is handled as a dedicated workflow.
    if (
        "dilution" in q
        or "stock concentration" in q
        or "final concentration" in q
    ):
        return ["calculate_dilution"]

    tools = []

    if question_needs_experiments(question):
        tools.append("search_experiments")

    if question_needs_research_evidence(question):
        tools.append("search_research_evidence")

    if (
        question_needs_document(question)
        and not question_needs_research_evidence(question)
    ):
        tools.append("get_research_document")

    if not tools:
        tools.append(choose_tool(question))

    return list(dict.fromkeys(tools))



# ============================================================
# CROSS-TOOL RELEVANCE VALIDATION
# ============================================================

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


# ============================================================
# COMBINED MULTI-TOOL ANSWER
# ============================================================

def build_combined_research_answer(question, tool_results):
    """
    Combine experiment/database results with research evidence,
    but only connect them scientifically when topic validation passes.
    """

    lines = []

    experiment_result = tool_results.get(
        "search_experiments"
    )

    evidence_result = tool_results.get(
        "search_research_evidence"
    )

    document_result = tool_results.get(
        "get_research_document"
    )

    validation = None

    if (
        experiment_result is not None
        and evidence_result is not None
    ):
        validation = validate_cross_tool_relevance(
            question,
            experiment_result,
            evidence_result,
        )

    # ------------------------------------------------------------
    # Experiment findings
    # ------------------------------------------------------------

    if experiment_result is not None:
        lines.append("Experiment Findings")
        lines.append("-------------------")
        lines.append(
            format_experiment_answer(
                experiment_result
            )
        )
        lines.append("")

    # ------------------------------------------------------------
    # Research evidence
    # ------------------------------------------------------------

    if evidence_result is not None:
        if (
            validation is not None
            and not validation["relevant"]
        ):
            lines.append(
                "Research Evidence"
            )
            lines.append(
                "-----------------"
            )
            lines.append(
                "The available research document was retrieved, "
                "but its evidence does not directly support the "
                "treatment/topic in the selected experiment."
            )
            lines.append("")
            lines.append(
                "Available document evidence was about:"
            )

            if validation["evidence_topics"]:
                for topic in validation["evidence_topics"]:
                    lines.append(
                        f"- {topic.replace('_', ' ')}"
                    )
            else:
                lines.append(
                    "- No specific treatment/topic was identified."
                )

            lines.append("")
            lines.append(
                "For this question, the mechanism evidence is "
                "therefore not used as evidence for the doxorubicin "
                "experiment."
            )
            lines.append("")
        else:
            lines.append("Research Evidence")
            lines.append("-----------------")
            lines.append(
                generate_research_answer(
                    question,
                    evidence_result,
                )
            )
            lines.append("")

    # ------------------------------------------------------------
    # Document metadata
    # ------------------------------------------------------------

    if document_result is not None:
        lines.append("Research Document")
        lines.append("-----------------")
        lines.append(
            format_document_answer(
                document_result
            )
        )
        lines.append("")

    # ------------------------------------------------------------
    # Cross-tool interpretation
    # ------------------------------------------------------------

    if validation is not None:
        lines.append(
            "Cross-Tool Validation"
        )
        lines.append(
            "---------------------"
        )
        lines.append(
            format_cross_tool_validation(
                validation
            )
        )
        lines.append("")

        experiments = []

        if isinstance(experiment_result, dict):
            experiments = (
                experiment_result.get("experiments")
                or experiment_result.get("results")
                or []
            )

        if (
            validation["relevant"]
            and experiments
        ):
            first = experiments[0]

            experiment_id = first.get(
                "experiment_id",
                "the matching experiment",
            )

            name = first.get(
                "name",
                "the matching experiment",
            )

            treatment = first.get(
                "treatment"
            )

            cell_type = first.get(
                "cell_type"
            )

            duration = first.get(
                "duration_hours"
            )

            details = []

            if treatment:
                details.append(
                    f"treatment={treatment}"
                )

            if cell_type:
                details.append(
                    f"cell type={cell_type}"
                )

            if duration is not None:
                details.append(
                    f"duration={duration} hours"
                )

            if details:
                description = (
                    f"{experiment_id} ({name}) used "
                    + ", ".join(details)
                    + "."
                )
            else:
                description = (
                    f"{experiment_id} ({name}) is the matching experiment."
                )

            lines.append(
                "Combined Interpretation"
            )
            lines.append(
                "-----------------------"
            )
            lines.append(
                description
            )
            lines.append(
                "The experiment record and research evidence "
                "were judged to be topically compatible."
            )
            lines.append("")

        elif not validation["relevant"]:
            lines.append(
                "Combined Interpretation"
            )
            lines.append(
                "-----------------------"
            )
            lines.append(
                "The experiment search and document search produced "
                "different scientific topics. They are intentionally "
                "kept separate rather than combining unrelated evidence."
            )
            lines.append("")

    # ------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------

    lines.append("Provenance")
    lines.append("----------")

    if experiment_result is not None:
        lines.append(
            "- Experiment information: SQLite research database."
        )

    if evidence_result is not None:
        lines.append(
            "- Research evidence: retrieved research-document evidence."
        )

    if document_result is not None:
        lines.append(
            "- Document metadata: research-document record."
        )

    lines.append(
        "Evidence provenance chain: document -> page -> evidence "
        "sentence -> mechanism -> evidence strength -> retrieval/topic scores."
    )
    lines.append(
        "Note: This response organizes evidence returned by "
        "the MCP tools. Cross-tool relevance is checked using "
        "transparent topic matching; it is not independent "
        "scientific validation."
    )

    return "\n".join(lines)


async def execute_tool_plan(session, question, tool_names):
    """Execute all selected MCP tools and retain results by tool name."""
    question = validate_question(question)

    if not tool_names:
        raise AgentInputError("No MCP tool was selected for this question.")

    results = {}

    for tool_name in tool_names:
        results[tool_name] = await execute_tool(
            session,
            tool_name,
            question,
        )

    return results


def print_planned_result(question, tool_names, tool_results):
    """Display the result of a single-tool or multi-tool plan."""

    if len(tool_names) == 1:
        tool_name = tool_names[0]

        print()
        print(
            f"Selected MCP tool: {tool_name}"
        )

        print_result(
            tool_name,
            question,
            tool_results.get(tool_name),
        )
        return

    print()
    print("Selected MCP tools:")

    for tool_name in tool_names:
        print(f"- {tool_name}")

    print()
    print("=" * 60)
    print("Combined Research Answer")
    print("------------------------")

    print(
        build_combined_research_answer(
            question,
            tool_results,
        )
    )

    print("=" * 60)
    print()



# ============================================================
# TOOL EXECUTION
# ============================================================

async def execute_tool(
    session,
    tool_name,
    question,
):

    # --------------------------------------------------------
    # Experiment search
    # --------------------------------------------------------

    if tool_name == "search_experiments":

        filters = parse_experiment_filters(
            question
        )

        if filters:
            query = ""
        else:
            query = extract_experiment_search_query(
                question
            )

        arguments = {
            "query": query,
            "limit": 10,
        }

        arguments.update(
            filters
        )

        print(
            f"Database text query: {query}"
        )

        print(
            f"Structured filters: {filters}"
        )

        logger.info(
            "Calling MCP tool=%s with experiment-search filters=%s",
            tool_name,
            filters,
        )

        result = await session.call_tool(
            tool_name,
            arguments=arguments,
        )

        return parse_mcp_result(
            result
        )

    # --------------------------------------------------------
    # Research evidence
    # --------------------------------------------------------

    if tool_name == "search_research_evidence":

        logger.info(
            "Calling MCP tool=%s document_id=DOC001 top_k=5",
            tool_name,
        )

        result = await session.call_tool(
            tool_name,
            arguments={
                "question": question,
                "document_id": "DOC001",
                "top_k": 5,
            },
        )

        return parse_mcp_result(
            result
        )

    # --------------------------------------------------------
    # Research document
    # --------------------------------------------------------

    if tool_name == "get_research_document":

        result = await session.call_tool(
            tool_name,
            arguments={
                "document_id": "DOC001",
            },
        )

        return parse_mcp_result(
            result
        )

    # --------------------------------------------------------
    # Dilution
    # --------------------------------------------------------

    if tool_name == "calculate_dilution":

        print(
            "Dilution calculation selected."
        )

        print(
            "Please provide values in this format:"
        )

        print(
            "stock concentration, "
            "desired concentration, final volume"
        )

        user_input = input(
            "Values: "
        ).strip()

        parts = [
            part.strip()
            for part in user_input.split(",")
        ]

        if len(parts) != 3:
            return {
                "error": (
                    "Please provide exactly three "
                    "comma-separated values."
                )
            }

        try:
            stock, desired, final_volume = validate_numeric_dilution_values(
                parts[0],
                parts[1],
                parts[2],
            )

        except AgentInputError as e:
            logger.warning("Invalid dilution input: %s", e)
            return {
                "error": str(e)
            }

        result = await session.call_tool(
            tool_name,
            arguments={
                "stock": stock,
                "desired": desired,
                "final_volume": final_volume,
            },
        )

        return parse_mcp_result(
            result
        )

    return {
        "error": (
            f"Unsupported tool: {tool_name}"
        )
    }


# ============================================================
# RESULT DISPLAY
# ============================================================

def print_result(
    tool_name,
    question,
    result,
):

    print()
    print("=" * 60)

    # MCP tools can return structured error dictionaries.
    # Handle them before normal answer formatting so the user
    # never sees an empty answer section for a failed operation.
    if isinstance(result, dict) and result.get("error"):
        print("MCP Tool Error")
        print("--------------")
        print(f"Tool: {tool_name}")
        print(f"Error: {result['error']}")
        print("Please correct the input and try again.")
        print("=" * 60)
        print()
        return

    if tool_name == "search_research_evidence":

        print(
            "Research Answer"
        )

        print(
            "----------------"
        )

        answer = generate_research_answer(
            question,
            result,
        )

        print(answer)

    elif tool_name == "search_experiments":

        print(
            "Experiment Search Answer"
        )

        print(
            "------------------------"
        )

        answer = format_experiment_answer(
            result
        )

        print(answer)

    elif tool_name == "get_research_document":

        print(
            "Document Answer"
        )

        print(
            "----------------"
        )

        answer = format_document_answer(
            result
        )

        print(answer)

    elif tool_name == "calculate_dilution":

        print(
            "Dilution Answer"
        )

        print(
            "----------------"
        )

        answer = format_dilution_answer(
            result
        )

        print(answer)

    else:

        print(
            json.dumps(
                result,
                indent=2,
                default=str,
            )
        )

    print("=" * 60)
    print()


# ============================================================
# SHOW TOOLS
# ============================================================

async def show_tools(session):

    tools_result = await session.list_tools()

    print()

    print(
        f"Connected to MCP server. "
        f"Discovered {len(tools_result.tools)} tools."
    )

    print()

    for tool in tools_result.tools:
        print(
            f"- {tool.name}"
        )

    print()


# ============================================================
# MAIN
# ============================================================

async def main():

    print("=" * 60)
    print("Biomedical Research MCP Agent")
    print("=" * 60)

    async with stdio_client(
        server_params
    ) as (read_stream, write_stream):

        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            await session.initialize()

            await show_tools(
                session
            )

            print(
                "Type a research question."
            )

            print(
                "The agent can use one or multiple MCP tools "
                "for a single question."
            )

            print(
                "Type 'tools' to show MCP tools."
            )

            print(
                "Type 'quit' to exit."
            )

            print()

            while True:

                question = input(
                    "You: "
                ).strip()

                if not question:
                    continue

                if question.lower() in {
                    "quit",
                    "exit",
                }:
                    print(
                        "Goodbye."
                    )
                    break

                if question.lower() == "tools":
                    await show_tools(
                        session
                    )
                    continue

                tool_names = plan_tools(
                    question
                )

                try:
                    question = validate_question(question)

                    logger.info(
                        "Processing question with tools=%s",
                        tool_names,
                    )

                    tool_results = await execute_tool_plan(
                        session,
                        question,
                        tool_names,
                    )

                    print_planned_result(
                        question,
                        tool_names,
                        tool_results,
                    )

                except AgentInputError as e:
                    logger.warning("Invalid user input: %s", e)
                    print()
                    print(f"Input error: {e}")
                    print()

                except Exception as e:
                    logger.exception(
                        "Unexpected error while executing MCP tool plan"
                    )
                    print()
                    print(
                        "An unexpected error occurred while processing "
                        "the request."
                    )
                    print(
                        "Check the console log for technical details."
                    )
                    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
