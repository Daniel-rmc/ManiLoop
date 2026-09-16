"""HTTP presentation; all episode state and decisions belong to the runner."""

import json, os, queue, threading, time, signal, argparse
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from maniloop.runtime.runner import Demo
from maniloop.backends.factory import create_environment, options_from_args
from maniloop.providers.credentials import (
    ConfigError,
    discover_configs,
    normalize_base_url,
)
from maniloop.providers.catalog import ModelCatalogError
from maniloop.providers.responses import DEFAULT_MODEL

ROOT = Path(__file__).resolve().parents[1]


def handler_for(demo):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ManiLoop/0.1"

        def log_message(self, *args):
            pass

        def send(self, status, body, kind="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def json(self, status, value):
            self.send(
                status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            )

        def trusted(self):
            host = self.headers.get("Host", "")
            expected = {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }
            origin = self.headers.get("Origin")
            return host in expected and (
                origin is None or origin in {f"http://{h}" for h in expected}
            )

        def do_GET(self):
            if not self.trusted():
                return self.json(
                    403, {"error": "Only the local demo origin is allowed"}
                )
            path = urlparse(self.path).path
            if path == "/":
                self.send(
                    200,
                    (ROOT / "ui" / "index.html").read_bytes(),
                    "text/html; charset=utf-8",
                )
            elif path == "/api/config-options":
                configs = discover_configs()
                try:
                    manual_base = normalize_base_url(
                        demo.manual_base_url or os.environ.get("OPENAI_BASE_URL")
                    )
                except ConfigError:
                    manual_base = ""
                self.json(
                    200,
                    {
                        "configs": configs,
                        "default_path": configs[0]["path"] if configs else "",
                        "models": list(
                            dict.fromkeys([demo.default_model, DEFAULT_MODEL])
                        ),
                        "manual_base_url": manual_base,
                    },
                )
            elif path == "/api/libero-tasks":
                from maniloop.backends.libero.transport import list_tasks

                suite = parse_qs(urlparse(self.path).query).get(
                    "suite", ["libero_spatial"]
                )[0]
                try:
                    self.json(200, {"tasks": list_tasks(suite)})
                except (ValueError, RuntimeError) as exc:
                    self.json(400, {"error": str(exc)})
            elif path == "/api/state":
                with demo.lock:
                    state = dict(demo.state)
                self.json(200, state)
            elif path in ["/camera/external.jpg", "/camera/wrist.jpg"]:
                with demo.lock:
                    img = demo.images.get(path.split("/")[-1].split(".")[0])
                (
                    self.send(
                        200,
                        img,
                        "image/png" if img.startswith(b"\x89PNG") else "image/jpeg",
                    )
                    if img
                    else self.json(503, {"error": "Camera warming up"})
                )
            else:
                self.json(404, {"error": "Not found"})

        def do_POST(self):
            if not self.trusted():
                return self.json(
                    403, {"error": "Only the local demo origin is allowed"}
                )
            name = urlparse(self.path).path.removeprefix("/api/")
            if name not in [
                "start",
                "diagnose",
                "stop",
                "reset",
                "configure",
                "manual",
                "config-preview",
                "models",
            ]:
                return self.json(404, {"error": "Not found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 8 * 1024 * 1024:
                    raise ValueError("Invalid request length")
                try:
                    payload = json.loads(self.rfile.read(size))
                except (ValueError, UnicodeError):
                    raise ValueError("请求格式无效，请重新读取配置后再试") from None
                if not isinstance(payload, dict):
                    raise ValueError("Expected JSON object")
                if name in ["config-preview", "models"]:
                    try:
                        return self.json(200, demo.connection_request(name, payload))
                    except (ConfigError, ModelCatalogError, ValueError) as exc:
                        return self.json(400, {"ok": False, "error": str(exc)})
                    except Exception:
                        return self.json(
                            400,
                            {
                                "ok": False,
                                "error": "读取连接配置失败，请检查路径和供应商设置",
                            },
                        )
                done = queue.Queue(maxsize=1)
                demo.commands.put((name, payload, done))
                result = done.get(
                    timeout=360
                    if name == "start" and payload.get("agent") == "lerobot"
                    else 240
                )
                self.json(200 if result["ok"] else 400, result)
            except (ValueError, queue.Empty) as exc:
                self.json(400, {"ok": False, "error": str(exc)})

    return Handler


def serve(args):
    sim = create_environment(**options_from_args(args))
    if sim.backend == "libero":
        sim.set_llm_control(getattr(args, "llm_control", "osc_step"))
    demo = Demo(sim, args.model, timing=args.timing, output=args.output)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(demo))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    stopping = threading.Event()

    def stop_signal(*_):
        stopping.set()

    signal.signal(signal.SIGINT, stop_signal)
    signal.signal(signal.SIGTERM, stop_signal)
    print(f"ManiLoop demo: http://127.0.0.1:{args.port}", flush=True)
    next_publish = 0.0
    try:
        while not stopping.is_set():
            demo.advance(0.004)
            now = time.monotonic()
            if now >= next_publish:
                demo.publish()
                next_publish = now + 0.2
            time.sleep(0.002)
    finally:
        server.shutdown()
        server.server_close()
        demo.close()
