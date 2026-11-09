#!/usr/bin/env python3
"""Bearer-authenticated MCP server with workspace-confined native tools."""
import hmac
import os
import shlex
import shutil
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
MAX_COMMAND_LENGTH = 8000
MAX_FILE_BYTES = 1_000_000
MAX_OUTPUT_CHARS = 20_000

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
    """Run a small allowlist of native file/workspace commands without a shell.

    This is NOT a general Bash terminal. Commands and paths are restricted to
    the MCP workspace. Shell operators, pipes, redirects, interpreters, and
    arbitrary executables are intentionally unsupported.
    """
    if not isinstance(command, str) or not command.strip():
        raise ValueError("Provide a non-empty command.")
    if len(command) > MAX_COMMAND_LENGTH:
        raise ValueError(f"Command exceeds {MAX_COMMAND_LENGTH} characters.")
    if any(ch in command for ch in (";", "|", "&", "`", "$", ">", "<", "\n", "\r")):
        raise ValueError("Shell operators and multi-command input are not allowed.")

    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"Invalid command syntax: {exc}") from exc
    if not parts:
        raise ValueError("Provide a command.")

    name, args = parts[0], parts[1:]
    allowed = {"pwd", "ls", "cat", "head", "tail", "wc", "mkdir", "touch", "rm"}
    if name not in allowed:
        raise ValueError(f"Command not allowed. Allowed commands: {', '.join(sorted(allowed))}")

    def get_target(value: str) -> Path:
        if value.startswith("-"):
            raise ValueError("Command options are not supported for path arguments.")
        return safe_path(value)

    output = ""
    if name == "pwd":
        if args:
            raise ValueError("pwd takes no arguments.")
        output = str(WORKSPACE)
    elif name == "ls":
        if len(args) > 1:
            raise ValueError("ls accepts at most one workspace-relative path.")
        target = get_target(args[0] if args else ".")
        if not target.is_dir():
            raise ValueError("ls target is not a directory.")
        output = "\n".join(sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir()))
    elif name == "cat":
        if not args:
            raise ValueError("cat requires at least one file path.")
        chunks = []
        for arg in args:
            target = get_target(arg)
            if not target.is_file() or target.stat().st_size > MAX_FILE_BYTES:
                raise ValueError(f"Not a readable file within the 1 MB limit: {arg}")
            chunks.append(target.read_text(encoding="utf-8"))
        output = "".join(chunks)
    elif name in {"head", "tail", "wc"}:
        if len(args) != 1:
            raise ValueError(f"{name} requires exactly one file path.")
        target = get_target(args[0])
        if not target.is_file() or target.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("File is missing or exceeds the 1 MB limit.")
        data = target.read_text(encoding="utf-8")
        lines = data.splitlines()
        if name == "head":
            output = "\n".join(lines[:10])
        elif name == "tail":
            output = "\n".join(lines[-10:])
        else:
            output = f"{len(lines)} lines, {len(data.split())} words, {len(data.encode('utf-8'))} bytes"
    elif name == "mkdir":
        if not args:
            raise ValueError("mkdir requires at least one directory path.")
        for arg in args:
            get_target(arg).mkdir(parents=True, exist_ok=True)
        output = f"Created {len(args)} workspace director(ies)."
    elif name == "touch":
        if not args:
            raise ValueError("touch requires at least one file path.")
        for arg in args:
            target = get_target(arg)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch(exist_ok=True)
        output = f"Touched {len(args)} workspace file(s)."
    elif name == "rm":
        if not args:
            raise ValueError("rm requires at least one file path.")
        for arg in args:
            target = get_target(arg)
            if target.is_dir():
                raise ValueError("rm only removes files, not directories.")
            if target.exists():
                target.unlink()
        output = f"Removed {len(args)} workspace file(s) if present."

    return {"exit_code": 0, "stdout": output[:MAX_OUTPUT_CHARS], "stderr": "", "execution": "restricted native; no shell; workspace-only paths"}


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
