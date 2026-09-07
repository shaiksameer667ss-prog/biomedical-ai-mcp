import asyncio
import atexit
import json
import logging
import re
import sqlite3
from pathlib import Path

from mcp.server import MCPServer

from config import (
    DATABASE_PATH,
    DOCUMENTS_DIR,
    configure_logging,
)


# Configure logging once at the application entry point.
configure_logging()

logger = logging.getLogger("biomedical_research_mcp")


def safe_internal_error(public_message: str, exc: Exception):
    """Log internal exception details without exposing them to MCP clients."""

    # This helper may be called outside an active ``except`` block by tests
    # or future code. Use ``logger.error`` rather than ``logger.exception``
    # so we do not emit the misleading ``NoneType: None`` traceback.
    logger.error(
        "%s | %s: %s",
        public_message,
        type(exc).__name__,
        exc,
    )

    return {
        "error": public_message
    }


# ============================================================
# PATHS
# ============================================================

# Compatibility alias retained for existing tests and code that
# needs the project root. The actual database path is still controlled
# centrally by config.py.
BASE_DIR = DATABASE_PATH.parent

DB_PATH = DATABASE_PATH

DOCUMENTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def secure_document_path(file_name):
    """
    Resolve a document filename and ensure it stays inside
    the configured documents directory.

    This prevents path traversal and absolute-path escapes.
    """
    try:
        documents_root = DOCUMENTS_DIR.resolve()
        pdf_path = (DOCUMENTS_DIR / file_name).resolve()

        if documents_root not in pdf_path.parents:
            raise ValueError(
                "Invalid file path. The document must be "
                "inside the documents directory."
            )

        return pdf_path

    except (OSError, RuntimeError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise

        raise ValueError("Invalid document file path.") from exc


# ============================================================
# DATABASE
# ============================================================

db = sqlite3.connect(
    DB_PATH,
    check_same_thread=False,
)

db.row_factory = sqlite3.Row


def close_database():
    """Close the shared SQLite connection during normal process shutdown."""

    try:
        db.close()
    except sqlite3.Error:
        # Shutdown cleanup must never crash the process.
        pass


atexit.register(close_database)


# ============================================================
# MCP SERVER
# ============================================================

server = MCPServer(
    name="Biomedical Research MCP Server"
)


# ============================================================
# SECURITY VALIDATION HELPERS
# ============================================================

DOCUMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# Resource and input safety limits
MAX_SEARCH_QUERY_LENGTH = 500
MAX_FILTER_LENGTH = 200
MAX_EXPERIMENT_FIELD_LENGTH = 200
MAX_DOCUMENT_TITLE_LENGTH = 300
MAX_DOCUMENT_DESCRIPTION_LENGTH = 2000
MAX_DOCUMENT_FILE_SIZE_BYTES = 25 * 1024 * 1024
MAX_EXTRACTED_TEXT_LENGTH = 5_000_000
MAX_PAGE_TEXT_LENGTH = 1_000_000
MAX_SEARCH_LIMIT = 100
MAX_EVIDENCE_TOP_K = 20
MAX_DURATION_HOURS = 24 * 365 * 100


ALLOWED_TABLES = {
    "experiments",
}


def validate_text_field(value: str, field_name: str, max_length: int):
    """Validate a required text field and enforce a maximum length."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text.")
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty.")
    if len(value) > max_length:
        raise ValueError(
            f"{field_name} is too long. Maximum allowed length is {max_length} characters."
        )
    return value


def validate_optional_text(value: str, field_name: str, max_length: int):
    """Validate an optional text field and enforce a maximum length."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text.")
    value = value.strip()
    if len(value) > max_length:
        raise ValueError(
            f"{field_name} is too long. Maximum allowed length is {max_length} characters."
        )
    return value


