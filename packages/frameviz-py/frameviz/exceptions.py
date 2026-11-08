"""
Custom exception types for FrameViz Python SDK.

Provides a hierarchy of exceptions for better error handling:
- FrameVizError: Base exception for all FrameViz errors
- ConnectionError: WebSocket connection failures
- ProtocolError: Protocol-level errors (version mismatch, invalid messages)
- TimeoutError: Command and connection timeouts
- ValidationError: Input validation failures
"""
from __future__ import annotations


class FrameVizError(Exception):
    """Base exception for all FrameViz errors.
    
    All FrameViz-specific exceptions inherit from this class,
    allowing users to catch all FrameViz errors with a single except clause.
    
    Example:
        try:
            viz.add_box(size=[1, 1, 1])
        except FrameVizError as e:
            print(f"FrameViz error: {e}")
    """
    pass


class ConnectionError(FrameVizError):
    """Raised when WebSocket connection fails.
    
    This error occurs when:
    - Cannot establish connection to the Host
    - Connection is unexpectedly closed
    - Network issues during communication
    
    Attributes:
        url: The WebSocket URL that failed to connect
        cause: The underlying exception that caused the failure
    """
    
    def __init__(self, message: str, url: str = None, cause: Exception = None):
        super().__init__(message)
        self.url = url
        self.cause = cause


class ProtocolError(FrameVizError):
    """Raised when there's a protocol-level error.
    
    This error occurs when:
    - Protocol version mismatch between client and Host
    - Invalid message format received
    - Command rejected by Host with an error code
    
    Attributes:
        code: Error code returned by the Host (if applicable)
        details: Additional error details from the Host
    """
    
    def __init__(self, message: str, code: str = None, details: dict = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class TimeoutError(FrameVizError):
    """Raised when an operation times out.
    
    This error occurs when:
    - Connection attempt exceeds timeout
    - Command response not received within timeout
    - Event wait exceeds timeout
    
    Attributes:
        operation: Description of the operation that timed out
        timeout_seconds: The timeout value that was exceeded
    """
    
    def __init__(self, message: str, operation: str = None, timeout_seconds: float = None):
        super().__init__(message)
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class ValidationError(FrameVizError):
    """Raised when input validation fails.
    
    This error occurs when:
    - Vector has wrong number of components
    - Color value is out of range
    - Negative values for positive-only parameters
    - Invalid parameter combinations
    
    Attributes:
        parameter: Name of the parameter that failed validation
        value: The invalid value that was provided
        constraint: Description of the validation constraint
    """
    
    def __init__(self, message: str, parameter: str = None, value: any = None, constraint: str = None):
        super().__init__(message)
        self.parameter = parameter
        self.value = value
        self.constraint = constraint


class ResourceError(FrameVizError):
    """Raised when there's a resource management error.
    
    This error occurs when:
    - Buffer creation fails
    - Object handle is invalid
    - Scene or view not found
    
    Attributes:
        resource_type: Type of resource (buffer, object, scene, view)
        resource_id: ID of the resource
    """
    
    def __init__(self, message: str, resource_type: str = None, resource_id: str = None):
        super().__init__(message)
        self.resource_type = resource_type
        self.resource_id = resource_id
