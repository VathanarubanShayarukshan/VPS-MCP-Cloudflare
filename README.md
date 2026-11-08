# VPS MCP Cloudflare

A Python MCP server for a VPS, exposed through a Cloudflare Quick Tunnel. It provides authenticated workspace file operations and a small allowlist of diagnostic commands.

> **Security:** This project intentionally does not expose unrestricted shell access. Do not remove authentication or publish your token. A Cloudflare Quick Tunnel makes the endpoint reachable from the internet.

## Features
- MCP Streamable HTTP endpoint at `/mcp`
- Bearer-token authentication
- Workspace-confined file listing, reading, and writing
- Limited diagnostic commands (no shell, no sudo)
- Cloudflare Quick Tunnel launched in the background with `nohup`
- Start, stop, restart, status, and logs commands

## Requirements
- Linux VPS
- Python 3.10+
- `cloudflared` installed and available on PATH
- An MCP client that supports Streamable HTTP and Bearer authentication

### Install cloudflared
Install Cloudflare's official `cloudflared` package for your Linux distribution by following:
https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

## Start
From the project directory:

```bash
chmod +x start_mcp.sh
./start_mcp.sh start
```

The launcher creates a Python virtual environment, installs dependencies, generates a local token (if missing), and starts both processes in the background. It prints the current endpoint and Bearer token.

**Keep the token private.** Configure your MCP client with:
- URL: printed `https://....trycloudflare.com/mcp`
- Authorization: `Bearer YOUR_TOKEN`

The exact configuration format depends on your MCP client. The client must support remote Streamable HTTP MCP and Bearer headers.

## Manage the service

```bash
./start_mcp.sh status
./start_mcp.sh logs
./start_mcp.sh restart
./start_mcp.sh stop
```

## Workspace
Files are accessible only under the `workspace/` directory by default. Set `MCP_WORKSPACE` before starting the launcher to use another dedicated directory. Do not point it at `/`, your home directory, or a directory containing credentials.

## Available MCP tools
- `workspace_info()`
- `list_files(path=".")`
- `read_file(path)`
- `write_file(path, content)`
- `run_command(argv)`

Allowed command names: `pwd`, `ls`, `whoami`, `hostname`, `uptime`, `date`, `uname`, `df`, `free`, and limited `git status` / `git log`.

## Important notes
- Quick Tunnel URLs are temporary and may change after a restart. Use the latest printed URL.
- The server binds to localhost; Cloudflare Tunnel forwards traffic to it.
- The token is stored in `.mcp_token` with restricted local permissions and is excluded from Git.
- Do not commit logs, virtual environments, local tokens, or private VPS information.
- Quick Tunnels are useful for testing, not a substitute for a stable production deployment.
- Review the code and restrict network access before using it with sensitive systems.

## AI instructions
See [skill.md](skill.md) for the tool descriptions and safe operating procedure.
