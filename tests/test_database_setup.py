"""
Deterministic SQLite database setup for the test suite.

This module makes the test suite independent from a developer's
personal/local biomedical.db.

In a clean CI environment, the required SQLite schema and deterministic
test data are created automatically.

If an existing local database already contains the expected schema,
it is preserved.
"""

from pathlib import Path
import sqlite3


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "biomedical.db"


# ============================================================
# DETERMINISTIC TEST EXPERIMENT DATA
# ============================================================

EXPERIMENTS = [
    (
        "EXP001",
        "Cytotoxicity Study",
        "Skin Cells",
        "Copper Nanoparticles",
        None,
        None,
        24,
    ),
    (
        "EXP002",
        "Antimicrobial Susceptibility Study",
        None,
        None,
        "Bacterial Culture",
        "Antimicrobial Susceptibility",
        24,
    ),
    (
        "EXP003",
        "Drug Cytotoxicity Study",
        "Liver Cells",
        "Doxorubicin",
        None,
        "Cell Viability Assay",
        48,
    ),
]


# ============================================================
# DETERMINISTIC TEST RESEARCH CONTENT
# ============================================================

RESEARCH_PAGES = [
    (
        "DOC001",
        1,
        (
            "Copper nanoparticles can produce toxic effects in biological "
            "systems. Increased production of reactive oxygen species (ROS) "
            "and reactive nitrogen species (RNS) can contribute to oxidative "
            "stress and cellular dysfunction."
        ),
    ),
    (
        "DOC001",
        2,
        (
            "Copper nanoparticles have been associated with cytotoxicity, "
            "oxidative stress, and cellular responses in several experimental "
            "models."
        ),
    ),
    (
        "DOC001",
        3,
        (
            "Copper nanoparticles may affect tissues and organs depending "
            "on exposure conditions and dose."
        ),
    ),
    (
        "DOC001",
        4,
        (
            "Nano-copper exposure has been associated with increased ROS "
            "and reduced cell viability in experimental systems."
        ),
    ),
    (
        "DOC001",
        5,
        (
            "Oxidative stress can contribute to cellular injury following "
            "exposure to copper nanoparticles."
        ),
    ),
    (
        "DOC001",
        6,
        (
            "Copper oxide nanoparticles can inhibit mitochondrial "
            "dehydrogenases and cause ROS generation. Cytotoxicity can also "
            "involve lipid peroxidation of mitochondrial membranes, disruption "
            "of electron transport, and decreased mitochondrial membrane "
            "potential."
        ),
    ),
    (
        "DOC001",
        7,
        (
            "Nano-copper poisoning can increase cytosolic cytochrome c, "
            "Apaf 1, caspase 9, and cleaved caspase 3. Increased ROS can "
            "activate pathways that eventually lead to apoptosis."
        ),
    ),
]


# ============================================================
# TABLE CHECK
# ============================================================

def table_exists(connection, table_name):
    """
    Check whether a SQLite table exists.
    """

    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


# ============================================================
# COLUMN CHECK
# ============================================================

def get_table_columns(connection, table_name):
    """
    Return the column names for a SQLite table.
    """

    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        row[1]
        for row in rows
    }


# ============================================================
# DATABASE READINESS CHECK
# ============================================================

def database_is_ready(connection):
    """
    Determine whether the existing database contains the schema
    required by the test suite.
    """

    required_tables = {
        "experiments",
        "research_documents",
        "research_content",
        "research_pages",
        "research_document_pages",
    }

    for table_name in required_tables:

        if not table_exists(
            connection,
            table_name,
        ):
            return False

    # --------------------------------------------------------
    # Experiments
    # --------------------------------------------------------

    experiment_columns = get_table_columns(
        connection,
        "experiments",
    )

    required_experiment_columns = {
        "experiment_id",
        "name",
        "cell_type",
        "treatment",
        "organism",
        "test",
        "duration_hours",
    }

    if not required_experiment_columns.issubset(
        experiment_columns
    ):
        return False

    # --------------------------------------------------------
    # Research documents
    # --------------------------------------------------------

    document_columns = get_table_columns(
        connection,
        "research_documents",
    )

    required_document_columns = {
        "document_id",
        "title",
        "file_name",
        "document_type",
        "description",
        "created_at",
    }

    if not required_document_columns.issubset(
        document_columns
    ):
        return False

    # --------------------------------------------------------
    # Research content
    # --------------------------------------------------------

    content_columns = get_table_columns(
        connection,
        "research_content",
    )

    required_content_columns = {
        "document_id",
        "content",
    }

    if not required_content_columns.issubset(
        content_columns
    ):
        return False

    # --------------------------------------------------------
    # Research pages
    # --------------------------------------------------------

    page_columns = get_table_columns(
        connection,
        "research_pages",
    )

    required_page_columns = {
        "document_id",
        "page_number",
        "content",
    }

    if not required_page_columns.issubset(
        page_columns
    ):
        return False

    # --------------------------------------------------------
    # Research document pages
    # --------------------------------------------------------

    document_page_columns = get_table_columns(
        connection,
        "research_document_pages",
    )

    required_document_page_columns = {
        "document_id",
        "page_number",
        "page_text",
    }

    if not required_document_page_columns.issubset(
        document_page_columns
    ):
        return False

    return True