def validate_positive_int(value, field_name: str, maximum: int):
    """Validate a positive integer within a configured upper bound."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")
    if value > maximum:
        raise ValueError(
            f"{field_name} exceeds the maximum allowed value of {maximum}."
        )
    return value


def validate_document_id(document_id: str):
    """Validate a document identifier used by database queries."""

    if not isinstance(document_id, str):
        raise ValueError("Document ID must be text.")

    document_id = document_id.strip()

    if not document_id:
        raise ValueError("Document ID cannot be empty.")

    if not DOCUMENT_ID_PATTERN.fullmatch(document_id):
        raise ValueError(
            "Invalid document ID. Use letters, numbers, hyphens, "
            "and underscores only (maximum 64 characters)."
        )

    return document_id


def validate_document_file_name(file_name: str):
    """Validate a research-document filename before storing metadata."""

    if not isinstance(file_name, str):
        raise ValueError("File name must be text.")

    file_name = file_name.strip()

    if not file_name:
        raise ValueError("File name cannot be empty.")

    path = Path(file_name)

    if path.is_absolute() or path.name != file_name:
        raise ValueError(
            "Invalid file name. Only a filename inside the documents "
            "directory is allowed."
        )

    if "\\" in file_name or "/" in file_name:
        raise ValueError(
            "Invalid file name. Directory separators are not allowed."
        )

    if len(file_name) > 255:
        raise ValueError("File name is too long.")

    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF documents are supported.")

    return file_name


def validate_document_type(document_type: str):
    """Validate the supported research-document type."""

    if not isinstance(document_type, str):
        raise ValueError("Document type must be text.")

    document_type = document_type.strip().upper()

    if document_type != "PDF":
        raise ValueError("Only PDF documents are supported.")

    return document_type


# ============================================================
# DATABASE HELPER
# ============================================================

def get_table_columns(table_name: str):
    """Return column names for an explicitly allowed SQLite table."""

    if table_name not in ALLOWED_TABLES:
        raise ValueError("Requested database table is not allowed.")

    cursor = db.execute(
        f"PRAGMA table_info({table_name})"
    )

    return [
        row["name"]
        for row in cursor.fetchall()
    ]


# ============================================================
# TOOL 1 - DILUTION CALCULATOR
# ============================================================

@server.tool()
async def calculate_dilution(
    stock: float,
    desired: float,
    final_volume: float,
):
    """
    Calculate dilution using C1V1 = C2V2.
    """

    if stock <= 0:
        return {
            "error": "Stock concentration must be greater than 0."
        }

    if desired <= 0:
        return {
            "error": "Desired concentration must be greater than 0."
        }

    if final_volume <= 0:
        return {
            "error": "Final volume must be greater than 0."
        }

    if desired > stock:
        return {
            "error": (
                "Desired concentration cannot be greater "
                "than stock concentration."
            )
        }

    stock_volume = (
        desired * final_volume
    ) / stock

    diluent_volume = (
        final_volume - stock_volume
    )

    return {
        "stock_concentration": stock,
        "desired_concentration": desired,
        "final_volume": final_volume,
        "stock_volume": round(stock_volume, 4),
        "diluent_volume": round(diluent_volume, 4),
        "formula": "C1V1 = C2V2",
    }


# ============================================================
# TOOL 2 - GET EXPERIMENT
# ============================================================

@server.tool()
async def get_experiment(
    experiment_id: str,
):
    """
    Retrieve one experiment by experiment ID.
    """

    cursor = db.execute(
        """
        SELECT *
        FROM experiments
        WHERE experiment_id = ?
        """,
        (experiment_id,),
    )

    row = cursor.fetchone()

    if row is None:
        return {
            "error": (
                f"Experiment '{experiment_id}' "
                "was not found."
            )
        }

    return dict(row)


# ============================================================
# TOOL 3 - SEARCH EXPERIMENTS
# ============================================================

@server.tool()
async def search_experiments(
    query: str = "",
    cell_type: str = "",
    treatment: str = "",
    organism: str = "",
    test: str = "",
    duration_hours: int | None = None,
    limit: int = 10,
):
    """
    Search experiments using:

    - general text query
    - cell type
    - treatment
    - organism
    - test
    - duration in hours
    """

    try:
        query = validate_optional_text(query, "query", MAX_SEARCH_QUERY_LENGTH) if query else ""
        cell_type = validate_optional_text(cell_type, "cell_type", MAX_FILTER_LENGTH)
        treatment = validate_optional_text(treatment, "treatment", MAX_FILTER_LENGTH)
        organism = validate_optional_text(organism, "organism", MAX_FILTER_LENGTH)
        test = validate_optional_text(test, "test", MAX_FILTER_LENGTH)
        if limit is None:
            limit = 10
        limit = validate_positive_int(limit, "limit", MAX_SEARCH_LIMIT)
        if duration_hours is not None:
            duration_hours = validate_positive_int(duration_hours, "duration_hours", MAX_DURATION_HOURS)
    except ValueError as exc:
        return {"error": str(exc)}

    # --------------------------------------------------------
    # Get actual database columns
    # --------------------------------------------------------

    columns = get_table_columns(
        "experiments"
    )

    if not columns:
        return {
            "error": (
                "The experiments table "
                "could not be found."
            )
        }

    # --------------------------------------------------------
    # Base SQL
    # --------------------------------------------------------

    sql = """
        SELECT *
        FROM experiments
        WHERE 1 = 1
    """

    params = []

    # --------------------------------------------------------
    # GENERAL TEXT SEARCH
    # --------------------------------------------------------

    if query:

        searchable_columns = [
            column
            for column in [
                "experiment_id",
                "name",
                "cell_type",
                "treatment",
                "organism",
                "test",
            ]
            if column in columns
        ]

        if searchable_columns:

            conditions = []

            for column in searchable_columns:

                conditions.append(
                    f"""
                    LOWER(
                        CAST({column} AS TEXT)
                    ) LIKE ?
                    """
                )

                params.append(
                    f"%{query.lower()}%"
                )

            sql += (
                " AND ("
                + " OR ".join(conditions)
                + ")"
            )

    # --------------------------------------------------------
    # CELL TYPE FILTER
    # --------------------------------------------------------

    if (
        cell_type
        and "cell_type" in columns
    ):

        sql += """
            AND LOWER(cell_type) = LOWER(?)
        """

        params.append(
            cell_type
        )

    # --------------------------------------------------------
    # TREATMENT FILTER
    # --------------------------------------------------------

    if (
        treatment
        and "treatment" in columns
    ):

        sql += """
            AND LOWER(treatment) = LOWER(?)
        """

        params.append(
            treatment
        )

    # --------------------------------------------------------
    # ORGANISM FILTER
    # --------------------------------------------------------

    if (
        organism
        and "organism" in columns
    ):

        sql += """
            AND LOWER(organism) = LOWER(?)
        """

        params.append(
            organism
        )

    # --------------------------------------------------------
    # TEST FILTER
    # --------------------------------------------------------

    if (
        test
        and "test" in columns
    ):

        sql += """
            AND LOWER(test) = LOWER(?)
        """

        params.append(
            test
        )

    # --------------------------------------------------------
    # DURATION FILTER
    # --------------------------------------------------------

    if (
        duration_hours is not None
        and "duration_hours" in columns
    ):

        sql += """
            AND duration_hours = ?
        """

        params.append(
            duration_hours
        )

    # --------------------------------------------------------
    # LIMIT
    # --------------------------------------------------------

    sql += """
        LIMIT ?
    """

    params.append(
        limit
    )

    # --------------------------------------------------------
    # EXECUTE QUERY
    # --------------------------------------------------------

    cursor = db.execute(
        sql,
        params,
    )

    rows = cursor.fetchall()

    results = [
        dict(row)
        for row in rows
    ]

    # --------------------------------------------------------
    # RETURN RESULTS
    # --------------------------------------------------------

    return {
        "count": len(results),
        "results": results,
        "columns": columns,
        "filters": {
            "query": query,
            "cell_type": cell_type,
            "treatment": treatment,
            "organism": organism,
            "test": test,
            "duration_hours": duration_hours,
            "limit": limit,
        },
    }


# ============================================================
# TOOL 4 - ADD EXPERIMENT
# ============================================================

@server.tool()
async def add_experiment(
    experiment_id: str,
    experiment_name: str,
    cell_type: str = "",
    treatment: str = "",
    organism: str = "",
    test: str = "",
    duration_hours: int | None = None,
):
    """
    Add a new experiment to the database.
    """

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------
    try:
        experiment_id = validate_document_id(experiment_id)
        experiment_name = validate_text_field(experiment_name, "experiment_name", MAX_EXPERIMENT_FIELD_LENGTH)
        cell_type = validate_optional_text(cell_type, "cell_type", MAX_EXPERIMENT_FIELD_LENGTH)
        treatment = validate_optional_text(treatment, "treatment", MAX_EXPERIMENT_FIELD_LENGTH)
        organism = validate_optional_text(organism, "organism", MAX_EXPERIMENT_FIELD_LENGTH)
        test = validate_optional_text(test, "test", MAX_EXPERIMENT_FIELD_LENGTH)
        if duration_hours is not None:
            duration_hours = validate_positive_int(duration_hours, "duration_hours", MAX_DURATION_HOURS)
    except ValueError as exc:
        return {"error": str(exc)}

    # --------------------------------------------------------
    # Check duplicate
    # --------------------------------------------------------

    cursor = db.execute(
        """
        SELECT experiment_id
        FROM experiments
        WHERE experiment_id = ?
        """,
        (experiment_id,),
    )

    if cursor.fetchone():

        return {
            "error": (
                f"Experiment '{experiment_id}' "
                "already exists."
            )
        }

    # --------------------------------------------------------
    # Insert
    # --------------------------------------------------------

    db.execute(
        """
        INSERT INTO experiments (
            experiment_id,
            name,
            cell_type,
            treatment,
            organism,
            test,
            duration_hours
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            experiment_id,
            experiment_name,
            cell_type or None,
            treatment or None,
            organism or None,
            test or None,
            duration_hours,
        ),
    )

    db.commit()

    return {
        "success": True,
        "message": (
            f"Experiment '{experiment_id}' "
            "was added successfully."
        ),
        "experiment": {
            "experiment_id": experiment_id,
            "name": experiment_name,
            "cell_type": cell_type or None,
            "treatment": treatment or None,
            "organism": organism or None,
            "test": test or None,
            "duration_hours": duration_hours,
        },
    }


