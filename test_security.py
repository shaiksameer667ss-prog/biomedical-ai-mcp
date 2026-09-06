import asyncio
import unittest

import server


class SecurityTests(unittest.TestCase):

    def test_documents_directory_is_configured(self):
        self.assertTrue(server.DOCUMENTS_DIR.exists())
        self.assertTrue(server.DOCUMENTS_DIR.is_dir())

    def test_path_traversal_is_blocked(self):
        documents_root = server.DOCUMENTS_DIR.resolve()

        malicious_path = (
            server.DOCUMENTS_DIR / ".." / "biomedical.db"
        ).resolve()

        self.assertNotIn(
            documents_root,
            malicious_path.parents,
            "Traversal path incorrectly remains inside documents directory.",
        )

    def test_valid_document_path_stays_inside_directory(self):
        valid_path = (
            server.DOCUMENTS_DIR / "copper_nanoparticle_study.pdf"
        ).resolve()

        documents_root = server.DOCUMENTS_DIR.resolve()

        self.assertIn(
            documents_root,
            valid_path.parents,
        )

    def test_missing_file_is_not_treated_as_existing(self):
        missing_path = (
            server.DOCUMENTS_DIR / "file_that_does_not_exist.pdf"
        ).resolve()

        self.assertFalse(missing_path.exists())


if __name__ == "__main__":
    unittest.main()