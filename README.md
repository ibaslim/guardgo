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
- docker-compose.yml - local docker stack
- docker-compose-production.yml - production docker stack
- nginx/ - reverse proxy config

## Quick Start (run.sh)

1) Create your environment file:

```bash
cp env .env
```

2) Start the stack:

```bash
./run.sh -d
```

This script wraps Docker Compose and uses the project defaults.

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

The app expects a `.env` file at the project root. Use `env` as a starting point and replace secrets for your
environment. Do not commit real secrets to source control.

## API Docs

Swagger UI is available at `/docs` when the API is running.

## License

See LICENSE.
