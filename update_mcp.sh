#!/usr/bin/env bash
# Safely update VPS-MCP-Cloudflare from GitHub.
set -Eeuo pipefail
BRANCH="main"
EXPECTED_ORIGIN="https://github.com/VathanarubanShayarukshan/VPS-MCP-Cloudflare.git"
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$APP_DIR/backups"
LOG_DIR="$APP_DIR/logs"
LOG_FILE="$LOG_DIR/update.log"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/pre-update-$STAMP.tar.gz"
OLD_COMMIT=""
SERVICE_STOPPED=0
UPDATE_APPLIED=0
mkdir -p "$BACKUP_DIR" "$LOG_DIR"
log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"; }
fail() { log "ERROR: $*"; exit 1; }
start_services() {
  log "Starting MCP server and Cloudflare tunnel..."
  if bash "$APP_DIR/start_mcp.sh" start; then SERVICE_STOPPED=0; else log "WARNING: Start failed. Check: bash start_mcp.sh logs"; return 1; fi
}
on_exit() {
  local rc=$?
  trap - EXIT
  if [[ "$rc" -ne 0 ]]; then
    log "Update failed (exit $rc)."
    if [[ "$UPDATE_APPLIED" -eq 1 && -n "$OLD_COMMIT" ]]; then
      git -C "$APP_DIR" reset --hard "$OLD_COMMIT" || log "WARNING: Git rollback failed."
      if [[ -x "$APP_DIR/.venv/bin/python" && -f "$APP_DIR/requirements.txt" ]]; then
        "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt" >>"$LOG_FILE" 2>&1 || log "WARNING: Could not restore Python dependencies."
      fi
    fi
    if [[ "$SERVICE_STOPPED" -eq 1 ]]; then start_services || true; fi
    log "Review $LOG_FILE. Backup: $BACKUP_FILE"
  fi
  exit "$rc"
}
trap on_exit EXIT
cd "$APP_DIR"
command -v git >/dev/null 2>&1 || fail "Git is not installed."
command -v python3 >/dev/null 2>&1 || fail "Python 3 is not installed."
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "Run inside the cloned Git repository."
[[ "$(git branch --show-current)" == "$BRANCH" ]] || fail "Switch to '$BRANCH' before updating."
[[ -f "$APP_DIR/start_mcp.sh" ]] || fail "start_mcp.sh is missing."
ORIGIN="$(git remote get-url origin 2>/dev/null || true)"
if [[ "$ORIGIN" != "$EXPECTED_ORIGIN" && "$ORIGIN" != "git@github.com:VathanarubanShayarukshan/VPS-MCP-Cloudflare.git" ]]; then fail "Unexpected origin remote: $ORIGIN"; fi
if [[ -n "$(git status --porcelain)" ]]; then fail "Local Git changes detected. Commit or stash them first."; fi
OLD_COMMIT="$(git rev-parse HEAD)"
log "Current version: $OLD_COMMIT"
backup_items=()
[[ -f "$APP_DIR/.mcp_token" ]] && backup_items+=(".mcp_token")
[[ -d "$APP_DIR/workspace" ]] && backup_items+=("workspace")
if (("${#backup_items[@]}" > 0)); then
  tar -czf "$BACKUP_FILE" -C "$APP_DIR" "${backup_items[@]}" || fail "Could not back up local token/workspace."
  chmod 600 "$BACKUP_FILE"
  log "Backup created: $BACKUP_FILE"
fi
log "Stopping MCP services..."
bash "$APP_DIR/start_mcp.sh" stop
SERVICE_STOPPED=1
log "Fetching origin/$BRANCH..."
git fetch origin "$BRANCH"
git merge --ff-only "origin/$BRANCH"
UPDATE_APPLIED=1
log "Installing Python dependencies..."
[[ -x "$APP_DIR/.venv/bin/python" ]] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
log "Starting Docker-free MCP server and Cloudflare tunnel..."
start_services
log "Update completed successfully. Previous: $OLD_COMMIT Current: $(git rev-parse HEAD)"
log "Backup: ${BACKUP_FILE:-not created}"
