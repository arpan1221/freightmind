import fitz  # pymupdf

SUPPORTED_TYPES = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
}


class ExtractionPlanner:
    @staticmethod
    def prepare(file_bytes: bytes, content_type: str) -> tuple[bytes, str]:
        """Convert upload to image bytes ready for the vision model.

        Returns (image_bytes, mime_type).
        Raises ValueError for unsupported content types.
        """
        if content_type not in SUPPORTED_TYPES:
            raise ValueError(
                f"unsupported_file_type: '{content_type}'. "
                f"Accepted: PDF, PNG, JPEG."
            )

        if content_type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc[0]  # single-page only for Story 3.1
            mat = fitz.Matrix(2, 2)  # 2x scale for better OCR quality
            pix = page.get_pixmap(matrix=mat)
            return pix.tobytes("png"), "image/png"

        # PNG / JPEG — pass through unchanged
        return file_bytes, content_type
