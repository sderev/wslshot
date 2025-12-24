"""Custom exceptions for wslshot."""


class WslshotError(Exception):
    """Base exception for wslshot errors."""


class ConfigurationError(WslshotError):
    """Configuration-related errors."""


class ScreenshotNotFoundError(WslshotError):
    """Screenshot not found errors."""


class GitError(WslshotError):
    """Git operation errors."""


class ValidationError(WslshotError):
    """Input validation errors."""


class SecurityError(WslshotError):
    """Security violation errors (symlinks, permissions, etc.)."""
