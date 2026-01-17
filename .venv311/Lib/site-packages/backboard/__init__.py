"""
Backboard API Python SDK

A developer-friendly Python SDK for the Backboard API.
Build conversational AI applications with persistent memory and intelligent document processing.
"""

__version__ = "1.4.7"

from .client import BackboardClient
from .models import (
    Assistant,
    Thread, 
    Document,
    Message,
    ToolDefinition,
    FunctionDefinition,
    ToolParameters,
    ToolParameterProperties,
    ToolCall,
    ToolCallFunction,
    AttachmentInfo,
    MessageResponse,
    ToolOutputsResponse,
    SubmitToolOutputsRequest,
    ToolOutput,
    Memory,
    MemoryCreate,
    MemoryUpdate,
    MemoriesListResponse,
    MemoryStats
)
from .exceptions import (
    BackboardError,
    BackboardAPIError,
    BackboardValidationError,
    BackboardNotFoundError,
    BackboardRateLimitError,
    BackboardServerError
)

__all__ = [
    "BackboardClient",
    "Assistant",
    "Thread",
    "Document", 
    "Message",
    "ToolDefinition",
    "FunctionDefinition",
    "ToolParameters",
    "ToolParameterProperties",
    "ToolCall",
    "ToolCallFunction",
    "AttachmentInfo",
    "MessageResponse",
    "ToolOutputsResponse",
    "SubmitToolOutputsRequest",
    "ToolOutput",
    "Memory",
    "MemoryCreate",
    "MemoryUpdate",
    "MemoriesListResponse",
    "MemoryStats",
    "BackboardError",
    "BackboardAPIError",
    "BackboardValidationError", 
    "BackboardNotFoundError",
    "BackboardRateLimitError",
    "BackboardServerError"
]
