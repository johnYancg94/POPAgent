from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid


@dataclass
class UsageData:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0


MODEL_PRICING_RMB_PER_MILLION = {
    "mimo-v2.5": {
        "cache_hit_input": 0.02,
        "cache_miss_input": 1.0,
        "output": 2.0,
    },
    "mimo-v2.5-pro": {
        "cache_hit_input": 0.025,
        "cache_miss_input": 3.0,
        "output": 6.0,
    },
    "deepseek-v4-flash": {
        "cache_hit_input": 0.02,
        "cache_miss_input": 1.0,
        "output": 2.0,
    },
    "deepseek-v4-pro": {
        # Current discounted price from DeepSeek: 2.5x discount.
        "cache_hit_input": 0.025,
        "cache_miss_input": 3.0,
        "output": 6.0,
    },
}


def get_current_model(prefs) -> str:
    org = getattr(prefs, "llm_organization", "")
    if org == "openai":
        return getattr(prefs, "open_ai_model", "")
    if org == "mimo":
        return getattr(prefs, "mimo_model", "")
    if org == "deepseek":
        return getattr(prefs, "deepseek_model", "")
    if org == "anthropic":
        return getattr(prefs, "anthropic_model", "")
    return ""


def prompt_preview(prompt: str, limit: int = 80) -> str:
    prompt = " ".join((prompt or "").split())
    if len(prompt) <= limit:
        return prompt
    return prompt[: limit - 3] + "..."


def normalize_usage(raw_usage: dict | None, provider: str = "") -> UsageData:
    if not isinstance(raw_usage, dict):
        return UsageData()

    input_tokens = int(
        raw_usage.get("input_tokens")
        or raw_usage.get("prompt_tokens")
        or 0
    )
    output_tokens = int(
        raw_usage.get("output_tokens")
        or raw_usage.get("completion_tokens")
        or 0
    )

    prompt_details = raw_usage.get("prompt_tokens_details") or {}
    completion_details = raw_usage.get("completion_tokens_details") or {}

    cache_creation_tokens = int(
        raw_usage.get("cache_creation_input_tokens")
        or raw_usage.get("cache_creation_tokens")
        or 0
    )
    cache_read_tokens = int(
        raw_usage.get("cache_read_input_tokens")
        or raw_usage.get("cache_read_tokens")
        or prompt_details.get("cached_tokens")
        or 0
    )
    reasoning_tokens = int(
        raw_usage.get("reasoning_tokens")
        or completion_details.get("reasoning_tokens")
        or 0
    )

    total_tokens = int(raw_usage.get("total_tokens") or 0)
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens

    return UsageData(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation_tokens,
        cache_read_tokens=cache_read_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
    )


def calculate_cost_rmb(model: str, usage: UsageData) -> tuple[float, bool]:
    pricing = MODEL_PRICING_RMB_PER_MILLION.get(model)
    if not pricing:
        return 0.0, False

    cached_input = max(0, usage.cache_read_tokens)
    uncached_input = max(0, usage.input_tokens - cached_input)
    cost = (
        cached_input * pricing["cache_hit_input"]
        + uncached_input * pricing["cache_miss_input"]
        + usage.output_tokens * pricing["output"]
    ) / 1_000_000
    return cost, True


def add_usage_record(
    context,
    prefs,
    raw_usage: dict | None,
    *,
    mode: str,
    prompt: str,
    latency_ms: int = 0,
    status_code: int = 0,
    is_error: bool = False,
    error_message: str = "",
) -> None:
    usage = normalize_usage(raw_usage, getattr(prefs, "llm_organization", ""))
    if usage.total_tokens <= 0 and not is_error:
        return

    model = get_current_model(prefs)
    cost, is_estimated = calculate_cost_rmb(model, usage)

    collection = context.scene.chat_companion_usage
    item = collection.add()
    item.request_id = str(uuid.uuid4())
    item.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item.prompt_preview = prompt_preview(prompt)
    item.llm_organization = getattr(prefs, "llm_organization", "")
    item.model = model
    item.mode = mode
    item.input_tokens = usage.input_tokens
    item.output_tokens = usage.output_tokens
    item.cache_creation_tokens = usage.cache_creation_tokens
    item.cache_read_tokens = usage.cache_read_tokens
    item.reasoning_tokens = usage.reasoning_tokens
    item.total_tokens = usage.total_tokens
    item.estimated_cost_rmb = cost
    item.cost_is_estimated = is_estimated
    item.latency_ms = max(0, int(latency_ms))
    item.status_code = int(status_code or 0)
    item.is_error = is_error
    item.error_message = error_message or ""


def summarize_usage(records) -> dict:
    summary = {
        "requests": 0,
        "errors": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_rmb": 0.0,
        "avg_latency_ms": 0,
    }
    latency_total = 0
    latency_count = 0

    for item in records:
        summary["requests"] += 1
        summary["errors"] += 1 if item.is_error else 0
        summary["input_tokens"] += item.input_tokens
        summary["output_tokens"] += item.output_tokens
        summary["cache_creation_tokens"] += item.cache_creation_tokens
        summary["cache_read_tokens"] += item.cache_read_tokens
        summary["reasoning_tokens"] += item.reasoning_tokens
        summary["total_tokens"] += item.total_tokens
        summary["estimated_cost_rmb"] += item.estimated_cost_rmb
        if item.latency_ms > 0:
            latency_total += item.latency_ms
            latency_count += 1

    if latency_count:
        summary["avg_latency_ms"] = round(latency_total / latency_count)

    return summary


def format_tokens(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 10_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def format_cost_rmb(value: float, is_estimated: bool = True) -> str:
    if value <= 0:
        return "not priced"
    prefix = "~" if is_estimated else ""
    if value < 0.01:
        return f"{prefix}¥{value:.4f}"
    return f"{prefix}¥{value:.2f}"
