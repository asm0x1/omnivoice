#!/usr/bin/env python3
"""
Web UI server for OmniVoice.

Launches omnivoice-demo directly on port 1219.
Access at http://localhost:1219 after starting.
"""
import os
import signal
import subprocess
import sys

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "1219"))

_process = None


def start_server():
    """Launch omnivoice-demo directly on the target port."""
    import shutil
    demo_cmd = shutil.which("omnivoice-demo")
    if demo_cmd:
        cmd = [demo_cmd, "--ip", HOST, "--port", str(PORT)]
    else:
        cmd = [sys.executable, "-m", "omnivoice.demo", "--ip", HOST, "--port", str(PORT)]

    env = {**os.environ}
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

    print(f"Starting omnivoice-demo on port {PORT}... cmd={' '.join(cmd)}", file=sys.stderr)
    return subprocess.Popen(cmd, env=env)


if __name__ == "__main__":
    import uvicorn

    _process = start_server()

    def signal_handler(sig, frame):
        print("Shutting down...", file=sys.stderr)
        _process.terminate()
        _process.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep main thread alive, monitor process
    while _process.poll() is None:
        import time
        time.sleep(1)

    stdout, stderr = _process.communicate()
    print(f"omnivoice-demo exited ({_process.returncode}):\nSTDOUT:\n{stdout.decode()}\nSTDERR:\n{stderr.decode()}", file=sys.stderr)