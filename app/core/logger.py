# app/core/logger.py
import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def setup_logging():
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO) # Set default logging level

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (for rotation)
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'app.log'),
        maxBytes=1024 * 1024 * 5, # 5 MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Set specific log levels for libraries if needed (e.g., uvicorn)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)