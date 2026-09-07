import sqlite3
from datetime import datetime

from config import DATABASE_PATH


# ==================================================
# DATABASE CONFIGURATION
# ==================================================

DATABASE = DATABASE_PATH


# ==================================================
# DATABASE SETUP
# ==================================================

def create_tables():
    """
    Create all required database tables.
    """

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # --------------------------------------------------
    # EXPERIMENTS
    # --------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            cell_type TEXT,
            treatment TEXT,
            organism TEXT,
            test TEXT,
            duration_hours INTEGER
        )
        """
    )

    # --------------------------------------------------
    # RESEARCH DOCUMENTS
    # --------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS research_documents (
            document_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            file_name TEXT NOT NULL,
            document_type TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------
    # OLD DOCUMENT CONTENT TABLE
    #
    # We keep this table because it already exists
    # in your database.
    # --------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS research_document_content (
            document_id TEXT PRIMARY KEY,
            extracted_text TEXT NOT NULL,
            extracted_at TEXT NOT NULL,
            FOREIGN KEY (document_id)
                REFERENCES research_documents(document_id)
        )
        """
    )

    # --------------------------------------------------
    # NEW PAGE-LEVEL CONTENT TABLE
    # --------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS research_document_pages (
            document_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            page_text TEXT NOT NULL,
            extracted_at TEXT NOT NULL,

            PRIMARY KEY (
                document_id,
                page_number
            ),

            FOREIGN KEY (document_id)
                REFERENCES research_documents(document_id)
        )
        """
    )

    connection.commit()

    # ==================================================
    # SEED EXP001
    # ==================================================

    cursor.execute(
        """
        SELECT experiment_id
        FROM experiments
        WHERE experiment_id = ?
        """,
        ("EXP001",)
    )

    if cursor.fetchone() is None:

        cursor.execute(
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
                "EXP001",
                "Cytotoxicity Study",
                "Skin Cells",
                "Copper Nanoparticles",
                "Human",
                "Cell Viability Assay",
                24
            )
        )

    # ==================================================
    # SEED EXP002
    # ==================================================

    cursor.execute(
        """
        SELECT experiment_id
        FROM experiments
        WHERE experiment_id = ?
        """,
        ("EXP002",)
    )

    if cursor.fetchone() is None:

        cursor.execute(
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
                "EXP002",
                "Antimicrobial Susceptibility Study",
                "Bacterial Culture",
                "Antimicrobial",
                "Bacteria",
                "Antimicrobial Susceptibility Testing",
                24
            )
        )

    # ==================================================
    # SEED DOC001
    # ==================================================

    cursor.execute(
        """
        SELECT document_id
        FROM research_documents
        WHERE document_id = ?
        """,
        ("DOC001",)
    )

    if cursor.fetchone() is None:

        cursor.execute(
            """
            INSERT INTO research_documents (
                document_id,
                title,
                file_name,
                document_type,
                description,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "DOC001",
                "Copper Nanoparticle Cytotoxicity Study",
                "copper_nanoparticle_study.pdf",
                "PDF",
                "Research document related to copper nanoparticle cytotoxicity.",
                datetime.now().isoformat()
            )
        )

    connection.commit()
    connection.close()

    print("Database setup completed successfully.")


# ==================================================
# RUN SETUP
# ==================================================

if __name__ == "__main__":
    create_tables()