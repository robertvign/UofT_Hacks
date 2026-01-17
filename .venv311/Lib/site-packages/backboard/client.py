"""
Backboard API Python client (async only)
"""

import json
import uuid
from typing import Optional, List, Dict, Any, Union, AsyncIterator
from pathlib import Path

import httpx

from .models import (
    Assistant, Thread, Document, Message, MessageResponse,
    ToolOutputsResponse, ToolDefinition, ToolOutput,
    Memory, MemoryCreate, MemoryUpdate, MemoriesListResponse, MemoryStats
)
from .exceptions import (
    BackboardAPIError, BackboardValidationError, BackboardNotFoundError,
    BackboardRateLimitError, BackboardServerError
)


class BackboardClient:
    """
    Async Backboard API client for building conversational AI applications
    with persistent memory and intelligent document processing.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://app.backboard.io/api",
        timeout: int = 30,
    ):
        """
        Initialize the Backboard client (async only)

        Args:
            api_key: Your Backboard API key
            base_url: API base URL (default: https://app.backboard.io/api)
            timeout: Request timeout in seconds (default: 30)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

        # Create async HTTP client
        self._client = httpx.AsyncClient(
            headers={
                "X-API-Key": self.api_key,
                "User-Agent": "backboard-python-sdk/async",
            },
            timeout=self.timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "BackboardClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make HTTP request with error handling (async)."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        headers = {"X-API-Key": self.api_key}
        # Let httpx set Content-Type automatically based on payload

        try:
            response = await self._client.request(
                method=method,
                url=url,
                json=json_data,
                data=data,
                files=files,
                params=params,
                headers=headers,
            )
            if response.status_code >= 400:
                await self._handle_error_response(response)
            return response
        except httpx.TimeoutException:
            raise BackboardAPIError("Request timed out")
        except httpx.NetworkError:
            raise BackboardAPIError("Connection error")
        except httpx.HTTPError as e:
            raise BackboardAPIError(f"Request failed: {str(e)}")

    async def _stream_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = {"X-API-Key": self.api_key}
        if headers:
            request_headers.update(headers)
        try:
            async with self._client.stream(
                method=method,
                url=url,
                json=json_data,
                data=data,
                files=files,
                params=params,
                headers=request_headers,
            ) as response:
                if response.status_code >= 400:
                    await self._handle_error_response(response)
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        try:
                            payload = json.loads(line[6:])
                            # If the backend emits an error event over SSE, raise an SDK exception
                            if isinstance(payload, dict) and payload.get('type') == 'error':
                                error_message = (
                                    payload.get('error')
                                    or payload.get('message')
                                    or "Streaming error"
                                )
                                raise BackboardAPIError(error_message)
                            # Raise for explicit run failure events
                            if isinstance(payload, dict) and payload.get('type') == 'run_failed':
                                error_message = (
                                    payload.get('error')
                                    or payload.get('message')
                                    or "Run failed"
                                )
                                raise BackboardAPIError(error_message)
                            # If a run ends with a non-completed status, raise
                            if (
                                isinstance(payload, dict)
                                and payload.get('type') == 'run_ended'
                                and payload.get('status') not in (None, 'completed')
                            ):
                                status = payload.get('status')
                                raise BackboardAPIError(f"Run ended with status: {status}")
                            yield payload
                        except json.JSONDecodeError:
                            continue
        except httpx.TimeoutException:
            raise BackboardAPIError("Request timed out")
        except httpx.NetworkError:
            raise BackboardAPIError("Connection error")
        except httpx.HTTPError as e:
            raise BackboardAPIError(f"Request failed: {str(e)}")

    async def _handle_error_response(self, response: httpx.Response):
        """Handle error responses from the API (async)."""
        try:
            error_data = response.json()
            error_message = error_data.get('detail', f"HTTP {response.status_code}")
        except Exception:
            try:
                text = response.text
            except Exception:
                text = "<no body>"
            error_message = f"HTTP {response.status_code}: {text}"

        if response.status_code == 400:
            raise BackboardValidationError(error_message, response.status_code, response)
        elif response.status_code == 404:
            raise BackboardNotFoundError(error_message, response.status_code, response)
        elif response.status_code == 429:
            raise BackboardRateLimitError(error_message, response.status_code, response)
        elif response.status_code >= 500:
            raise BackboardServerError(error_message, response.status_code, response)
        else:
            raise BackboardAPIError(error_message, response.status_code, response)

    async def create_assistant(
        self,
        name: str,
        description: Optional[str] = None,
        tools: Optional[List[Union[ToolDefinition, Dict[str, Any]]]] = None,
        embedding_provider: Optional[str] = None,
        embedding_model_name: Optional[str] = None,
        embedding_dims: Optional[int] = None,
    ) -> Assistant:
        data = {"name": name}
        if description:
            data["description"] = description
        if tools:
            data["tools"] = [self._tool_to_dict(tool) for tool in tools]
        if embedding_provider:
            data["embedding_provider"] = embedding_provider
        if embedding_model_name:
            data["embedding_model_name"] = embedding_model_name
        if embedding_dims:
            data["embedding_dims"] = embedding_dims

        response = await self._make_request("POST", "/assistants", json_data=data)
        return Assistant.model_validate(response.json())

    async def list_assistants(self, skip: int = 0, limit: int = 100) -> List[Assistant]:
        params = {"skip": skip, "limit": limit}
        response = await self._make_request("GET", "/assistants", params=params)
        return [Assistant.model_validate(data) for data in response.json()]

    async def get_assistant(self, assistant_id: Union[str, uuid.UUID]) -> Assistant:
        response = await self._make_request("GET", f"/assistants/{assistant_id}")
        return Assistant.model_validate(response.json())

    async def update_assistant(
        self,
        assistant_id: Union[str, uuid.UUID],
        name: Optional[str] = None,
        description: Optional[str] = None,
        tools: Optional[List[Union[ToolDefinition, Dict[str, Any]]]] = None
    ) -> Assistant:
        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if tools is not None:
            data["tools"] = [self._tool_to_dict(tool) for tool in tools]

        response = await self._make_request("PUT", f"/assistants/{assistant_id}", json_data=data)
        return Assistant.model_validate(response.json())

    async def delete_assistant(self, assistant_id: Union[str, uuid.UUID]) -> Dict[str, Any]:
        response = await self._make_request("DELETE", f"/assistants/{assistant_id}")
        return response.json()

    async def create_thread(self, assistant_id: Union[str, uuid.UUID]) -> Thread:
        response = await self._make_request("POST", f"/assistants/{assistant_id}/threads", json_data={})
        return Thread.model_validate(response.json())

    async def list_threads(self, skip: int = 0, limit: int = 100) -> List[Thread]:
        params = {"skip": skip, "limit": limit}
        response = await self._make_request("GET", "/threads", params=params)
        return [Thread.model_validate(data) for data in response.json()]

    async def get_thread(self, thread_id: Union[str, uuid.UUID]) -> Thread:
        response = await self._make_request("GET", f"/threads/{thread_id}")
        return Thread.model_validate(response.json())

    async def delete_thread(self, thread_id: Union[str, uuid.UUID]) -> Dict[str, Any]:
        response = await self._make_request("DELETE", f"/threads/{thread_id}")
        return response.json()

    async def add_message(
        self,
        thread_id: Union[str, uuid.UUID],
        content: Optional[str] = None,
        files: Optional[List[Union[str, Path]]] = None,
        llm_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        stream: bool = False,
        memory: Optional[str] = None
    ) -> Union[MessageResponse, AsyncIterator[Dict[str, Any]]]:
        form_data = {
            "stream": "true" if stream else "false",
        }
        if content:
            form_data["content"] = content
        if llm_provider:
            form_data["llm_provider"] = llm_provider
        if model_name:
            form_data["model_name"] = model_name
        if memory:
            form_data["memory"] = memory

        if files:
            files_data = []
            file_handles = []
            try:
                for file_path in files:
                    path = Path(file_path)
                    if not path.exists():
                        raise FileNotFoundError(f"File not found: {file_path}")
                    file_handle = open(path, "rb")
                    file_handles.append(file_handle)
                    files_data.append(("files", (path.name, file_handle, "text/plain")))

                if stream:
                    # For streaming, wrap the generator to close files when done
                    return self._parse_streaming_response_with_file_cleanup(
                        method="POST",
                        endpoint=f"/threads/{thread_id}/messages",
                        data=form_data,
                        files=files_data,
                        file_handles=file_handles,
                    )
                response = await self._make_request(
                    "POST",
                    f"/threads/{thread_id}/messages",
                    data=form_data,
                    files=files_data,
                )
                return MessageResponse.model_validate(response.json())
            finally:
                # Only close files if not streaming (streaming will handle it)
                if not stream:
                    for fh in file_handles:
                        fh.close()
        else:
            if stream:
                return self._parse_streaming_response_iter(
                    method="POST",
                    endpoint=f"/threads/{thread_id}/messages",
                    data=form_data,
                )
            response = await self._make_request(
                "POST",
                f"/threads/{thread_id}/messages",
                data=form_data,
            )
            return MessageResponse.model_validate(response.json())

    async def submit_tool_outputs(
        self,
        thread_id: Union[str, uuid.UUID],
        run_id: str,
        tool_outputs: List[Union[ToolOutput, Dict[str, str]]],
        stream: bool = False
    ) -> Union[ToolOutputsResponse, AsyncIterator[Dict[str, Any]]]:
        formatted_outputs: List[Dict[str, str]] = []
        for output in tool_outputs:
            if isinstance(output, dict):
                formatted_outputs.append(output)
            else:
                formatted_outputs.append({
                    "tool_call_id": output.tool_call_id,
                    "output": output.output,
                })
        data = {"tool_outputs": formatted_outputs}
        params = {"stream": "true" if stream else "false"}

        if stream:
            return self._parse_streaming_response_iter(
                method="POST",
                endpoint=f"/threads/{thread_id}/runs/{run_id}/submit-tool-outputs",
                json_data=data,
                params=params,
            )
        response = await self._make_request(
            "POST",
            f"/threads/{thread_id}/runs/{run_id}/submit-tool-outputs",
            json_data=data,
            params=params,
        )
        return ToolOutputsResponse.model_validate(response.json())

    async def upload_document_to_assistant(
        self,
        assistant_id: Union[str, uuid.UUID],
        file_path: Union[str, Path]
    ) -> Document:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(path, "rb") as file_handle:
            files = {"file": (path.name, file_handle, "text/plain")}
            response = await self._make_request(
                "POST",
                f"/assistants/{assistant_id}/documents",
                files=files,
            )
            return Document.model_validate(response.json())

    async def upload_document_to_thread(
        self,
        thread_id: Union[str, uuid.UUID],
        file_path: Union[str, Path]
    ) -> Document:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(path, "rb") as file_handle:
            files = {"file": (path.name, file_handle, "text/plain")}
            response = await self._make_request(
                "POST",
                f"/threads/{thread_id}/documents",
                files=files,
            )
            return Document.model_validate(response.json())

    async def list_assistant_documents(self, assistant_id: Union[str, uuid.UUID]) -> List[Document]:
        response = await self._make_request("GET", f"/assistants/{assistant_id}/documents")
        return [Document.model_validate(data) for data in response.json()]

    async def list_thread_documents(self, thread_id: Union[str, uuid.UUID]) -> List[Document]:
        response = await self._make_request("GET", f"/threads/{thread_id}/documents")
        return [Document.model_validate(data) for data in response.json()]

    async def get_document_status(self, document_id: Union[str, uuid.UUID]) -> Document:
        response = await self._make_request("GET", f"/documents/{document_id}/status")
        return Document.model_validate(response.json())

    async def delete_document(self, document_id: Union[str, uuid.UUID]) -> Dict[str, Any]:
        response = await self._make_request("DELETE", f"/documents/{document_id}")
        return response.json()

    async def get_memories(self, assistant_id: Union[str, uuid.UUID]) -> MemoriesListResponse:
        """
        Get all memories for an assistant.
        
        Args:
            assistant_id: UUID of the assistant
            
        Returns:
            MemoriesListResponse with list of memories
        """
        response = await self._make_request("GET", f"/assistants/{assistant_id}/memories")
        return MemoriesListResponse.model_validate(response.json())

    async def add_memory(
        self,
        assistant_id: Union[str, uuid.UUID],
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a new memory to an assistant.
        
        Args:
            assistant_id: UUID of the assistant
            content: Memory content text
            metadata: Optional metadata dictionary
            
        Returns:
            Dictionary with success status and memory_id
        """
        data = {"content": content}
        if metadata:
            data["metadata"] = metadata
            
        response = await self._make_request("POST", f"/assistants/{assistant_id}/memories", json_data=data)
        return response.json()

    async def get_memory(
        self,
        assistant_id: Union[str, uuid.UUID],
        memory_id: str
    ) -> Memory:
        """
        Get a specific memory by ID.
        
        Args:
            assistant_id: UUID of the assistant
            memory_id: ID of the memory
            
        Returns:
            Memory object
        """
        response = await self._make_request("GET", f"/assistants/{assistant_id}/memories/{memory_id}")
        return Memory.model_validate(response.json())

    async def update_memory(
        self,
        assistant_id: Union[str, uuid.UUID],
        memory_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Memory:
        """
        Update an existing memory.
        
        Args:
            assistant_id: UUID of the assistant
            memory_id: ID of the memory to update
            content: New memory content
            metadata: Optional new metadata
            
        Returns:
            Updated Memory object
        """
        data = {"content": content}
        if metadata:
            data["metadata"] = metadata
            
        response = await self._make_request("PUT", f"/assistants/{assistant_id}/memories/{memory_id}", json_data=data)
        return Memory.model_validate(response.json())

    async def delete_memory(
        self,
        assistant_id: Union[str, uuid.UUID],
        memory_id: str
    ) -> Dict[str, Any]:
        """
        Delete a memory.
        
        Args:
            assistant_id: UUID of the assistant
            memory_id: ID of the memory to delete
            
        Returns:
            Dictionary with success status and message
        """
        response = await self._make_request("DELETE", f"/assistants/{assistant_id}/memories/{memory_id}")
        return response.json()

    async def get_memory_stats(self, assistant_id: Union[str, uuid.UUID]) -> MemoryStats:
        """
        Get memory statistics for an assistant.
        
        Args:
            assistant_id: UUID of the assistant
            
        Returns:
            MemoryStats object with usage information
        """
        response = await self._make_request("GET", f"/assistants/{assistant_id}/memories/stats")
        return MemoryStats.model_validate(response.json())

    def _tool_to_dict(self, tool: Union[ToolDefinition, Dict[str, Any]]) -> Dict[str, Any]:
        if isinstance(tool, dict):
            return tool
        return {
            "type": tool.type,
            "function": {
                "name": tool.function.name,
                "description": tool.function.description,
                "parameters": {
                    "type": tool.function.parameters.type,
                    "properties": {
                        k: {
                            "type": v.type,
                            "description": v.description,
                            "enum": v.enum,
                            "properties": v.properties,
                            "items": v.items,
                        }
                        for k, v in (tool.function.parameters.properties or {}).items()
                    },
                    "required": tool.function.parameters.required,
                },
            },
        }

    def _parse_streaming_response_iter(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[List[Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        async def generator() -> AsyncIterator[Dict[str, Any]]:
            async for event in self._stream_request(
                method=method,
                endpoint=endpoint,
                json_data=json_data,
                data=data,
                files=files,
                params=params,
            ):
                yield event
        return generator()

    def _parse_streaming_response_with_file_cleanup(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[List[Any]] = None,
        file_handles: Optional[List[Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Parse streaming response and ensure file handles are closed when done.
        This is needed because when we return a generator, file handles must stay
        open until the stream is consumed.
        """
        async def generator() -> AsyncIterator[Dict[str, Any]]:
            try:
                async for event in self._stream_request(
                    method=method,
                    endpoint=endpoint,
                    data=data,
                    files=files,
                    params=params,
                ):
                    yield event
            finally:
                # Close file handles after stream completes or on error
                if file_handles:
                    for fh in file_handles:
                        try:
                            fh.close()
                        except Exception:
                            pass  # Ignore errors closing files
        return generator()


