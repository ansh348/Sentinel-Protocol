#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_capture_proxy.py  --  FEASIBILITY helper (NOT FROZEN)

A localhost logging forward-proxy for the D38 equivalence gate's STEP 2 (request
equivalence).  It logs the FULL request body the Claude Code CLI (Path A) actually
sends to /v1/messages -- captured BEFORE forwarding, so the capture succeeds even
if the response handling later hiccups -- then forwards verbatim to
api.anthropic.com and returns the upstream response.

Secrets (x-api-key / authorization) are redacted from the log; the request BODY
(model, system, tools, sampling params, messages) is what we diff.

  python _capture_proxy.py <port> <logfile.jsonl>
"""
import json
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1])
LOG = sys.argv[2]
UPSTREAM = "https://api.anthropic.com"
REDACT = {"x-api-key", "authorization"}
HOP = {"host", "content-length", "connection", "transfer-encoding"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _forward(self, method):
        n = int(self.headers.get("content-length", 0) or 0)
        body = self.rfile.read(n) if n else b""
        # ---- LOG FIRST (capture guaranteed) ----
        try:
            parsed = json.loads(body) if body else None
        except ValueError:
            parsed = {"_unparsed_len": len(body)}
        hdrs = {k: ("<redacted>" if k.lower() in REDACT else v) for k, v in self.headers.items()}
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"method": method, "path": self.path,
                                "headers": hdrs, "body": parsed}) + "\n")
        # ---- forward verbatim ----
        req = urllib.request.Request(UPSTREAM + self.path, data=body if body else None, method=method)
        for k, v in self.headers.items():
            if k.lower() not in HOP:
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
                self.send_response(r.status)
                for k, v in r.headers.items():
                    if k.lower() in HOP:
                        continue
                    self.send_header(k, v)
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:  # noqa
            msg = json.dumps({"proxy_error": str(e)[:200]}).encode()
            self.send_response(502)
            self.send_header("content-length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def do_POST(self):
        self._forward("POST")

    def do_GET(self):
        self._forward("GET")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    open(LOG, "w").close()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
