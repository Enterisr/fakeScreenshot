"""Application entry point for the Fake News Screenshot Validator.

Loads environment variables from .env and starts the uvicorn server.

Validates: Requirements 7.1, 7.3
"""

import os

import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=True,
    )
