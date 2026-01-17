"""
Backboard API data models using Pydantic
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum
import uuid
import json

from pydantic import BaseModel, Field, field_validator, computed_field


class DocumentStatus(str, Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class MessageRole(str, Enum):
    """Message role types"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ToolCallFunction(BaseModel):
    """Tool call function definition"""
    name: str
    arguments: str  # JSON string of arguments
    
    @computed_field
    @property
    def parsed_arguments(self) -> Dict[str, Any]:
        """Parse arguments JSON string into a dictionary"""
        try:
            return json.loads(self.arguments)
        except (json.JSONDecodeError, TypeError):
            return {}


class ToolCall(BaseModel):
    """Tool call from assistant response"""
    id: str
    type: str
    function: ToolCallFunction


class ToolParameterProperties(BaseModel):
    """Tool parameter property definition"""
    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None
    properties: Optional[Dict[str, Any]] = None
    items: Optional[Dict[str, Any]] = None


class ToolParameters(BaseModel):
    """Tool parameters definition"""
    type: str = "object"
    properties: Dict[str, ToolParameterProperties] = Field(default_factory=dict)
    required: Optional[List[str]] = None


class FunctionDefinition(BaseModel):
    """Function definition for tools"""
    name: str
    description: Optional[str] = None
    parameters: ToolParameters


class ToolDefinition(BaseModel):
    """Tool definition"""
    type: str = "function"
    function: Optional[FunctionDefinition] = None


class Assistant(BaseModel):
    """Assistant model"""
    assistant_id: uuid.UUID
    name: str
    description: Optional[str] = None
    tools: Optional[List[ToolDefinition]] = None
    embedding_provider: Optional[str] = None
    embedding_model_name: Optional[str] = None
    embedding_dims: Optional[int] = None
    created_at: datetime

    @field_validator('created_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v


class AttachmentInfo(BaseModel):
    """Message attachment information"""
    document_id: uuid.UUID
    filename: str
    status: str
    file_size_bytes: int
    summary: Optional[str] = None


class Message(BaseModel):
    """Message model"""
    message_id: uuid.UUID
    role: MessageRole
    content: Optional[str] = None
    created_at: datetime
    status: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = Field(default=None, alias='metadata')
    attachments: Optional[List[AttachmentInfo]] = None

    @field_validator('created_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    class Config:
        populate_by_name = True


class LatestMessageInfo(BaseModel):
    """Reduced latest message payload (unique fields only)"""
    metadata_: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    created_at: datetime

    @field_validator('created_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    class Config:
        populate_by_name = True


class Thread(BaseModel):
    """Thread model"""
    thread_id: uuid.UUID
    created_at: datetime
    messages: List[Message] = Field(default_factory=list)
    metadata_: Optional[Dict[str, Any]] = Field(default=None, alias='metadata')

    @field_validator('created_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    class Config:
        populate_by_name = True


class Document(BaseModel):
    """Document model"""
    document_id: uuid.UUID
    filename: str
    status: DocumentStatus
    created_at: datetime
    status_message: Optional[str] = None
    summary: Optional[str] = None
    updated_at: Optional[datetime] = None
    file_size_bytes: Optional[int] = None
    total_tokens: Optional[int] = None
    chunk_count: Optional[int] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    document_type: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = Field(default=None, alias='metadata')

    @field_validator('created_at', 'updated_at', 'processing_started_at', 'processing_completed_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str) and v:
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    class Config:
        populate_by_name = True


class MessageResponse(BaseModel):
    """Response from adding a message to a thread"""
    message: str
    thread_id: uuid.UUID
    content: Optional[str] = None
    message_id: uuid.UUID
    role: MessageRole
    status: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    run_id: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    created_at: Optional[datetime] = None
    attachments: Optional[List[AttachmentInfo]] = None
    timestamp: datetime

    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v
    
    def __str__(self):
        """Return a clean string representation with readable values"""
        return (
            f"MessageResponse(\n"
            f"  message='{self.message}',\n"
            f"  thread_id='{self.thread_id}',\n"
            f"  content='{self.content}',\n"
            f"  message_id='{self.message_id}',\n"
            f"  role='{self.role.value}',\n"
            f"  status='{self.status}',\n"
            f"  tool_calls={self.tool_calls},\n"
            f"  run_id='{self.run_id}',\n"
            f"  model_provider='{self.model_provider}',\n"
            f"  model_name='{self.model_name}',\n"
            f"  input_tokens={self.input_tokens},\n"
            f"  output_tokens={self.output_tokens},\n"
            f"  total_tokens={self.total_tokens},\n"
            f"  created_at='{self.created_at.isoformat() if self.created_at else None}',\n"
            f"  attachments={self.attachments},\n"
            f"  timestamp='{self.timestamp.isoformat()}'\n"
            f")"
        )


class ToolOutput(BaseModel):
    """Tool output for submitting tool results"""
    tool_call_id: str
    output: str


class SubmitToolOutputsRequest(BaseModel):
    """Request for submitting tool outputs"""
    tool_outputs: List[ToolOutput]


class ToolOutputsResponse(BaseModel):
    """Response from submitting tool outputs"""
    message: str
    thread_id: uuid.UUID
    run_id: str
    content: Optional[str] = None
    message_id: uuid.UUID
    role: MessageRole
    status: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    created_at: Optional[datetime] = None
    timestamp: datetime

    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v
    
    def __str__(self):
        """Return a clean string representation with readable values"""
        return (
            f"ToolOutputsResponse(\n"
            f"  message='{self.message}',\n"
            f"  thread_id='{self.thread_id}',\n"
            f"  run_id='{self.run_id}',\n"
            f"  content='{self.content}',\n"
            f"  message_id='{self.message_id}',\n"
            f"  role='{self.role.value}',\n"
            f"  status='{self.status}',\n"
            f"  tool_calls={self.tool_calls},\n"
            f"  model_provider='{self.model_provider}',\n"
            f"  model_name='{self.model_name}',\n"
            f"  input_tokens={self.input_tokens},\n"
            f"  output_tokens={self.output_tokens},\n"
            f"  total_tokens={self.total_tokens},\n"
            f"  created_at='{self.created_at.isoformat() if self.created_at else None}',\n"
            f"  timestamp='{self.timestamp.isoformat()}'\n"
            f")"
        )


# Memory Models

class Memory(BaseModel):
    """Memory model"""
    id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    score: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryCreate(BaseModel):
    """Schema for creating a memory"""
    content: str
    metadata: Optional[Dict[str, Any]] = None


class MemoryUpdate(BaseModel):
    """Schema for updating a memory"""
    content: str
    metadata: Optional[Dict[str, Any]] = None


class MemoriesListResponse(BaseModel):
    """Response for listing memories"""
    memories: List[Memory]
    total_count: int


class MemoryStats(BaseModel):
    """Memory statistics"""
    total_memories: int = 0
    last_updated: Optional[str] = None
    limits: Optional[Dict[str, Any]] = None