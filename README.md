## Overview

The service exposes a single endpoint:

### `POST /classify`

Accepts a PDF file upload and returns a JSON response containing:

* **`document_type`**: One of the supported document types — `"1040"`, `"W2"`, `"1099"`, `"1098"`, `"ID Card"`, `"Handwritten note"`, or `"OTHER"`.
* **`year`**: The year the document was issued or pertains to, if detectable.

---

## Core Functionality

The classification and year extraction pipeline operates as follows:

### PDF Content Extraction

* Extracts text from multiple sources within the PDF:

  * Interactive form fields
  * Extracted tables
  * Full page text content
* Falls back to **OCR-based text extraction** if no usable text is found.

### Document Classification

* Uses rule-based keyword matching on the combined extracted text to classify the document type.

### Year Extraction

* Identifies candidate years within the extracted text.
* Prioritizes years found on lines containing document-identifying keywords.
* Excludes **revision** or **form version** years based on contextual keywords.
* For forms referencing a calendar year with interactive fields, reconstructs the full year from two-digit fields with validation.

---

## Technology Stack

* **FastAPI** – API framework serving the classification endpoint.
* **pdfplumber** – Extracts text and tables from PDFs.
* **pypdf** – Accesses interactive form fields in PDFs.
* **pytesseract** – Performs OCR on scanned PDF pages as a fallback.
* **Pillow (PIL)** – Image processing for OCR enhancement.

---

## Running the Service

* The application is served via **Uvicorn**.
* It accepts **multipart form uploads** of PDF files at `/classify`.
* Responses are **JSON-formatted** with classification results.

---

## Extensibility

* The rule-based classifier is designed to be easily extended with additional document types by updating keyword lists.
* The year extraction logic can be adapted to handle more complex date patterns or validation rules as needed.

---
