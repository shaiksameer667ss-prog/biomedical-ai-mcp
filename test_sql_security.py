import unittest

import server


class SQLAndInputSecurityTests(unittest.TestCase):

    def test_allowed_table_name_works(self):
        columns = server.get_table_columns("experiments")

        self.assertIsInstance(columns, list)
        self.assertIn("experiment_id", columns)
        self.assertIn("treatment", columns)

    def test_sql_identifier_injection_is_rejected(self):
        with self.assertRaises(ValueError):
            server.get_table_columns(
                "experiments; DROP TABLE experiments; --"
            )

    def test_document_id_rejects_sql_payload(self):
        with self.assertRaises(ValueError):
            server.validate_document_id(
                "DOC001' OR '1'='1"
            )

    def test_document_id_rejects_path_payload(self):
        with self.assertRaises(ValueError):
            server.validate_document_id(
                "../../biomedical.db"
            )

    def test_document_id_accepts_normal_value(self):
        self.assertEqual(
            server.validate_document_id("DOC001"),
            "DOC001",
        )

    def test_file_name_rejects_directory_traversal(self):
        with self.assertRaises(ValueError):
            server.validate_document_file_name(
                "../../malicious.pdf"
            )

    def test_file_name_rejects_windows_traversal(self):
        with self.assertRaises(ValueError):
            server.validate_document_file_name(
                r"..\..\malicious.pdf"
            )

    def test_file_name_rejects_non_pdf(self):
        with self.assertRaises(ValueError):
            server.validate_document_file_name(
                "malicious.txt"
            )

    def test_file_name_accepts_normal_pdf(self):
        self.assertEqual(
            server.validate_document_file_name(
                "copper_nanoparticle_study.pdf"
            ),
            "copper_nanoparticle_study.pdf",
        )

    def test_document_type_rejects_unsupported_type(self):
        with self.assertRaises(ValueError):
            server.validate_document_type("EXE")

    def test_document_type_accepts_pdf_case_insensitively(self):
        self.assertEqual(
            server.validate_document_type("pdf"),
            "PDF",
        )


if __name__ == "__main__":
    unittest.main()
