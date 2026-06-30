# GuardGo Stage Manual Deploy

This document describes the manual staging deployment path after the environment split.

## Naming

- Local env file: `.env.local`
- Staging env file on VPS: `/opt/guardgo/.env.stage`
- Production env file on VPS: `/opt/guardgo/.env.prod`

The active staging stack is [`docker-compose.stage.yml`](/home/ibsalim/Projects/guardgo/docker-compose.stage.yml:1).

## Staging assumptions

- Staging app directory: `/opt/guardgo`
- Staging is reachable through a domain that points to the staging VPS
- Mailpit runs directly on the VPS host, not inside Docker

Because Mailpit is host-installed, the stage app container should use:

```bash
ACCOUNTS_SMTP_SERVER=host.docker.internal
ACCOUNTS_SMTP_PORT=1025
```

The stage compose file already maps `host.docker.internal` to the Docker host using `host-gateway`.

Before deploying, verify the host Mailpit SMTP listener is reachable on the VPS:

```bash
ss -lntp | grep ':1025'
```

If Mailpit is only bound to `127.0.0.1`, reconfigure it to listen on the VPS host interface as well.

## One-time VPS setup

```bash
sudo mkdir -p /opt/guardgo
sudo chown -R "$USER":"$USER" /opt/guardgo
```

Copy the repository to the VPS:

```bash
rsync -az --delete \
  --exclude '.git' \
  --exclude '.env' \
  --exclude '.env.local' \
  --exclude 'client/node_modules' \
  --exclude 'backend/build' \
  /path/to/guardgo/ \
  <user>@<stage-vps>:/opt/guardgo/
```

Create the stage env file:

```bash
cd /opt/guardgo
cp .env.example .env.stage
```

## Required stage env values

At minimum set:

- `APP_URL=http://<stage-domain>`
- `PRODUCTION=0`
- `PRODUCTION_DOMAIN=<stage-domain>`
- `MONGO_ROOT_USERNAME`
- `MONGO_ROOT_PASSWORD`
- `REDIS_PASSWORD`
- `ENCRYPTION_KEY`
- `S_SUPER_PASSWORD_V1`
- `S_CRAWLER_PASSWORD`
- `ACCOUNTS_MAIL`
- `ACCOUNTS_MAIL_PASSWORD`
- `ACCOUNTS_SMTP_SERVER=host.docker.internal`
- `ACCOUNTS_SMTP_PORT=1025`

Notes:

- Keep `PRODUCTION=0` for HTTP-only staging.
- If you later put TLS in front of staging, you can flip `PRODUCTION=1`.
- If staging uses HTTPS immediately, set `APP_URL=https://<stage-domain>` and `PRODUCTION=1`.

## Build and ship the app image

Stage now uses a prebuilt Docker image. Do not build on the VPS.

Build the image on your local machine:

```bash
cd /path/to/guardgo
docker build -t guardgo-app:stage -f dockerFiles/api_docker .
```

Transfer it to the staging VPS:

```bash
docker save guardgo-app:stage | gzip > guardgo-app-stage.tar.gz
scp guardgo-app-stage.tar.gz <user>@<stage-vps>:/opt/guardgo/
```

Load it on the staging VPS:

```bash
cd /opt/guardgo
gunzip -c guardgo-app-stage.tar.gz | docker load
docker image ls | grep guardgo-app
```

## Manual stage deploy

On the staging VPS:

```bash
cd /opt/guardgo
APP_IMAGE=guardgo-app IMAGE_TAG=stage \
./scripts/deploy.sh stage up
```

This starts:

- `web` for the FastAPI app
- `worker` for `backend/cronjobs.py`
- `nginx`, `mongo`, and `redis_server`

## Manual stage rollback

For now rollback is source-based:

1. deploy an older Git revision into `/opt/guardgo`
2. rerun:

```bash
./scripts/deploy.sh stage up
```

## Useful commands

View logs:

```bash
cd /opt/guardgo
APP_IMAGE=guardgo-app IMAGE_TAG=stage ./scripts/deploy.sh stage logs
```

Stop staging:

```bash
cd /opt/guardgo
APP_IMAGE=guardgo-app IMAGE_TAG=stage ./scripts/deploy.sh stage down
```

## Local workflow

Your local compatibility command still works:

```bash
./run.sh build -d
```

Internally that now routes to [`scripts/run-local.sh`](/home/ibsalim/Projects/guardgo/scripts/run-local.sh:1) and prefers `.env.local`.
