#!/usr/bin/env python3
"""Authenticated, workspace-scoped VPS MCP server."""
import os
import re
import shlex
import subprocess
from pathlib import Path

import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE = Path(os.environ.get("MCP_WORKSPACE", BASE_DIR / "workspace")).resolve()
TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")
HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8000"))
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
    """Return the configured workspace path and available disk space."""
    usage = __import__("shutil").disk_usage(WORKSPACE)
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
    """Read a UTF-8 text file inside the restricted workspace (max 1 MB)."""
    target = safe_path(path)
    if not target.is_file():
        raise ValueError("File does not exist.")
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File exceeds the 1 MB limit.")
    return target.read_text(encoding="utf-8")

@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Create or replace a UTF-8 text file inside the restricted workspace."""
    target = safe_path(path)
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise ValueError("Content exceeds the 1 MB limit.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Saved {len(encoded)} bytes to {target.relative_to(WORKSPACE)}"

@mcp.tool()
def run_command(argv: list[str]) -> dict:
    """Run a limited, non-shell command. Commands execute in the workspace."""
    if not argv or len(argv) > 12 or any(not isinstance(x, str) for x in argv):
        raise ValueError("Provide a command as a list of up to 12 strings.")
    allowed = {"pwd", "ls", "whoami", "hostname", "uptime", "date", "uname", "df", "free", "git"}
    command = argv[0]
    if command not in allowed:
        raise ValueError(f"Command not allowed. Allowed commands: {', '.join(sorted(allowed))}")
    if any(x in {";", "&&", "||", "|", ">", "<", "$(", "`"} for x in argv):
        raise ValueError("Shell operators are not accepted.")
    if command == "git" and (len(argv) < 2 or argv[1] not in {"status", "log"}):
        raise ValueError("Only git status and git log are allowed.")
    if command == "git" and argv[1] == "log" and len(argv) > 4:
        raise ValueError("git log accepts at most two additional arguments.")
    result = subprocess.run(argv, cwd=WORKSPACE, capture_output=True, text=True,
                            timeout=20, check=False, shell=False)
    return {"exit_code": result.returncode, "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-4000:]}

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        supplied = request.headers.get("authorization", "")
        expected = "Bearer " + TOKEN
        import hmac
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)

app = mcp.streamable_http_app()
app.add_middleware(BearerAuthMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
