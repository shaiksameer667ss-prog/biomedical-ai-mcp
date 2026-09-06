import re
import sqlite3
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "biomedical.db"


# ============================================================
# SCIENTIFIC CONCEPT MAP
# ============================================================

CONCEPT_MAP = {
    "oxidative stress": [
        "oxidative stress",
        "oxidative damage",
        "oxidative injury",
    ],

    "reactive oxygen species": [
        "reactive oxygen species",
        "reactive oxygen",
        "ROS",
    ],

    "DNA damage": [
        "DNA damage",
        "DNA damage response",
        "genotoxicity",
        "genotoxic",
    ],

    "apoptosis": [
        "apoptosis",
        "apoptotic",
        "programmed cell death",
    ],

    "cell death": [
        "cell death",
        "cell viability",
        "cell survival",
        "cytotoxicity",
    ],

    "cytotoxicity": [
        "cytotoxicity",
        "cytotoxic",
        "toxicity",
        "toxic effects",
    ],

    "mitochondrial damage": [
        "mitochondrial damage",
        "mitochondrial dysfunction",
        "mitochondria",
        "mitochondrial membrane",
        "mitochondrial membrane potential",
    ],

    "membrane damage": [
        "membrane damage",
        "membrane disruption",
        "cell membrane",
        "membrane integrity",
    ],

    "lipid peroxidation": [
        "lipid peroxidation",
        "lipid oxidation",
        "lipid oxidative damage",
    ],

    "cell signaling": [
        "cell signaling",
        "signaling pathway",
        "signal transduction",
    ],

    "copper ions": [
        "copper ions",
        "Cu ions",
        "Cu2+",
        "ionic copper",
    ],
}


# ============================================================
# MECHANISM QUERY EXPANSION
# ============================================================

MECHANISM_EXPANSION = [
    "oxidative stress",
    "reactive oxygen species",
    "ROS",
    "free radicals",
    "mitochondrial damage",
    "mitochondrial dysfunction",
    "mitochondrial membrane",
    "mitochondrial membrane potential",
    "membrane damage",
    "membrane disruption",
    "lipid peroxidation",
    "DNA damage",
    "genotoxicity",
    "apoptosis",
    "caspase",
    "cytochrome c",
    "cell death",
    "cell viability",
    "cell signaling",
]


# ============================================================
# QUESTION INTENTS
# ============================================================

QUESTION_INTENTS = {
    "mechanism": [
        "mechanism",
        "mechanisms",
        "how does",
        "how do",
        "pathway",
        "pathways",
        "process",
        "processes",
        "cause",
        "causes",
        "responsible",
        "underlying",
    ],

    "toxicity": [
        "toxicity",
        "toxic",
        "cytotoxicity",
        "cytotoxic",
        "cell damage",
        "cell death",
    ],

    "effect": [
        "effect",
        "effects",
        "impact",
        "response",
        "responses",
        "result",
        "results",
    ],

    "dose": [
        "dose",
        "dosage",
        "concentration",
        "concentrations",
        "dose-dependent",
    ],
}


# ============================================================
# BASIC TEXT PROCESSING
# ============================================================

def clean_text(text):
    """
    Normalize whitespace and return clean text.
    """

    if not text:
        return ""

    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def tokenize(text):
    """
    Convert text into lowercase word tokens.
    """

    text = text.lower()

    return re.findall(
        r"\b[a-zA-Z][a-zA-Z0-9\-]*\b",
        text
    )


# ============================================================
# QUERY ANALYSIS
# ============================================================

def extract_keywords(question):
    """
    Extract useful keywords from the research question.

    Very common stop words are removed.
    """

    stop_words = {
        "what",
        "are",
        "is",
        "the",
        "a",
        "an",
        "of",
        "in",
        "on",
        "to",
        "for",
        "and",
        "or",
        "with",
        "associated",
        "related",
        "does",
        "do",
        "how",
        "can",
        "be",
        "by",
        "from",
        "this",
        "that",
    }

    words = tokenize(question)

    keywords = []

    for word in words:

        if word not in stop_words and len(word) > 2:
            keywords.append(word)

    return keywords


