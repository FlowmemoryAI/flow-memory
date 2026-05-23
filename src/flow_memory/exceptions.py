"""Domain exceptions."""


class FlowMemoryError(Exception):
    """Base exception for Flow Memory."""


class SafetyRejection(FlowMemoryError):
    """Raised when a plan is rejected by safety policy."""


class ToolNotFound(FlowMemoryError):
    """Raised when a tool cannot be found."""


class PermissionDenied(FlowMemoryError):
    """Raised when an action lacks permission."""
