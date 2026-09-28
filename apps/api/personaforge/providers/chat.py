"""Model-agnostic structured chat interface and OpenAI-compatible HTTP adapter."""

import json
from typing import Any, Protocol

import httpx


class ChatModel(Protocol):
    model_name: str
    provider_name: str

    async def generate(
        self, system: str, user: str, response_schema: dict[str, Any]
    ) -> dict[str, Any]: ...


class OpenAICompatibleChatModel:
    provider_name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        *,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

    async def generate(
        self, system: str, user: str, response_schema: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "personaforge_output",
                    "strict": True,
                    "schema": response_schema,
                },
            },
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        if isinstance(content, dict):
            return content
        return json.loads(content)
