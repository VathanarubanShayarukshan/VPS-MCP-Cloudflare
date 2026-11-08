# VPS MCP Cloudflare — AI Skill Guide

## Purpose
This MCP server exposes a small, authenticated set of VPS tools over a Cloudflare Quick Tunnel. It is intended for an MCP-compatible AI client.

## Connection
- Transport: MCP Streamable HTTP
- Endpoint: the current URL printed by `start_mcp.sh`, ending in `/mcp`
- Authentication: HTTP Bearer token printed at startup
- The Quick Tunnel URL can change after restart. Always use the latest URL.

## Available tools
- `workspace_info`: workspace path and free disk space.
- `list_files(path)`: list entries inside the workspace.
- `read_file(path)`: read a UTF-8 text file inside the workspace.
- `write_file(path, content)`: create or replace a UTF-8 text file inside the workspace.
- `run_command(argv)`: run only the documented allowlisted commands.

## Safe operating procedure
1. Inspect with `workspace_info` and `list_files` before changing files.
2. Read a file before replacing it.
3. Keep project work inside the configured workspace.
4. Use `run_command` with an argument array, never a shell command string.
5. Check the returned exit code and output.
6. Do not attempt privilege escalation, access to secrets, destructive operations, or commands outside the allowlist.
7. Never print, store in project files, or share the Bearer token.
8. Ask the user before making consequential changes outside the workspace.

## Command allowlist
`pwd`, `ls`, `whoami`, `hostname`, `uptime`, `date`, `uname`, `df`, `free`, and limited `git status` / `git log`.

## Important limitations
This is not unrestricted remote shell access. File tools are confined to the workspace. Commands execute without a shell and have a 20-second timeout. File reads and writes are limited to 1 MB. A Quick Tunnel is temporary and is not a production hosting setup.
