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
