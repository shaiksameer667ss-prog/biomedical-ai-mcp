import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import server


class PDFLimitTests(unittest.TestCase):

    def run_async(self, coroutine):
        return asyncio.run(coroutine)

    def test_pdf_file_size_limit_is_enforced(self):
        """A PDF larger than the configured maximum must be rejected."""

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "large.pdf"
            pdf_path.write_bytes(b"%PDF-test")

            fake_stat = MagicMock()
            fake_stat.st_size = (
                server.MAX_DOCUMENT_FILE_SIZE_BYTES + 1
            )

            with patch.object(
                server,
                "secure_document_path",
                return_value=pdf_path,
            ), patch.object(
                type(pdf_path),
                "stat",
                return_value=fake_stat,
            ):
                result = self.run_async(
                    server.extract_pdf_text("DOC001")
                )

            self.assertIsInstance(result, dict)

            error_text = str(result).lower()

            self.assertTrue(
                "file" in error_text
                or "size" in error_text
                or "limit" in error_text
            )

    def test_single_page_text_limit_is_enforced(self):
        """A single extracted PDF page exceeding the limit must be rejected."""

        huge_page_text = (
            "A" * (server.MAX_PAGE_TEXT_LENGTH + 1)
        )

        fake_page = MagicMock()
        fake_page.extract_text.return_value = huge_page_text

        fake_reader = MagicMock()
        fake_reader.pages = [fake_page]

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "huge_page.pdf"
            pdf_path.write_bytes(b"%PDF-test")

            fake_stat = MagicMock()
            fake_stat.st_size = 100

            with patch.object(
                server,
                "secure_document_path",
                return_value=pdf_path,
            ), patch.object(
                type(pdf_path),
                "stat",
                return_value=fake_stat,
            ):

                # Patch the PDF reader where the server actually imports it.
                with patch(
                    "pypdf.PdfReader",
                    return_value=fake_reader,
                ):

                    result = self.run_async(
                        server.extract_pdf_text("DOC001")
                    )

            self.assertIsInstance(result, dict)

            error_text = str(result).lower()

            self.assertTrue(
                "page" in error_text
                or "text" in error_text
                or "limit" in error_text
            )

    def test_total_extracted_text_limit_is_enforced(self):
        """Total extracted text exceeding the configured limit must be rejected."""

        page_text = (
            "B" * server.MAX_PAGE_TEXT_LENGTH
        )

        pages = []

        page_count = (
            server.MAX_EXTRACTED_TEXT_LENGTH
            // server.MAX_PAGE_TEXT_LENGTH
        ) + 1

        for _ in range(page_count):
            page = MagicMock()
            page.extract_text.return_value = page_text
            pages.append(page)

        fake_reader = MagicMock()
        fake_reader.pages = pages

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "huge_document.pdf"
            pdf_path.write_bytes(b"%PDF-test")

            fake_stat = MagicMock()
            fake_stat.st_size = 100

            with patch.object(
                server,
                "secure_document_path",
                return_value=pdf_path,
            ), patch.object(
                type(pdf_path),
                "stat",
                return_value=fake_stat,
            ):

                # Patch the PDF reader where the dependency is defined.
                with patch(
                    "pypdf.PdfReader",
                    return_value=fake_reader,
                ):

                    result = self.run_async(
                        server.extract_pdf_text("DOC001")
                    )

            self.assertIsInstance(result, dict)

            error_text = str(result).lower()

            self.assertTrue(
                "text" in error_text
                or "document" in error_text
                or "limit" in error_text
            )


if __name__ == "__main__":
    unittest.main()