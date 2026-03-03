# Production Deployment

## Netlify frontend + external backend

This app is ready for Netlify as **frontend-only** hosting. The Flask API must run separately (Render/Railway/VM/Fly.io/etc.).

1. Deploy backend first and confirm:

```bash
GET https://<backend-domain>/api/health
GET https://<backend-domain>/api/ready
```

2. On Netlify, import this repository. `netlify.toml` already sets:
   - Base directory: `frontend`
   - Build command: `npm ci && npm run build`
   - Publish directory: `dist`

3. In Netlify Site Settings -> Environment Variables, set:

```bash
VITE_API_BASE=https://<backend-domain>
```

4. Trigger deploy and verify in browser dev tools that frontend calls:
   - `https://<backend-domain>/api/...`
   - `https://<backend-domain>/uploads/...` (for uploaded files)

5. If backend domain changes, update `VITE_API_BASE` and redeploy.

Notes:
- Netlify does not host this long-running Flask + SQLite backend directly.
- Backend CORS is already enabled for cross-origin frontend calls.

## Local/VM deployment from source

1. Copy template:

```bash
cp .env.production.example .env
```

2. Fill real SMTP/OTP provider values in `.env`.
   - For email OTP: set `SMTP_*`
   - For mobile OTP: set optional `TWILIO_*` values

3. Start services:

```bash
./run-prod.sh
```

This builds and starts:
- Frontend on `http://localhost:8080`
- Backend API on `http://localhost:5000`

## GitHub deployment (GHCR images)

Use GitHub Actions to build and publish Docker images to GitHub Container Registry.

1. Push this repository to GitHub (default branch: `main` or `master`).
2. In your GitHub repo, ensure Actions are enabled.
3. Optional: set repo variable `VITE_API_BASE` if frontend should call a fully-qualified backend URL.
   - Leave unset to use same-origin `/api` (recommended with the included Nginx proxy).
4. Trigger workflow [`deploy-ghcr.yml`](./.github/workflows/deploy-ghcr.yml) by pushing to default branch or running it manually.
5. On your server/VM, create `.env` from `.env.production.example` and add:

```bash
GHCR_REPOSITORY=<github-owner>/<github-repo>
IMAGE_TAG=latest
```

6. Pull and run published images:

```bash
docker login ghcr.io
docker compose -f docker-compose.ghcr.yml --env-file .env up -d
```

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

For GHCR compose:

```bash
docker compose -f docker-compose.ghcr.yml --env-file .env ps
docker compose -f docker-compose.ghcr.yml --env-file .env logs -f
docker compose -f docker-compose.ghcr.yml --env-file .env down
```

Manual DB backup:

```bash
python3 backend/backup_db.py --label manual --max-backups 30
```
