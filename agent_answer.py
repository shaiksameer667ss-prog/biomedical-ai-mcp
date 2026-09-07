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


def get_result_page(item):
    if not isinstance(item, dict):
        return None

    return (
        item.get("page_number")
        or item.get("page")
        or item.get("page_num")
    )


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
    """Build a concise, traceable research answer from retrieved evidence.

    Each mechanism is presented once with one strongest supporting sentence.
    Detailed retrieval/provenance scores remain available in the underlying
    result and are summarized at the end instead of being repeated for every
    sentence.
    """
    if not isinstance(result, dict):
        return "The research retrieval tool returned an unexpected result."

    raw_results = (
        result.get("results")
        or result.get("evidence")
        or result.get("matches")
        or []
    )

    if not raw_results:
        return "No sufficiently relevant research evidence was retrieved."

    pages = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue

        page_number = get_result_page(item)
        content = (
            item.get("content")
            or item.get("text")
            or item.get("snippet")
            or ""
        )

        if content:
            pages.append({
                "page_number": page_number,
                "content": content,
            })

    if not pages:
        return "No usable research evidence was returned."

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

        if not evidence:
            continue

        # Choose one strongest sentence.  Evidence strength is evaluated
        # after retrieval so the presentation can prefer DIRECT evidence.
        ranked = []
        for item in evidence:
            page_text = next(
                (
                    p["content"]
                    for p in pages
                    if p["page_number"] == item["page_number"]
                ),
                "",
            )

            provenance = classify_evidence_strength(
                sentence=item["sentence"],
                page_text=page_text,
                mechanism=mechanism,
                question=question,
            )

            strength_rank = {
                "DIRECT": 4,
                "SUPPORTING": 3,
                "PAGE CONTEXT": 2,
                "WEAK/INDIRECT": 1,
            }.get(provenance["level"], 0)

            ranked.append((
                strength_rank,
                provenance["score"],
                provenance["topic_score"],
                item,
                provenance,
            ))

        ranked.sort(key=lambda x: x[:3], reverse=True)
        _, _, _, best_item, provenance = ranked[0]

        mechanism_results.append({
            "mechanism": mechanism,
            "evidence": best_item,
            "provenance": provenance,
        })

    lines = []
    lines.append(
        "The retrieved evidence indicates that copper nanoparticle "
        "toxicity involves several cellular mechanisms."
    )
    lines.append("")
    lines.append("Evidence-based summary")
    lines.append("----------------------")

    summaries = {
        "Oxidative stress":
            "Copper nanoparticle exposure can increase reactive oxygen "
            "species (ROS) and reactive nitrogen species (RNS), contributing "
            "to oxidative stress and cellular dysfunction.",
        "Mitochondrial damage":
            "Copper nanoparticle or copper oxide exposure can impair "
            "mitochondrial function and contribute to ROS generation.",
        "Lipid peroxidation":
            "Lipid peroxidation can affect mitochondrial membranes, disrupting "
            "electron transport and reducing mitochondrial membrane potential.",
        "DNA damage":
            "DNA damage or genotoxic effects can contribute to cellular injury "
            "following nanoparticle exposure.",
        "Apoptosis":
            "Nano-copper exposure is associated with apoptotic signaling "
            "involving factors such as cytochrome c, Apaf-1, and caspases.",
        "Cell membrane damage":
            "Nanoparticle-related membrane disruption can alter membrane "
            "integrity or permeability and contribute to cellular injury.",
        "Cell death / reduced viability":
            "Copper nanoparticle exposure can produce cytotoxic effects, "
            "including reduced cell viability and cell death.",
    }

    if not mechanism_results:
        lines.append(
            "No mechanism-specific evidence met the topic-relevance and "
            "evidence-quality thresholds."
        )
    else:
        for index, data in enumerate(mechanism_results, start=1):
            mechanism = data["mechanism"]
            item = data["evidence"]
            provenance = data["provenance"]
            page_number = item.get("page_number")

            lines.append(f"{index}. {mechanism}")
            lines.append(f"   {summaries[mechanism]}")
            lines.append("")
            if page_number is not None:
                lines.append(
                    f"   Evidence (Page {page_number}): {item['sentence']}"
                )
            else:
                lines.append(
                    f"   Evidence: {item['sentence']}"
                )
            lines.append(
                f"   Evidence strength: {provenance['level']}"
            )
            lines.append("")

    strength_counts = {}
    source_pages = []

    for data in mechanism_results:
        level = data["provenance"]["level"]
        strength_counts[level] = strength_counts.get(level, 0) + 1

        page_number = data["evidence"].get("page_number")
        if page_number is not None and page_number not in source_pages:
            source_pages.append(page_number)

    lines.append("Evidence quality")
    lines.append("----------------")
    for level in ("DIRECT", "SUPPORTING", "PAGE CONTEXT", "WEAK/INDIRECT"):
        if strength_counts.get(level):
            lines.append(f"- {level}: {strength_counts[level]}")

    lines.append("")
    lines.append("Sources")
    lines.append("-------")
    if document_id:
        if document_title:
            lines.append(f"- {document_id}: {document_title}")
        else:
            lines.append(f"- {document_id}")
    if source_pages:
        lines.append(
            "- Supporting pages: "
            + ", ".join(f"Page {page}" for page in source_pages)
        )

    lines.append("")
    lines.append("Interpretation limits")
    lines.append("--------------------")
    lines.append(
        "The evidence-strength labels are rule-based annotations. They do "
        "not establish causality, dose-response relationships, or "
        "generalizability. This answer is based only on retrieved document "
        "evidence; check the original paper before using the information "
        "for research decisions."
    )

    # Keep a compact machine-readable provenance summary in the returned
    # text without repeating every sentence and score multiple times.
    if mechanism_results:
        lines.append("")
        lines.append(
            "Traceability: each mechanism is linked to its strongest "
            "retrieved evidence sentence and source page."
        )

    return "\n".join(lines)

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


