# Manual test helper: prints each webhook POST body to stdout.
# Run: python3 fixtures/webhook_sink.py
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        print(self.rfile.read(length).decode("utf-8"), flush=True)
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass

HTTPServer(("127.0.0.1", 9002), Handler).serve_forever()
