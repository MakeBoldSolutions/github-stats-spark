"""Logging utility for Stats Spark."""

import sys
from datetime import datetime
from typing import Optional


class Logger:
    """Simple logger for stdout/stderr with timestamps."""

    def __init__(self, name: str = "spark", verbose: bool = False):
        """Initialize logger.

        Args:
            name: Logger name
            verbose: Enable verbose logging
        """
        self.name = name
        self.verbose = verbose

    def _format_message(self, level: str, message: str) -> str:
        """Format a log message with timestamp.

        Args:
            level: Log level (INFO, WARN, ERROR, DEBUG)
            message: Log message

        Returns:
            Formatted log message
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"[{timestamp}] [{self.name}] {level}: {message}"

    def info(self, message: str) -> None:
        """Log an info message to stdout.

        Args:
            message: Info message
        """
        print(self._format_message("INFO", message), file=sys.stdout)

    def warning(self, message: str) -> None:
        """Log a warning message to stderr.

        Args:
            message: Warning message
        """
        print(self._format_message("WARN", message), file=sys.stderr)

    def warn(self, message: str) -> None:
        """Deprecated: use warning() instead."""
        self.warning(message)

    def error(self, message: str, exc_info: bool = False) -> None:
        """Log an error message to stderr.

        Args:
            message: Error message
            exc_info: If true, include exception info from sys.exc_info()
        """
        error_msg = self._format_message("ERROR", message)
        print(error_msg, file=sys.stderr)

        if exc_info:
            import traceback

            traceback.print_exc(file=sys.stderr)

    def debug(self, message: str) -> None:
        """Log a debug message to stdout (only if verbose enabled).

        Args:
            message: Debug message
        """
        if self.verbose:
            print(self._format_message("DEBUG", message), file=sys.stdout)


# Global logger instance
_logger: Optional[Logger] = None


def get_logger(name: str = "spark", verbose: bool = False) -> Logger:
    """Get or create the global logger instance.

    Args:
        name: Logger name
        verbose: Enable verbose logging

    Returns:
        Logger instance
    """
    global _logger
    if _logger is None:
        _logger = Logger(name, verbose)
    return _logger
