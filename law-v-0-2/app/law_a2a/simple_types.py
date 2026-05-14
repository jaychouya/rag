from enum import Enum
from typing import Any, Literal, Optional

from a2a.types import DataPart, FilePart, FileWithBytes, FileWithUri, Part, TextPart
from pydantic import BaseModel, Field


class SimpleA2APart(BaseModel):
    data_type: Literal["text", "file", "file_url", "json", "status"]
    content: str | dict
    mime_type: Optional[str] = None
    file_name: Optional[str] = None

    def to_part(self) -> Part:
        if self.data_type == "text":
            return Part(root=TextPart(text=self.content))
        if self.data_type in ("json", "status"):
            return Part(root=DataPart(data=self.content))
        if self.data_type == "file":
            return Part(
                root=FilePart(file=FileWithBytes(bytes=self.content, mimeType=self.mime_type, name=self.file_name))
            )
        if self.data_type == "file_url":
            return Part(root=FilePart(file=FileWithUri(uri=self.content, mimeType=self.mime_type, name=self.file_name)))
        raise ValueError(f"不支持的data_type: {self.data_type}")


class SimpleA2ATaskStatus(Enum):
    submitted = "submitted"
    working = "working"
    input_required = "input-required"
    completed = "completed"
    canceled = "canceled"
    failed = "failed"
    rejected = "rejected"
    auth_required = "auth-required"
    unknown = "unknown"


class SimpleA2AResult(BaseModel):
    metadata: Optional[dict[str, Any]] = Field(default=None)
    parts: Optional[list[SimpleA2APart]] = Field(default=None)


class SimpleA2AMessageResult(SimpleA2AResult):
    pass


class SimpleA2AStatusResult(SimpleA2AResult):
    status: SimpleA2ATaskStatus = SimpleA2ATaskStatus.working
