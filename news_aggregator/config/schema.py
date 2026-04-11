from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EmailDeliveryConfig(BaseModel):
    type: Literal["email"]
    recipients: list[str]
    subject_prefix: str = "[News Digest]"


class SlackDeliveryConfig(BaseModel):
    type: Literal["slack"]
    channel: str
    webhook_url: str = ""


DeliveryConfig = Annotated[
    EmailDeliveryConfig | SlackDeliveryConfig,
    Field(discriminator="type"),
]


class LLMConfig(BaseModel):
    model: str
    headline_max_chars: int  # A — max characters for the generated headline
    summary_max_lines: int   # B — number of lines in the generated summary
    temperature: float = 0.3

    @field_validator("headline_max_chars")
    @classmethod
    def validate_headline_chars(cls, v: int) -> int:
        if not (20 <= v <= 500):
            raise ValueError("headline_max_chars must be between 20 and 500")
        return v

    @field_validator("summary_max_lines")
    @classmethod
    def validate_summary_lines(cls, v: int) -> int:
        if not (1 <= v <= 20):
            raise ValueError("summary_max_lines must be between 1 and 20")
        return v


class SourceConfig(BaseModel):
    name: str           # "newsapi" | "guardian" | "gdelt"
    enabled: bool = True
    extra: dict[str, Any] = {}


class CategoryAggregationConfig(BaseModel):
    """Per-category aggregation overrides — all fields are optional and fall back to global config."""
    strategy: str | None = None
    params: dict[str, Any] = {}
    lookback_hours: int | None = Field(None, ge=1, le=168)
    dedup_threshold: float | None = Field(None, ge=0.0, le=1.0)
    output_template: str | None = None  # Jinja2 template; None → strategy default


class CategoryConfig(BaseModel):
    name: str
    sources: list[str] | None = None  # overrides global sources if set
    aggregation: CategoryAggregationConfig = Field(default_factory=CategoryAggregationConfig)


class AggregationConfig(BaseModel):
    strategy: str               # "TopN" | "TopNLuckyM"
    params: dict[str, Any] = {}
    lookback_hours: int = 24
    dedup_threshold: float = 0.85

    @field_validator("lookback_hours")
    @classmethod
    def validate_lookback(cls, v: int) -> int:
        if not (1 <= v <= 168):
            raise ValueError("lookback_hours must be between 1 and 168 (7 days)")
        return v

    @field_validator("dedup_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("dedup_threshold must be between 0.0 and 1.0")
        return v


class AppConfig(BaseModel):
    sources: list[SourceConfig]
    categories: list[CategoryConfig]
    aggregation: AggregationConfig
    llm: LLMConfig
    output_format: str = "text"
    delivery: list[DeliveryConfig] = []

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        allowed = {"text", "json", "markdown"}
        if v not in allowed:
            raise ValueError(f"output_format must be one of {allowed}")
        return v

    @model_validator(mode="after")
    def validate_category_sources(self) -> "AppConfig":
        valid_source_names = {s.name for s in self.sources}
        for cat in self.categories:
            if cat.sources:
                for src in cat.sources:
                    if src not in valid_source_names:
                        raise ValueError(
                            f"Category '{cat.name}' references unknown source '{src}'. "
                            f"Known sources: {valid_source_names}"
                        )
        return self