# ============================================================
# CREATE DATABASE SCHEMA
# ============================================================

def create_schema(connection):
    """
    Create the SQLite schema required by the test suite.

    The research_documents.created_at field is required because
    the production database schema enforces it as NOT NULL.
    """

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            cell_type TEXT,
            treatment TEXT,
            organism TEXT,
            test TEXT,
            duration_hours INTEGER
        );

        CREATE TABLE IF NOT EXISTS research_documents (
            document_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            file_name TEXT NOT NULL,
            document_type TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS research_content (
            document_id TEXT PRIMARY KEY,
            content TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS research_pages (
            document_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            content TEXT NOT NULL,
            PRIMARY KEY (
                document_id,
                page_number
            )
        );

        CREATE TABLE IF NOT EXISTS research_document_pages (
            document_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            page_text TEXT NOT NULL,
            PRIMARY KEY (
                document_id,
                page_number
            )
        );
        """
    )


# ============================================================
# REPAIR EXISTING TEST DATABASE
# ============================================================

def repair_existing_schema(connection):
    """
    Repair the local/CI database when the tables exist but a
    required non-breaking column is missing.

    This specifically handles databases that were created by an
    earlier version of test_database_setup.py.
    """

    # --------------------------------------------------------
    # research_documents.created_at
    # --------------------------------------------------------

    if table_exists(
        connection,
        "research_documents",
    ):

        columns = get_table_columns(
            connection,
            "research_documents",
        )

        if "created_at" not in columns:

            connection.execute(
                """
                ALTER TABLE research_documents
                ADD COLUMN created_at TEXT
                NOT NULL
                DEFAULT CURRENT_TIMESTAMP
                """
            )


# ============================================================
# INSERT EXPERIMENT DATA
# ============================================================

def insert_experiments(connection):
    """
    Insert deterministic experiment records.
    """

    connection.executemany(
        """
        INSERT OR REPLACE INTO experiments (
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
        EXPERIMENTS,
    )


# ============================================================
# INSERT DOCUMENT METADATA
# ============================================================

def insert_document_metadata(connection):
    """
    Insert deterministic research document metadata.
    """

    connection.execute(
        """
        INSERT OR REPLACE INTO research_documents (
            document_id,
            title,
            file_name,
            document_type,
            description
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "DOC001",
            "Copper Nanoparticle Cytotoxicity Study",
            "copper_nanoparticle_study.pdf",
            "PDF",
            "Deterministic test document metadata.",
        ),
    )


# ============================================================
# INSERT RESEARCH CONTENT
# ============================================================

def insert_research_content(connection):
    """
    Insert deterministic document content and page-level content.
    """

    connection.execute(
        """
        DELETE FROM research_pages
        WHERE document_id = 'DOC001'
        """
    )

    connection.execute(
        """
        DELETE FROM research_document_pages
        WHERE document_id = 'DOC001'
        """
    )

    connection.execute(
        """
        DELETE FROM research_content
        WHERE document_id = 'DOC001'
        """
    )

    full_text = "\n\n".join(
        page_text
        for _, _, page_text in RESEARCH_PAGES
    )

    connection.execute(
        """
        INSERT INTO research_content (
            document_id,
            content
        )
        VALUES (?, ?)
        """,
        (
            "DOC001",
            full_text,
        ),
    )

    connection.executemany(
        """
        INSERT INTO research_pages (
            document_id,
            page_number,
            content
        )
        VALUES (?, ?, ?)
        """,
        RESEARCH_PAGES,
    )

    connection.executemany(
        """
        INSERT INTO research_document_pages (
            document_id,
            page_number,
            page_text
        )
        VALUES (?, ?, ?)
        """,
        RESEARCH_PAGES,
    )


# ============================================================
# ENSURE TEST DATABASE
# ============================================================

def ensure_test_database():
    """
    Ensure that the SQLite database contains the schema and
    deterministic records required by the test suite.

    Existing valid development databases are preserved.
    """

    connection = sqlite3.connect(
        DB_PATH
    )

    try:

        # ----------------------------------------------------
        # Existing valid database
        # ----------------------------------------------------

        if database_is_ready(
            connection
        ):
            return

        # ----------------------------------------------------
        # Create missing tables
        # ----------------------------------------------------

        create_schema(
            connection
        )

        # ----------------------------------------------------
        # Repair compatible existing tables
        # ----------------------------------------------------

        repair_existing_schema(
            connection
        )

        # ----------------------------------------------------
        # Insert deterministic test data
        # ----------------------------------------------------

        insert_experiments(
            connection
        )

        insert_document_metadata(
            connection
        )

        insert_research_content(
            connection
        )

        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        connection.commit()

    finally:

        connection.close()


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    ensure_test_database()

    print(
        f"Test database ready: {DB_PATH}"
    )