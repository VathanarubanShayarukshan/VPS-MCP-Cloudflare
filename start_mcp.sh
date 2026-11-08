#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
PORT="${MCP_PORT:-8000}"
LOG_DIR="$ROOT/logs"
PID_DIR="$ROOT/.run"
SERVER_LOG="$LOG_DIR/mcp.log"
TUNNEL_LOG="$LOG_DIR/cloudflared.log"
SERVER_PID="$PID_DIR/server.pid"
TUNNEL_PID="$PID_DIR/tunnel.pid"
TOKEN_FILE="$ROOT/.mcp_token"

mkdir -p "$LOG_DIR" "$PID_DIR" "$ROOT/workspace"

is_running() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }
stop_one() {
  local f="$1"
  if is_running "$f"; then kill "$(cat "$f")" 2>/dev/null || true; fi
  rm -f "$f"
}
status() {
  is_running "$SERVER_PID" && echo "MCP server: running (PID $(cat "$SERVER_PID"))" || echo "MCP server: stopped"
  is_running "$TUNNEL_PID" && echo "Cloudflare tunnel: running (PID $(cat "$TUNNEL_PID"))" || echo "Cloudflare tunnel: stopped"
  [[ -f "$TOKEN_FILE" ]] && echo "Token: configured (stored locally)" || echo "Token: missing"
}
stop_all() {
  stop_one "$TUNNEL_PID"
  stop_one "$SERVER_PID"
  echo "Stopped launcher-managed processes."
}
start() {
  if is_running "$SERVER_PID" || is_running "$TUNNEL_PID"; then
    echo "Already running. Use: $0 status"
    status
    exit 0
  fi
  command -v cloudflared >/dev/null || { echo "cloudflared is not installed. Install it first; see README.md."; exit 1; }
  [[ -x "$PY" ]] || python3 -m venv "$VENV"
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install -r "$ROOT/requirements.txt"
  if [[ ! -s "$TOKEN_FILE" ]]; then
    umask 077
    "$PY" -c 'import secrets; print(secrets.token_urlsafe(48))' > "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
  fi
  export MCP_AUTH_TOKEN="$(cat "$TOKEN_FILE")"
  export MCP_PORT="$PORT"
  nohup "$PY" "$ROOT/vps_mcp_server.py" >>"$SERVER_LOG" 2>&1 &
  echo $! > "$SERVER_PID"
  sleep 2
  if ! is_running "$SERVER_PID"; then
    echo "MCP server failed. Check $SERVER_LOG"
    rm -f "$SERVER_PID"
    exit 1
  fi
  nohup cloudflared tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate >>"$TUNNEL_LOG" 2>&1 &
  echo $! > "$TUNNEL_PID"
  echo "Waiting for Cloudflare Quick Tunnel URL..."
  for _ in $(seq 1 40); do
    URL="$(grep -Eo 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | tail -n1 || true)"
    [[ -n "$URL" ]] && break
    sleep 1
  done
  if [[ -z "${URL:-}" ]]; then
    echo "Tunnel URL not found yet. Check $TUNNEL_LOG and run: $0 status"
    exit 1
  fi
  echo
  echo "MCP endpoint: $URL/mcp"
  echo "Bearer token (copy into your MCP client; keep it secret):"
  cat "$TOKEN_FILE"
  echo
  echo "Logs: $SERVER_LOG and $TUNNEL_LOG"
}
case "${1:-start}" in
  start) start ;;
  stop) stop_all ;;
  restart) stop_all; sleep 1; start ;;
  status) status ;;
  logs) tail -n 80 -f "$SERVER_LOG" "$TUNNEL_LOG" ;;
  *) echo "Usage: $0 {start|stop|restart|status|logs}"; exit 2 ;;
esac
