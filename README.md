# VPS MCP Cloudflare

A Python MCP server exposed through a Cloudflare Quick Tunnel. It provides authenticated workspace file operations and broad Bash command execution **inside a restricted Docker sandbox**.

> **Security boundary:** Commands run in a rootless-Docker container with no network, a read-only container filesystem, dropped capabilities, resource limits, and only the project workspace mounted writable. This is not unrestricted host shell access.

## Features
- MCP Streamable HTTP endpoint at `/mcp`
- Bearer-token authentication
- Workspace-confined file tools
- Broad Bash command execution in Docker sandbox
- Cloudflare Quick Tunnel in the background
- Start, stop, restart, status, and logs commands

## Requirements
- Ubuntu 24.04 (recommended)
- Python 3.10+
- Cloudflare `cloudflared` installed and available on PATH
- Rootless Docker Engine
- MCP client supporting remote Streamable HTTP and Bearer authentication

## 1. Install rootless Docker
Clone this repository, then run as your normal VPS user:

```bash
chmod +x install_docker_rootless.sh start_mcp.sh
./install_docker_rootless.sh
```

The installer uses the official Docker Ubuntu repository and configures rootless Docker for the current user. It may ask for your sudo password during package installation. Log out and back in after installation, then verify:

```bash
docker info --format '{{json .SecurityOptions}}'
```

The output must include `rootless`. Do not add your account to the `docker` group; that grants broad root-equivalent access to a rootful daemon.

## 2. Install cloudflared
Follow Cloudflare's official installation guide for your Ubuntu version:
https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

## 3. Start MCP
From the repository directory:

```bash
./start_mcp.sh start
```

The launcher verifies rootless Docker, builds the sandbox image, installs Python dependencies, generates a local token, and starts the MCP server and Cloudflare tunnel in the background.

It prints:
- Current MCP endpoint, ending in `/mcp`
- Bearer token (keep it private)

Configure your MCP client with the endpoint and HTTP header `Authorization: Bearer YOUR_TOKEN`. Client configuration varies; it must support remote Streamable HTTP MCP with custom headers.

## 4. Manage service

```bash
./start_mcp.sh status
./start_mcp.sh logs
./start_mcp.sh restart
./start_mcp.sh stop
```

## Sandbox behavior
The `run_command(command)` MCP tool accepts Bash commands and runs them inside the image built from `Dockerfile.sandbox`.

Default restrictions:
- Rootless Docker daemon required
- `--network none`
- Read-only container root filesystem
- Only `workspace/` is mounted writable
- All Linux capabilities dropped
- `no-new-privileges`
- 512 MiB memory, 1 CPU, 128 processes
- 120-second command timeout
- Output is truncated to bounded sizes
- No host root filesystem or Docker socket mounted

The image includes common Ubuntu development and administration utilities. Add more packages to `Dockerfile.sandbox` and restart to rebuild the image. Network is disabled while commands run, so download dependencies during image build or add them to the image beforehand.

## Workspace and secrets
The default workspace is `workspace/`. Do not put credentials, SSH keys, tokens, or sensitive host files there. The local token is stored in `.mcp_token` with restrictive permissions and excluded from Git.

## Limitations
Rootless Docker is safer than giving an AI access to a rootful Docker socket, but it is not a perfect isolation boundary. Keep the host patched, use a dedicated VPS account, and do not expose the token. Quick Tunnel URLs are temporary and can change after restart.
