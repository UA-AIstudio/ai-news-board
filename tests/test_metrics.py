"""Metrics on news items: schema, validator, and how build.py shows them."""

import math

import pytest

import build
import validate
from conftest import FIXTURE_NOW, load_fixture


def errors_for(news, pinned):
    return validate.validate(news, pinned, now=FIXTURE_NOW)


def test_good_metrics_pass(good_pinned):
    assert errors_for(load_fixture("good_metrics.json"), good_pinned) == []


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("bad_metrics_too_many.json", "is too long"),
        ("bad_metrics_no_reporter.json", "reported_by is required"),
        ("bad_metrics_reporter_only.json", "reported_by is only used with metrics"),
        ("bad_metrics_percent_range.json", "100.5% is outside 0 to 100"),
        ("bad_metrics_negative_percent.json", "-1% is outside 0 to 100"),
        ("bad_metrics_long_label.json", "is too long"),
        ("bad_metrics_long_unit.json", "is too long"),
        ("bad_metrics_string_value.json", "is not of type 'number'"),
        ("bad_metrics_extra_key.json", "Additional properties are not allowed"),
        ("bad_metrics_empty.json", "should be non-empty"),
    ],
)
def test_bad_metrics_fail(fixture, expected, good_pinned):
    errors = errors_for(load_fixture(fixture), good_pinned)
    assert any(expected in e for e in errors), errors


@pytest.mark.parametrize("value", [0, 100, 0.0, 99.99])
def test_percent_boundaries_pass(value, good_pinned):
    news = load_fixture("good_metrics.json")
    news["columns"]["models"][0]["metrics"] = [{"label": "Score", "value": value, "unit": "%"}]
    assert errors_for(news, good_pinned) == []


@pytest.mark.parametrize("value", [math.nan, math.inf, True])
def test_non_finite_or_boolean_values_fail(value, good_pinned):
    news = load_fixture("good_metrics.json")
    news["columns"]["models"][0]["metrics"] = [{"label": "Score", "value": value}]
    assert errors_for(news, good_pinned)


def test_large_values_without_percent_are_allowed(good_pinned):
    news = load_fixture("good_metrics.json")
    news["columns"]["models"][0]["metrics"] = [{"label": "Context window", "value": 1000000, "unit": "tok"}]
    assert errors_for(news, good_pinned) == []


@pytest.mark.parametrize(
    "value, unit, text",
    [
        (71.4, "%", "71.4%"),
        (30, "%", "30%"),
        (30.0, "%", "30%"),
        (2.5, "x", "2.5x"),
        (180, None, "180"),
        (1234.5, "ms", "1234.5 ms"),
        (0.05, "s", "0.05 s"),
        (1000000, "tok", "1000000 tok"),
    ],
)
def test_metric_value_text_is_exact(value, unit, text):
    assert build.format_metric_value(value, unit) == text


def test_bars_only_where_there_is_a_scale():
    prepared = build.prepare_metrics([
        {"label": "Score", "value": 72.5, "unit": "%"},
        {"label": "Speedup long", "value": 3, "unit": "x"},
        {"label": "Speedup short", "value": 1.5, "unit": "x"},
        {"label": "Latency", "value": 120, "unit": "ms"},
    ])
    assert [p["fill"] for p in prepared] == ["0.7250", "1.0000", "0.5000", None]
    assert [p["text"] for p in prepared] == ["72.5%", "3x", "1.5x", "120 ms"]


def test_spotlight_shows_metrics_and_reporter(good_pinned):
    news = load_fixture("good_metrics.json")
    html = build.render(news, good_pinned)
    assert '<span class="metric-label">Score on benchmark A</span>' in html
    assert '<span class="metric-value">71.4%</span>' in html
    assert '<span class="metric-value">180</span>' in html
    assert 'style="--fill: 0.7140"' in html
    assert html.count('class="metric-fill"') == 1  # the lone unitless value has no bar
    assert "Reported by Anthropic" in html
    assert html.count('class="slide has-metrics') == 1


def test_no_metrics_no_panel(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    assert 'class="metrics"' not in html and "Reported by" not in html
