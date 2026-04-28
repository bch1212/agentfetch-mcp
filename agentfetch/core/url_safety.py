"""SSRF protection — validate URLs before fetching.

The fetcher is server-side, so anything users can pass to it is a potential
SSRF vector. We block:
  - non-http(s) schemes (file://, gopher://, ftp://, ldap://, etc.)
  - localhost and loopback addresses
  - link-local (169.254/16) — including AWS / GCP metadata service
  - RFC1918 private ranges (10/8, 172.16/12, 192.168/16)
  - the cloud-internal hostnames an attacker might guess

This runs at the API edge so the fetcher modules don't need to know.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata",  # GCP metadata
    "metadata.google.internal",
    "instance-data",  # AWS instance data
    "instance-data.us-east-1.compute.internal",
    "169.254.169.254",  # AWS / Azure metadata
    "kubernetes.default",
    "kubernetes.default.svc",
}


class UnsafeURLError(ValueError):
    """Raised when a URL is rejected by SSRF protection."""


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_url(url: str, *, allow_dns_resolution: bool = True) -> str:
    """Validate a URL for SSRF safety. Returns the URL unchanged or raises.

    Args:
        url: The URL to validate.
        allow_dns_resolution: If True (default), resolve the hostname to verify
            it doesn't point at a blocked IP. Disable for tests where DNS
            shouldn't be hit.
    """
    if not url or not isinstance(url, str):
        raise UnsafeURLError("URL is required.")
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(
            f"URL scheme '{scheme or '(none)'}' not allowed. Use http or https."
        )

    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeURLError("URL must include a hostname.")

    if host in BLOCKED_HOSTNAMES:
        raise UnsafeURLError("URL targets a blocked internal hostname.")

    # Direct IP address?
    if _is_blocked_ip(host):
        raise UnsafeURLError("URL targets a private or loopback address.")

    # Suspicious internal-style hostnames (xxx.internal, xxx.local).
    if host.endswith(".internal") or host.endswith(".local"):
        raise UnsafeURLError("URL targets an internal hostname.")

    # Resolve and check the actual address. This catches DNS rebinding-style
    # attacks where an external hostname resolves to an internal IP.
    if allow_dns_resolution:
        try:
            for info in socket.getaddrinfo(host, None):
                ip = info[4][0]
                if _is_blocked_ip(ip):
                    raise UnsafeURLError(
                        "URL hostname resolves to a private or loopback address."
                    )
        except socket.gaierror:
            # If DNS fails, let the fetcher hit it and return the natural error.
            # We don't want false positives blocking real URLs in flaky DNS.
            pass

    return url
