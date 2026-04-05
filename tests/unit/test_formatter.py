from __future__ import annotations

import json

import pytest

from news_aggregator.output.formatter import format_result


def test_text_format_contains_category(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "text")
    assert "TECHNOLOGY" in output
    assert "FINANCE" in output


def test_text_format_contains_headline(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "text")
    assert "Tech News Today" in output


def test_text_format_contains_summary_lines(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "text")
    assert "Line one." in output


def test_text_format_contains_lookback(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "text")
    assert "24h" in output


def test_markdown_format_uses_headers(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "markdown")
    assert "## Technology" in output
    assert "## Finance" in output


def test_markdown_format_bolds_headline(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "markdown")
    assert "**Tech News Today**" in output


def test_markdown_format_uses_bullet_summary(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "markdown")
    assert "- Line one." in output


def test_json_format_is_valid_json(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "json")
    data = json.loads(output)
    assert isinstance(data, dict)


def test_json_format_has_categories(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "json")
    data = json.loads(output)
    assert "categories" in data
    assert len(data["categories"]) == 2


def test_json_format_has_generated_at(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "json")
    data = json.loads(output)
    assert "generated_at" in data


def test_unknown_format_falls_back_to_text(sample_aggregated_result):
    output = format_result(sample_aggregated_result, "unknown_format")
    assert "TECHNOLOGY" in output
