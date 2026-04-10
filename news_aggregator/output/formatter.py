from __future__ import annotations

import dataclasses
import json
from datetime import datetime

from news_aggregator.models.result import AggregatedResult


def format_result(result: AggregatedResult, fmt: str) -> str:
    if fmt == "json":
        return _format_json(result)
    elif fmt == "markdown":
        return _format_markdown(result)
    else:
        return _format_text(result)


def _format_text(result: AggregatedResult) -> str:
    lines = [
        f"News Digest — {result.generated_at.strftime('%Y-%m-%d %H:%M UTC')} "
        f"(last {result.lookback_hours}h)",
        "=" * 70,
    ]
    for cat in result.categories:
        lines.append(f"\n[{cat.category.upper()}]")
        lines.append(cat.rendered_text.rstrip())
        if cat.articles:
            lines.append(f"  ({len(cat.articles)} article(s) aggregated)")
    return "\n".join(lines)


def _format_markdown(result: AggregatedResult) -> str:
    lines = [
        "# News Digest",
        f"*{result.generated_at.strftime('%Y-%m-%d %H:%M UTC')} — last {result.lookback_hours}h*",
        "",
    ]
    for cat in result.categories:
        lines.append(f"## {cat.category.title()}")
        lines.append("")
        lines.append(cat.rendered_text.rstrip())
        lines.append("")
        if cat.articles:
            lines.append(f"*{len(cat.articles)} article(s) aggregated*")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _format_json(result: AggregatedResult) -> str:
    def _default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Not serializable: {type(obj)}")

    data = dataclasses.asdict(result)
    return json.dumps(data, default=_default, indent=2)
