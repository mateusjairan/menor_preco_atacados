"""Cliente HTTP com curl-cffi, retry, rate limit e fallback de impersonation."""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote, urlencode

from curl_cffi import requests
from curl_cffi.requests.exceptions import RequestException, Timeout

from . import config

logger = logging.getLogger(__name__)


class HttpError(RuntimeError):
    """Erro de rede já traduzido para uma mensagem curta de UI."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


SessionFactory = Callable[[str], Any]


class HttpClient:
    """Uma instância/sessão por rede. Nunca compartilhe sessão entre redes."""

    RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        chain: str = "",
        *,
        timeout: float | None = None,
        impersonate: str | None = None,
        fallbacks: tuple[str, ...] | None = None,
        min_interval: float | None = None,
        max_retries: int = 2,
        backoff: tuple[float, ...] = (0.5, 1.5),
        session_factory: SessionFactory | None = None,
    ) -> None:
        self.chain = chain
        self.timeout = config.HTTP_TIMEOUT if timeout is None else timeout
        primary = impersonate or config.IMPERSONATE
        alternates = config.IMPERSONATE_FALLBACKS if fallbacks is None else fallbacks
        self._impersonates = tuple(dict.fromkeys((primary, *alternates)))
        self.min_interval = (
            1.0 / config.RATE_LIMIT_PER_SECOND if min_interval is None else min_interval
        )
        self.max_retries = max_retries
        self._backoff = backoff
        self._session_factory: SessionFactory = session_factory or (
            lambda profile: requests.Session(impersonate=profile)
        )
        self._session: Any | None = None
        self._impersonate_index = 0
        self._last_request_at: float | None = None
        self.headers = {
            "User-Agent": config.USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "pt-BR",
        }

    @property
    def impersonate(self) -> str:
        return self._impersonates[self._impersonate_index]

    def _get_session(self) -> Any:
        if self._session is None:
            self._session = self._session_factory(self.impersonate)
        return self._session

    def _rotate_impersonate(self) -> bool:
        if self._impersonate_index + 1 >= len(self._impersonates):
            return False
        self._impersonate_index += 1
        self.close()
        logger.info(
            "HTTP %s: alternando impersonation para %s",
            self.chain,
            self.impersonate,
        )
        return True

    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        if self._last_request_at is not None:
            wait = self.min_interval - (now - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _build_url(url: str, params: dict[str, Any] | None) -> str:
        if not params:
            return url
        # `quote_via=quote` gera %20 em vez de "+". VTEX rejeita "+" com 400.
        query = urlencode(params, quote_via=quote, safe="")
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{query}"

    def _request_json(
        self,
        url: str,
        params: dict[str, Any] | None,
        send: Callable[[str], Any],
    ) -> list[dict[str, Any]] | dict[str, Any]:
        target = self._build_url(url, params)
        attempts = 0
        rotated = False

        while True:
            self._throttle()
            try:
                response = send(target)
            except Timeout as exc:
                raise HttpError("tempo esgotado") from exc
            except RequestException as exc:
                if not rotated and self._rotate_impersonate():
                    rotated = True
                    continue
                raise HttpError("falha de conexão") from exc

            status = response.status_code
            if status in self.RETRY_STATUSES and attempts < self.max_retries:
                delay = self._backoff[min(attempts, len(self._backoff) - 1)]
                logger.info(
                    "HTTP %s: status %s, retry em %.1fs", self.chain, status, delay
                )
                time.sleep(delay)
                attempts += 1
                continue

            if status == 429:
                raise HttpError("bloqueio temporário")
            if status >= 500:
                raise HttpError("instabilidade")
            if status >= 400:
                raise HttpError("resposta inesperada")

            try:
                return response.json()
            except (ValueError, TypeError) as exc:
                raise HttpError("resposta inesperada") from exc

    def get_json(
        self, url: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """GET + JSON com retry em 429/5xx e fallback de impersonation."""

        return self._request_json(
            url,
            params,
            lambda target: self._get_session().get(
                target,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True,
            ),
        )

    def post_json(
        self,
        url: str,
        body: dict[str, Any] | list[Any],
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """POST JSON com o mesmo retry/fallback do GET."""

        return self._request_json(
            url,
            params,
            lambda target: self._get_session().post(
                target,
                headers=self.headers,
                json=body,
                timeout=self.timeout,
                allow_redirects=True,
            ),
        )

    def close(self) -> None:
        if self._session is not None:
            with contextlib.suppress(Exception):  # fechamento best effort
                self._session.close()
            self._session = None

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
