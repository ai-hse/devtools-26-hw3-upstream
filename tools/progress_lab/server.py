"""Ready demonstration: one task history, three network interfaces."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import signal
import sys
import threading
import time
from urllib.parse import urlsplit
import uuid

import grpc
from websockets.exceptions import ConnectionClosed
from websockets.protocol import State
from websockets.sync.server import serve

import progress_pb2 as messages
import progress_pb2_grpc as rpc


STAGES = ("read_csv", "validate_rows", "calculate_metrics", "write_report", "done")


class Tasks:
    def __init__(self, delay):
        self.delay = delay
        self.changed = threading.Condition()
        self.tasks = {}
        self.stopping = threading.Event()

    def create(self):
        with self.changed:
            if len(self.tasks) >= 100:
                raise ValueError("Task limit reached; restart the demonstration")
            task_id = uuid.uuid4().hex
            self.tasks[task_id] = {"id": task_id, "state": "waiting", "events": []}
            return task_id

    def snapshot(self, task_id):
        with self.changed:
            task = self.tasks[task_id]
            return {**task, "events": list(task["events"])}

    def start(self, task_id):
        with self.changed:
            task = self.tasks[task_id]
            if task["state"] != "waiting":
                raise ValueError("Task has already been started")
            task["state"] = "running"
            threading.Thread(target=self.produce, args=(task_id,), daemon=True).start()

    def produce(self, task_id):
        for sequence, stage in enumerate(STAGES, 1):
            if self.stopping.wait(self.delay):
                return
            with self.changed:
                task = self.tasks[task_id]
                task["events"].append({
                    "task_id": task_id, "sequence": sequence,
                    "stage": stage, "created_at": time.time(),
                })
                if sequence == len(STAGES):
                    task["state"] = "done"
                self.changed.notify_all()

    def live_events(self, task_id, active, cursor):
        # Streams begin at subscription time; HTTP alone exposes past history.
        while not self.stopping.is_set() and active():
            with self.changed:
                task = self.tasks[task_id]
                pending = task["events"][cursor:]
                cursor += len(pending)
                done = task["state"] == "done"
                if not pending and not done:
                    self.changed.wait(timeout=0.2)
            yield from pending
            if done:
                return

    def close(self):
        self.stopping.set()
        with self.changed:
            self.changed.notify_all()


def http_handler(tasks):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, pattern, *args):
            print("HTTP " + pattern % args, file=sys.stderr, flush=True)

        def reply(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/health":
                self.reply(200, {"status": "ok"})
                return
            parts = path.strip("/").split("/")
            if len(parts) == 2 and parts[0] == "tasks":
                try:
                    self.reply(200, tasks.snapshot(parts[1]))
                except KeyError:
                    self.reply(404, {"error": "task not found"})
                return
            self.reply(404, {"error": "route not found"})

        def do_POST(self):
            path = urlsplit(self.path).path
            try:
                if path == "/tasks":
                    self.reply(201, {"id": tasks.create(), "state": "waiting"})
                    return
                parts = path.strip("/").split("/")
                if len(parts) == 3 and parts[0] == "tasks" and parts[2] == "start":
                    tasks.start(parts[1])
                    self.reply(202, {"id": parts[1], "state": "running"})
                    return
            except KeyError:
                self.reply(404, {"error": "task not found"})
                return
            except ValueError as error:
                self.reply(409, {"error": str(error)})
                return
            self.reply(404, {"error": "route not found"})

    return Handler


def websocket_handler(tasks):
    def handle(connection):
        parts = urlsplit(connection.request.path).path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != "tasks":
            connection.close(1008, "expected /tasks/ID")
            return
        try:
            # Establish the cursor before advertising readiness to the client.
            with tasks.changed:
                cursor = len(tasks.tasks[parts[1]]["events"])
                connection.send(json.dumps({"type": "ready", "id": parts[1]}))
            active = lambda: connection.state is State.OPEN
            for event in tasks.live_events(parts[1], active, cursor):
                connection.send(json.dumps({"type": "event", **event}))
            if tasks.stopping.is_set():
                connection.close(1012, "server stopped")
                return
            connection.send(json.dumps({"type": "done", "id": parts[1]}))
        except KeyError:
            connection.close(1008, "task not found")
        except ConnectionClosed:
            pass
    return handle


class Progress(rpc.ProgressServicer):
    def __init__(self, tasks):
        self.tasks = tasks

    def GetState(self, request, context):
        try:
            return messages.TaskState(**self.tasks.snapshot(request.id))
        except KeyError:
            context.abort(grpc.StatusCode.NOT_FOUND, "task not found")

    def Watch(self, request, context):
        try:
            with self.tasks.changed:
                cursor = len(self.tasks.tasks[request.id]["events"])
            context.send_initial_metadata((("subscription", "ready"),))
            for event in self.tasks.live_events(request.id, context.is_active, cursor):
                yield messages.Event(**event)
            if self.tasks.stopping.is_set():
                context.abort(grpc.StatusCode.UNAVAILABLE, "server stopped")
        except KeyError:
            context.abort(grpc.StatusCode.NOT_FOUND, "task not found")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1"],
                        help="loopback only; use SSH for remote access")
    parser.add_argument("--http-port", type=int, default=8020)
    parser.add_argument("--ws-port", type=int, default=8021)
    parser.add_argument("--grpc-port", type=int, default=8022)
    parser.add_argument("--step-delay", type=float, default=1.0,
                        help="seconds between five events; default 1")
    args = parser.parse_args()
    if not 0.02 <= args.step_delay <= 10:
        parser.error("--step-delay must be between 0.02 and 10 seconds")
    for port in (args.http_port, args.ws_port, args.grpc_port):
        if not 0 <= port <= 65535:
            parser.error("ports must be in 0..65535; 0 selects a free port")

    tasks = Tasks(args.step_delay)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    http = ws = backend = None
    threads = []
    try:
        http = ThreadingHTTPServer((args.host, args.http_port), http_handler(tasks))
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        threads.append(thread)
        ws = serve(websocket_handler(tasks), args.host, args.ws_port,
                   ping_interval=2, ping_timeout=3, close_timeout=1)
        thread = threading.Thread(target=ws.serve_forever, daemon=True)
        thread.start()
        threads.append(thread)
        backend = grpc.server(ThreadPoolExecutor(max_workers=12),
                              options=[("grpc.so_reuseport", 0)])
        rpc.add_ProgressServicer_to_server(Progress(tasks), backend)
        grpc_port = backend.add_insecure_port(f"{args.host}:{args.grpc_port}")
        if not grpc_port:
            raise RuntimeError("gRPC port could not be bound")
        backend.start()
        print(json.dumps({"ready": True, "http_port": http.server_port,
                          "ws_port": ws.socket.getsockname()[1], "grpc_port": grpc_port}),
              flush=True)
        stop.wait()
    except (OSError, RuntimeError) as error:
        print(f"Cannot start demonstration: {error}", file=sys.stderr)
        return 1
    finally:
        tasks.close()
        if backend:
            backend.stop(0).wait(timeout=3)
        if ws:
            ws.shutdown()
        if http:
            if threads:
                http.shutdown()
            http.server_close()
        for thread in threads:
            thread.join(timeout=3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
