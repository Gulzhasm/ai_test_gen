"""
Structured logging for metrics and events.

Provides JSON-formatted logs with timestamps and structured fields.
"""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter."""

    EXCLUDED_ATTRS = {
        'name', 'msg', 'args', 'levelname', 'levelno',
        'pathname', 'filename', 'module', 'exc_info',
        'exc_text', 'stack_info', 'lineno', 'funcName',
        'created', 'msecs', 'relativeCreated', 'thread',
        'threadName', 'processName', 'process', 'message',
        'asctime'
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON formatted string
        """
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "logger": record.name,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in self.EXCLUDED_ATTRS:
                # Handle non-serializable objects
                try:
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return json.dumps(log_data)


class StructuredLogger:
    """Structured logger wrapper with convenience methods."""

    def __init__(
        self,
        name: str = "test_gen.metrics",
        level: int = logging.INFO,
        enable_console: bool = True,
        enable_file: bool = False,
        log_file: Optional[str] = None
    ):
        """Initialize structured logger.

        Args:
            name: Logger name
            level: Logging level
            enable_console: Output to console
            enable_file: Output to file
            log_file: Path to log file
        """
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.handlers = []  # Clear existing handlers

        formatter = StructuredFormatter()

        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

        if enable_file and log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

    def info(self, event: str, **kwargs: Any) -> None:
        """Log info level message.

        Args:
            event: Event name/message
            **kwargs: Additional structured fields
        """
        self._logger.info(event, extra=kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        """Log warning level message.

        Args:
            event: Event name/message
            **kwargs: Additional structured fields
        """
        self._logger.warning(event, extra=kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        """Log error level message.

        Args:
            event: Event name/message
            **kwargs: Additional structured fields
        """
        self._logger.error(event, extra=kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        """Log debug level message.

        Args:
            event: Event name/message
            **kwargs: Additional structured fields
        """
        self._logger.debug(event, extra=kwargs)

    def log_generation(
        self,
        request_id: str,
        provider: str,
        model: str,
        duration_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        cache_hit: bool = False,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """Log an LLM generation request.

        Args:
            request_id: Unique request identifier
            provider: LLM provider name
            model: Model name
            duration_ms: Request duration in milliseconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_usd: Estimated cost in USD
            cache_hit: Whether response was from cache
            success: Whether request succeeded
            error: Error message if failed
        """
        level = logging.INFO if success else logging.ERROR
        self._logger.log(
            level,
            "llm_generation",
            extra={
                "request_id": request_id,
                "provider": provider,
                "model": model,
                "duration_ms": round(duration_ms, 2),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "cost_usd": round(cost_usd, 6),
                "cache_hit": cache_hit,
                "success": success,
                "error": error
            }
        )

    def log_parsing(
        self,
        parser: str,
        duration_ms: float,
        success: bool,
        confidence: float = 1.0,
        fallback_used: bool = False
    ) -> None:
        """Log a parsing operation.

        Args:
            parser: Parser type used
            duration_ms: Duration in milliseconds
            success: Whether parsing succeeded
            confidence: Confidence score
            fallback_used: Whether fallback was used
        """
        self._logger.info(
            "parsing_completed",
            extra={
                "parser": parser,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "confidence": round(confidence, 3),
                "fallback_used": fallback_used
            }
        )

    def log_cache_operation(
        self,
        cache_type: str,
        operation: str,
        key: str,
        hit: Optional[bool] = None
    ) -> None:
        """Log a cache operation.

        Args:
            cache_type: Type of cache (memory/file)
            operation: Operation type (get/set/delete)
            key: Cache key (truncated for privacy)
            hit: For get operations, whether it was a hit
        """
        self._logger.debug(
            "cache_operation",
            extra={
                "cache_type": cache_type,
                "operation": operation,
                "key_prefix": key[:16] if len(key) > 16 else key,
                "hit": hit
            }
        )

    def log_test_generation(
        self,
        story_id: int,
        num_test_cases: int,
        duration_ms: float,
        provider: Optional[str] = None
    ) -> None:
        """Log test case generation completion.

        Args:
            story_id: Story ID
            num_test_cases: Number of test cases generated
            duration_ms: Total duration
            provider: LLM provider used (if any)
        """
        self._logger.info(
            "test_generation_completed",
            extra={
                "story_id": story_id,
                "num_test_cases": num_test_cases,
                "duration_ms": round(duration_ms, 2),
                "provider": provider
            }
        )
