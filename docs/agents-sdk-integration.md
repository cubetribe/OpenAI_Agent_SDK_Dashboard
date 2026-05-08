# OpenAI Agents SDK Integration

## Official SDK Contract

The OpenAI Agents SDK tracing processor interface receives lifecycle callbacks for traces and spans:
`on_trace_start`, `on_trace_end`, `on_span_start`, `on_span_end`, `shutdown`, and `force_flush`.

Official references:

- [Tracing guide](https://openai.github.io/openai-agents-python/tracing/)
- [Processor interface](https://openai.github.io/openai-agents-python/ref/tracing/processor_interface/)
- [Tracing module reference](https://openai.github.io/openai-agents-python/ref/tracing/)

The dashboard adapter uses the additive processor path. Registering with `add_trace_processor()`
keeps the SDK's default tracing exporter in place while also publishing normalized events to Redis.
Using `set_trace_processors()` replaces the SDK processor list and should be reserved for applications
that intentionally own the full tracing pipeline.

## Registering the Processor

Install this package into the upstream agent application's environment, configure Redis, and register
the processor during application startup before running agents:

```python
from dashboard_service.agents_sdk import register_dashboard_trace_processor

register_dashboard_trace_processor()
```

Equivalent explicit wiring:

```python
from agents.tracing import add_trace_processor

from dashboard_service.agents_sdk import AgentsDashboardTraceProcessor
from dashboard_service.publisher import RedisDashboardPublisher

publisher = RedisDashboardPublisher(
    redis_url="redis://redis:6379/0",
    channel="agent:traces",
)
add_trace_processor(AgentsDashboardTraceProcessor(publisher=publisher))
```

## Published Event Fields

The adapter emits the dashboard event contract:

- `trace_start` and `trace_end` for workflow lifecycle.
- `span_start` and `span_end` for agent, tool, handoff, and generation spans.
- `agent_id` when span data identifies an agent.
- `tool_name` when span data identifies a function or tool call.
- `span_type`, IDs, timestamps, duration, and error status when the SDK provides them.
- safe structural metadata such as turn number, task name, model name, handoff endpoints, and
  declared agent tool names. Raw inputs and outputs stay out of viewer payloads and are only
  included in developer detail when explicitly enabled.

## Sensitive Data

The adapter does not forward raw span detail by default. Set
`DASHBOARD_TRACE_INCLUDE_DETAIL=true` only for trusted developer environments. The Agents SDK can
capture LLM and tool inputs or outputs in spans, so detail forwarding should be paired with an
explicit privacy review and upstream `trace_include_sensitive_data` settings.
