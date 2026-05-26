"""Run the Flow Memory TouchDesigner live stack from one terminal.

This starts, in order:
1. The local Flow Memory API server, unless one is already reachable.
2. The read-only UDP telemetry bridge for TouchDesigner.
3. A local neural live-session pump that emits step/learn ticks.

TouchDesigner itself still stays open as the visual surface. Run the Textport
loader in TouchDesigner once, then leave this process running until Ctrl+C.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8766
DEFAULT_UDP_PORT = 7000
DEFAULT_AGENT_ID = "touchdesigner-neural-worker"
DEFAULT_GOAL = "Stream a local neural memory loop into TouchDesigner"

LOCAL_OPENER = build_opener(ProxyHandler({}))


@dataclass(frozen=True)
class StackConfig:
    host: str = DEFAULT_HOST
    api_port: int = DEFAULT_API_PORT
    udp_port: int = DEFAULT_UDP_PORT
    ticks: int = 999_999
    interval: float = 0.25
    learn_every: int = 2
    learning_rate: float = 0.12
    agent_id: str = DEFAULT_AGENT_ID
    goal: str = DEFAULT_GOAL
    backend: str = "tiny_torch"
    show_bridge_frames: bool = False
    dry_run: bool = False
    startup_timeout: float = 12.0

    @property
    def api_url(self) -> str:
        return f"http://{self.host}:{self.api_port}"


@dataclass
class ManagedProcess:
    name: str
    popen: subprocess.Popen[str]
    owned: bool = True


def api_server_command(config: StackConfig) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "scripts" / "run_local_api_server.py"),
        "--host",
        config.host,
        "--port",
        str(config.api_port),
    ]


def bridge_command(config: StackConfig) -> list[str]:
    command = [
        sys.executable,
        str(ROOT / "tools" / "touchdesigner" / "flowmemory_td_bridge.py"),
        "--api",
        config.api_url,
        "--udp-host",
        config.host,
        "--udp-port",
        str(config.udp_port),
        "--interval",
        str(config.interval),
    ]
    if config.show_bridge_frames:
        command.append("--stdout")
    return command


def agent_command(config: StackConfig) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "tools" / "touchdesigner" / "start_live_neural_agent.py"),
        "--api",
        config.api_url,
        "--agent-id",
        config.agent_id,
        "--goal",
        config.goal,
        "--backend",
        config.backend,
        "--ticks",
        str(config.ticks),
        "--interval",
        str(config.interval),
        "--learn-every",
        str(config.learn_every),
        "--learning-rate",
        str(config.learning_rate),
    ]


def is_api_ready(config: StackConfig) -> bool:
    request = Request(f"{config.api_url}/health", method="GET", headers={"accept": "application/json"})
    try:
        with LOCAL_OPENER.open(request, timeout=0.45) as response:  # noqa: S310 - local operator API only
            return 200 <= response.status < 300
    except (OSError, TimeoutError, URLError):
        return False


def wait_for_api(config: StackConfig, api_proc: ManagedProcess | None) -> bool:
    deadline = time.monotonic() + config.startup_timeout
    while time.monotonic() < deadline:
        if is_api_ready(config):
            return True
        if api_proc is not None and api_proc.popen.poll() is not None:
            return is_api_ready(config)
        time.sleep(0.2)
    return False


def launch_process(name: str, command: list[str], *, quiet: bool = False) -> ManagedProcess:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL if quiet else subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=creationflags,
    )
    managed = ManagedProcess(name=name, popen=process)
    if not quiet:
        threading.Thread(target=forward_output, args=(managed,), daemon=True).start()
    return managed


def forward_output(process: ManagedProcess) -> None:
    stream = process.popen.stdout
    if stream is None:
        return
    prefix = f"[{process.name}] "
    for line in stream:
        print(prefix + line.rstrip())


def run_stack(config: StackConfig) -> int:
    print("Flow Memory TouchDesigner live stack")
    print(f"API: {config.api_url}")
    print(f"TouchDesigner UDP: {config.host}:{config.udp_port}")
    print("TouchDesigner Textport loader:")
    print(r'exec(open(r"E:\FlowMemory\flow-memory\tools\touchdesigner\create_flowmemory_neural_loom.py").read())')

    if config.dry_run:
        print("Dry run commands:")
        print("API:    " + format_command(api_server_command(config)))
        print("Bridge: " + format_command(bridge_command(config)))
        print("Agent:  " + format_command(agent_command(config)))
        return 0

    processes: list[ManagedProcess] = []
    api_proc: ManagedProcess | None = None
    try:
        if is_api_ready(config):
            print("API already running; reusing it.")
        else:
            api_proc = launch_process("api", api_server_command(config))
            processes.append(api_proc)
            print("Started local API server.")

        if not wait_for_api(config, api_proc):
            print(f"API did not become reachable at {config.api_url}/health", file=sys.stderr)
            return 2

        bridge = launch_process("bridge", bridge_command(config), quiet=not config.show_bridge_frames)
        processes.append(bridge)
        print("Started read-only TouchDesigner UDP bridge.")

        agent = launch_process("agent", agent_command(config))
        processes.append(agent)
        print("Started local neural live agent pump. Press Ctrl+C to stop all owned processes.")

        return monitor_until_exit(processes)
    except KeyboardInterrupt:
        print("Stopping TouchDesigner live stack.")
        return 130
    finally:
        stop_processes(reversed(processes))


def monitor_until_exit(processes: Iterable[ManagedProcess]) -> int:
    watched = list(processes)
    while True:
        for managed in watched:
            code = managed.popen.poll()
            if code is not None:
                if managed.name == "agent" and code == 0:
                    print("Agent pump completed configured tick count.")
                    return 0
                print(f"{managed.name} exited with code {code}.", file=sys.stderr)
                return code or 0
        time.sleep(0.25)


def stop_processes(processes: Iterable[ManagedProcess]) -> None:
    for managed in processes:
        if not managed.owned or managed.popen.poll() is not None:
            continue
        try:
            if os.name == "nt":
                managed.popen.terminate()
            else:
                managed.popen.send_signal(signal.SIGTERM)
        except OSError:
            continue
    deadline = time.monotonic() + 4.0
    for managed in processes:
        if not managed.owned:
            continue
        remaining = max(0.0, deadline - time.monotonic())
        try:
            managed.popen.wait(timeout=remaining)
        except (OSError, subprocess.TimeoutExpired):
            try:
                managed.popen.kill()
            except OSError:
                pass


def parse_args(argv: list[str] | None = None) -> StackConfig:
    parser = argparse.ArgumentParser(description="Run the Flow Memory TouchDesigner API, UDP bridge, and live neural agent from one terminal")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Local API/UDP host")
    parser.add_argument("--api-port", type=int, default=DEFAULT_API_PORT, help="Local API port")
    parser.add_argument("--udp-port", type=int, default=DEFAULT_UDP_PORT, help="TouchDesigner UDP In DAT port")
    parser.add_argument("--ticks", type=int, default=999_999, help="Live agent ticks before exit")
    parser.add_argument("--interval", type=float, default=0.25, help="Seconds between agent/bridge ticks")
    parser.add_argument("--learn-every", type=int, default=2, help="Send one learn call every N ticks; 0 disables learn calls")
    parser.add_argument("--learning-rate", type=float, default=0.12, help="Local deterministic learning-rate metadata")
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID, help="Agent id shown in telemetry")
    parser.add_argument("--goal", default=DEFAULT_GOAL, help="Goal/context sent through neural session")
    parser.add_argument("--backend", default="tiny_torch", help="Neural backend name")
    parser.add_argument("--show-bridge-frames", action="store_true", help="Print every UDP JSON frame in this terminal")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without starting processes")
    parser.add_argument("--startup-timeout", type=float, default=12.0, help="Seconds to wait for API readiness")
    args = parser.parse_args(argv)
    if not (0 < args.api_port <= 65535):
        raise ValueError("--api-port must be 1..65535")
    if not (0 < args.udp_port <= 65535):
        raise ValueError("--udp-port must be 1..65535")
    if args.ticks < 1:
        raise ValueError("--ticks must be positive")
    if args.interval < 0:
        raise ValueError("--interval must be non-negative")
    if args.learn_every < 0:
        raise ValueError("--learn-every must be non-negative")
    if args.learning_rate < 0:
        raise ValueError("--learning-rate must be non-negative")
    if args.startup_timeout <= 0:
        raise ValueError("--startup-timeout must be positive")
    return StackConfig(
        host=args.host,
        api_port=args.api_port,
        udp_port=args.udp_port,
        ticks=args.ticks,
        interval=args.interval,
        learn_every=args.learn_every,
        learning_rate=args.learning_rate,
        agent_id=args.agent_id,
        goal=args.goal,
        backend=args.backend,
        show_bridge_frames=args.show_bridge_frames,
        dry_run=args.dry_run,
        startup_timeout=args.startup_timeout,
    )


def format_command(command: Iterable[str]) -> str:
    return " ".join(quote_arg(part) for part in command)


def quote_arg(value: str) -> str:
    if not value or any(ch.isspace() for ch in value):
        return '"' + value.replace('"', '\\"') + '"'
    return value


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv)
    return run_stack(config)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
