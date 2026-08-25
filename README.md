# obs-kit

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An observability toolkit: context-managed tracing with error capture, counters/gauges/histograms with percentile snapshots, and threshold alert rules — OpenTelemetry's three pillars in one small package.

## 🚀 Overview

Production systems fail in ways you can't debug after the fact without telemetry. `obs-kit` provides the three pillars: **tracing** (context-managed spans capturing duration, parent linkage, and exceptions), **metrics** (monotonic counters, settable gauges, histograms with p50/p95/max summaries), and **alerting** (threshold rules evaluated against metric snapshots, missing metrics never firing).

## ✨ Features

- **Tracer:** `with tracer.span("op"):` records duration + status; exceptions captured as error spans and re-raised
- **Span linkage:** `parent_span_id` connects child spans for trace trees
- **Metrics registry:** counter (non-negative increments), gauge (overwrite), histogram (numeric-only observations)
- **Percentile math:** linear interpolation between order statistics — p50/p95/max per histogram
- **Alert manager:** declarative `AlertRule`s with five comparisons; unknown metrics silently never fire
- **Zero dependencies**

## 🚧 Structure

```
observability-kit/
├── src/obs_kit/
│   ├── __init__.py
│   └── core.py
├── tests/
│   └── test_core.py
├── README.md
└── pyproject.toml
```

## 📦 Installation

```bash
git clone https://github.com/supremeloki/observability-kit.git
cd observability-kit
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## 📋 Requirements

- Python 3.11+
- No runtime dependencies

## 🏃 Quick Start

```python
from obs_kit import AlertManager, AlertRule, MetricsRegistry, Tracer

tracer = Tracer()
registry = MetricsRegistry()

with tracer.span("handle_request") as span:
    registry.counter_inc("requests.total")
    registry.histogram_observe("request_ms", 42.0)

alerts = (
    AlertManager(registry)
    .add_rule(AlertRule("slow-requests", "request_ms", 100.0, comparison=">"))
    .firing_alerts()
)

print(tracer.error_spans(), alerts)
```

## 🔧 Error Handling

```text
ObservabilityError
└── UnknownMetricError   # snapshot() on an undefined metric name
```

Invalid inputs (negative counters, non-numeric observations) raise at call time.

## 🧪 Testing

```bash
pytest tests/ -v
```

## 📝 Code Quality

- Full type hints (`X | None` style), frozen contexts/rules
- Zero comments — names carry the meaning
- Percentile interpolation verified against hand-computed values

## 📄 License

MIT — see [LICENSE](LICENSE).

## 👤 Author

**Kooroush Masoumi** - [kooroushmasoumi@gmail.com](mailto:kooroushmasoumi@gmail.com)

---

⭐ Star this repo if you find it useful!
