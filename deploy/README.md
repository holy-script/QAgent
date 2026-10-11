# Deploying QAgent on one machine

1. Get a small Linux VM (2 vCPU, 4 GB RAM is plenty) with Docker, and point a domain at it (optional but recommended).
2. Copy the repo there. Create `backend/.env` from `.env.example` (Neon database, storage bucket, Jev and Bedrock keys).
3. Next to `docker-compose.yml` create `.env`:
   ```
   AUTH_SECRET=<long random string, e.g. output of: openssl rand -hex 32>
   SITE_ADDRESS=qagent.example.com        # or :80 for plain HTTP (then also AUTH_COOKIE_SECURE=false)
   PUBLIC_URL=https://qagent.example.com
   ```
4. `docker compose up -d --build`, then open the address and sign in with the team account.
5. Testing the bundled demo shop? `docker compose --profile demo up -d`, then add an app with the address `http://demo-shop:8001`
   and allow the host `demo-shop` in the app's settings.

Why this shape: everything is on one address, so the sign-in cookie just works and live run events are not buffered or cut by a proxy.
The backend runs one worker because live run events are kept in memory; scale up the machine, not the worker count.
Updating: `git pull && docker compose up -d --build`. Migrations run automatically on start.
