# Deploying on Hugging Face Spaces

A Space runs ONE container on ONE port (7860). QAgent is three programs (web app, API, demo shop), so `deploy/hf/Dockerfile`
packs them into a single image behind Caddy. The Neon database and Neon storage stay where they are.

## Check first
Hugging Face's documentation is inconsistent about whether Docker Spaces on the free "CPU Basic" hardware (2 vCPU, 16 GB)
need a paid plan. Creating the Space (step 1) will tell you immediately: if it asks for payment for Docker, use Oracle
Always Free instead (`deploy/README.md`).

## Steps
1. huggingface.co > New Space > name it > SDK **Docker** > template **Blank** > hardware **CPU basic (free)** > Private is fine
   (the app has its own sign-in) > Create.
2. Space > Settings > **Variables and secrets** > add these as *Secrets*:
   - `AUTH_SECRET` (long random string: `openssl rand -hex 32`)
   - `DATABASE_URL`, `DATABASE_URL_DIRECT`
   - `NEON_S3_ENDPOINT`, `NEON_S3_ACCESS_KEY_ID`, `NEON_S3_SECRET_ACCESS_KEY`, `NEON_S3_REGION`, `NEON_S3_BUCKET`
   - `TYPESAFE_API_KEY`, `JEV_API_TOKEN`, `BEDROCK_API_KEY`, `BEDROCK_REGION`, `BEDROCK_REASONING_MODEL_ID`
   (same values as `backend/.env`; `AUTH_EMAIL` / `AUTH_PASSWORD` too if you changed them).
3. Create a Hugging Face **access token with Write permission** (Settings > Access Tokens).
4. From the repo root, with everything committed:
   `deploy/hf/publish.sh https://huggingface.co/spaces/<you>/<space>`
   Username = your Hugging Face username, password = the token.
5. Open the Space's **Logs** tab; the first build takes about 10 minutes. When it says running, open the direct address
   `https://<you>-<space>.hf.space` (not the huggingface.co page: sign-in cookies do not work inside its frame) and sign in.
6. In QAgent, open **Demo Shop** and run a test. The demo shop runs inside the same container, so `http://localhost:8001` works.
   To test another site, add it as an app (it must be reachable from the internet).

## Keeping it awake and what to expect
- A free Space sleeps after a period without traffic (reports say 48 hours) and wakes on the next visit (about a minute).
  To keep it up for a demo week, point a free pinger (UptimeRobot, cron-job.org) at `https://<you>-<space>.hf.space/api/health`
  every 30 minutes.
- If it restarts mid-run, that run is marked as failed on startup; start it again.
- The container disk is temporary. Nothing is lost: runs, bugs and files live in Neon.
- Updating: commit, run `deploy/hf/publish.sh` again (it force-pushes a clean copy; the Space rebuilds).
