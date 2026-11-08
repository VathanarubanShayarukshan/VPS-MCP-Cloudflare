#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Run this installer as your normal VPS user, not root."
  exit 1
fi
if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required to install Docker packages."
  exit 1
fi
if ! command -v systemctl >/dev/null 2>&1; then
  echo "This installer expects Ubuntu 24.04 with systemd."
  exit 1
fi

ARCH="$(dpkg --print-architecture)"
case "$ARCH" in
  amd64|arm64|armhf) ;;
  *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

echo "[1/5] Installing prerequisites..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg uidmap dbus-user-session \
  slirp4netns fuse-overlayfs iptables

echo "[2/5] Configuring the official Docker apt repository..."
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

echo "[3/5] Installing Docker Engine and rootless extras..."
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras

echo "[4/5] Preparing user services..."
systemctl --user daemon-reload || true
sudo loginctl enable-linger "$USER"
export PATH="$HOME/bin:$PATH"

if [[ -S "/run/user/$(id -u)/docker.sock" ]]; then
  echo "A rootless Docker socket already exists."
else
  dockerd-rootless-setuptool.sh install
fi

systemctl --user enable --now docker
mkdir -p "$HOME/.config/environment.d"
printf 'DOCKER_HOST=unix://%s/docker.sock\n' "/run/user/$(id -u)" \
  > "$HOME/.config/environment.d/docker.conf"

echo "[5/5] Verifying rootless daemon..."
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
for _ in $(seq 1 20); do
  if docker info >/dev/null 2>&1; then break; fi
  sleep 1
done
if ! docker info --format '{{json .SecurityOptions}}' | grep -q rootless; then
  echo "Rootless Docker could not be verified. Check: systemctl --user status docker"
  exit 1
fi

echo
echo "Rootless Docker is installed and running."
echo "Log out and back in, then run:"
echo "  cd VPS-MCP-Cloudflare"
echo "  ./start_mcp.sh start"
echo
echo "Do NOT add this account to the docker group for a rootful daemon."
