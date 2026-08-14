import httpx
import pytest

from tournament.llm_clients.openai_compatible import (
    OpenAICompatibleLLMClient,
    groq_client,
    ollama_cloud_client,
    ollama_local_client,
)


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_complete_posts_chat_completions_and_parses_response() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": "D"}}]})

    client = OpenAICompatibleLLMClient(
        base_url="https://example.com/v1",
        api_key="secret",
        model="test-model",
        http_client=_mock_client(handler),
    )

    result = client.complete("be ruthless", "what is your move?")

    assert result == "D"
    assert captured["url"] == "https://example.com/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer secret"


def test_complete_sends_correct_request_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["max_tokens"] == 500
        assert body["messages"] == [
            {"role": "system", "content": "be ruthless"},
            {"role": "user", "content": "what is your move?"},
        ]
        return httpx.Response(200, json={"choices": [{"message": {"content": "C"}}]})

    client = OpenAICompatibleLLMClient(
        base_url="https://example.com/v1",
        api_key="secret",
        model="test-model",
        http_client=_mock_client(handler),
    )

    assert client.complete("be ruthless", "what is your move?") == "C"


def test_complete_omits_authorization_header_when_api_key_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": "C"}}]})

    client = OpenAICompatibleLLMClient(
        base_url="https://example.com/v1",
        api_key="",
        model="test-model",
        http_client=_mock_client(handler),
    )

    client.complete("prompt", "message")


def test_complete_raises_immediately_on_non_retryable_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tournament.llm_clients.openai_compatible.time.sleep", lambda _seconds: None)
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(403)

    client = OpenAICompatibleLLMClient(
        base_url="https://example.com/v1",
        api_key="secret",
        model="test-model",
        http_client=_mock_client(handler),
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.complete("prompt", "message")

    assert call_count["n"] == 1


def test_complete_retries_on_429_and_returns_eventual_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tournament.llm_clients.openai_compatible.time.sleep", lambda _seconds: None)
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] < 3:
            return httpx.Response(429)
        return httpx.Response(200, json={"choices": [{"message": {"content": "D"}}]})

    client = OpenAICompatibleLLMClient(
        base_url="https://example.com/v1",
        api_key="secret",
        model="test-model",
        http_client=_mock_client(handler),
    )

    assert client.complete("prompt", "message") == "D"
    assert call_count["n"] == 3


def test_complete_raises_after_exhausting_retries_on_persistent_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tournament.llm_clients.openai_compatible.time.sleep", lambda _seconds: None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    client = OpenAICompatibleLLMClient(
        base_url="https://example.com/v1",
        api_key="secret",
        model="test-model",
        http_client=_mock_client(handler),
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.complete("prompt", "message")


def test_complete_falls_back_to_reasoning_field_when_content_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "", "reasoning": "I'll cooperate. C"}}]}
        )

    client = OpenAICompatibleLLMClient(
        base_url="https://example.com/v1",
        api_key="secret",
        model="test-model",
        http_client=_mock_client(handler),
    )

    assert client.complete("prompt", "message") == "I'll cooperate. C"


def test_groq_client_reads_api_key_from_env_and_sets_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")

    client = groq_client(model="llama-3.3-70b-versatile")

    assert client.base_url == "https://api.groq.com/openai/v1"
    assert client.api_key == "groq-secret"
    assert client.model == "llama-3.3-70b-versatile"


def test_groq_client_defaults_to_8b_instant_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")

    assert groq_client().model == "llama-3.1-8b-instant"


def test_groq_client_paces_requests_to_stay_under_30_rpm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")

    assert groq_client().min_request_interval >= 2.0


def test_groq_clients_for_different_models_share_pacing_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret")
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "tournament.llm_clients.openai_compatible.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "C"}}]})

    small = groq_client(model="llama-3.1-8b-instant")
    big = groq_client(model="llama-3.3-70b-versatile")
    small._http = _mock_client(handler)
    big._http = _mock_client(handler)

    small.complete("prompt", "message")
    big.complete("prompt", "message")

    assert sleep_calls, "second client's call should have waited on the first client's pacing"
    assert sleep_calls[-1] >= small.min_request_interval - 0.1


def test_ollama_local_client_has_no_api_key_and_local_base_url() -> None:
    client = ollama_local_client()

    assert client.base_url == "http://localhost:11434/v1"
    assert client.api_key == ""
    assert client.model == "qwen2.5"


def test_ollama_cloud_client_reads_api_key_from_env_and_sets_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-secret")

    client = ollama_cloud_client(model="deepseek-v3.1:671b-cloud")

    assert client.base_url == "https://ollama.com/v1"
    assert client.api_key == "ollama-secret"
    assert client.model == "deepseek-v3.1:671b-cloud"


def test_ollama_cloud_client_defaults_to_gemma4_31b(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-secret")

    assert ollama_cloud_client().model == "gemma4:31b-cloud"