# ============================================================
# TOOL 5 - GET RESEARCH DOCUMENT
# ============================================================

@server.tool()
async def get_research_document(
    document_id: str,
):
    """
    Retrieve research document metadata.
    """

    try:
        document_id = validate_document_id(document_id)
    except ValueError as exc:
        return {"error": str(exc)}

    cursor = db.execute(
        """
        SELECT *
        FROM research_documents
        WHERE document_id = ?
        """,
        (document_id,),
    )

    row = cursor.fetchone()

    if row is None:
        return {
            "error": (
                f"Research document '{document_id}' "
                "was not found."
            )
        }

    return dict(row)


# ============================================================
# TOOL 6 - ADD RESEARCH DOCUMENT
# ============================================================

@server.tool()
async def add_research_document(
    document_id: str,
    title: str,
    file_name: str,
    document_type: str = "PDF",
    description: str = "",
):
    """
    Add research document metadata.
    """

    try:
        document_id = validate_document_id(document_id)
        file_name = validate_document_file_name(file_name)
        document_type = validate_document_type(document_type)
    except ValueError as exc:
        return {"error": str(exc)}

    try:
        title = validate_text_field(title, "Document title", MAX_DOCUMENT_TITLE_LENGTH)
        description = validate_optional_text(description, "Document description", MAX_DOCUMENT_DESCRIPTION_LENGTH)
    except ValueError as exc:
        return {"error": str(exc)}

    cursor = db.execute(
        """
        SELECT document_id
        FROM research_documents
        WHERE document_id = ?
        """,
        (document_id,),
    )

    if cursor.fetchone():

        return {
            "error": (
                f"Document '{document_id}' "
                "already exists."
            )
        }

    db.execute(
        """
        INSERT INTO research_documents (
            document_id,
            title,
            file_name,
            document_type,
            description
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            document_id,
            title,
            file_name,
            document_type,
            description,
        ),
    )

    db.commit()

    return {
        "success": True,
        "message": (
            f"Research document '{document_id}' "
            "was added successfully."
        ),
    }


# ============================================================
# TOOL 7 - EXTRACT PDF TEXT
# ============================================================

@server.tool()
async def extract_pdf_text(
    document_id: str,
):
    """
    Extract text from a PDF and save it into
    research_content and research_pages.
    """

    # --------------------------------------------------------
    # Get metadata
    # --------------------------------------------------------

    try:
        document_id = validate_document_id(document_id)
    except ValueError as exc:
        return {"error": str(exc)}

    cursor = db.execute(
        """
        SELECT *
        FROM research_documents
        WHERE document_id = ?
        """,
        (document_id,),
    )

    document = cursor.fetchone()

    if document is None:

        return {
            "error": (
                f"Research document '{document_id}' "
                "was not found."
            )
        }

    document = dict(document)

    # --------------------------------------------------------
    # Check document type
    # --------------------------------------------------------

    document_type = (
        document.get("document_type")
        or ""
    ).upper()

    if document_type != "PDF":

        return {
            "error": (
                "Only PDF documents are "
                "currently supported."
            )
        }

    # --------------------------------------------------------
    # File name
    # --------------------------------------------------------

    file_name = document.get(
        "file_name"
    )

    if not file_name:

        return {
            "error": (
                "No file name is associated "
                "with this document."
            )
        }

    # --------------------------------------------------------
    # Secure file path
    # --------------------------------------------------------
    try:
        pdf_path = secure_document_path(file_name)

    except ValueError as exc:
        return {
            "error": str(exc)
        }

    if not pdf_path.exists():
        return {
            "error": "PDF file was not found."
        }

    if not pdf_path.is_file():
        return {
            "error": "The document path is not a regular file."
        }

    try:
        file_size = pdf_path.stat().st_size
    except OSError as exc:
        return safe_internal_error(
            "Could not inspect the PDF file.",
            exc,
        )

    if file_size > MAX_DOCUMENT_FILE_SIZE_BYTES:
        return {
            "error": "PDF file is too large. Maximum allowed size is 25 MB."
        }

    # --------------------------------------------------------
    # Import pypdf
    # --------------------------------------------------------

    try:

        from pypdf import PdfReader

    except ImportError:

        return {
            "error": (
                "pypdf is not installed. "
                "Run: pip install pypdf"
            )
        }

    # --------------------------------------------------------
    # Extract
    # --------------------------------------------------------

    try:

        reader = PdfReader(
            str(pdf_path)
        )

        page_texts = []

        for page in reader.pages:

            text = page.extract_text()

            if text is None:
                text = ""

            if len(text) > MAX_PAGE_TEXT_LENGTH:
                return {
                    "error": "A PDF page contains too much text to process safely."
                }

            page_texts.append(text)

            if sum(len(page) for page in page_texts) > MAX_EXTRACTED_TEXT_LENGTH:
                return {
                    "error": "The extracted PDF text is too large to process safely."
                }

    except Exception as exc:

        return safe_internal_error(
            "PDF extraction failed. Please verify the PDF file and try again.",
            exc,
        )

    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    full_text = "\n\n".join(
        page_texts
    )

    # --------------------------------------------------------
    # Remove old extracted content
    # --------------------------------------------------------

    db.execute(
        """
        DELETE FROM research_pages
        WHERE document_id = ?
        """,
        (document_id,),
    )

    db.execute(
        """
        DELETE FROM research_content
        WHERE document_id = ?
        """,
        (document_id,),
    )

    # --------------------------------------------------------
    # Save full content
    # --------------------------------------------------------

    db.execute(
        """
        INSERT INTO research_content (
            document_id,
            content
        )
        VALUES (?, ?)
        """,
        (
            document_id,
            full_text,
        ),
    )

    # --------------------------------------------------------
    # Save individual pages
    # --------------------------------------------------------

    for page_number, text in enumerate(
        page_texts,
        start=1,
    ):

        db.execute(
            """
            INSERT INTO research_pages (
                document_id,
                page_number,
                content
            )
            VALUES (?, ?, ?)
            """,
            (
                document_id,
                page_number,
                text,
            ),
        )

    db.commit()

    # --------------------------------------------------------
    # Return
    # --------------------------------------------------------

    return {
        "success": True,
        "document_id": document_id,
        "pages_extracted": len(
            page_texts
        ),
        "characters_extracted": len(
            full_text
        ),
    }


# ============================================================
# TOOL 8 - GET RESEARCH CONTENT
# ============================================================

@server.tool()
async def get_research_content(
    document_id: str,
):
    """
    Retrieve extracted research document content.
    """

    cursor = db.execute(
        """
        SELECT *
        FROM research_content
        WHERE document_id = ?
        """,
        (document_id,),
    )

    row = cursor.fetchone()

    if row is None:

        return {
            "error": (
                f"No extracted content found "
                f"for document '{document_id}'."
            )
        }

    return dict(row)


# ============================================================
# TOOL 9 - SEARCH RESEARCH CONTENT
# ============================================================

@server.tool()
async def search_research_content(
    query: str,
    document_id: str = "",
    limit: int = 10,
):
    """
    Search extracted research pages using
    SQL text matching.
    """

    try:
        query = validate_text_field(query, "Search query", MAX_SEARCH_QUERY_LENGTH)
        limit = validate_positive_int(limit, "limit", MAX_SEARCH_LIMIT)
    except ValueError as exc:
        return {"error": str(exc)}

    if document_id:
        try:
            document_id = validate_document_id(document_id)
        except ValueError as exc:
            return {"error": str(exc)}

    # --------------------------------------------------------
    # SQL
    # --------------------------------------------------------

    sql = """
        SELECT
            document_id,
            page_number,
            content
        FROM research_pages
        WHERE LOWER(content) LIKE ?
    """

    params = [
        f"%{query.lower()}%"
    ]

    if document_id:

        sql += """
            AND document_id = ?
        """

        params.append(
            document_id
        )

    sql += """
        ORDER BY document_id, page_number
        LIMIT ?
    """

    params.append(
        limit
    )

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    cursor = db.execute(
        sql,
        params,
    )

    rows = cursor.fetchall()

    results = []

    for row in rows:

        content = row["content"]

        lower_content = content.lower()
        lower_query = query.lower()

        position = lower_content.find(
            lower_query
        )

        if position >= 0:

            start = max(
                0,
                position - 250,
            )

            end = min(
                len(content),
                position + len(query) + 500,
            )

            snippet = content[
                start:end
            ]

        else:

            snippet = content[:750]

        results.append(
            {
                "document_id": row[
                    "document_id"
                ],
                "page_number": row[
                    "page_number"
                ],
                "snippet": snippet,
            }
        )

    return {
        "query": query,
        "document_id": document_id,
        "count": len(results),
        "results": results,
    }


# ============================================================
# TOOL 10 - SEARCH RESEARCH EVIDENCE
# ============================================================

@server.tool()
async def search_research_evidence(
    question: str,
    document_id: str = "DOC001",
    top_k: int = 5,
):
    """
    Retrieve relevant biomedical evidence using
    the local retrieval system.
    """

    try:
        document_id = validate_document_id(document_id)
    except ValueError as exc:
        return {"error": str(exc)}

    try:
        question = validate_text_field(question, "Research question", MAX_SEARCH_QUERY_LENGTH)
        top_k = validate_positive_int(top_k, "top_k", MAX_EVIDENCE_TOP_K)
    except ValueError as exc:
        return {"error": str(exc)}

    # --------------------------------------------------------
    # Import retrieval system
    # --------------------------------------------------------

    try:

        from retrieval import retrieve_evidence

    except ImportError as exc:

        return safe_internal_error(
            "The research retrieval component is unavailable.",
            exc,
        )

    # --------------------------------------------------------
    # Retrieve evidence
    # --------------------------------------------------------

    try:

        result = retrieve_evidence(
            question=question,
            document_id=document_id,
            top_k=top_k,
        )

        return result

    except Exception as exc:

        return safe_internal_error(
            "Research evidence retrieval failed. Please try again.",
            exc,
        )


# ============================================================
# RESOURCE 1 - ALL EXPERIMENTS
# ============================================================

@server.resource(
    "research://experiments"
)
async def experiments_resource():
    """
    Return all experiments as a resource.
    """

    cursor = db.execute(
        """
        SELECT *
        FROM experiments
        ORDER BY experiment_id
        """
    )

    rows = cursor.fetchall()

    results = [
        dict(row)
        for row in rows
    ]

    return json.dumps(
        results,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# RESOURCE 2 - SINGLE EXPERIMENT
# ============================================================

@server.resource(
    "research://experiments/{experiment_id}"
)
async def experiment_resource(
    experiment_id: str,
):
    """
    Return one experiment as a resource.
    """

    result = await get_experiment(
        experiment_id
    )

    return json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# RESOURCE 3 - ALL DOCUMENTS
# ============================================================

@server.resource(
    "research://documents"
)
async def documents_resource():
    """
    Return all research documents.
    """

    cursor = db.execute(
        """
        SELECT *
        FROM research_documents
        ORDER BY document_id
        """
    )

    rows = cursor.fetchall()

    results = [
        dict(row)
        for row in rows
    ]

    return json.dumps(
        results,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# RESOURCE 4 - SINGLE DOCUMENT
# ============================================================

@server.resource(
    "research://documents/{document_id}"
)
async def document_resource(
    document_id: str,
):
    """
    Return one research document.
    """

    result = await get_research_document(
        document_id
    )

    return json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# RESOURCE 5 - DOCUMENT CONTENT
# ============================================================

@server.resource(
    "research://documents/{document_id}/content"
)
async def document_content_resource(
    document_id: str,
):
    """
    Return extracted research document content.
    """

    result = await get_research_content(
        document_id
    )

    return json.dumps(
        result,
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# RESOURCE 6 - INDIVIDUAL PAGE
# ============================================================

@server.resource(
    "research://documents/{document_id}/pages/{page_number}"
)
async def document_page_resource(
    document_id: str,
    page_number: str,
):
    """
    Return one page from a research document.
    """

    try:

        page_number_int = int(
            page_number
        )

    except ValueError:

        return json.dumps(
            {
                "error": (
                    "Page number must be an integer."
                )
            },
            indent=2,
        )

    cursor = db.execute(
        """
        SELECT *
        FROM research_pages
        WHERE document_id = ?
        AND page_number = ?
        """,
        (
            document_id,
            page_number_int,
        ),
    )

    row = cursor.fetchone()

    if row is None:

        return json.dumps(
            {
                "error": (
                    f"Page {page_number_int} "
                    f"was not found for document "
                    f"'{document_id}'."
                )
            },
            indent=2,
        )

    return json.dumps(
        dict(row),
        indent=2,
        ensure_ascii=False,
    )


# ============================================================
# MAIN
# ============================================================

async def main():
    """
    Start the MCP server using stdio.

    IMPORTANT:
    stdout must remain reserved for MCP communication.
    """

    await server.run_stdio_async()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )