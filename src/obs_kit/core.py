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
