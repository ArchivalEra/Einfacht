"""Exercise all three doctor probe kinds: http, port-free, docker.

http and port-free are exercised for real (a local server we start, and a port
we bind then release). docker is exercised only when the CLI exists — a
capability probe, not a required dependency — and the example states which
path it took, so a missing docker never passes silently as "covered".
"""
import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("X-Example", "einfacht")
        self.end_headers()

    def log_message(self, _format, *_args):
        return


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run(spec, expect):
    Path("doctor.json").write_text(json.dumps(spec), encoding="utf-8")
    proc = subprocess.run([sys.executable, "zreflect/doctor.py"], check=False,
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != expect:
        print("unexpected rc %d (expected %d): %s"
              % (proc.returncode, expect, proc.stdout + proc.stderr),
              file=sys.stderr)
        raise SystemExit(1)


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    url = f"http://127.0.0.1:{server.server_port}/"
    idle = free_port()

    alive = {"checks": [
        {"kind": "http", "url": url, "expect_status": 200,
         "expect_headers": {"X-Example": "einfacht"},
         "why": "local acceptance service"},
        {"kind": "port-free", "port": idle,
         "why": "experiment-exclusive port must stay free"},
    ]}
    run(alive, 0)

    wrong_status = {"checks": [
        {"kind": "http", "url": url, "expect_status": 201,
         "why": "demonstrate a status mismatch"}]}
    run(wrong_status, 1)

    occupied = {"checks": [
        {"kind": "port-free", "port": server.server_port,
         "why": "demonstrate an occupied port going DOWN"}]}
    run(occupied, 1)

    unknown_kind = {"checks": [{"kind": "carrier-pigeon", "why": "zero-value guard"}]}
    run(unknown_kind, 2)

    docker = "docker"
    from shutil import which
    if which(docker):
        no_such = {"checks": [
            {"kind": "docker", "container": "einfacht-no-such-container",
             "state": "running", "why": "demonstrate a missing container going DOWN"}]}
        run(no_such, 1)
        print("doctor example ok (http + port-free + docker inspected)")
    else:
        print("doctor example ok (http + port-free; docker CLI absent — "
              "docker probe not exercised on this machine)")
finally:
    server.shutdown()
    server.server_close()
    thread.join()
