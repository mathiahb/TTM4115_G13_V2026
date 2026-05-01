#!/usr/bin/env bash
set -euo pipefail

USAGE="
Usage: install.sh <server|drone> [options]

Options:
  --dir DIR       Installation directory (default: /opt/drone-delivery)
  --env FILE      Path to .env file to copy (required for drone)
  --runtime CMD   Container runtime: docker or podman (default: auto-detect)
  -h, --help      Show this help

Examples:
  # On the server machine:
  sudo ./deploy/install.sh server

  # On a drone machine:
  sudo ./deploy/install.sh drone --env .env.drone-3

  # With custom dir:
  sudo ./deploy/install.sh drone --dir /home/pi/drone --env .env.drone-1
"

DIR="/opt/drone-delivery"
RUNTIME=""
ENV_FILE=""
ROLE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        server|drone) ROLE="$1"; shift ;;
        --dir)        DIR="$2"; shift 2 ;;
        --env)        ENV_FILE="$2"; shift 2 ;;
        --runtime)    RUNTIME="$2"; shift 2 ;;
        -h|--help)    echo "$USAGE"; exit 0 ;;
        *)            echo "Unknown argument: $1" >&2; echo "$USAGE" >&2; exit 1 ;;
    esac
done

if [[ -z "$ROLE" ]]; then
    echo "Error: must specify 'server' or 'drone'" >&2
    echo "$USAGE" >&2
    exit 1
fi

if [[ "$ROLE" == "drone" && -z "$ENV_FILE" ]]; then
    echo "Error: --env is required for drone deployment (set SERVER_HOST)" >&2
    echo "$USAGE" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installing drone-delivery ($ROLE) to $DIR"
mkdir -p "$DIR"

echo "Copying files..."
cp -r "$SCRIPT_DIR/server" "$DIR/"
cp -r "$SCRIPT_DIR/drone" "$DIR/"
cp "$SCRIPT_DIR/mosquitto.conf" "$DIR/"
cp "$SCRIPT_DIR/deploy"/*.service "$DIR/deploy/" 2>/dev/null || true
mkdir -p "$DIR/deploy"
cp "$SCRIPT_DIR/deploy/compose-wrapper.sh" "$DIR/deploy/"
cp "$SCRIPT_DIR/docker-compose.server.yaml" "$DIR/"
cp "$SCRIPT_DIR/docker-compose.drone.yaml" "$DIR/"
cp "$SCRIPT_DIR/.env.example" "$DIR/"

if [[ -n "$ENV_FILE" && -f "$ENV_FILE" ]]; then
    cp "$ENV_FILE" "$DIR/.env"
    echo "Copied .env from $ENV_FILE"
else
    if [[ ! -f "$DIR/.env" ]]; then
        cp "$DIR/.env.example" "$DIR/.env"
        echo "Created .env from .env.example - EDIT IT before starting"
    fi
fi

chmod +x "$DIR/deploy/compose-wrapper.sh"

if [[ "$ROLE" == "server" ]]; then
    SERVICE_FILE="deploy/drone-delivery-server.service"
    SERVICE_NAME="drone-delivery-server"
elif [[ "$ROLE" == "drone" ]]; then
    SERVICE_FILE="deploy/drone-delivery-drone.service"
    SERVICE_NAME="drone-delivery-drone"
fi

echo "Installing systemd service..."
cp "$DIR/$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "Done. To start now:  systemctl start $SERVICE_NAME"
echo "To check status:     systemctl status $SERVICE_NAME"
echo "To view logs:        journalctl -u $SERVICE_NAME -f"
if [[ "$ROLE" == "drone" ]]; then
    echo ""
    echo "IMPORTANT: Edit $DIR/.env and set SERVER_HOST to the server's IP"
fi
