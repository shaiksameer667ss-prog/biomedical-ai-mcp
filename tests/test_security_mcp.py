import unittest

import server


class MCPFileSecurityTests(unittest.TestCase):

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(ValueError) as context:
            server.secure_document_path(
                "../../biomedical.db"
            )

        self.assertIn(
            "inside the documents directory",
            str(context.exception),
        )

    def test_absolute_path_is_rejected(self):
        malicious_path = (
            server.BASE_DIR / "biomedical.db"
        )

        with self.assertRaises(ValueError) as context:
            server.secure_document_path(
                str(malicious_path)
            )

        self.assertIn(
            "inside the documents directory",
            str(context.exception),
        )

    def test_valid_document_path_is_allowed(self):
        path = server.secure_document_path(
            "copper_nanoparticle_study.pdf"
        )

        documents_root = server.DOCUMENTS_DIR.resolve()

        self.assertIn(
            documents_root,
            path.parents,
        )

    def test_valid_path_resolves_inside_documents_directory(self):
        path = server.secure_document_path(
            "subfolder/example.pdf"
        )

        documents_root = server.DOCUMENTS_DIR.resolve()

        self.assertIn(
            documents_root,
            path.parents,
        )


if __name__ == "__main__":
    unittest.main()
