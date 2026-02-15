# Production Deployment

## One-command startup

```bash
./run-prod.sh
```

This builds and starts:
- Frontend on `http://localhost:8080`
- Backend API on `http://localhost:5000`

## Environment setup

1. Copy template:

```bash
cp .env.production.example .env
```

2. Fill real SMTP/OTP provider values in `.env`.
   - For email OTP: set `SMTP_*`
   - For mobile OTP: set optional `TWILIO_*` values

## Health and readiness

- Health: `GET /api/health`
- Readiness: `GET /api/ready`

Compose waits for backend readiness before frontend starts.

## Persistent data

Docker volumes are used for:
- `backend_data` -> SQLite DB
- `backend_uploads` -> uploaded records
- `backend_backups` -> automatic/manual DB backups

## Operations

```bash
docker compose ps
docker compose logs -f
docker compose down
```

Manual DB backup:

```bash
python3 backend/backup_db.py --label manual --max-backups 30
```
