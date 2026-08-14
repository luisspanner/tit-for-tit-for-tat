import os
import time

import httpx

DEFAULT_MAX_TOKENS = 500
MAX_RETRIES = 4
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MIN_REQUEST_INTERVAL = 0.5
# Groq's free tier caps every model at 30 requests/minute; pace at just
# under one request per 2s so we rarely trigger a 429 reactively at all.
GROQ_MIN_REQUEST_INTERVAL = 2.1


class RequestPacer:
    """Tracks last-call time so it can be shared across multiple clients that
    hit the same rate-limited account (e.g. several Groq models under one
    API key) instead of each client only pacing against its own calls."""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._last_request_time: float | None = None

    def wait(self) -> None:
        if self._last_request_time is not None:
            elapsed = time.monotonic() - self._last_request_time
            remaining = self.min_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_time = time.monotonic()


class OpenAICompatibleLLMClient:
    """Talks to any OpenAI-compatible chat-completions endpoint (Groq, Ollama, ...)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        http_client: httpx.Client | None = None,
        min_request_interval: float = MIN_REQUEST_INTERVAL,
        pacer: RequestPacer | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self._pacer = pacer if pacer is not None else RequestPacer(min_request_interval)
        self._http = http_client if http_client is not None else httpx.Client()

    @property
    def min_request_interval(self) -> float:
        return self._pacer.min_interval

    def _post_with_retry(self, headers: dict[str, str], body: dict) -> httpx.Response:
        attempt = 0
        while True:
            self._pacer.wait()
            response = self._http.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=body,
                timeout=60.0,
            )
            if response.status_code not in RETRYABLE_STATUS_CODES:
                response.raise_for_status()
                return response

            attempt += 1
            if attempt >= MAX_RETRIES:
                response.raise_for_status()
                return response

            retry_after = response.headers.get("retry-after")
            delay = float(retry_after) if retry_after is not None else 2**attempt
            time.sleep(delay)

    def complete(self, system_prompt: str, user_message: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = self._post_with_retry(
            headers,
            {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            },
        )
        message = response.json()["choices"][0]["message"]
        content = message.get("content") or ""
        if content.strip():
            return content
        return message.get("reasoning") or message.get("reasoning_content") or content


# Groq's 30 req/min cap applies per API key, shared across every model —
# so all groq_client() instances pace against this one shared clock rather
# than each tracking only its own calls.
_GROQ_PACER = RequestPacer(GROQ_MIN_REQUEST_INTERVAL)


def groq_client(model: str = "llama-3.1-8b-instant") -> OpenAICompatibleLLMClient:
    return OpenAICompatibleLLMClient(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY", ""),
        model=model,
        pacer=_GROQ_PACER,
    )


def ollama_local_client(model: str = "qwen2.5") -> OpenAICompatibleLLMClient:
    return OpenAICompatibleLLMClient(base_url="http://localhost:11434/v1", api_key="", model=model)


def ollama_cloud_client(model: str = "gemma4:31b-cloud") -> OpenAICompatibleLLMClient:
    return OpenAICompatibleLLMClient(
        base_url="https://ollama.com/v1",
        api_key=os.environ.get("OLLAMA_API_KEY", ""),
        model=model,
    )
