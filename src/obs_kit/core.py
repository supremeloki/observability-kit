from __future__ import annotations

import math
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator, Sequence


class ObservabilityError(Exception):
    pass


class UnknownMetricError(ObservabilityError):
    def __init__(self, name: str) -> None:
        super().__init__(f"unknown metric: {name!r}")


@dataclass(frozen=True)
class SpanContext:
    trace_id: str
    span_id: str
    parent_span_id: str | None = None


class TraceCollector:
    _sequence = 0

    def start_trace(self) -> str:
        self._sequence += 1
        return f"trace-{int(time.time() * 1000)}-{self._sequence}"

    @staticmethod
    def new_span_id() -> str:
        return f"span-{time.monotonic_ns()}"


class Tracer:
    def __init__(self, collector: TraceCollector | None = None) -> None:
        self._collector = collector or TraceCollector()
        self._finished_spans: list[dict[str, Any]] = []

    @property
    def finished_count(self) -> int:
        return len(self._finished_spans)

    @contextmanager
    def span(self, operation: str,
             parent_span_id: str | None = None) -> Generator[SpanContext, None, None]:
        trace_id = self._collector.start_trace()
        span_id = self._collector.new_span_id()
        context = SpanContext(
            trace_id=trace_id, span_id=span_id, parent_span_id=parent_span_id,
        )
        started = time.perf_counter()
        try:
            yield context
        except Exception as exc:
            self._finished_spans.append({
                "operation": operation,
                "trace_id": context.trace_id,
                "span_id": context.span_id,
                "parent_span_id": context.parent_span_id,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "status": "error",
                "error": type(exc).__name__,
            })
            raise
        else:
            self._finished_spans.append({
                "operation": operation,
                "trace_id": context.trace_id,
                "span_id": context.span_id,
                "parent_span_id": context.parent_span_id,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "status": "ok",
            })

    def spans_for(self, trace_id: str) -> list[dict[str, Any]]:
        return [s for s in self._finished_spans if s["trace_id"] == trace_id]

    def error_spans(self) -> list[dict[str, Any]]:
        return [s for s in self._finished_spans if s["status"] == "error"]


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def counter_inc(self, name: str, amount: float = 1.0) -> None:
        if amount < 0:
            raise ObservabilityError("counter increments must be non-negative")
        self._counters[name] = self._counters.get(name, 0.0) + amount

    def gauge_set(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def histogram_observe(self, name: str, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ObservabilityError("histogram observations must be numeric")
        self._histograms[name].append(float(value))

    def snapshot(self, name: str) -> dict[str, Any]:
        if name in self._counters:
            return {"type": "counter", "value": self._counters[name]}
        if name in self._gauges:
            return {"type": "gauge", "value": self._gauges[name]}
        if name in self._histograms:
            values = sorted(self._histograms[name])
            return {
                "type": "histogram",
                "count": len(values),
                "sum": round(sum(values), 6),
                "p50": percentile(values, 50),
                "p95": percentile(values, 95),
                "max": values[-1],
            }
        raise UnknownMetricError(name)

    def all_metric_names(self) -> tuple[str, ...]:
        combined = set(self._counters) | set(self._gauges) | set(self._histograms)
        return tuple(sorted(combined))


def percentile(sorted_values: Sequence[float], percent: float) -> float:
    if not sorted_values:
        return 0.0
    rank = (percent / 100.0) * (len(sorted_values) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    fraction = rank - lower
    return round(sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction, 6)


@dataclass(frozen=True)
class AlertRule:
    alert_name: str
    metric_name: str
    threshold: float
    comparison: str = ">"
    severity: str = "warning"

    def __post_init__(self) -> None:
        if self.comparison not in {">", "<", ">=", "<=", "=="}:
            raise ObservabilityError(f"invalid comparison: {self.comparison!r}")

    def evaluate(self, value: float) -> bool:
        return {
            ">": value > self.threshold,
            "<": value < self.threshold,
            ">=": value >= self.threshold,
            "<=": value <= self.threshold,
            "==": value == self.threshold,
        }[self.comparison]


class AlertManager:
    def __init__(self, registry: MetricsRegistry) -> None:
        self._registry = registry
        self._rules: dict[str, AlertRule] = {}

    def add_rule(self, rule: AlertRule) -> "AlertManager":
        self._rules[rule.alert_name] = rule
        return self

    def firing_alerts(self) -> list[dict[str, Any]]:
        firing: list[dict[str, Any]] = []
        for rule in self._rules.values():
            try:
                snapshot = self._registry.snapshot(rule.metric_name)
            except UnknownMetricError:
                continue
            if rule.evaluate(float(snapshot["value"])):
                firing.append({
                    "alert": rule.alert_name,
                    "metric": rule.metric_name,
                    "value": snapshot["value"],
                    "threshold": rule.threshold,
                    "severity": rule.severity,
                })
        return firing
