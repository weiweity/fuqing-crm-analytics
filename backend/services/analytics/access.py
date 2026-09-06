"""Server-owned B0 identities and object capabilities; no CRM auth imports."""

from dataclasses import dataclass
from hashlib import sha256
from threading import RLock


class AnalyticsError(Exception):
    """Only safe, predefined messages reach HTTP clients."""

    def __init__(self, status: int, code: str, message: str, *, retryable: bool = False,
                 recovery_url: str | None = None):
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable
        self.recovery_url = recovery_url


@dataclass(frozen=True)
class AnalyticsPrincipal:
    actor_id: str
    capabilities: frozenset[str]
    data_scopes: frozenset[str]


def require(principal: AnalyticsPrincipal, capability: str, *, data_scope: str = "b0-fixture") -> None:
    if capability not in principal.capabilities or data_scope not in principal.data_scopes:
        if data_scope == "b0-fixture":
            raise AnalyticsError(403, "FORBIDDEN", "当前身份无权操作此 B0 合成任务。")
        raise AnalyticsError(403, "FORBIDDEN", "当前身份无权操作此查询任务。")


class B0IdentityRegistry:
    """Explicit injected identities for local B0, never production authentication.

    Tokens are opaque caller secrets, not actor IDs. No identity is enabled by
    default, and every request/replay/stream read resolves current grants again.
    """

    def __init__(self):
        self._grants: dict[bytes, AnalyticsPrincipal] = {}
        self._lock = RLock()

    def grant(self, token: str, principal: AnalyticsPrincipal) -> None:
        if (not isinstance(token, str) or not 32 <= len(token) <= 1017
                or any(ord(c) < 33 or ord(c) > 126 for c in token)
                or not principal.actor_id or len(principal.actor_id) > 128):
            raise ValueError("explicit B0 identity and a sufficiently long token required")
        with self._lock:
            self._grants[sha256(token.encode()).digest()] = principal

    def revoke(self, token: str) -> None:
        with self._lock:
            self._grants.pop(sha256(token.encode()).digest(), None)

    def resolve(self, authorization: str | None) -> AnalyticsPrincipal:
        if not authorization or not authorization.startswith("Bearer ") or len(authorization) > 1024:
            raise AnalyticsError(401, "UNAUTHENTICATED", "需要本次 B0 的有效身份。")
        digest = sha256(authorization[7:].encode()).digest()
        with self._lock:
            principal = self._grants.get(digest)
        if principal is None:
            raise AnalyticsError(401, "UNAUTHENTICATED", "需要本次 B0 的有效身份。")
        return principal
