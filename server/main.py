"""Main FastAPI application for the Fake News Screenshot Validator.

Exposes /health and /validate-screenshot endpoints.
Initializes the OCR Engine at startup via lifespan context manager.

Validates: Requirements 1.1, 1.2, 1.3, 5.1, 5.2, 5.3, 5.4, 6.1, 7.1, 7.2
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from server.engines.ocr_engine import OCREngine
from server.engines.verification_engine import VerificationEngine
from server.models.schemas import ValidationResponse
from server.utils.image_validator import validate_image

logger = logging.getLogger(__name__)

# Processing timeout per request (seconds)
PROCESSING_TIMEOUT = 30

# Global engine references (initialized at startup)
ocr_engine: OCREngine | None = None
verification_engine: VerificationEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize resources at startup."""
    global ocr_engine, verification_engine

    logger.info("Initializing OCR Engine...")
    ocr_engine = OCREngine()
    logger.info("OCR Engine initialized successfully")

    verification_engine = VerificationEngine()
    logger.info("Verification Engine initialized")

    yield

    # Cleanup (if needed)
    ocr_engine = None
    verification_engine = None
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Fake News Screenshot Validator",
    description="Validates news screenshots by extracting text via OCR and verifying against web sources.",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve the upload UI at the root
STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the upload UI."""
    html_file = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint.

    Returns HTTP 200 with status indicating the server is operational.
    Validates: Requirement 6.1
    """
    return {"status": "ok"}


@app.post("/validate-screenshot")
async def validate_screenshot(file: UploadFile = File(...)) -> JSONResponse:
    """Validate a news screenshot for authenticity.

    Pipeline:
    1. Read uploaded file bytes
    2. Validate image format and size
    3. Extract text via OCR
    4. If no text extracted, return confidence 0.0
    5. Verify via web search
    6. Return ValidationResponse

    Validates: Requirements 1.1, 1.2, 1.3, 5.1, 5.2, 5.3, 5.4, 7.2
    """
    # Read file bytes
    image_bytes = await file.read()

    # Validate image (format + size)
    is_valid, error_message, status_code = validate_image(image_bytes)
    if not is_valid:
        return JSONResponse(
            status_code=status_code,
            content={"error": error_message},
        )

    # Process with timeout
    try:
        result = await asyncio.wait_for(
            _process_validation(image_bytes),
            timeout=PROCESSING_TIMEOUT,
        )
        return JSONResponse(status_code=200, content=result)
    except asyncio.TimeoutError:
        logger.error("Validation processing timed out after %d seconds", PROCESSING_TIMEOUT)
        response = ValidationResponse(
            is_real=False,
            confidence=0.0,
            extracted_text="",
            sources=[],
            details={"error": "Processing timed out"},
        )
        return JSONResponse(status_code=200, content=response.model_dump())


async def _process_validation(image_bytes: bytes) -> dict:
    """Run the validation pipeline (OCR → verification → response).

    Runs in a thread to avoid blocking the event loop with CPU-bound OCR.

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        Dictionary representation of ValidationResponse.
    """
    loop = asyncio.get_event_loop()

    # Run OCR in a thread (CPU-bound)
    ocr_result = await loop.run_in_executor(None, ocr_engine.extract_text, image_bytes)

    # If no text extracted, return early with confidence 0.0
    if not ocr_result.full_text:
        response = ValidationResponse(
            is_real=False,
            confidence=0.0,
            extracted_text="",
            sources=[],
            details={"error": "No text could be extracted"},
        )
        return response.model_dump()

    # Run verification using the headline (most prominent text) for better search results
    search_text = ocr_result.headline if ocr_result.headline else ocr_result.full_text
    verification_result = await loop.run_in_executor(
        None, verification_engine.verify, search_text
    )

    # Build response
    details = None
    if verification_result.error:
        details = {"error": verification_result.error}

    response = ValidationResponse(
        is_real=verification_result.is_real,
        confidence=verification_result.confidence,
        extracted_text=ocr_result.full_text,
        sources=verification_result.sources,
        details=details,
    )
    return response.model_dump()
