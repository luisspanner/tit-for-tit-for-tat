from typing import Protocol

import anthropic


class LLMClient(Protocol):
    def complete(self, system_prompt: str, user_message: str) -> str:
        """Return the raw text response for a single-turn completion."""
        ...


class AnthropicLLMClient:
    def __init__(self, model: str = "claude-sonnet-5", max_tokens: int = 10) -> None:
        self._client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, system_prompt: str, user_message: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
