import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from contextvars import ContextVar

# Colors
GREY = "\x1b[38;20m"
GREEN = "\x1b[32;20m"
YELLOW = "\x1b[33;20m"
RED = "\x1b[31;20m"
BOLD_RED = "\x1b[31;1m"
RESET = "\x1b[0m"

# Global context vars for audit trail
session_ctx_var: ContextVar[str] = ContextVar("session_id", default="system")
user_ctx_var: ContextVar[str] = ContextVar("user", default="system")
ip_ctx_var: ContextVar[str] = ContextVar("ip_address", default="0.0.0.0")

class ColumnarFormatter(logging.Formatter):
    """Formats log records into perfectly aligned columns (Date, Level, User, IP, Message)."""
    
    LEVEL_COLORS = {
        logging.DEBUG: GREY,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def __init__(self, use_color=False):
        super().__init__()
        self.use_color = use_color

    def format(self, record):
        # 1. Date/Time format: [YYYY-MM-DD HH:MM:SS]
        date_time = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # 2. Level formatting
        level_name = record.levelname
        if self.use_color:
            color = self.LEVEL_COLORS.get(record.levelno, RESET)
            level_str = f"{color}{level_name:^8}{RESET}"
        else:
            level_str = f"{level_name:^8}"
        
        # 3. User & IP (From ContextVars)
        user = user_ctx_var.get()
        ip = ip_ctx_var.get()
        
        user_str = f"{user[:12]:<12}"
        ip_str = f"{ip:^15}"
        
        # 4. Message
        message = record.getMessage()
        
        # Final Format: [DATE TIME] | LEVEL | USER | IP | MESSAGE
        full_msg = f"[{date_time}] | {level_str} | {user_str} | {ip_str} | {message}"
        
        # Managed Exception Handling: Just show the summary instead of a full terminal-style traceback
        if record.exc_info:
            etype, evalue, tb = record.exc_info
            # Get the actual line where the error happened
            import traceback
            summary = traceback.extract_tb(tb)[-1]
            
            error_prefix = f" >>> {etype.__name__}: {evalue} (at {os.path.basename(summary.filename)}:{summary.lineno})"
            if self.use_color:
                compact_exc = f" {BOLD_RED}{error_prefix}{RESET}"
            else:
                compact_exc = f" {error_prefix}"
                
            full_msg += f"\n{compact_exc}"
            
        return full_msg


def setup_logger(name: str) -> logging.Logger:
    """Initialize a logger with Columnar formatters (Color for console, Plain for file)."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # 1. Console Handler (with Colors)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColumnarFormatter(use_color=True))
        logger.addHandler(console_handler)
        
        # 2. File Handler (Plain text for universal compatibility)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        log_file_path = os.path.join(log_dir, "system.log")
        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setFormatter(ColumnarFormatter(use_color=False))
        logger.addHandler(file_handler)
        
        logger.propagate = False 
        
    logger.setLevel(logging.INFO)
    return logger


class ContextAdapter(logging.LoggerAdapter):
    """Adapter to securely inject arbitrary 'extra' fields into the log record."""
    
    # Standard LogRecord attributes that cannot be overwritten by 'extra'
    RESERVED_KEYS = {
        'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
        'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
        'message', 'msg', 'name', 'pathname', 'process', 'processName',
        'relativeCreated', 'stack_info', 'thread', 'threadName'
    }

    def process(self, msg, kwargs):
        if "extra" in kwargs:
            # Filter out any keys that would cause a KeyError in logging.LogRecord
            filtered_extra = {
                k: v for k, v in kwargs["extra"].items() 
                if k not in self.RESERVED_KEYS
            }
            kwargs["extra"] = filtered_extra
        return msg, kwargs


def get_logger(name: str) -> ContextAdapter:
    """Public factory method to get a configured columnar logger adapter."""
    logger = setup_logger(name)
    return ContextAdapter(logger, {})
