"""Ready clients for the optional polling, WebSocket and gRPC experiments."""

import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import grpc
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

import progress_pb2 as messages
import progress_pb2_grpc as rpc


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def http_request(base, path, method="GET", timeout=3):
    request = Request(base.rstrip("/") + path, method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def event_line(event):
    return {"type": "event", **event,
            "latency_ms": round((time.time() - event["created_at"]) * 1000, 3)}


def from_proto(event):
    return {"task_id": event.task_id, "sequence": event.sequence,
            "stage": event.stage, "created_at": event.created_at}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http", default="http://127.0.0.1:8020",
                        help="HTTP base URL; default http://127.0.0.1:8020")
    parser.add_argument("--ws", default="ws://127.0.0.1:8021",
                        help="WebSocket base URL; default ws://127.0.0.1:8021")
    parser.add_argument("--grpc", default="127.0.0.1:8022",
                        help="gRPC host:port; default 127.0.0.1:8022")
    parser.add_argument("--timeout", type=float, default=120,
                        help="maximum observation time in seconds; default 120")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("create", help="create a waiting task; print its ID only")
    for name in ("start", "state", "poll", "ws", "grpc-state", "grpc-stream"):
        cmd = commands.add_parser(name)
        cmd.add_argument("id", help="task ID printed by create")
        if name == "poll":
            cmd.add_argument("--interval", type=float, default=2,
                             help="pause between requests in seconds; default 2")
    args = parser.parse_args()
    if not 0 < args.timeout <= 3600:
        parser.error("--timeout must be in (0, 3600]")
    if args.command == "poll" and not 0.02 <= args.interval <= 60:
        parser.error("--interval must be in [0.02, 60]")

    try:
        if args.command == "create":
            print(http_request(args.http, "/tasks", "POST")["id"], flush=True)
        elif args.command == "start":
            emit(http_request(args.http, f"/tasks/{args.id}/start", "POST"))
        elif args.command == "state":
            emit(http_request(args.http, f"/tasks/{args.id}"))
        elif args.command == "poll":
            seen = set()
            requests = 0
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                state = http_request(args.http, f"/tasks/{args.id}",
                                     timeout=min(3, max(0.01, deadline-time.monotonic())))
                requests += 1
                if requests == 1:
                    emit({"type": "ready", "transport": "poll", "id": args.id})
                for event in state["events"]:
                    if event["sequence"] not in seen:
                        emit(event_line(event))
                        seen.add(event["sequence"])
                if state["state"] == "done":
                    emit({"type": "summary", "transport": "poll", "events": len(seen),
                          "http_requests": requests})
                    return 0
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(args.interval, remaining))
            raise TimeoutError("observation deadline expired")
        elif args.command == "ws":
            count = 0
            deadline = time.monotonic() + args.timeout
            with connect(args.ws.rstrip("/") + f"/tasks/{args.id}",
                         open_timeout=min(3, args.timeout), close_timeout=1,
                         ping_interval=2, ping_timeout=3) as connection:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("observation deadline expired")
                    message = json.loads(connection.recv(timeout=remaining))
                    if message["type"] == "event":
                        emit(event_line(message))
                        count += 1
                    elif message["type"] == "ready":
                        emit({**message, "transport": "ws"})
                    elif message["type"] == "done":
                        emit({"type": "summary", "transport": "ws", "events": count,
                              "http_requests": 1, "data_requests": 0})
                        return 0
        elif args.command in ("grpc-state", "grpc-stream"):
            with grpc.insecure_channel(args.grpc) as channel:
                client = rpc.ProgressStub(channel)
                request = messages.TaskRequest(id=args.id)
                if args.command == "grpc-state":
                    state = client.GetState(request, timeout=min(3, args.timeout))
                    emit({"id": state.id, "state": state.state,
                          "events": [from_proto(event) for event in state.events]})
                else:
                    stream = client.Watch(request, timeout=args.timeout)
                    metadata = dict(stream.initial_metadata())
                    if metadata.get("subscription") != "ready":
                        # Iteration raises the original gRPC status for a failed call.
                        next(stream)
                        raise RuntimeError("missing subscription confirmation")
                    emit({"type": "ready", "transport": "grpc", "id": args.id})
                    count = 0
                    for event in stream:
                        emit(event_line(from_proto(event)))
                        count += 1
                    emit({"type": "summary", "transport": "grpc", "events": count,
                          "rpc_calls": 1})
        return 0
    except HTTPError as error:
        print(f"HTTP {error.code}: {error.read().decode(errors='replace')}", file=sys.stderr)
    except grpc.RpcError as error:
        print(f"gRPC {error.code().name}: {error.details()}", file=sys.stderr)
    except ConnectionClosed as error:
        print(f"WebSocket closed before task completion: {error}", file=sys.stderr)
    except (URLError, OSError, TimeoutError, ValueError, RuntimeError) as error:
        print(f"Client failed: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        print("Client interrupted", file=sys.stderr)
        return 130
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
