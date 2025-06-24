"""
Centralized logging configuration with colored output
"""
import logging
import sys
import colorlog
from typing import Optional


def setup_colored_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    module_name: Optional[str] = None
) -> logging.Logger:
    """
    Setup colored logging configuration
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        module_name: Optional module name for the logger
        
    Returns:
        Configured logger instance
    """
    # Color scheme
    log_colors = {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
    
    # Console formatter with colors
    console_formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s - %(name)-20s - %(levelname)-8s%(reset)s %(blue)s%(message)s',
        datefmt='%H:%M:%S',
        log_colors=log_colors,
        secondary_log_colors={
            'message': {
                'DEBUG': 'white',
                'INFO': 'white',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red'
            }
        }
    )
    
    # Get logger
    logger = logging.getLogger(module_name) if module_name else logging.getLogger()
    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers = []  # Clear existing handlers
    
    # Console handler
    console_handler = colorlog.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(getattr(logging, level.upper()))
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)-20s - %(levelname)-8s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(getattr(logging, level.upper()))
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with colored output
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # If logger doesn't have handlers, it will use root logger's handlers
    if not logger.handlers and not logging.getLogger().handlers:
        # Setup default colored logging if not already configured
        setup_colored_logging()
    
    return logger


# Log level indicators for better visibility
class LogSymbols:
    """Unicode symbols for different log levels"""
    SUCCESS = "✅"
    INFO = "ℹ️"
    WARNING = "⚠️"
    ERROR = "❌"
    DEBUG = "🔍"
    ARROW = "➜"
    CHECK = "✓"
    CROSS = "✗"
    BULLET = "•"