def build_combined_research_answer(question, tool_results):
    """Build a concise, traceable answer for multi-tool research questions.

    The formatter keeps each MCP result distinct, then adds a rule-based
    interpretation explaining how the experiment context and retrieved
    document evidence relate. It does not claim that document evidence
    proves findings in a specific database experiment unless the available
    context supports that conclusion.
    """
    from agent_validator import (
        format_cross_tool_alignment,
        format_cross_tool_validation,
        validate_cross_tool_alignment,
        validate_cross_tool_relevance,
    )

    lines = []
    experiment_result = tool_results.get("search_experiments")
    evidence_result = tool_results.get("search_research_evidence")
    document_result = tool_results.get("get_research_document")

    validation = None
    alignment = None
    if experiment_result is not None and evidence_result is not None:
        validation = validate_cross_tool_relevance(
            question, experiment_result, evidence_result
        )
        alignment = validate_cross_tool_alignment(
            question, experiment_result, evidence_result
        )

    # Extract the first matching experiment for the concise interpretation.
    experiments = []
    if isinstance(experiment_result, dict):
        experiments = (
            experiment_result.get("experiments")
            or experiment_result.get("results")
            or []
        )

    # ------------------------------------------------------------
    # Research question
    # ------------------------------------------------------------
    lines.append("Research Question")
    lines.append("-----------------")
    lines.append(question.strip())
    lines.append("")

    # ------------------------------------------------------------
    # Relevant experiments
    # ------------------------------------------------------------
    if experiment_result is not None:
        lines.append("Relevant Experiments")
        lines.append("--------------------")
        lines.append(format_experiment_answer(experiment_result))
        lines.append("")

    # ------------------------------------------------------------
    # Mechanistic evidence
    # ------------------------------------------------------------
    if evidence_result is not None:
        lines.append("Mechanistic Evidence")
        lines.append("--------------------")
        if validation is not None and not validation["relevant"]:
            lines.append(
                "The retrieved document evidence does not directly support "
                "the treatment/topic in the selected experiment, so the "
                "evidence is kept separate."
            )
            if validation.get("evidence_topics"):
                lines.append("Available document topics:")
                for topic in validation["evidence_topics"]:
                    lines.append(f"- {topic.replace('_', ' ')}")
        else:
            lines.append(generate_research_answer(question, evidence_result))
        lines.append("")

    # ------------------------------------------------------------
    # Research document metadata
    # ------------------------------------------------------------
    if document_result is not None:
        lines.append("Research Document")
        lines.append("-----------------")
        lines.append(format_document_answer(document_result))
        lines.append("")

    # ------------------------------------------------------------
    # Cross-tool interpretation
    # ------------------------------------------------------------
    if validation is not None:
        lines.append("Cross-Tool Interpretation")
        lines.append("--------------------------")

        if experiments and validation["relevant"]:
            first = experiments[0]
            experiment_id = first.get("experiment_id", "the matching experiment")
            name = first.get("name", "the matching experiment")
            treatment = first.get("treatment")
            cell_type = first.get("cell_type")
            duration = first.get("duration_hours")

            details = []
            if treatment:
                details.append(f"treatment={treatment}")
            if cell_type:
                details.append(f"cell type={cell_type}")
            if duration is not None:
                details.append(f"duration={duration} hours")

            if details:
                lines.append(
                    f"{experiment_id} ({name}) used "
                    + ", ".join(details)
                    + "."
                )

            if alignment is not None:
                lines.append(
                    f"Overall cross-tool alignment: {alignment['overall']}."
                )
                if alignment["overall"] == "MATCHED":
                    lines.append(
                        "The checked dimensions are aligned, but this does "
                        "not constitute independent scientific validation."
                    )
                elif alignment["overall"] == "PARTIALLY ALIGNED":
                    lines.append(
                        "The document supports the requested mechanism/topic, "
                        "but its cell models or other experimental details do "
                        "not establish that it is the same experimental context."
                    )
                else:
                    lines.append(
                        "The sources should not be treated as establishing "
                        "the same experimental context."
                    )

                lines.append("")
                lines.append(format_cross_tool_alignment(alignment))
            else:
                lines.append(
                    "The experiment record and research evidence are "
                    "topically compatible."
                )
        elif validation is not None and not validation["relevant"]:
            lines.append(
                "The experiment record and retrieved document evidence "
                "cover different scientific contexts. They are intentionally "
                "not combined as if they describe the same experiment."
            )
        else:
            lines.append(
                "The available results could not establish a shared "
                "experimental context."
            )

        lines.append("")
        lines.append("Cross-Tool Validation")
        lines.append("---------------------")
        lines.append(format_cross_tool_validation(validation))
        lines.append("")

    # ------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------
    lines.append("Evidence & Provenance")
    lines.append("---------------------")
    if experiment_result is not None:
        lines.append("- Experiment information: SQLite research database.")
    if evidence_result is not None:
        lines.append("- Mechanistic evidence: retrieved research-document evidence.")
    if document_result is not None:
        lines.append("- Document metadata: research-document record.")
    lines.append(
        "- Evidence chain: document -> page -> evidence sentence -> mechanism "
        "-> evidence strength -> retrieval/topic scores."
    )
    lines.append(
        "- Cross-tool alignment is a rule-based consistency check, not "
        "independent scientific validation."
    )

    return "\n".join(lines)

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


