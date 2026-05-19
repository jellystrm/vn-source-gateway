from __future__ import annotations

import logging
import threading
from http.server import ThreadingHTTPServer

from .handler import build_handler

log = logging.getLogger(__name__)


class UiServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.httpd = ThreadingHTTPServer((host, port), build_handler())

    def start_background(self) -> None:
        thread = threading.Thread(target=self.serve_forever, name="vn-source-gateway-ui", daemon=True)
        thread.start()

    def serve_forever(self) -> None:
        log.info("UI listening on http://%s:%s", self.host, self.port)
        self.httpd.serve_forever()
