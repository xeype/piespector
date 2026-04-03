from __future__ import annotations

import errno
from time import perf_counter
import socket
import ssl
from urllib import error, request

from piespector.domain.requests import RequestDefinition, ResponseSummary
from piespector.placeholders import resolve_placeholders
from piespector.request_builder import (
    RequestValidationError,
    _encode_multipart_form_data,
    build_request,
    preview_auto_headers,
    preview_effective_headers,
    preview_request_url,
    validate_raw_body,
)


def perform_request(
    definition: RequestDefinition,
    env_pairs: dict[str, str],
    timeout_seconds: float = 15.0,
) -> ResponseSummary:
    started = perf_counter()

    try:
        req = build_request(
            definition,
            env_pairs,
            timeout_seconds=timeout_seconds,
            urlopen=request.urlopen,
        )
        with request.urlopen(req, timeout=timeout_seconds) as response:
            raw_body = response.read()
            elapsed_ms = (perf_counter() - started) * 1000
            return ResponseSummary(
                status_code=response.status,
                elapsed_ms=elapsed_ms,
                body_length=len(raw_body),
                body_text=_decode_body(raw_body, response.headers.get_content_charset()),
                response_headers=_header_items(response.headers.items()),
            )
    except error.HTTPError as exc:
        raw_body = exc.read()
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            status_code=exc.code,
            elapsed_ms=elapsed_ms,
            body_length=len(raw_body),
            body_text=_decode_body(raw_body, exc.headers.get_content_charset()),
            error=str(exc),
            response_headers=_header_items(exc.headers.items()),
        )
    except error.URLError as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=_friendly_request_error(exc.reason),
        )
    except TimeoutError as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=_friendly_request_error(exc),
        )
    except ssl.SSLError as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=_friendly_request_error(exc),
        )
    except RequestValidationError as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=str(exc),
        )
    except ValueError as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=_friendly_value_error(exc),
        )
    except Exception as exc:
        elapsed_ms = (perf_counter() - started) * 1000
        return ResponseSummary(
            elapsed_ms=elapsed_ms,
            error=_friendly_request_error(exc),
        )


def _friendly_value_error(exc: ValueError) -> str:
    message = str(exc)
    if "unknown url type" in message.lower():
        return "Invalid URL: use a full http:// or https:// address."
    return f"Invalid request: {message}"


def _friendly_request_error(exc: object) -> str:
    if isinstance(exc, socket.gaierror):
        return "DNS lookup failed: could not resolve the host name."

    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "Request timed out: the server did not respond in time."

    if isinstance(exc, ssl.SSLError):
        return "SSL error: could not establish a secure connection."

    if isinstance(exc, ConnectionRefusedError):
        return "Connection refused: the server is not accepting connections."

    if isinstance(exc, OSError):
        if exc.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
            return "Network unavailable: could not reach the remote host."
        if exc.errno == errno.ECONNRESET:
            return "Connection reset by peer."
        if exc.errno == errno.ECONNREFUSED:
            return "Connection refused: the server is not accepting connections."

    message = str(exc).strip()
    if not message:
        return "Network error: request could not be completed."
    return f"Network error: {message}"


def _decode_body(raw_body: bytes, charset: str | None) -> str:
    encoding = charset or "utf-8"
    try:
        return raw_body.decode(encoding)
    except UnicodeDecodeError:
        return raw_body.decode("utf-8", errors="replace")


def response_preview(body_text: str, limit: int = 600) -> str:
    if len(body_text) <= limit:
        return body_text
    return body_text[:limit] + "\n…"


def _header_items(headers: object) -> list[tuple[str, str]]:
    return [(str(key), str(value)) for key, value in headers]
