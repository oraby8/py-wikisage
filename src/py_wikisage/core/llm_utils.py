"""Shared LiteLLM call configuration from project config.yaml."""

from __future__ import annotations

import os
from typing import Any

from rich.console import Console

console = Console()


def llm_model_id(config: dict) -> str:
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "openai")
    model_name = llm_config.get("model", "gpt-4o-mini")
    return f"{provider}/{model_name}" if provider != "openai" else model_name


def resolve_api_key(config: dict) -> str | None:
    llm_config = config.get("llm", {})
    api_key = llm_config.get("api_key")
    api_key_env = llm_config.get("api_key_env")
    if not api_key and api_key_env:
        api_key = os.getenv(api_key_env)
    return api_key


def build_completion_kwargs(
    config: dict,
    messages: list[dict[str, str]],
    *,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "openai")
    kwargs: dict[str, Any] = {
        "model": llm_model_id(config),
        "messages": messages,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    api_key = resolve_api_key(config)
    if api_key:
        kwargs["api_key"] = api_key
    elif provider == "gemini":
        console.print(
            "[yellow]No API key resolved. Set llm.api_key or export the env var named in llm.api_key_env.[/yellow]"
        )
    return kwargs
