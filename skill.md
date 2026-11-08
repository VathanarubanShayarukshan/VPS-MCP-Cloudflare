# VPS MCP Cloudflare — AI Skill Guide

## Connection
- Transport: MCP Streamable HTTP.
- Endpoint: current Cloudflare Quick Tunnel URL ending in `/mcp`.
- Authentication: HTTP Bearer token generated locally and printed at first start.
- Quick Tunnel URLs can change after restart. Use the latest URL.
- Never disclose, echo, commit, or write the Bearer token into workspace files.

## Available tools
- `workspace_info()`: workspace location and free disk space.
- `list_files(path=".")`: list workspace entries.
- `read_file(path)`: read a UTF-8 text file in the workspace.
- `write_file(path, content)`: write a UTF-8 text file in the workspace.
- `run_command(command)`: execute a Bash command inside the isolated Docker sandbox.

## Command execution
The sandbox permits ordinary shell commands and scripts available in the image. Examples include Bash, Python, Git, Node.js, package/build utilities, text-processing tools, and standard Ubuntu commands. Commands execute in the mounted workspace. Internet networking is disabled inside the sandbox.

### Isolation controls
- Docker daemon must be in rootless mode; the launcher refuses a non-rootless daemon.
- Container network is disabled.
- Container root filesystem is read-only.
- Only the project workspace is mounted writable.
- Linux capabilities are dropped; no-new-privileges is enabled.
- CPU, memory, process count, file descriptors, and command duration are limited.
- No Docker socket or host root filesystem is mounted into the container.

## Safe operating procedure
1. Inspect workspace files before editing.
2. Keep generated files and project operations inside the workspace.
3. Check command exit codes and output.
4. Ask before destructive changes to user data.
5. Do not try to bypass container restrictions, access host files, or retrieve credentials.
6. If a required program is missing, ask the user to add it to `Dockerfile.sandbox` and rebuild the image.

## Important
This provides broad command access **inside the sandbox**, not unrestricted host VPS access. The host MCP process has access to the user's rootless Docker daemon, so protect the VPS account and MCP Bearer token. Rootless Docker reduces risk but is not a perfect security boundary; keep the host and Docker packages updated.
