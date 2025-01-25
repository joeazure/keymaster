"""Secure API key management for the services you use, including AI services."""

import os
import sys
import logging
import structlog
from typing import Any, Dict

__version__ = "0.1.1"

# Create .keymaster/logs directory if it doesn't exist
log_dir = os.path.expanduser("~/.keymaster/logs")
os.makedirs(log_dir, exist_ok=True)

# Configure logging to write to file
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "keymaster.log"))
    ]
)

# Configure structlog to write to file only, not console
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
) 