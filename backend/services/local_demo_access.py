"""Opt-in, loopback-only access to synthetic Mission routes, never CRM auth."""

import ipaddress
import os
from urllib.parse import urlsplit

from fastapi import Request

DEMO_ACTOR = "LOCAL_SYNTHETIC_DEMO"
ACCESS_PATH = "/api/v1/missions/access"


def _loopback(value: str) -> bool:
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _local_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme in {"http", "https"}
            and _loopback(parsed.hostname or "")
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query and not parsed.fragment
        )
    except ValueError:
        return False


def allows_local_demo(request: Request) -> bool:
    if os.environ.get("FQ_LOCAL_DEMO_NO_LOGIN") != "1":
        return False
    if os.environ.get("FQ_MISSION_DEMO_ENABLED") != "1":
        return False
    if not request.scope.get("path", "").startswith("/api/v1/missions/"):
        return False
    if not request.client or not _loopback(request.client.host):
        return False
    if not _local_url("http://" + request.headers.get("host", "")):
        return False
    # Defend browser cross-site requests and reverse-proxy forwarding. A public
    # tunnel must not inherit access just because its final hop is localhost.
    if request.headers.get("sec-fetch-site") == "cross-site":
        return False
    if "origin" in request.headers and not _local_url(request.headers["origin"]):
        return False
    if "forwarded" in request.headers:
        return False
    if "x-forwarded-for" in request.headers and not all(
        _loopback(item.strip()) for item in request.headers["x-forwarded-for"].split(",")
    ):
        return False
    if "x-forwarded-host" in request.headers and not _local_url(
        "http://" + request.headers["x-forwarded-host"]
    ):
        return False
    return True
