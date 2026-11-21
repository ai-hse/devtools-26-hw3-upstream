"""Check the ready demonstration; this does not grade homework solutions."""

import json
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent


def first_line(process):
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        if not selector.select(timeout=10):
            raise AssertionError("process produced no readiness message")
    line = process.stdout.readline()
    if not line:
        raise AssertionError(f"process exited early: {process.poll()}")
    return json.loads(line)


def main():
    processes = []
    with tempfile.TemporaryFile(mode="w+") as logs:
        try:
            server = subprocess.Popen(
                [sys.executable, str(HERE / "server.py"), "--http-port", "0",
                 "--ws-port", "0", "--grpc-port", "0", "--step-delay", "0.15"],
                stdout=subprocess.PIPE, stderr=logs, text=True,
            )
            processes.append(server)
            ports = first_line(server)
            assert ports["ready"]
            for kind in ("http", "ws", "grpc"):
                occupied = subprocess.run(
                    [sys.executable, str(HERE / "server.py"), "--http-port", "0",
                     "--ws-port", "0", "--grpc-port", "0",
                     f"--{kind}-port", str(ports[f"{kind}_port"])],
                    capture_output=True, text=True, timeout=8,
                )
                assert occupied.returncode != 0, occupied.stdout
                assert server.poll() is None
            print("PASS: occupied ports fail promptly; the original server survives")
            prefix = [sys.executable, str(HERE / "client.py"),
                      "--http", f"http://127.0.0.1:{ports['http_port']}",
                      "--ws", f"ws://127.0.0.1:{ports['ws_port']}",
                      "--grpc", f"127.0.0.1:{ports['grpc_port']}", "--timeout", "8"]

            def call(*args, ok=True):
                result = subprocess.run(prefix + list(args), capture_output=True,
                                        text=True, timeout=12)
                if ok:
                    assert result.returncode == 0, result.stderr
                else:
                    assert result.returncode != 0, result.stdout
                return result

            def subscribe(task_id):
                clients = []
                for mode in ("poll", "ws", "grpc-stream"):
                    args = [mode, task_id] + (["--interval", "0.4"] if mode == "poll" else [])
                    process = subprocess.Popen(prefix + args, stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE, text=True)
                    processes.append(process)
                    ready = first_line(process)
                    assert ready["type"] == "ready", ready
                    clients.append(process)
                return clients

            task_id = call("create").stdout.strip()
            waiting = json.loads(call("state", task_id).stdout)
            assert waiting["state"] == "waiting" and waiting["events"] == []
            assert json.loads(call("grpc-state", task_id).stdout) == waiting
            clients = subscribe(task_id)
            call("start", task_id)
            histories = []
            for process in clients:
                out, err = process.communicate(timeout=10)
                assert process.returncode == 0, err
                rows = [json.loads(line) for line in out.splitlines()]
                events = [row for row in rows if row["type"] == "event"]
                assert [row["sequence"] for row in events] == list(range(1, 6)), rows
                assert all(row["task_id"] == task_id for row in events)
                assert all(isinstance(row["latency_ms"], (int, float)) for row in events)
                assert rows[-1]["type"] == "summary" and rows[-1]["events"] == 5
                histories.append([(row["sequence"], row["stage"], row["created_at"])
                                  for row in events])
            assert histories[0] == histories[1] == histories[2]
            http = json.loads(call("state", task_id).stdout)
            assert http == json.loads(call("grpc-state", task_id).stdout)
            assert http["state"] == "done" and len(http["events"]) == 5
            assert "HTTP 409" in call("start", task_id, ok=False).stderr
            assert "HTTP 404" in call("state", "missing", ok=False).stderr
            assert "NOT_FOUND" in call("grpc-state", "missing", ok=False).stderr
            assert "NOT_FOUND" in call("grpc-stream", "missing", ok=False).stderr
            assert "task not found" in call("ws", "missing", ok=False).stderr
            print("PASS: same five events and timestamps over all three transports")
            print("PASS: waiting/start, complete history, duplicate start, missing IDs")

            waiting_id = call("create").stdout.strip()
            interrupted = subscribe(waiting_id)
            server.terminate()
            server.wait(timeout=8)
            for process in interrupted:
                _, err = process.communicate(timeout=10)
                assert process.returncode != 0, err
            assert "UNAVAILABLE" in call("grpc-state", task_id, ok=False).stderr
            print("PASS: server shutdown is detected by poll, WebSocket and gRPC")
        except Exception:
            logs.seek(0)
            print(logs.read(), file=sys.stderr)
            raise
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
