# GuardGo Stage CI/CD Manual

This is the final stage deployment guide for the current architecture.

## Final Architecture

- Deployment trigger: push to `stage` branch
- Build location: GitHub Actions runner
- Image registry: GHCR (`ghcr.io/<owner>/guardgo-app:stage`)
- Deploy target: staging VPS at `/opt/guardgo`
- Runtime edge: Docker nginx in stage stack (ports 80 and 443)
- TLS termination: inside Docker nginx using host cert mounts (`/etc/letsencrypt`)

## What Happens On Every Stage Push

Workflow file: `.github/workflows/deploy-stage.yml`

1. Build app image from `dockerFiles/api_docker`
2. Push image to GHCR with tag `stage`
3. SSH to VPS and update git branch
4. Pull image on VPS
5. Restart stage stack (`deploy.sh stage down` then `up`)
6. Run HTTPS smoke checks:
   - `/health/live`
   - `/health/ready`

## One-Time Setup Checklist

### 1) GitHub repository secrets

Add in GitHub: Settings -> Secrets and variables -> Actions

- `STAGE_VPS_HOST`
- `STAGE_VPS_USER`
- `STAGE_VPS_SSH_KEY`
- `STAGE_VPS_SSH_PASSPHRASE` (only if key is passphrase-protected)

### 2) VPS repository + compose prerequisites

```bash
sudo mkdir -p /opt/guardgo
cd /opt/guardgo
git clone <repo-url> .
```

### 3) Stage environment file on VPS

Path: `/opt/guardgo/.env.stage`

Required highlights for HTTPS stage:

- `APP_URL='https://ggstage.vaultcentric.com'`
- `PRODUCTION='1'`
- `PRODUCTION_DOMAIN='ggstage.vaultcentric.com'`
- `ALLOWED_CORS_ORIGINS='https://ggstage.vaultcentric.com'`
- `GUNICORN_WORKERS='1'` (recommended for this codebase startup behavior)

### 4) VPS cert paths used by stage nginx

The stage compose mounts these host paths into the nginx container:

- `/etc/letsencrypt`
- `/var/www/letsencrypt`

Required files:

```bash
ls -l /etc/letsencrypt/live/ggstage.vaultcentric.com/fullchain.pem
ls -l /etc/letsencrypt/live/ggstage.vaultcentric.com/privkey.pem
```

### 5) Port ownership

Stage stack needs host ports 80 and 443 available.

If another service is listening (for example host nginx), free those ports first.

## Standard Operating Flow (Daily)

1. Commit code
2. Push to `stage`
3. Watch workflow in GitHub Actions
4. Done if workflow is green

No manual image build, no tarball transfer, no manual `docker load`.

## Verification Commands

### From your machine

```bash
curl -i https://ggstage.vaultcentric.com/health/live
curl -i https://ggstage.vaultcentric.com/health/ready
```

### On VPS (if needed)

```bash
cd /opt/guardgo
export ENV_FILE=/opt/guardgo/.env.stage
export APP_IMAGE=ghcr.io/<owner>/guardgo-app
export IMAGE_TAG=stage
docker compose --project-name guardgo-stage --env-file "$ENV_FILE" -f docker-compose.stage.yml ps
```

## Manual Fallback (Only If CI Fails)

```bash
cd /opt/guardgo
export ENV_FILE=/opt/guardgo/.env.stage
export APP_IMAGE=ghcr.io/<owner>/guardgo-app
export IMAGE_TAG=stage
./scripts/deploy.sh stage restart
```

Logs:

```bash
cd /opt/guardgo
export ENV_FILE=/opt/guardgo/.env.stage
export APP_IMAGE=ghcr.io/<owner>/guardgo-app
export IMAGE_TAG=stage
./scripts/deploy.sh stage logs
```

## Troubleshooting Quick Map

- Workflow fails at SSH auth: verify key/passphrase secrets
- Workflow fails at port check: another process owns 80 or 443
- Workflow passes but browser fails: verify DNS + external 443 reachability
- Health endpoint returns 405 on `curl -I`: use GET (`curl -i` or `curl -sS`)

## Security Notes

- Never commit real secrets into repository files
- Keep production and stage credentials separate
- Rotate any credentials that were exposed during setup/testing
