from __future__ import annotations

import json
from typing import Any, Dict, Optional

import requests


class ComfyClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def get_json(self, path: str) -> Dict[str, Any]:
        response = requests.get(self._url(path), timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: Dict[str, Any] | None = None) -> requests.Response:
        response = requests.post(self._url(path), json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response

    def post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.post(path, payload)
        return response.json()

    def post_optional_json(self, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        response = self.post(path, payload)
        if not response.content:
            return {}
        try:
            return response.json()
        except json.JSONDecodeError:
            return {}

    def system_stats(self) -> Dict[str, Any]:
        return self.get_json("/system_stats")

    def object_info(self) -> Dict[str, Any]:
        return self.get_json("/object_info")

    def queue_status(self) -> Dict[str, Any]:
        return self.get_json("/queue")

    def history(self, prompt_id: str | None = None) -> Dict[str, Any]:
        if prompt_id:
            return self.get_json(f"/history/{prompt_id}")
        return self.get_json("/history")

    def submit_prompt(self, prompt: Dict[str, Any], client_id: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"prompt": prompt}
        if client_id:
            payload["client_id"] = client_id
        return self.post_json("/prompt", payload)

    def interrupt(self, prompt_id: str | None = None) -> Dict[str, Any]:
        payload = {"prompt_id": prompt_id} if prompt_id else None
        return self.post_optional_json("/interrupt", payload)

    def manage_queue(self, *, delete: list[str] | None = None, clear: bool = False) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if delete:
            payload["delete"] = delete
        if clear:
            payload["clear"] = True
        return self.post_optional_json("/queue", payload or None)
