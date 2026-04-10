from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from news_aggregator.config.loader import ConfigError, load_config
from news_aggregator.config.schema import AppConfig, AggregationConfig, CategoryAggregationConfig, LLMConfig, SourceConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


MINIMAL_YAML = """\
sources:
  - name: newsapi
  - name: guardian
categories:
  - name: technology
aggregation:
  strategy: TopN
  params:
    n: 5
  lookback_hours: 24
llm:
  model: gpt-4o-mini
  headline_max_chars: 100
  summary_max_lines: 3
output_format: text
"""


# ---------------------------------------------------------------------------
# Basic loading
# ---------------------------------------------------------------------------

def test_load_valid_config(tmp_path):
    p = _write_yaml(tmp_path, MINIMAL_YAML)
    cfg = load_config(p)
    assert isinstance(cfg, AppConfig)
    assert len(cfg.sources) == 2
    assert len(cfg.categories) == 1
    assert cfg.aggregation.strategy == "TopN"
    assert cfg.llm.headline_max_chars == 100


def test_load_default_config():
    """The shipped default.yaml should load without errors."""
    path = Path(__file__).parent.parent.parent / "config" / "default.yaml"
    os.environ.setdefault("LLM_MODEL", "gpt-4o-mini")
    cfg = load_config(path)
    assert cfg.aggregation.lookback_hours == 24
    assert cfg.output_format == "text"


def test_file_not_found(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.yaml")


def test_invalid_yaml(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("key: [unclosed")
    with pytest.raises(ConfigError, match="Failed to parse YAML"):
        load_config(p)


def test_non_mapping_yaml(tmp_path):
    p = tmp_path / "list.yaml"
    p.write_text("- item1\n- item2\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(p)


# ---------------------------------------------------------------------------
# Env var expansion
# ---------------------------------------------------------------------------

def test_env_var_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_MODEL", "claude-3-5-sonnet")
    content = MINIMAL_YAML.replace("gpt-4o-mini", "${MY_MODEL}")
    p = _write_yaml(tmp_path, content)
    cfg = load_config(p)
    assert cfg.llm.model == "claude-3-5-sonnet"


def test_unexpanded_env_var_stays_as_is(tmp_path, monkeypatch):
    monkeypatch.delenv("UNDEFINED_VAR", raising=False)
    content = MINIMAL_YAML.replace("gpt-4o-mini", "${UNDEFINED_VAR}")
    p = _write_yaml(tmp_path, content)
    cfg = load_config(p)
    assert cfg.llm.model == "${UNDEFINED_VAR}"


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

def test_missing_required_field_raises(tmp_path):
    # Remove 'llm' section entirely
    data = yaml.safe_load(MINIMAL_YAML)
    del data["llm"]
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(data))
    with pytest.raises(ConfigError, match="validation failed"):
        load_config(p)


def test_invalid_output_format(tmp_path):
    content = MINIMAL_YAML + "output_format: xml\n"
    p = _write_yaml(tmp_path, content)
    with pytest.raises(ConfigError):
        load_config(p)


def test_lookback_hours_out_of_range(tmp_path):
    data = yaml.safe_load(MINIMAL_YAML)
    data["aggregation"]["lookback_hours"] = 200
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(data))
    with pytest.raises(ConfigError):
        load_config(p)


def test_headline_max_chars_out_of_range(tmp_path):
    data = yaml.safe_load(MINIMAL_YAML)
    data["llm"]["headline_max_chars"] = 5
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(data))
    with pytest.raises(ConfigError):
        load_config(p)


def test_category_references_unknown_source(tmp_path):
    data = yaml.safe_load(MINIMAL_YAML)
    data["categories"][0]["sources"] = ["nonexistent_source"]
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(data))
    with pytest.raises(ConfigError, match="unknown source"):
        load_config(p)


# ---------------------------------------------------------------------------
# Category-level overrides
# ---------------------------------------------------------------------------

def test_category_aggregation_override(tmp_path):
    data = yaml.safe_load(MINIMAL_YAML)
    data["categories"][0]["aggregation"] = {"strategy": "TopNLuckyM", "params": {"n": 5, "m": 2}}
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(data))
    cfg = load_config(p)
    assert cfg.categories[0].aggregation.strategy == "TopNLuckyM"
    assert cfg.categories[0].aggregation.params == {"n": 5, "m": 2}


def test_category_lookback_and_dedup_override(tmp_path):
    data = yaml.safe_load(MINIMAL_YAML)
    data["categories"][0]["aggregation"] = {"lookback_hours": 48, "dedup_threshold": 0.75}
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(data))
    cfg = load_config(p)
    assert cfg.categories[0].aggregation.lookback_hours == 48
    assert cfg.categories[0].aggregation.dedup_threshold == 0.75


def test_category_output_template_stored(tmp_path):
    template = "{{ headline }}\n{% for s in summaries %}* {{ s }}\n{% endfor %}"
    data = yaml.safe_load(MINIMAL_YAML)
    data["categories"][0]["aggregation"] = {"output_template": template}
    p = tmp_path / "config.yaml"
    p.write_text(yaml.dump(data))
    cfg = load_config(p)
    assert cfg.categories[0].aggregation.output_template == template


def test_category_aggregation_defaults_to_empty(tmp_path):
    p = _write_yaml(tmp_path, MINIMAL_YAML)
    cfg = load_config(p)
    agg = cfg.categories[0].aggregation
    assert agg.strategy is None
    assert agg.params == {}
    assert agg.lookback_hours is None
    assert agg.dedup_threshold is None
    assert agg.output_template is None
