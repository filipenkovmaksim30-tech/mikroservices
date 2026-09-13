import httpx
from fastapi import Response

from api_gateway.config import Settings

FORWARDED_RESPONSE_HEADERS = (
    "content-type",
    "www-authenticate",
    "retry-after",
    "location",
    "cache-control",
    "x-request-id",
)

def create_http_client(settings: Settings) -> httpx.AsyncClient:
    timeout = httpx.Timeout(
        connect=settings.http_connect_timeout,
        read=settings.http_read_timeout,
        write=settings.http_write_timeout,
        pool=settings.http_pool_timeout
    )

    limits = httpx.Limits(
        max_connections=settings.http_max_connections,
        max_keepalive_connections=settings.keepalive_connections,
        keepalive_expiry=30.0,
    )

    return httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=False,
    )

async def request_upstream(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    params: dict[str, str | int] | None = None,
    json_body: object | None = None,
    form_data: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None
) -> httpx.Response:

    return await client.request(
        method=method,
        url=url,
        params=params,
        json=json_body,
        data=form_data,
        cookies=cookies,
        headers=headers
    )

def build_gateway_response(
    upstream_response: httpx.Response
) -> Response:

    headers = {
        name: value
        for name in FORWARDED_RESPONSE_HEADERS
        if (value := upstream_response.headers.get(name)) is not None
    }

    response = Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=headers,
    )

    for cookie in upstream_response.headers.get_list("set-cookie"):
        response.headers.append("set-cookie", cookie)

    return response
