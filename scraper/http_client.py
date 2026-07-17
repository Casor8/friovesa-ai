from __future__ import annotations

import logging
import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import Settings


class HttpClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.local = threading.local()
        self.log = logging.getLogger(__name__)

    def _session(self) -> requests.Session:
        if not hasattr(self.local, "session"):
            session = requests.Session()
            retry = Retry(
                total=self.settings.retries,
                connect=self.settings.retries,
                read=self.settings.retries,
                status=self.settings.retries,
                backoff_factor=0.8,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset(("GET", "HEAD")),
                raise_on_status=False,
            )
            session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20))
            session.mount("http://", HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20))
            session.headers.update({"User-Agent": self.settings.user_agent, "Accept-Language": "es-EC,es;q=0.9"})
            self.local.session = session
        return self.local.session

    def get(self, url: str, *, allow_redirects: bool = True) -> requests.Response:
        if self.settings.delay_seconds:
            time.sleep(self.settings.delay_seconds)
        response = self._session().get(
            url,
            timeout=self.settings.timeout_seconds,
            allow_redirects=allow_redirects,
        )
        self.log.debug("GET %s -> %s", url, response.status_code)
        return response

    def head(self, url: str, *, allow_redirects: bool = True) -> requests.Response:
        response = self._session().head(
            url, timeout=self.settings.timeout_seconds, allow_redirects=allow_redirects
        )
        # Algunos sitios WordPress no implementan HEAD correctamente.
        if response.status_code in (405, 501):
            return self.get(url, allow_redirects=allow_redirects)
        return response
