# GuardGo Deployment Manual

This document is the single source of truth for GuardGo deployment across staging and production.

## Deployment Model

GuardGo uses the same core deployment model in both environments:

- application runtime: Docker Compose
- app image build source: `dockerFiles/api_docker`
- reverse proxy: Docker nginx container
- database: MongoDB container
- cache: Redis container
- app path on VPS: `/opt/guardgo`

Environment differences:

- staging branch: `stage`
- production branch: `master`
- staging env file: `/opt/guardgo/.env.stage`
- production env file: `/opt/guardgo/.env.prod`
- staging compose: `docker-compose.stage.yml`
- production compose: `docker-compose.prod.yml`

## Core Files

- stage workflow: `.github/workflows/deploy-stage.yml`
- production workflow: `.github/workflows/deploy-prod.yml`
- deploy script: `scripts/deploy.sh`
- stage nginx config: `nginx/nginx-stage.conf`
- production nginx config: `nginx/nginx-prod.conf`

## Standard VPS Layout

Keep a single active project directory:

- `/opt/guardgo`

Do not keep multiple active GuardGo deployments on the same VPS binding the same ports.

Recommended policy:

- use Docker nginx only
- do not run host-installed nginx alongside Docker nginx
- ensure ports `80` and `443` are free before deploy

## One-Time VPS Bootstrap

### Install prerequisites

Install Docker, Docker Compose plugin, Git, and Certbot.

### Create app directory

```bash
sudo mkdir -p /opt/guardgo
sudo chown -R "$USER":"$USER" /opt/guardgo
```

### Clone repository

```bash
git clone <repo-url> /opt/guardgo
cd /opt/guardgo
```

### Remove host nginx if Docker nginx is the edge

```bash
sudo systemctl stop nginx 2>/dev/null || true
sudo systemctl disable nginx 2>/dev/null || true
sudo apt remove --purge -y nginx nginx-common nginx-core nginx-full || true
sudo apt autoremove -y
```

## DNS Setup

For a domain plus `www`:

- `A` record: `@ -> <vps-ip>`
- `CNAME` record: `www -> @` or `www -> your-domain`

Verify:

```bash
dig +short your-domain
dig +short www.your-domain
```

## SSL Certificate Setup

Expected certificate paths on VPS host:

- `/etc/letsencrypt/live/<domain>/fullchain.pem`
- `/etc/letsencrypt/live/<domain>/privkey.pem`

These are mounted into Docker nginx in both stage and production compose files.

### Recommended issuance path

Use Certbot webroot mode with a temporary nginx container if direct standalone challenge is unreliable.

Basic validation rule:

- public HTTP on port `80` must reach the VPS that is serving the ACME challenge

After issuing certs, verify:

```bash
ls -l /etc/letsencrypt/live/<domain>/fullchain.pem
ls -l /etc/letsencrypt/live/<domain>/privkey.pem
```

## Environment Files

Commit only `.env.example`.
Never commit real secrets.

### Shared required values

- `APP_URL`
- `PRODUCTION`
- `PRODUCTION_DOMAIN`
- `ENCRYPTION_KEY`
- `MONGO_ROOT_USERNAME`
- `MONGO_ROOT_PASSWORD`
- `REDIS_PASSWORD`
- `GUNICORN_WORKERS`
- `GUNICORN_THREADS`

### Important app constraints

- `ENCRYPTION_KEY` must be a valid Fernet key
- `PRODUCTION_DOMAIN` may contain multiple comma-separated hosts when both apex and `www` are allowed
- health checks should use a single `HEALTHCHECK_HOST` value when needed
- `GUNICORN_WORKERS='1'` is the safest default for this codebase because startup initialization can race with multiple workers

## Stage Deployment

### Stage architecture

- branch: `stage`
- workflow: `.github/workflows/deploy-stage.yml`
- image tag: `stage`
- domain example: `ggstage.vaultcentric.com`

### Stage GitHub secrets

- `STAGE_VPS_HOST`
- `STAGE_VPS_USER`
- `STAGE_VPS_SSH_KEY`
- `STAGE_VPS_SSH_PASSPHRASE` if the key is encrypted

### Stage runtime expectations

- HTTPS served by Docker nginx
- certs mounted from host letsencrypt paths
- smoke checks run after deploy

### Stage daily flow

