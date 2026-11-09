# VPS MCP Cloudflare

A Python MCP server exposed through a Cloudflare Quick Tunnel. It provides Bearer-authenticated workspace file operations and a **restricted native command tool**. Docker is not required or used.

> **Security notice:** The command tool is deliberately not a general Bash terminal. It supports a small set of workspace operations without invoking a shell. This is not an OS-level sandbox. The MCP process still runs with the permissions of the Linux account that starts it. Use a dedicated, unprivileged VPS account and do not run this service as root.

## Features
- MCP Streamable HTTP endpoint at `/mcp`
- Bearer-token authentication
- Workspace-confined file tools
- Restricted native workspace commands (no shell, pipes, redirects, or arbitrary executables)
- Cloudflare Quick Tunnel running in the background
- Start, stop, restart, status, and logs commands
- No Docker Engine, Docker daemon, Docker image, or Docker installation script

## Requirements
- Debian/Kali/Ubuntu Linux with Python 3.10+
- `python3-venv` and `python3-pip`
- Cloudflare `cloudflared` installed and available on PATH
- Git (for updates)
- MCP client supporting remote Streamable HTTP and Bearer authentication

## 1. Install system packages

On Debian or Kali:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl
```

Install `cloudflared` using Cloudflare's official instructions:
https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

## 2. Start MCP

```bash
chmod +x start_mcp.sh update_mcp.sh
./start_mcp.sh start
``

The launcher creates a Python virtual environment, installs requirements, generates a local token, and starts the MCP server and Cloudflare Quick Tunnel in the background.

It prints the current MCP endpoint ending in `/mcp` and the Bearer token. Configure your MCP client with the endpoint and HTTP header:

```
Authorization: Bearer YOUR_TOKEN
```

Keep the token private. The Quick Tunnel URL can change after restart.

## 3. Manage service

```bash
./start_mcp.sh status
./start_mcp.sh logs
./start_mcp.sh restart
./start_mcp.sh stop
```

## MCP tools

- `workspace_info()`: workspace location and free disk space.
- `list_files(path=".")`: list workspace entries.
- `read_file(path)`: read a UTF-8 file in the workspace (maximum 1 MB).
- `write_file(path, content)`: write a UTF-8 file in the workspace (maximum 1 MB).
- `run_command(command)`: restricted native workspace operations.

### Restricted command tool

Supported commands: `pwd`, `ls`, `cat`, `head`, `tail`, `wc`, `mkdir`, `touch`, and `rm` (files only).

The tool does not invoke Bash or another shell. Pipes, redirects, command chaining, shell expansion, interpreters, and arbitrary executables are rejected. Paths are resolved and checked to remain inside `workspace/`. Directory deletion is not supported by `rm`.

This restriction reduces exposure but is not a security boundary equivalent to a container, VM, or OS sandbox. Never expose the MCP endpoint without its token, do not run the service as root, and consider using a dedicated low-privilege account.

## Workspace and secrets

The default workspace is `workspace/`. Do not store SSH keys, credentials, or other secrets there. The token is stored in `.mcp_token` with restrictive permissions and should never be committed.

## Update

```bash
./update_mcp.sh
```

The updater backs up the local token and workspace, updates the Git checkout, installs Python dependencies, and restarts the server. It does not build or run Docker images.
