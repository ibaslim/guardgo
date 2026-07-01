#!/usr/bin/env bash

set -Eeuo pipefail

environment="${1:-}"
action="${2:-up}"

case "$environment" in
    stage)
        APP_DIR="${APP_DIR:-/opt/guardgo}"
        ENV_FILE="${ENV_FILE:-$APP_DIR/.env.stage}"
        COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.stage.yml}"
        PROJECT_NAME="${PROJECT_NAME:-guardgo-stage}"
        APP_IMAGE="${APP_IMAGE:-guardgo-app}"
        IMAGE_TAG="${IMAGE_TAG:-stage}"
        ;;
    prod)
        APP_DIR="${APP_DIR:-/opt/guardgo}"
        ENV_FILE="${ENV_FILE:-$APP_DIR/.env.prod}"
        COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
        PROJECT_NAME="${PROJECT_NAME:-guardgo-prod}"
        APP_IMAGE="${APP_IMAGE:-guardgo-app}"
        IMAGE_TAG="${IMAGE_TAG:-prod}"
        ;;
    *)
        echo "Usage: scripts/deploy.sh <stage|prod> [up|down|restart|pull|logs]" >&2
        exit 1
        ;;
esac

cd "$APP_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing environment file: $ENV_FILE" >&2
    exit 1
fi

compose() {
    ENV_FILE="$ENV_FILE" APP_IMAGE="$APP_IMAGE" IMAGE_TAG="$IMAGE_TAG" \
        docker compose --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

case "$action" in
    up)
        compose up -d --remove-orphans
        ;;
    down)
        compose down --remove-orphans
        ;;
    restart)
        compose up -d --force-recreate --remove-orphans
        ;;
    pull)
        compose pull
        ;;
    logs)
        compose logs -f
        ;;
    *)
        echo "Unsupported action: $action" >&2
        exit 1
        ;;
esac
