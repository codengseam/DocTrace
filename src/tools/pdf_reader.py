"""PDF 读取工具。

优先通过 MCP 服务器 `mcp_pdf-reader-mcp` 读取本地 PDF；
MCP 不可用时，依次 fallback 到 PyPDF2、pdfplumber；
三者均不可用时返回空字符串并记录 warning。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PDFReader:
    """读取本地 PDF 并返回文本、页数与来源信息。"""

    def __init__(self, mcp_server_name: str = "mcp_pdf-reader-mcp") -> None:
        self.mcp_server_name = mcp_server_name

    def _read_with_mcp(self, file_path: Path) -> Optional[dict]:
        """尝试通过 MCP 服务器读取 PDF。"""
        try:
            import mcp  # type: ignore

            logger.debug("Trying MCP server: %s", self.mcp_server_name)
            client = mcp.Client()
            result = client.call(
                server=self.mcp_server_name,
                tool="read_pdf",
                arguments={"file_path": str(file_path.resolve())},
            )
            text = result.get("text", "") if isinstance(result, dict) else str(result)
            pages = result.get("pages", 0) if isinstance(result, dict) else 0
            return {
                "text": text,
                "pages": int(pages) if pages else 0,
                "source": f"mcp:{self.mcp_server_name}",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("MCP PDF reader unavailable: %s", exc)
            return None

    def _read_with_pypdf2(self, file_path: Path) -> Optional[dict]:
        """使用 PyPDF2 读取 PDF。"""
        try:
            import PyPDF2  # type: ignore
        except ImportError:
            return None

        try:
            text_parts: list[str] = []
            with file_path.open("rb") as fh:
                reader = PyPDF2.PdfReader(fh)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return {
                "text": "\n\n".join(text_parts),
                "pages": len(reader.pages),
                "source": "PyPDF2",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("PyPDF2 failed to read %s: %s", file_path, exc)
            return None

    def _read_with_pdfplumber(self, file_path: Path) -> Optional[dict]:
        """使用 pdfplumber 读取 PDF。"""
        try:
            import pdfplumber  # type: ignore
        except ImportError:
            return None

        try:
            text_parts: list[str] = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return {
                "text": "\n\n".join(text_parts),
                "pages": len(pdf.pages),
                "source": "pdfplumber",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("pdfplumber failed to read %s: %s", file_path, exc)
            return None

    def read_pdf(self, file_path: Path) -> dict:
        """读取 PDF 全部文本。

        Returns:
            {"text": str, "pages": int, "source": str}
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning("PDF file not found: %s", file_path)
            return {"text": "", "pages": 0, "source": "none"}

        for reader_fn in (
            self._read_with_mcp,
            self._read_with_pypdf2,
            self._read_with_pdfplumber,
        ):
            result = reader_fn(file_path)
            if result is not None:
                return result

        logger.warning("No PDF backend available for %s", file_path)
        return {"text": "", "pages": 0, "source": "none"}

    def read_pdf_pages(self, file_path: Path, start: int, end: int) -> dict:
        """读取 PDF 指定页码范围（含 start，不含 end）。"""
        file_path = Path(file_path)
        if not file_path.exists():
            logger.warning("PDF file not found: %s", file_path)
            return {"text": "", "pages": 0, "source": "none"}

        start = max(1, start)
        end = max(start, end)

        try:
            import pdfplumber  # type: ignore

            text_parts: list[str] = []
            with pdfplumber.open(file_path) as pdf:
                total = len(pdf.pages)
                end = min(end, total + 1)
                for idx in range(start - 1, end - 1):
                    page_text = pdf.pages[idx].extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return {
                "text": "\n\n".join(text_parts),
                "pages": end - start,
                "source": "pdfplumber",
            }
        except ImportError:
            pass

        try:
            import PyPDF2  # type: ignore

            text_parts = []
            with file_path.open("rb") as fh:
                reader = PyPDF2.PdfReader(fh)
                total = len(reader.pages)
                end = min(end, total + 1)
                for idx in range(start - 1, end - 1):
                    page_text = reader.pages[idx].extract_text()
                    if page_text:
                        text_parts.append(page_text)
            return {
                "text": "\n\n".join(text_parts),
                "pages": end - start,
                "source": "PyPDF2",
            }
        except ImportError:
            pass

        logger.warning("No local PDF backend available for page range read")
        return {"text": "", "pages": 0, "source": "none"}


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    reader = PDFReader()
    test_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace/data/sample.pdf")

    if test_pdf.exists():
        print(reader.read_pdf(test_pdf))
        print(reader.read_pdf_pages(test_pdf, 1, 3))
    else:
        print("PDFReader self-check: no sample PDF found, returning empty result")
        print(reader.read_pdf(test_pdf))
