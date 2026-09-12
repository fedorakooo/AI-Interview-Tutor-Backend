"""Optional Langfuse / Sentry / OTel hooks — no-op when deps or keys are missing."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_sentry_inited = False
_langfuse_client: Any = None


def init_sentry(service_name: str = "ai-interview-tutor") -> bool:
    global _sentry_inited
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn or _sentry_inited:
        return bool(_sentry_inited)
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=dsn, traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")))
        _sentry_inited = True
        logger.info("Sentry initialized for %s", service_name)
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("Sentry init skipped: %s", exc)
        return False


def init_langfuse() -> Any:
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not public_key or not secret_key:
        return None
    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        logger.info("Langfuse initialized")
        return _langfuse_client
    except Exception as exc:  # pragma: no cover
        logger.warning("Langfuse init skipped: %s", exc)
        return None


@contextmanager
def trace_llm_call(name: str, metadata: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Yield a mutable span dict; records to Langfuse when available."""
    span: dict[str, Any] = {"name": name, "metadata": metadata or {}, "output": None}
    client = init_langfuse()
    generation = None
    if client is not None:
        try:
            generation = client.generation(name=name, metadata=metadata or {})
        except Exception:
            generation = None
    try:
        yield span
        if generation is not None:
            generation.end(output=span.get("output"))
    except Exception as exc:
        if generation is not None:
            try:
                generation.end(output={"error": str(exc)})
            except Exception:
                pass
        raise


def init_otel(service_name: str = "ai-interview-tutor") -> bool:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        resource = Resource.create({"service.name": service_name})
        trace.set_tracer_provider(TracerProvider(resource=resource))
        logger.info("OpenTelemetry tracer provider set for %s", service_name)
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("OTel init skipped: %s", exc)
        return False