def detect_intents(question):
    """
    Detect the scientific intent of the question.
    """

    question_lower = question.lower()

    detected = []

    for intent, phrases in QUESTION_INTENTS.items():

        for phrase in phrases:

            if phrase.lower() in question_lower:

                detected.append(intent)

                break

    return detected


def detect_concepts(question):
    """
    Detect explicit scientific concepts in the question.
    """

    question_lower = question.lower()

    detected = []

    for concept, terms in CONCEPT_MAP.items():

        for term in terms:

            if term.lower() in question_lower:

                detected.append(concept)

                break

    return detected


# ============================================================
# REFERENCE PAGE FILTER
# ============================================================

def is_reference_page(text):
    """
    Identify pages that mainly contain references/bibliography.

    These pages should not normally be returned as scientific
    evidence.
    """

    text_lower = text.lower()

    # Strong indicators

    if text_lower.startswith("references"):
        return True

    if text_lower.startswith("bibliography"):
        return True

    if (
        "conflict of interest" in text_lower
        and "references" in text_lower
    ):
        return True

    # Citation-like patterns

    citation_patterns = re.findall(
        r"\([A-Z][A-Za-z\-]+(?:\s+et al\.)?,\s*\d{4}\)",
        text,
    )

    doi_count = len(
        re.findall(
            r"doi\s*:",
            text_lower,
        )
    )

    journal_like_count = len(
        re.findall(
            r"\b(journal|press|vol\.|volume|issue|pp\.)\b",
            text_lower,
        )
    )

    et_al_count = text_lower.count("et al.")

    # Strong reference-page pattern

    if len(citation_patterns) >= 8 and doi_count >= 1:
        return True

    if (
        et_al_count >= 5
        and journal_like_count >= 3
        and len(text) > 2000
    ):
        return True

    if "references" in text_lower and doi_count >= 1:
        return True

    return False


# ============================================================
# LOAD RESEARCH PAGES
# ============================================================

