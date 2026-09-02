# Medicii

Production-oriented medicine quote-to-order platform. This repository intentionally uses mock data and placeholder secrets only.

## Run locally

1. `copy .env.example .env`
2. `docker compose up --build`
3. Open `http://localhost:3000` (API docs: `http://localhost:8000/docs`).

The seed account is `admin@medicii.example.com` / `ChangeMe123!` (development only). Registering normally creates a customer account.

See [docs/production-readiness.md](docs/production-readiness.md) before any deployment.

## Use Supabase PostgreSQL

The normal command above continues to use the local Docker PostgreSQL database.
To use a Supabase database instead:

1. Create a Supabase project and open its **Connect** panel.
2. Copy its Postgres connection string into the private `.env` file as
   `SUPABASE_POOLER_DATABASE_URL`. Change its prefix from `postgres://` to
   `postgresql+psycopg://` and append `?sslmode=require` if it is not already
   present.
3. Run `docker compose -f docker-compose.supabase.yml up --build`.

This project automatically creates its development schema on first startup.
Do not put the Supabase database password in GitHub or in any `NEXT_PUBLIC_*`
environment variable. The application still needs production private object
storage before storing actual prescription or ID documents.
