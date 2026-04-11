from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from news_aggregator.config.loader import ConfigError, load_config
from news_aggregator.output.emailer import dispatch_deliveries
from news_aggregator.output.formatter import format_result
from news_aggregator.output.writers import write_output
from news_aggregator.pipeline import Pipeline

app = typer.Typer(
    name="news-aggregator",
    help="LLM-powered config-driven news aggregator.",
    add_completion=False,
)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


@app.command()
def run(
    config: Path = typer.Option(
        Path("config/default.yaml"),
        "--config", "-c",
        help="Path to YAML config file.",
    ),
    output_format: Optional[str] = typer.Option(
        None,
        "--output-format", "-f",
        help="Output format: text, json, markdown (overrides config).",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output-file", "-o",
        help="Write output to this file instead of stdout.",
    ),
    lookback_hours: Optional[int] = typer.Option(
        None,
        "--lookback-hours",
        help="Hours to look back for articles (overrides config).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """Fetch, aggregate, and summarise news using an LLM."""
    if verbose:
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger("news_aggregator").setLevel(logging.INFO)

    load_dotenv()

    try:
        cfg = load_config(config)
    except ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    # CLI overrides
    if output_format:
        cfg = cfg.model_copy(update={"output_format": output_format})
    if lookback_hours:
        cfg = cfg.model_copy(
            update={"aggregation": cfg.aggregation.model_copy(
                update={"lookback_hours": lookback_hours}
            )}
        )

    try:
        result = asyncio.run(Pipeline(cfg, dict(os.environ)).run())
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    content = format_result(result, cfg.output_format)
    write_output(content, output_file)

    if cfg.delivery:
        md_content = content if cfg.output_format == "markdown" \
            else format_result(result, "markdown")
        dispatch_deliveries(md_content, cfg.delivery, dict(os.environ))


@app.command()
def validate_config(
    config: Path = typer.Option(
        Path("config/default.yaml"),
        "--config", "-c",
        help="Path to YAML config file.",
    ),
) -> None:
    """Validate a config file without fetching news."""
    load_dotenv()

    try:
        cfg = load_config(config)
    except ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)

    typer.echo(f"Config valid: {config}")
    typer.echo(f"  Sources   : {[s.name for s in cfg.sources if s.enabled]}")
    typer.echo(f"  Categories: {[c.name for c in cfg.categories]}")
    typer.echo(f"  Strategy  : {cfg.aggregation.strategy} {cfg.aggregation.params}")
    typer.echo(f"  Lookback  : {cfg.aggregation.lookback_hours}h")
    typer.echo(f"  LLM model : {cfg.llm.model}")
    typer.echo(f"  Headline  : ≤{cfg.llm.headline_max_chars} chars")
    typer.echo(f"  Summary   : {cfg.llm.summary_max_lines} line(s)")


@app.command()
def list_sources() -> None:
    """List all registered news source adapters."""
    import news_aggregator.sources  # noqa: F401
    from news_aggregator.sources.registry import _REGISTRY

    if not _REGISTRY:
        typer.echo("No sources registered.")
        return

    typer.echo("Registered news sources:")
    for name in sorted(_REGISTRY):
        typer.echo(f"  - {name}")
