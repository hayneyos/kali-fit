import logging
import os
from datetime import datetime
from pathlib import Path

# Import local config settings
from backend.app_recipe.config import settings

class LoggerConfig:
    def __init__(self, log_dir: str = "logs", log_level: int = logging.INFO, console_output: bool = True):
        self.log_dir = log_dir
        self.log_level = log_level
        self.console_output = console_output
        self._setup_log_directory()
        
    def _setup_log_directory(self):
        """Create log directory if it doesn't exist."""
        os.makedirs(self.log_dir, exist_ok=True)
        
    def get_log_file_path(self, name: str) -> str:
        """Get the path for a log file."""
        timestamp = datetime.now().strftime("%Y%m%d")
        return os.path.join(self.log_dir, f"{name}_{timestamp}.log")
    
    def setup_logger(self, name: str, level: int = None) -> logging.Logger:
        """Set up and return a logger instance."""
        logger = logging.getLogger(name)
        logger.setLevel(level if level is not None else self.log_level)
        
        # Create handlers
        log_file = self.get_log_file_path(name)
        file_handler = logging.FileHandler(log_file)
        
        # Create formatters and add it to handlers
        log_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(log_format)
        
        # Add handlers to the logger
        if not logger.hasHandlers():
            logger.addHandler(file_handler)
            if self.console_output:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(log_format)
                logger.addHandler(console_handler)
        
        return logger

# Create a default logger configuration
logger_config = LoggerConfig()

def get_logger(name: str, level: int = None) -> logging.Logger:
    """Get a logger instance with the given name and level."""
    return logger_config.setup_logger(name, level) 