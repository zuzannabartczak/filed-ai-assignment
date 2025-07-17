import os
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

# API endpoint
API_URL = "http://127.0.0.1:8000/classify"

# Folder containing sample PDFs
SAMPLES_DIR = "samples"

def classify_pdf(file_path: str):
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(API_URL, files=files)
            response.raise_for_status()

            logger.info(f"\n Processed: {os.path.basename(file_path)}")
            logger.info(f" Response: {response.json()}\n")

    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for {file_path}: {str(e)}")

def main():
    if not os.path.isdir(SAMPLES_DIR):
        logger.error(f"Samples directory does not exist: {SAMPLES_DIR}")
        return

    pdf_files = [f for f in os.listdir(SAMPLES_DIR) if f.lower().endswith(".pdf")]

    if not pdf_files:
        logger.warning("No PDF files found in 'samples' folder.")
        return

    for filename in pdf_files:
        file_path = os.path.join(SAMPLES_DIR, filename)
        classify_pdf(file_path)

if __name__ == "__main__":
    main()
