#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_NAME="${PROJECT_NAME:-guardgo-local}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.local.yml}"

resolve_env_file() {
    if [[ -f ".env.local" ]]; then
        printf '%s\n' ".env.local"
        return
    fi

    if [[ -f ".env" ]]; then
        printf '%s\n' ".env"
        return
    fi

    echo "Missing .env.local. Copy .env.example to .env.local first." >&2
    exit 1
}

build_frontend() {
    if [[ "${1:-}" == "-t" ]]; then
        (
            cd client
            npm ci
            npx ng build --configuration instrumented
        )
        return
    fi

    npm ci --prefix client
    npm run build --prefix client
}

stop_stack() {
    local env_file="$1"
    ENV_FILE="$env_file" docker compose --project-name "$PROJECT_NAME" --env-file "$env_file" -f "$COMPOSE_FILE" down --remove-orphans
}

up_stack() {
    local env_file="$1"
    local detach="$2"
    local testing_enabled="$3"

    if [[ "$detach" == "1" ]]; then
        ENV_FILE="$env_file" TESTING_ENABLED="$testing_enabled" \
            docker compose --project-name "$PROJECT_NAME" --env-file "$env_file" -f "$COMPOSE_FILE" up -d --build --remove-orphans
        return
    fi

    ENV_FILE="$env_file" TESTING_ENABLED="$testing_enabled" \
        docker compose --project-name "$PROJECT_NAME" --env-file "$env_file" -f "$COMPOSE_FILE" up --build --remove-orphans
}

main() {
    local command="${1:-build}"
    local flag="${2:-}"
    local env_file
    local testing_enabled="0"
    local detach="0"

    env_file="$(resolve_env_file)"

    case "$command" in
        stop)
            stop_stack "$env_file"
            return
            ;;
        build|"")
            ;;
        *)
            echo "Unsupported local command: $command" >&2
            exit 1
            ;;
    esac

    case "$flag" in
        -d)
            build_frontend "$flag"
            detach="1"
            ;;
        -t)
            build_frontend "$flag"
            testing_enabled="1"
            ;;
        -b)
            ;;
        -c|"")
            build_frontend "$flag"
            ;;
        *)
            echo "Unsupported local build flag: $flag" >&2
            exit 1
            ;;
    esac

    up_stack "$env_file" "$detach" "$testing_enabled"
}

main "$@"
