#!/usr/bin/env bash
# One-shot installer for Ubuntu/Debian. Run as your normal user (it uses sudo where needed):
#   curl -fsSL https://raw.githubusercontent.com/AvoBrandon/TrackHub/main/deploy/install-ubuntu.sh | bash
# Re-running is safe: it updates the code and restarts the service.
set -euo pipefail

REPO="https://github.com/AvoBrandon/TrackHub.git"
DIR="${TRACKHUB_DIR:-$HOME/trackhub}"
SVC="trackhub"
RUN_USER="$(id -un)"

echo "==> Installing system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-venv python3-pip curl >/dev/null

if [ -d "$DIR/.git" ]; then
  echo "==> Updating existing checkout in $DIR"
  git -C "$DIR" pull -q --ff-only
else
  echo "==> Cloning into $DIR"
  git clone -q "$REPO" "$DIR"
fi

cd "$DIR/backend"
echo "==> Python environment"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e .

if [ ! -f .env ]; then
  cp .env.example .env
  TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
  sed -i "s|^API_TOKEN=.*|API_TOKEN=$TOKEN|" .env
  echo "==> Created backend/.env with a random API_TOKEN"
fi
mkdir -p data secrets

echo "==> systemd service ($SVC, user $RUN_USER)"
sudo tee /etc/systemd/system/$SVC.service >/dev/null <<UNIT
[Unit]
Description=TrackHub watcher service
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$DIR/backend
ExecStart=$DIR/backend/.venv/bin/python -m app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable -q $SVC
sudo systemctl restart $SVC
sleep 3

IP="$(hostname -I | awk '{print $1}')"
if curl -fsS "http://localhost:8787/health" >/dev/null; then
  echo
  echo "============================================================"
  echo " TrackHub is running."
  echo "   Health:     http://$IP:8787/health"
  echo "   API token:  $(grep '^API_TOKEN=' .env | cut -d= -f2-)"
  echo "   Config:     $DIR/backend/.env   (add your API keys here, then: sudo systemctl restart $SVC)"
  echo "   Logs:       journalctl -u $SVC -f"
  echo "   Gmail:      see docs/SETUP.md section 2 (copy gmail_client_secret.json to $DIR/backend/secrets/)"
  echo "============================================================"
else
  echo "Service did not answer. Check: journalctl -u $SVC -n 50" >&2
  exit 1
fi
