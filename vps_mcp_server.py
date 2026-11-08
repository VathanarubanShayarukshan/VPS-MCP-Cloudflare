#!/usr/bin/env python3
"""Bearer-authenticated MCP server with workspace tools and isolated Docker commands."""
import hmac
import os
import shutil
import subprocess
from pathlib import Path

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("MCP_WORKSPACE", BASE_DIR / "workspace")).resolve()
TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8000"))
SANDBOX_IMAGE = os.environ.get("MCP_SANDBOX_IMAGE", "vps-mcp-sandbox:latest")
COMMAND_TIMEOUT = int(os.environ.get("MCP_COMMAND_TIMEOUT", "120"))
MAX_COMMAND_LENGTH = 8000
MAX_FILE_BYTES = 1_000_000

if len(TOKEN) < 32:
    raise SystemExit("MCP_AUTH_TOKEN must be set to a random value of at least 32 characters.")

WORKSPACE.mkdir(parents=True, exist_ok=True)
mcp = FastMCP("VPS MCP Cloudflare")


def safe_path(relative_path: str) -> Path:
    candidate = (WORKSPACE / relative_path).resolve()
    if candidate != WORKSPACE and WORKSPACE not in candidate.parents:
        raise ValueError("Path is outside the MCP workspace.")
    return candidate


@mcp.tool()
def workspace_info() -> dict:
    """Return workspace path and available disk space."""
    usage = shutil.disk_usage(WORKSPACE)
    return {"workspace": str(WORKSPACE), "free_bytes": usage.free}


@mcp.tool()
def list_files(path: str = ".") -> list[dict]:
    """List files and folders inside the restricted workspace."""
    target = safe_path(path)
    if not target.exists() or not target.is_dir():
        raise ValueError("Directory does not exist.")
    return [
        {"name": p.name, "type": "directory" if p.is_dir() else "file",
         "size": p.stat().st_size if p.is_file() else None}
        for p in sorted(target.iterdir(), key=lambda item: item.name.lower())
    ]


@mcp.tool()
def read_file(path: str) -> str:
    """Read a UTF-8 text file inside the workspace (maximum 1 MB)."""
    target = safe_path(path)
    if not target.is_file():
        raise ValueError("File does not exist.")
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File exceeds the 1 MB limit.")
    return target.read_text(encoding="utf-8")


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Create or replace a UTF-8 text file inside the workspace (maximum 1 MB)."""
    target = safe_path(path)
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise ValueError("Content exceeds the 1 MB limit.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Saved {len(encoded)} bytes to {target.relative_to(WORKSPACE)}"


@mcp.tool()
def run_command(command: str) -> dict:
    """Run an arbitrary Bash command inside the isolated, network-disabled Docker sandbox.

    Commands can read and modify only the mounted workspace. The container has
    resource limits, a read-only root filesystem, dropped Linux capabilities,
    and no access to the Docker socket or host root filesystem.
    """
    if not isinstance(command, str) or not command.strip():
        raise ValueError("Provide a non-empty command.")
    if len(command) > MAX_COMMAND_LENGTH:
        raise ValueError(f"Command exceeds {MAX_COMMAND_LENGTH} characters.")

    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Docker CLI is not installed or is not on PATH.")

    argv = [
        docker, "run", "--rm",
        "--network", "none",
        "--read-only",
        "--user", "0:0",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "--pids-limit", "128",
        "--memory", "512m",
        "--memory-swap", "512m",
        "--cpus", "1.0",
        "--ulimit", "nofile=1024:1024",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=128m",
        "--tmpfs", "/run:rw,nosuid,nodev,size=16m",
        "--mount", f"type=bind,src={WORKSPACE},dst=/workspace,rw",
        "--workdir", "/workspace",
        "--env", "HOME=/tmp",
        SANDBOX_IMAGE,
        "bash", "-lc", command,
    ]
    try:
        result = subprocess.run(
            argv, capture_output=True, text=True, timeout=COMMAND_TIMEOUT,
            check=False, shell=False,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[-20000:],
            "stderr": result.stderr[-8000:],
            "sandbox": "Docker rootless daemon; network disabled",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": 124,
            "stdout": (exc.stdout or "")[-20000:] if isinstance(exc.stdout, str) else "",
            "stderr": "Command timed out inside the sandbox.",
            "sandbox": "Docker rootless daemon; network disabled",
        }


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied, "Bearer " + TOKEN):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


app = mcp.streamable_http_app()
app.add_middleware(BearerAuthMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
