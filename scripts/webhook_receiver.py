"""Local-only signed webhook verifier used by integration tests and the demo."""

import hashlib
import hmac
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from foundry.config import settings

lock = threading.Lock()
secrets = {}
receipts = deque(maxlen=1000)
consumed = set()
fail_hooks = set()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, data):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def authorized(self):
        return hmac.compare_digest(self.headers.get("X-Receiver-Control", ""), settings().app_secret)

    def do_GET(self):
        if self.path == "/health":
            self.send(200, {"status": "ok"})
        elif self.path == "/receipts" and self.authorized():
            with lock:
                self.send(200, {"items": list(receipts), "consumed_count": len(consumed)})
        else:
            self.send(403, {"error": "Forbidden"})

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size > 1000000:
            return self.send(413, {"error": "Too large"})
        raw = self.rfile.read(size)
        if self.path == "/configure" and self.authorized():
            data = json.loads(raw)
            with lock:
                secrets[data["webhook_id"]] = data["secret"]
                (fail_hooks.add if data.get("fail") else fail_hooks.discard)(data["webhook_id"])
            return self.send(200, {"configured": True})
        if self.path != "/events":
            return self.send(404, {"error": "Not found"})
        hook = self.headers.get("X-Foundry-Webhook-Id", "")
        timestamp = self.headers.get("X-Foundry-Timestamp", "0")
        signature = self.headers.get("X-Foundry-Signature", "")
        with lock:
            secret = secrets.get(hook)
            expected = (
                "v1="
                + hmac.new(
                    (secret or "").encode(), timestamp.encode() + b"." + raw, hashlib.sha256
                ).hexdigest()
            )
            valid = bool(
                secret
                and timestamp.isdigit()
                and abs(time.time() - int(timestamp)) <= 300
                and hmac.compare_digest(signature, expected)
            )
            event = json.loads(raw)
            duplicate = event["event_id"] in consumed
            receipts.append(
                {
                    "payload": event,
                    "raw": raw.decode(),
                    "signature": signature,
                    "timestamp": timestamp,
                    "webhook_id": hook,
                    "delivery_id": self.headers.get("X-Foundry-Delivery-Id"),
                    "valid": valid,
                    "duplicate": duplicate,
                }
            )
            code = 401 if not valid else 500 if hook in fail_hooks else 200
            if code == 200:
                consumed.add(event["event_id"])
        self.send(code, {"accepted": code == 200, "duplicate": duplicate})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9100), Handler).serve_forever()
