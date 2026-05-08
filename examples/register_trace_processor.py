"""Register the dashboard trace processor in an upstream OpenAI Agents SDK app."""

from dashboard_service.agents_sdk import register_dashboard_trace_processor


def configure_tracing() -> None:
    # Call this during application startup before running agents.
    register_dashboard_trace_processor()