def load_pages(document_id):
    """
    Load extracted research-document pages from SQLite.
    """

    if not DB_PATH.exists():

        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                document_id,
                page_number,
                page_text
            FROM research_document_pages
            WHERE document_id = ?
            ORDER BY page_number
            """,
            (document_id,),
        )

        rows = cursor.fetchall()

        pages = []

        for row in rows:

            text = clean_text(
                row["page_text"]
            )

            if not text:
                continue

            pages.append(
                {
                    "document_id": row["document_id"],
                    "page_number": row["page_number"],
                    "text": text,
                }
            )

        return pages

    finally:

        connection.close()


# ============================================================
# QUERY EXPANSION
# ============================================================

def expand_query(question, intents, concepts):
    """
    Expand the original question with scientific terminology.

    Mechanism questions receive additional mechanism terms.
    """

    terms = []

    # Original keywords

    terms.extend(
        extract_keywords(question)
    )

    # Detected concepts

    for concept in concepts:

        terms.append(concept)

        for term in CONCEPT_MAP.get(
            concept,
            []
        ):

            terms.append(term)

    # Mechanism expansion

    if "mechanism" in intents:

        terms.extend(
            MECHANISM_EXPANSION
        )

    # Remove duplicates while preserving order

    unique_terms = []

    seen = set()

    for term in terms:

        normalized = term.lower()

        if normalized not in seen:

            seen.add(normalized)

            unique_terms.append(term)

    return unique_terms


# ============================================================
# MECHANISTIC EVIDENCE
# ============================================================

def get_mechanistic_terms():
    """
    Terms that provide strong evidence for a biological mechanism.
    """

    return [
        "reactive oxygen species",
        "ROS",
        "oxidative stress",
        "oxidative damage",
        "lipid peroxidation",
        "mitochondrial damage",
        "mitochondrial dysfunction",
        "mitochondrial membrane potential",
        "cytochrome c",
        "caspase",
        "caspase-3",
        "caspase-8",
        "caspase-9",
        "apoptosis",
        "DNA damage",
        "genotoxicity",
        "membrane damage",
        "membrane potential",
        "cell death",
        "cell viability",
    ]


# ============================================================
# PAGE SCORING
# ============================================================

def score_page(
    page_text,
    question,
    expanded_terms,
    intents,
):
    """
    Calculate a relevance score for one research page.

    Mechanism-specific scientific evidence receives substantially
    more weight than generic keyword repetition.
    """

    text_lower = page_text.lower()

    score = 0.0

    # --------------------------------------------------------
    # Original question keyword matching
    # --------------------------------------------------------

    question_keywords = extract_keywords(
        question
    )

    for keyword in question_keywords:

        count = text_lower.count(
            keyword.lower()
        )

        if count > 0:

            # Prevent repeated generic words from dominating

            score += min(count, 5) * 4

    # --------------------------------------------------------
    # Expanded scientific term matching
    # --------------------------------------------------------

    for term in expanded_terms:

        term_lower = term.lower()

        count = text_lower.count(
            term_lower
        )

        if count == 0:
            continue

        # Scientific phrases are more informative

        if len(term_lower.split()) >= 2:

            score += min(count, 5) * 6

        else:

            score += min(count, 5) * 2

    # --------------------------------------------------------
    # Strong mechanism evidence
    # --------------------------------------------------------

    mechanism_matches = 0

    if "mechanism" in intents:

        mechanism_weights = {

            "reactive oxygen species": 60,

            "ros": 45,

            "oxidative stress": 60,

            "oxidative damage": 50,

            "lipid peroxidation": 60,

            "mitochondrial damage": 70,

            "mitochondrial dysfunction": 70,

            "mitochondrial membrane potential": 70,

            "cytochrome c": 70,

            "caspase": 60,

            "caspase-3": 65,

            "caspase-8": 65,

            "caspase-9": 65,

            "apoptosis": 70,

            "dna damage": 60,

            "genotoxicity": 55,

            "membrane damage": 50,

            "membrane potential": 45,

            "cell death": 45,

            "cell viability": 30,
        }

        for term, weight in mechanism_weights.items():

            if term.lower() in text_lower:

                mechanism_matches += 1

                score += weight

    # --------------------------------------------------------
    # Multiple-mechanism bonus
    # --------------------------------------------------------

    if "mechanism" in intents:

        if mechanism_matches >= 3:
            score += 75

        if mechanism_matches >= 5:
            score += 100

        if mechanism_matches >= 8:
            score += 125

    # --------------------------------------------------------
    # Mechanism relationship bonus
    # --------------------------------------------------------

    if "mechanism" in intents:

        mechanism_pairs = [

            (
                "oxidative stress",
                "reactive oxygen species",
            ),

            (
                "reactive oxygen species",
                "lipid peroxidation",
            ),

            (
                "oxidative stress",
                "mitochondrial",
            ),

            (
                "mitochondrial",
                "apoptosis",
            ),

            (
                "cytochrome c",
                "caspase",
            ),

            (
                "caspase",
                "apoptosis",
            ),

            (
                "DNA damage",
                "apoptosis",
            ),
        ]

        for first, second in mechanism_pairs:

            if (
                first.lower() in text_lower
                and second.lower() in text_lower
            ):

                score += 50

    # --------------------------------------------------------
    # Biomedical relevance
    # --------------------------------------------------------

    relevance_terms = [
        "copper nanoparticle",
        "copper nanoparticles",
        "nano-copper",
        "copper oxide",
    ]

    for term in relevance_terms:

        if term in text_lower:

            score += 15

    # --------------------------------------------------------
    # Toxicity context
    # --------------------------------------------------------

    toxicity_terms = [
        "toxicity",
        "cytotoxicity",
        "toxic effects",
        "cell death",
        "cell viability",
    ]

    for term in toxicity_terms:

        if term in text_lower:

            score += 8

    # --------------------------------------------------------
    # Page quality
    # --------------------------------------------------------

    # Small bonus for substantive pages.
    # Page length should not dominate scientific relevance.

    if len(page_text) > 3000:

        score += 10

    if len(page_text) > 6000:

        score += 10

    return score, mechanism_matches


# ============================================================
# SNIPPET CREATION
# ============================================================

def create_snippet(
    text,
    question,
    max_length=1400,
):
    """
    Create a useful evidence snippet around relevant terms.

    The snippet is expanded to 1400 characters and attempts to
    end at a sentence boundary so scientific evidence is not cut
    in the middle of a sentence.
    """

    question_keywords = extract_keywords(question)

    text_lower = text.lower()

    positions = []

    # --------------------------------------------------------
    # Search question keywords
    # --------------------------------------------------------

    for keyword in question_keywords:

        position = text_lower.find(
            keyword.lower()
        )

        if position >= 0:

            positions.append(position)

    # --------------------------------------------------------
    # Search mechanism terms
    # --------------------------------------------------------

    for term in get_mechanistic_terms():

        position = text_lower.find(
            term.lower()
        )

        if position >= 0:

            positions.append(position)

    # --------------------------------------------------------
    # If no relevant position found
    # --------------------------------------------------------

    if not positions:

        snippet = text[:max_length]

        if len(text) > max_length:

            # Prefer ending at a sentence boundary

            sentence_end = max(
                snippet.rfind(". "),
                snippet.rfind("."),
                snippet.rfind(";"),
            )

            if sentence_end > max_length * 0.60:

                snippet = snippet[
                    :sentence_end + 1
                ]

            else:

                snippet += "..."

        return snippet

    # --------------------------------------------------------
    # Build snippet around first relevant position
    # --------------------------------------------------------

    start_position = max(
        0,
        min(positions) - 350,
    )

    snippet_end = min(
        len(text),
        start_position + max_length,
    )

    snippet = text[
        start_position:
        snippet_end
    ]

    # --------------------------------------------------------
    # Clean beginning
    # --------------------------------------------------------

    if start_position > 0:

        snippet = "..." + snippet

    # --------------------------------------------------------
    # Avoid cutting scientific sentences
    # --------------------------------------------------------

    if snippet_end < len(text):

        # Look for the last complete sentence inside the snippet.

        sentence_end = max(
            snippet.rfind(". "),
            snippet.rfind("."),
            snippet.rfind(";"),
        )

        # Only shorten if we found a reasonably long section.

        if sentence_end > len(snippet) * 0.60:

            snippet = snippet[
                :sentence_end + 1
            ]

        else:

            snippet += "..."

    return snippet


# ============================================================
# MAIN RETRIEVAL FUNCTION
# ============================================================

def retrieve_evidence(
    question,
    document_id="DOC001",
    top_k=5,
):
    """
    Retrieve the most relevant scientific evidence pages.

    Returns structured data that can be exposed through MCP.
    """

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not question or not question.strip():

        raise ValueError(
            "Question cannot be empty."
        )

    if (
        not document_id
        or not document_id.strip()
    ):

        raise ValueError(
            "Document ID cannot be empty."
        )

    if not isinstance(top_k, int):

        raise ValueError(
            "top_k must be an integer."
        )

    if top_k < 1 or top_k > 20:

        raise ValueError(
            "top_k must be between 1 and 20."
        )

    # --------------------------------------------------------
    # Load pages
    # --------------------------------------------------------

    pages = load_pages(
        document_id
    )

    if not pages:

        raise ValueError(
            f"No extracted pages found for document {document_id}."
        )

    total_pages = len(pages)

    # --------------------------------------------------------
    # Remove reference pages
    # --------------------------------------------------------

    reference_pages = []

    scientific_pages = []

    for page in pages:

        if is_reference_page(
            page["text"]
        ):

            reference_pages.append(
                page["page_number"]
            )

        else:

            scientific_pages.append(
                page
            )

    # --------------------------------------------------------
    # Analyze question
    # --------------------------------------------------------

    keywords = extract_keywords(
        question
    )

    intents = detect_intents(
        question
    )

    concepts = detect_concepts(
        question
    )

    expanded_terms = expand_query(
        question,
        intents,
        concepts,
    )

    # --------------------------------------------------------
    # Score pages
    # --------------------------------------------------------

    ranked_results = []

    for page in scientific_pages:

        score, mechanism_matches = score_page(
            page["text"],
            question,
            expanded_terms,
            intents,
        )

        # Ignore completely irrelevant pages

        if score <= 0:
            continue

        snippet = create_snippet(
            page["text"],
            question,
        )

        ranked_results.append(
            {
                "page_number": page["page_number"],
                "score": round(score, 2),
                "mechanism_matches": mechanism_matches,
                "snippet": snippet,
            }
        )

    # --------------------------------------------------------
    # Rank
    # --------------------------------------------------------

    ranked_results.sort(
        key=lambda result: (
            result["score"],
            result["mechanism_matches"],
        ),
        reverse=True,
    )

    results = ranked_results[
        :top_k
    ]

    # --------------------------------------------------------
    # Claude-ready context
    # --------------------------------------------------------

    context_parts = []

    for result in results:

        context_parts.append(
            f"""
