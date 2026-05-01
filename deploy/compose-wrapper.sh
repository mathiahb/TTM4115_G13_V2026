#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD=""

if command -v docker &>/dev/null && docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v podman &>/dev/null && podman compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="podman compose"
elif command -v podman-compose &>/dev/null; then
    COMPOSE_CMD="podman-compose"
else
    echo "Error: no container compose command found (tried docker compose, podman compose, podman-compose)" >&2
    exit 1
fi

PROFILE="${1:?Usage: compose-wrapper.sh <server|drone> [compose args...]}"
shift

case "$PROFILE" in
    server) FILE="docker-compose.server.yaml" ;;
    drone)  FILE="docker-compose.drone.yaml" ;;
    *)      echo "Unknown profile: $PROFILE (use 'server' or 'drone')" >&2; exit 1 ;;
esac

exec $COMPOSE_CMD -f "$FILE" "$@"
