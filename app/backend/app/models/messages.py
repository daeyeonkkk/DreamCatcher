from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiMessage(BaseModel):
    level: Literal['info', 'success', 'warning', 'error'] = 'info'
    message_key: str = Field(..., description='프런트가 번역할 i18n 키')
    message_args: dict[str, Any] | None = Field(default=None, description='문자열 치환값')


class JobInfo(BaseModel):
    id: str
    status: Literal['queued', 'running', 'done', 'failed']
    progress: float | None = None


class ApiEnvelope(BaseModel):
    ok: bool = True
    message: ApiMessage | None = None
    job: JobInfo | None = None
    data: dict[str, Any] | None = None