1. push to `stage`
2. GitHub Actions builds image and pushes `:stage`
3. workflow deploys to VPS
4. workflow runs health checks

### Stage manual fallback

```bash
cd /opt/guardgo
export ENV_FILE=/opt/guardgo/.env.stage
export APP_IMAGE=ghcr.io/<owner>/guardgo-app
export IMAGE_TAG=stage
./scripts/deploy.sh stage restart
```

## Production Deployment

### Production architecture

- branch: `master`
- workflow: `.github/workflows/deploy-prod.yml`
- image tags: `prod` and `prod-<git-sha>`
- domains example: `guardgo.org`, `www.guardgo.org`

### Production GitHub secrets

- `PROD_VPS_HOST`
- `PROD_VPS_USER`
- `PROD_VPS_SSH_KEY`
- `PROD_VPS_SSH_PASSPHRASE` if the key is encrypted

### Production runtime expectations

- HTTPS served by Docker nginx
- `guardgo.org` and `www.guardgo.org` both allowed by app host validation
- smoke checks run after deploy

### Production daily flow

1. merge or push to `master`
2. GitHub Actions builds image and pushes `:prod`
3. workflow deploys to VPS
4. workflow runs HTTPS health checks for both domains

### Production manual fallback

Registry-based fallback:

```bash
cd /opt/guardgo
export ENV_FILE=/opt/guardgo/.env.prod
export APP_IMAGE=ghcr.io/<owner>/guardgo-app
export IMAGE_TAG=prod
./scripts/deploy.sh prod restart
```

Tarball-based fallback:

On local machine:

```bash
docker build -t guardgo-app:prod -f dockerFiles/api_docker .
docker save guardgo-app:prod | gzip > guardgo-app-prod.tar.gz
scp guardgo-app-prod.tar.gz <user>@<vps-ip>:/opt/guardgo/
```

On VPS:

```bash
cd /opt/guardgo
gunzip -c guardgo-app-prod.tar.gz | docker load
export ENV_FILE=/opt/guardgo/.env.prod
export APP_IMAGE=guardgo-app
export IMAGE_TAG=prod
./scripts/deploy.sh prod restart
```

## Health Checks

Preferred checks:

```bash
curl -i https://<domain>/health/live
curl -i https://<domain>/health/ready
```

If testing internally with host overrides:

```bash
curl -fsS --resolve <domain>:443:127.0.0.1 https://<domain>/health/live
curl -fsS --resolve <domain>:443:127.0.0.1 https://<domain>/health/ready
```

Do not rely on `curl -I` for endpoints that only allow `GET`.

## Mail / SMTP Guidance

Do not assume domain hosting automatically gives you suitable transactional SMTP.

Recommended production approach:

- use a transactional mail provider
- configure SPF
- configure DKIM
- configure DMARC

Examples:

- Postmark
- SendGrid
- Mailgun
- Amazon SES

For staging, host-installed Mailpit or equivalent test SMTP is acceptable.

## Troubleshooting Map

### SSH / workflow failures

- verify VPS host, user, SSH key, and passphrase secrets
- ensure branch exists remotely before VPS git checkout

### Port conflicts

- inspect listeners with `ss -lntp | grep -E ':80 |:443 '` 
- ensure no host nginx or old Docker stack owns those ports

### App unhealthy on startup

- inspect `web` logs first
- verify `ENCRYPTION_KEY` format
- prefer `GUNICORN_WORKERS='1'`

### Host validation / 400 on `www`

- include both domains in `PRODUCTION_DOMAIN`
- include both origins in `ALLOWED_CORS_ORIGINS`
- keep health checks on a single `HEALTHCHECK_HOST`

### Cert issues

- verify DNS points to the correct VPS IP
- verify ports `80` and `443` are reachable publicly
- verify letsencrypt files exist on host and are mounted into nginx

## Security Notes

- never commit real environment secrets
- rotate any secrets exposed during setup or troubleshooting
- keep stage and production secrets separate
- prefer immutable image tags for rollback clarity

## Rollback Guidance

Minimum safe rollback options:

1. redeploy previous known-good image tag
2. restore previous `.env` backup if a secret/config change caused the failure
3. keep previous tarball/image available if using manual image transfer

## Recommended Next Hardening

- add branch protection on `stage` and `master`
- add GitHub environment protection for production
- add uptime monitoring and alerting
- add Mongo backup and restore procedure
- add mail provider DNS records and send test checklist