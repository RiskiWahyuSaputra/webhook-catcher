import http.server
import socketserver
import urllib.parse
import urllib.request
import urllib.error
import json
import uuid
import time
import sys
import os
import threading
import mimetypes

from database import init_db, save_request, list_requests, get_request_by_id, clear_requests

PORT = 4040
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# SSE Clients registry
sse_clients = set()
sse_lock = threading.Lock()

def broadcast_sse(event_data):
    payload = f"data: {json.dumps(event_data)}\n\n".encode("utf-8")
    with sse_lock:
        dead_clients = set()
        for wfile in sse_clients:
            try:
                wfile.write(payload)
                wfile.flush()
            except Exception:
                dead_clients.add(wfile)
        sse_clients.difference_update(dead_clients)

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def send_json(self, status_code, data):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def handle_static(self, rel_path):
        clean = rel_path.lstrip("/") or "index.html"
        fpath = os.path.join(STATIC_DIR, clean)
        if os.path.exists(fpath) and os.path.isfile(fpath):
            mime, _ = mimetypes.guess_type(fpath)
            with open(fpath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime or "text/plain")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return True
        return False

    def handle_sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        with sse_lock:
            sse_clients.add(self.wfile)

        try:
            # Send initial keepalive
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                time.sleep(15)
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except Exception:
            with sse_lock:
                sse_clients.discard(self.wfile)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/events":
            self.handle_sse()
            return

        if path == "/api/requests":
            endpoint = query.get("endpoint", [None])[0]
            search = query.get("search", [None])[0]
            reqs = list_requests(endpoint=endpoint, search=search)
            self.send_json(200, {"ok": True, "data": reqs})
            return

        if path.startswith("/api/requests/"):
            req_id = path[len("/api/requests/"):]
            r = get_request_by_id(req_id)
            if r:
                self.send_json(200, {"ok": True, "data": r})
            else:
                self.send_json(404, {"ok": False, "error": "Request not found"})
            return

        # Check if it's a hook destination GET
        if path.startswith("/hook/"):
            self.capture_and_respond("GET")
            return

        # Static assets
        if path == "/" or not path.startswith("/api/"):
            if self.handle_static(path):
                return

        self.send_json(404, {"ok": False, "error": "Not Found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/replay":
            self.handle_replay()
            return

        if path == "/api/clear":
            clear_requests()
            broadcast_sse({"type": "clear"})
            self.send_json(200, {"ok": True, "message": "All requests cleared"})
            return

        if path.startswith("/hook/"):
            self.capture_and_respond("POST")
            return

        self.send_json(404, {"ok": False, "error": "Not Found"})

    def do_PUT(self):
        if self.path.startswith("/hook/"):
            self.capture_and_respond("PUT")
        else:
            self.send_json(404, {"ok": False, "error": "Not Found"})

    def do_PATCH(self):
        if self.path.startswith("/hook/"):
            self.capture_and_respond("PATCH")
        else:
            self.send_json(404, {"ok": False, "error": "Not Found"})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/hook/"):
            self.capture_and_respond("DELETE")
        else:
            self.send_json(404, {"ok": False, "error": "Not Found"})

    def capture_and_respond(self, method):
        parsed = urllib.parse.urlparse(self.path)
        endpoint = parsed.path[len("/hook/"):].strip("/") or "default"
        query_params = {k: v[0] if len(v) == 1 else v for k, v in urllib.parse.parse_qs(parsed.query).items()}

        content_length = int(self.headers.get("Content-Length", 0))
        body = ""
        if content_length > 0:
            raw_body = self.rfile.read(content_length)
            try:
                body = raw_body.decode("utf-8")
            except Exception:
                body = f"[Binary data: {len(raw_body)} bytes]"

        headers_dict = dict(self.headers)
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
        req_uuid = str(uuid.uuid4())

        record = {
            "uuid": req_uuid,
            "method": method,
            "path": parsed.path,
            "endpoint": endpoint,
            "query_params": query_params,
            "headers": headers_dict,
            "body": body,
            "client_ip": client_ip,
            "content_type": self.headers.get("Content-Type", ""),
            "size_bytes": content_length,
            "created_at": int(time.time())
        }

        # Save to DB
        save_request(record)

        # Broadcast live to SSE listeners
        broadcast_sse({"type": "new_request", "data": record})

        # Return 200 OK webhook acknowledgement
        self.send_json(200, {
            "ok": True,
            "message": "Webhook captured successfully",
            "uuid": req_uuid,
            "endpoint": endpoint,
            "method": method,
            "timestamp": record["created_at"]
        })

    def handle_replay(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(body)
            target_url = payload.get("target_url")
            req_id = payload.get("request_id")
            if not target_url or not req_id:
                self.send_json(400, {"ok": False, "error": "target_url and request_id required"})
                return

            req_item = get_request_by_id(req_id)
            if not req_item:
                self.send_json(404, {"ok": False, "error": "Request not found"})
                return

            # Execute HTTP request replay
            headers = {k: v for k, v in req_item["headers"].items() if k.lower() not in ("host", "content-length")}
            req_data = req_item["body"].encode("utf-8") if req_item["body"] else None

            forward_req = urllib.request.Request(target_url, data=req_data, headers=headers, method=req_item["method"])
            start_t = time.time()
            try:
                with urllib.request.urlopen(forward_req, timeout=10) as resp:
                    resp_body = resp.read().decode("utf-8", errors="ignore")
                    elapsed = round((time.time() - start_t) * 1000, 2)
                    self.send_json(200, {
                        "ok": True,
                        "status": resp.status,
                        "time_ms": elapsed,
                        "response": resp_body[:2000]
                    })
            except urllib.error.HTTPError as he:
                elapsed = round((time.time() - start_t) * 1000, 2)
                self.send_json(200, {
                    "ok": False,
                    "status": he.code,
                    "time_ms": elapsed,
                    "error": str(he)
                })
        except Exception as e:
            self.send_json(500, {"ok": False, "error": str(e)})

    def log_message(self, format, *args):
        # Clean terminal logging
        pass

def run():
    init_db()
    port = PORT
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True

    print("=" * 60)
    print("  WEBHOOK CATCHER & REQUEST INSPECTOR")
    print("=" * 60)
    print(f"  Dashboard UI : http://localhost:{port}")
    print(f"  Webhook URL  : http://localhost:{port}/hook/<any-name>")
    print("=" * 60)

    with ThreadedHTTPServer(("", port), WebhookHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer dihentikan.")

if __name__ == "__main__":
    run()
