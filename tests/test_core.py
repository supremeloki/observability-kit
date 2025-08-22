import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from obs_kit import (
    AlertManager,
    AlertRule,
    MetricsRegistry,
    ObservabilityError,
    Tracer,
    UnknownMetricError,
)


@pytest.fixture
def registry():
    return MetricsRegistry()


def test_counter_increments_accumulate(registry):
    registry.counter_inc("requests")
    registry.counter_inc("requests", 4)
    assert registry.snapshot("requests") == {"type": "counter", "value": 5.0}


def test_negative_counter_rejected(registry):
    with pytest.raises(ObservabilityError):
        registry.counter_inc("bad", -1.0)


def test_gauge_overwrites(registry):
    registry.gauge_set("queue_depth", 10)
    registry.gauge_set("queue_depth", 3)
    assert registry.snapshot("queue_depth")["value"] == 3


def test_histogram_percentiles(registry):
    for value in range(1, 101):
        registry.histogram_observe("latency_ms", float(value))
    snapshot = registry.snapshot("latency_ms")
    assert snapshot["count"] == 100
    assert 50 <= snapshot["p50"] <= 51
    assert snapshot["p95"] == pytest.approx(95.05)
    assert snapshot["max"] == 100.0


def test_non_numeric_observation_rejected(registry):
    with pytest.raises(ObservabilityError):
        registry.histogram_observe("latency_ms", "fast")


def test_unknown_metric_snapshot_raises(registry):
    with pytest.raises(UnknownMetricError):
        registry.snapshot("never_defined")


def test_tracer_records_ok_and_error_spans():
    tracer = Tracer()
    with tracer.span("healthy_operation"):
        pass
    with pytest.raises(ValueError):
        with tracer.span("failing_operation"):
            raise ValueError("boom")

    assert tracer.finished_count == 2
    errors = tracer.error_spans()
    assert len(errors) == 1
    assert errors[0]["error"] == "ValueError"


def test_span_captures_parent_linkage():
    tracer = Tracer()
    with tracer.span("parent") as parent_ctx:
        pass
    child_ctx = None
    with tracer.span("child", parent_span_id=parent_ctx.span_id) as child:
        child_ctx = child
    spans = tracer.spans_for(child_ctx.trace_id)
    linked = [s for s in spans if s["parent_span_id"] == parent_ctx.span_id]
    assert len(linked) >= 1


def test_alert_fires_on_threshold_breach(registry):
    registry.gauge_set("cpu_percent", 92.0)
    manager = AlertManager(registry)
    manager.add_rule(AlertRule(
        alert_name="cpu-high",
        metric_name="cpu_percent",
        threshold=90.0,
        comparison=">",
        severity="critical",
