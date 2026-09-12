import uuid

import pytest
from starlette.requests import Request
from starlette.responses import Response

from observability.correlation import CORRELATION_HEADER, CorrelationIdMiddleware, get_correlation_id


async def _noop(request: Request) -> Response:
    captured = get_correlation_id()
    return Response(content=captured or "", media_type="text/plain")


@pytest.mark.asyncio
async def test_correlation_middleware_mints_id():
    middleware = CorrelationIdMiddleware(_noop)
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)

    response = await middleware.dispatch(request, _noop)

    assert response.headers[CORRELATION_HEADER]
    uuid.UUID(response.headers[CORRELATION_HEADER])


@pytest.mark.asyncio
async def test_correlation_middleware_propagates_incoming():
    incoming = "test-correlation-123"
    middleware = CorrelationIdMiddleware(_noop)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(CORRELATION_HEADER.lower().encode(), incoming.encode())],
    }
    request = Request(scope)

    response = await middleware.dispatch(request, _noop)

    assert response.headers[CORRELATION_HEADER] == incoming
