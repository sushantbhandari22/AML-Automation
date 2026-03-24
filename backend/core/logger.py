"""
Standardized JSON Logging Module for the AML Report Generation System.
Uses `contextvars` to automatically inject `session_id` into all log records,
enabling request traceability without passing `session_id` continuously.
"""

import logging
import json
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from contextvars import ContextVar

# Global context var set by FastAPI endpoints
session_ctx_var: ContextVar[str] = ContextVar("session_id", default="system")

class JSONFormatter(logging.Formatter):
    """Formats log records as JSON for easy parsing by centralized logging systems."""
    
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "session_id": session_ctx_var.get(),
            "message": record.getMessage(),
        }
        
        # Include exception traceback if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        # Extract custom 'extra' properties passed by the caller
        if hasattr(record, "extra_attrs") and isinstance(record.extra_attrs, dict):
            for key, val in record.extra_attrs.items():
                if key not in log_record:
                    log_record[key] = val
                    
        return json.dumps(log_record)


def setup_logger(name: str) -> logging.Logger:
    """Initialize a logger with the JSON formatter if not already configured."""
    logger = logging.getLogger(name)
    
    # Prevents duplicate handlers if called multiple times
    if not logger.handlers:
        formatter = JSONFormatter()
        
        # 1. Console Handler (prints to terminal)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 2. File Handler (saves to backend/logs/)
        # Create logs directory if it doesn't exist relative to this file's path
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # RotatingFileHandler keeps file sizes manageable (e.g., max 10MB per file, keep 5 backups)
        log_file_path = os.path.join(log_dir, "system.log")
        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Ensure we don't pass logs to root logger unnecessarily
        logger.propagate = False 
        
    logger.setLevel(logging.INFO)
    return logger


class ContextAdapter(logging.LoggerAdapter):
    """Adapter to securely inject arbitrary 'extra' fields into the log record."""
    
    def process(self, msg, kwargs):
        # We move any 'extra' dict passed to the log call into a dedicated
        # 'extra_attrs' key for the JSONFormatter to extract safely.
        extra = kwargs.get("extra", {})
        kwargs["extra"] = {"extra_attrs": extra}
        return msg, kwargs


def get_logger(name: str) -> ContextAdapter:
    """Public factory method to get a configured JSON logger adapter."""
    logger = setup_logger(name)
    return ContextAdapter(logger, {})
