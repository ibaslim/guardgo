# GuardGo

GuardGo is an Uber-like platform that connects clients with licensed security guards. The platform supports three tenant
types:

- Guard (individual)
- Client (individual or company)
- Service Provider (security guard provider company)

## Features

- Tenant onboarding with profile verification
- Guard availability, licensing, and credentials management
- Client and provider profiles with structured contacts and addresses
- File uploads for licenses and documents
- Role-based access control

## Tech Stack

- Backend: FastAPI, Odmantic, MongoDB
- Frontend: Angular (standalone components), Tailwind CSS
- Infra: Docker, Nginx, Redis, Mailpit

## Project Structure

- backend/ - FastAPI app, routes, services, migrations
- client/ - Angular app
- docker-compose.local.yml - local Docker stack
- docker-compose.stage.yml - staging Docker stack
- docker-compose.prod.yml - production Docker stack
- scripts/ - local and deploy entrypoints
- docs/deploy-manual.md - unified staging and production deployment manual

## Quick Start (run.sh)

1) Create your environment file:

```bash
cp .env.example .env.local
```

2) Start the stack:

```bash
./run.sh build -d
```

This keeps the existing local command shape, but the real logic now lives in `scripts/run-local.sh`.

The app will be available on http://localhost:8080 and the API docs at http://localhost:8080/docs.

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Seeder Guidelines (Contributors)

GuardGo uses a reusable seeder framework for backend data seeders.

- Seeder files live in `backend/migrations/scripts/`
- Seeder files should be named `seed_<name>.py`
- Seeders are discovered and run through `backend/migrations/seeder_manager.py`
- App startup runs `AUTO_RUN` seeders via `backend/main.py`

For any new seeder, follow this pattern:

```python
AUTO_RUN = False  # Set True only if safe to run on startup

async def run(force: bool = False):
	# Implement idempotent seeding logic.
	# Respect force=True when overwrite/reseed behavior is needed.
	return {"ok": True}
```

Use the shared CLI runner:

```bash
cd backend

# List discovered seeders
python migrations/run_seeders.py --list

# Run all AUTO_RUN seeders
python migrations/run_seeders.py --auto

# Run one seeder by module name (without .py)
python migrations/run_seeders.py --seeder seed_billing_default_payrates

# Force rerun when supported by the seeder
python migrations/run_seeders.py --seeder seed_billing_default_payrates --force
```

Current example seeder:

- `backend/migrations/scripts/seed_billing_default_payrates.py`

### Frontend

```bash
cd client
npm install
npx ng serve
```

If you want the backend to serve the built frontend, run:

```bash
cd client
npm run build
```

## Tests

```bash
cd client
npm test
```

## Configuration

Use dedicated env files per environment:

- local machine: `.env.local`
- staging VPS: `/opt/guardgo/.env.stage`
- production VPS: `/opt/guardgo/.env.prod`

Commit only `.env.example`. Do not commit real secrets to source control.

For staging on a VPS with host-installed Mailpit, point SMTP to `host.docker.internal:1025`.

## Deployment

Staging and production deployment are documented in [docs/deploy-manual.md](/home/ibsalim/Projects/guardgo/docs/deploy-manual.md:1).

## API Docs

Swagger UI is available at `/docs` when the API is running.

## License

See LICENSE.
