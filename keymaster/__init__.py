"""
Keymaster: Secure API key management for AI services.
"""
import os
import sys
import logging
import structlog
from typing import Any, Dict

__version__ = "0.1.0"
__author__ = "Joe Azure"

# Create .keymaster/logs directory if it doesn't exist
log_dir = os.path.expanduser("~/.keymaster/logs")
os.makedirs(log_dir, exist_ok=True)

# Configure structlog to write to file
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(
        file=open(os.path.join(log_dir, "keymaster.log"), "a")
    ),
    cache_logger_on_first_use=True,
) 