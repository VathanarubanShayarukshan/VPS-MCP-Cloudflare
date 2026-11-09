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
- `run_command(command)`: run one supported native workspace operation.

## Command execution
This project does not use Docker. The command tool is intentionally limited to:
`pwd`, `ls`, `cat`, `head`, `tail`, `wc`, `mkdir`, `touch`, and `rm` (files only).

Commands are parsed as arguments and are never passed to Bash or a shell. Pipes, redirects, command chaining, shell expansion, scripts, interpreters, and arbitrary executables are unsupported. File paths must resolve inside the MCP workspace. Use the dedicated file tools for normal file editing.

## Safety
- Treat the workspace as the only permitted file area for MCP file and command tools.
- Do not attempt path traversal or access host secrets.
- Ask before destructive file changes.
- Do not claim this is a container or OS sandbox. The MCP server runs as its Linux service account, so that account's permissions define the process boundary.
- Recommend running under a dedicated unprivileged Linux user, not root.
- Never reveal or store the Bearer token in workspace files.
- Keep the host patched and protect the Cloudflare endpoint and token.
