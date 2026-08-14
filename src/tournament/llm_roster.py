import os
from pathlib import Path

from dotenv import load_dotenv

from tournament.cache import DiskCache
from tournament.llm_client import AnthropicLLMClient
from tournament.llm_clients import groq_client, ollama_cloud_client, ollama_local_client
from tournament.strategies.llm import LLMStrategy

load_dotenv()

GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
]
OLLAMA_CLOUD_MODELS = ["gemma4:31b-cloud"]


def _slug(model: str) -> str:
    return model.split("/")[-1].replace(":", "_").replace(".", "_").replace("-", "_")


def configured_model_names() -> list[str]:
    """Which model_names build_llm_strategies() would actually build right
    now, based on env vars alone - no clients/strategies constructed."""
    names: list[str] = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        names.append("claude-sonnet-5")
    if os.environ.get("GROQ_API_KEY"):
        names.extend(GROQ_MODELS)
    if os.environ.get("OLLAMA_API_KEY"):
        names.extend(OLLAMA_CLOUD_MODELS)
    if os.environ.get("OLLAMA_ENABLED"):
        names.append("qwen2.5")
    return names


def build_llm_strategies(
    system_prompt: str, cache_dir: Path, announce_last_round: bool = True
) -> list[LLMStrategy]:
    strategies: list[LLMStrategy] = []
    suffix = "" if announce_last_round else "_untold"

    if os.environ.get("ANTHROPIC_API_KEY"):
        strategies.append(
            LLMStrategy(
                name=f"llm_claude_sonnet_5{suffix}",
                system_prompt=system_prompt,
                client=AnthropicLLMClient(),
                cache=DiskCache(cache_dir / f"llm_claude_sonnet_5{suffix}.json"),
                model_name="claude-sonnet-5",
                announce_last_round=announce_last_round,
            )
        )
    else:
        print("ANTHROPIC_API_KEY not set - skipping llm_claude_sonnet_5.")

    if os.environ.get("GROQ_API_KEY"):
        for model in GROQ_MODELS:
            slug = _slug(model)
            strategies.append(
                LLMStrategy(
                    name=f"llm_groq_{slug}{suffix}",
                    system_prompt=system_prompt,
                    client=groq_client(model=model),
                    cache=DiskCache(cache_dir / f"llm_groq_{slug}{suffix}.json"),
                    model_name=model,
                    announce_last_round=announce_last_round,
                )
            )
    else:
        print("GROQ_API_KEY not set - skipping Groq models.")

    if os.environ.get("OLLAMA_API_KEY"):
        for model in OLLAMA_CLOUD_MODELS:
            slug = _slug(model)
            strategies.append(
                LLMStrategy(
                    name=f"llm_ollama_cloud_{slug}{suffix}",
                    system_prompt=system_prompt,
                    client=ollama_cloud_client(model=model),
                    cache=DiskCache(cache_dir / f"llm_ollama_cloud_{slug}{suffix}.json"),
                    model_name=model,
                    announce_last_round=announce_last_round,
                )
            )
    else:
        print("OLLAMA_API_KEY not set - skipping Ollama Cloud models.")

    if os.environ.get("OLLAMA_ENABLED"):
        strategies.append(
            LLMStrategy(
                name=f"llm_ollama_local_qwen2_5{suffix}",
                system_prompt=system_prompt,
                client=ollama_local_client(),
                cache=DiskCache(cache_dir / f"llm_ollama_local_qwen2_5{suffix}.json"),
                model_name="qwen2.5",
                announce_last_round=announce_last_round,
            )
        )
    else:
        print("OLLAMA_ENABLED not set - skipping local Ollama model.")

    return strategies