SOURCE PAGE {result["page_number"]}

Relevance score: {result["score"]}

Mechanism evidence matches:
{result["mechanism_matches"]}

Evidence:
{result["snippet"]}
""".strip()
        )

    claude_context = "\n\n".join(
        context_parts
    )

    # --------------------------------------------------------
    # Final structured result
    # --------------------------------------------------------

    return {
        "question": question,

        "document_id": document_id,

        "pages_loaded": total_pages,

        "reference_pages_removed": reference_pages,

        "pages_available_for_retrieval": len(
            scientific_pages
        ),

        "keywords": keywords,

        "intents": intents,

        "scientific_concepts": concepts,

        "expanded_terms": expanded_terms,

        "results": results,

        "result_count": len(results),

        "claude_context": claude_context,
    }


# ============================================================
# SIMPLE COMMAND-LINE TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)

    print(
        "BIOMEDICAL RESEARCH RETRIEVAL ENGINE"
    )

    print("=" * 70)

    question = (
        "What mechanisms are associated "
        "with copper nanoparticle toxicity?"
    )

    print("\nQuestion:")

    print(question)

    try:

        output = retrieve_evidence(
            question=question,
            document_id="DOC001",
            top_k=5,
        )

        print("\nDatabase:")

        print(DB_PATH)

        print("\nPages loaded:")

        print(
            output["pages_loaded"]
        )

        print("\nReference pages removed:")

        print(
            output["reference_pages_removed"]
        )

        print("\nPages available:")

        print(
            output[
                "pages_available_for_retrieval"
            ]
        )

        print("\nKeywords:")

        print(
            output["keywords"]
        )

        print("\nIntents:")

        print(
            output["intents"]
        )

        print("\nScientific concepts:")

        print(
            output[
                "scientific_concepts"
            ]
        )

        print("\nExpanded terms:")

        for term in output[
            "expanded_terms"
        ]:

            print(
                f"  - {term}"
            )

        print(
            "\n"
            + "=" * 70
        )

        print(
            "TOP EVIDENCE"
        )

        print(
            "=" * 70
        )

        for index, result in enumerate(
            output["results"],
            start=1,
        ):

            print(
                f"\nResult {index}"
            )

            print(
                f"Page: {result['page_number']}"
            )

            print(
                f"Score: {result['score']}"
            )

            print(
                "Mechanism matches: "
                f"{result['mechanism_matches']}"
            )

            print(
                "\nEvidence:"
            )

            print(
                result["snippet"]
            )

        print(
            "\n"
            + "=" * 70
        )

        print(
            "CLAUDE-READY CONTEXT"
        )

        print(
            "=" * 70
        )

        print(
            output["claude_context"]
        )

        print(
            "\n"
            + "=" * 70
        )

        print(
            "RETRIEVAL TEST COMPLETE"
        )

        print(
            "=" * 70
        )

    except Exception as error:

        print("\nERROR:")

        print(error)