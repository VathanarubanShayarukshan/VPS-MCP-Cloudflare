#!/usr/bin/env bash
# Safely update VPS-MCP-Cloudflare from the GitHub main branch.
set -Eeuo pipefail

REPO_URL="https://github.com/VathanarubanShayarukshan/VPS-MCP-Cloudflare.git"
BRANCH="main"
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

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

fail() {
  log "ERROR: $*"
  exit 1
}

restart_service() {
  if [[ "$SERVICE_STOPPED" -eq 1 ]]; then
    log "Starting MCP server and Cloudflare tunnel..."
    if bash "$APP_DIR/start_mcp.sh" start; then
      SERVICE_STOPPED=0
      log "Services started."
    else
      log "WARNING: Automatic service start failed. Inspect logs with: bash start_mcp.sh logs"
    fi
  fi
}

rollback() {
  local rc=$?
  if [[ "$rc" -ne 0 ]]; then
    log "Update failed (exit $rc)."
    if [[ "$UPDATE_APPLIED" -eq 1 && -n "$OLD_COMMIT" ]]; then
      log "Rolling tracked source files back to $OLD_COMMIT..."
      git -C "$APP_DIR" reset --hard "$OLD_COMMIT" || log "WARNING: Git rollback failed."
    fi
    restart_service
    log "Backup, if created: $BACKUP_FILE"
  fi
  exit "$rc"
}
trap rollback EXIT

cd "$APP_DIR"

command -v git >/dev/null 2>&1 || fail "Git is not installed."
command -v python3 >/dev/null 2>&1 || fail "Python 3 is not installed."
[[ -f "$APP_DIR/start_mcp.sh" ]] || fail "start_mcp.sh is missing."
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "Run this script from inside the cloned Git repository."

ORIGIN="$(git remote get-url origin 2>/dev/null || true)"
[[ "$ORIGIN" == "$REPO_URL" || "$ORIGIN" == "git@github.com:VathanarubanShayarukshan/VPS-MCP-Cloudflare.git" ]] || {
  log "WARNING: origin remote is '$ORIGIN' (expected $REPO_URL)."
}

if [[ -n "$(git status --porcelain)" ]]; then
  fail "Local Git changes detected. Commit, stash, or move them before updating; nothing was changed."
fi

OLD_COMMIT="$(git rev-parse HEAD)"
log "Current version: $OLD_COMMIT"

# Back up local token and workspace, if present. These are normally Git-ignored.
backup_items=()
[[ -f "$APP_DIR/.mcp_token" ]] && backup_items+=(".mcp_token")
[[ -d "$APP_DIR/workspace" ]] && backup_items+=("workspace")
if (("${#backup_items[@]}" > 0)); then
  tar -czf "$BACKUP_FILE" -C "$APP_DIR" "${backup_items[@]}"
  chmod 600 "$BACKUP_FILE"
  log "Local token/workspace backup created: $BACKUP_FILE"
else
  log "No local token or workspace directory found; skipping data backup."
fi

log "Stopping MCP server and Cloudflare tunnel..."
bash "$APP_DIR/start_mcp.sh" stop
SERVICE_STOPPED=1

log "Fetching GitHub branch '$BRANCH'..."
git fetch origin "$BRANCH"

log "Applying fast-forward update..."
git pull --ff-only origin "$BRANCH"
UPDATE_APPLIED=1

log "Updating Python dependencies..."
if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

log "Rebuilding sandbox image and restarting services..."
bash "$APP_DIR/start_mcp.sh" start
SERVICE_STOPPED=0

log "Update completed successfully."
log "New version: $(git rev-parse HEAD)"
log "Backup: ${BACKUP_FILE:-not created}"
trap - EXIT
