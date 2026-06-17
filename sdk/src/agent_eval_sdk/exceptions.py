"""SDK Custom Exceptions."""


class SDKError(Exception):
    """Base SDK exception."""
    pass


class TaskNotCreatedError(SDKError):
    """Called record method before start_task."""
    pass


class ReportingError(SDKError):
    """Data reporting failed."""
    pass


class ConfigError(SDKError):
    """Configuration error."""
    pass
