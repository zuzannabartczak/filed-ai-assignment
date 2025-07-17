import re
import io
from typing import Optional
from fastapi import FastAPI, File, UploadFile
import pdfplumber
import pytesseract
from PIL import Image, ImageFilter
from pypdf import PdfReader
from collections import Counter

pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

app = FastAPI()


def normalize(text: str) -> str:
    """
    Normalize text by lowercasing and collapsing whitespace.
    """
    return re.sub(r'\s+', ' ', text.lower()).strip()


def extract_form_fields(pdf_bytes: bytes) -> tuple[str, dict]:
    """
    Extracts AcroForm interactive fields from a PDF.
    
    Returns:
        A string containing joined form field values and the original field dictionary.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        fields = reader.get_fields()
        if not fields:
            return "", {}
        form_text = "\n".join(str(field.get("/V", "")).strip() for field in fields.values() if field.get("/V"))
        return form_text, fields
    except Exception:
        # Fallback if PDF is not form-enabled or corrupted
        return "", {}


def extract_tables_text(pdf_bytes: bytes) -> str:
    """
    Extracts text content from tabular data using pdfplumber.

    Returns:
        A string with table cells joined per row and page.
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(
            " ".join(cell.strip() for cell in row if cell)
            for page in pdf.pages
            for table in page.extract_tables() or []
            for row in table
        ).strip()


def extract_full_text(pdf_bytes: bytes) -> str:
    """
    Extracts all visible text from a PDF using pdfplumber's OCR-less method.

    Returns:
        Concatenated string of all text content in the PDF.
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(
            page.extract_text().strip()
            for page in pdf.pages
            if page.extract_text()
        ).strip()


def extract_ocr_text(pdf_bytes: bytes) -> str:
    """
    Applies OCR to each PDF page using pytesseract.
    A Gaussian blur is applied to improve OCR accuracy.

    Returns:
        OCR-derived text string for all pages.
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(
            pytesseract.image_to_string(
                page.to_image(resolution=300).original.convert("RGB").filter(ImageFilter.GaussianBlur(radius=2)),
                config="--psm 6"  # Assume uniform block of text
            ).strip()
            for page in pdf.pages
        ).strip()


def extract_year(text: str, form_fields: dict, form_keyword: Optional[str] = None) -> Optional[str]:
    """
    Extracts the most likely year associated with the form.
    Priority order:
        1. Year on the same line as a form keyword (e.g., "Form 1040 (2022)").
        2. Most common 4-digit year in the text, excluding lines with 'rev'.
        3. 2-digit year in AcroForm field labeled 'calendar year' (if exists and filled like in "f1098.pdf").

    Args:
        text: Text extracted from PDF.
        form_fields: Dictionary of interactive form fields.
        form_keyword: Optional form keyword (e.g., "W-2") used to locate context-specific year.

    Returns:
        The most likely year as a 4-digit string, or None.
    """
    lines = text.splitlines()
    candidate_years = []

    for line in lines:
        # Ignore years in revision notices
        if "rev" not in line.lower():
            match = re.search(r"\b(19|20)\d{2}\b", line)
            if match:
                candidate_years.append(int(match.group(0)))

    if candidate_years:
        if form_keyword:
            # If a form keyword is specified, prioritize year on the same line
            for line in lines:
                if form_keyword.lower() in line.lower():
                    match = re.search(r"\b(19|20)\d{2}\b", line)
                    if match:
                        return match.group(0)

        # Fallback to most frequently appearing year in the text
        most_common_year = Counter(candidate_years).most_common(1)[0][0]
        return str(most_common_year)

    # Fallback check for 'calendar year' in text and extract year from empty form field
    if "calendar year" in text.lower():
        for field in form_fields.values():
            value = str(field.get("/V", "")).strip()
            if not value:
                return None  # Field exists but is empty
            if re.fullmatch(r"\d{2}", value):
                year_int = int(value)
                if 0 <= year_int <= 30:
                    return f"20{value.zfill(2)}"

    return None  # No valid year found


class RuleBasedClassifier:
    """
    Rule-based classifier that matches tax form types based on normalized text.
    """

    def __init__(self, text: str):
        self.text = normalize(text)

    def match(self, keywords: list[str]) -> bool:
        """
        Checks if any keyword exists in the normalized text.
        """
        return any(keyword in self.text for keyword in keywords)

    def classify(self) -> str:
        """
        Determines the form type using fixed keyword rules.

        Returns:
            A label such as 'W2', '1040', '1099', etc.
        """
        if self.match(["form w-2", "wage and tax statement"]):
            return "W2"
        if self.match(["form 1040", "u.s. individual income tax return"]):
            return "1040"
        if self.match(["form 1099", "1099-div", "1099-int", "1099-misc"]):
            return "1099"
        if self.match(["form 1098", "mortgage interest statement"]):
            return "1098"
        if self.match(["driver license", "identity card", "passport", "nationality", "birth", "gender"]):
            return "ID Card"
        return "OTHER"  # If no known patterns matched


@app.post("/classify")
async def classify(file: Optional[UploadFile] = File(None)):
    """
    FastAPI endpoint for PDF classification.
    Accepts a file upload and returns document type and year.

    Returns:
        JSON response:
        {
            "document_type": "W2" | "1040" | "1099" | "ID Card" | "OTHER" | "Handwritten note",
            "year": "2022" | null
        }
    """
    if not file:
        return {"error": "No file uploaded"}

    pdf_bytes = await file.read()

    # Try extracting visible and structured content first
    form_fields_text, form_fields = extract_form_fields(pdf_bytes)
    tables_text = extract_tables_text(pdf_bytes)
    full_text = extract_full_text(pdf_bytes)

    combined_text = "\n".join([tables_text, full_text]).strip()

    if combined_text:
        doc_type = RuleBasedClassifier(combined_text).classify()
        year = extract_year(combined_text, form_fields)
        return {"document_type": doc_type, "year": year}

    # If no usable text found, fallback to OCR
    ocr_text = extract_ocr_text(pdf_bytes)
    if ocr_text:
        doc_type = RuleBasedClassifier(ocr_text).classify()
        year = extract_year(ocr_text, form_fields)
        return {
            "document_type": doc_type if doc_type != "OTHER" else "Handwritten note",
            "year": year
        }

    # If all methods fail
    return {"document_type": "OTHER", "year": None}
