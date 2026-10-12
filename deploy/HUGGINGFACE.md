# Backend on Hugging Face Spaces, web app on Vercel

```
browser --> Vercel (web app) --/api rewrite--> Hugging Face Space (API + Chromium + demo shop) --> Neon (database, files)
```
The browser only ever talks to the Vercel address. Vercel forwards `/api/...` to the Space, so the sign-in cookie, live run
events and screenshots work without any cross-site cookie tricks.

## Check first
Hugging Face's docs are inconsistent about whether Docker Spaces on the free CPU Basic hardware (2 vCPU, 16 GB) need a paid
plan. Creating the Space (step 1) tells you at once. The Space must be **Public** (Vercel cannot send a Hugging Face token);
the API still requires the QAgent sign-in for everything except `/api/health` and `/api/auth/*`.

## Tested
The image was built and run locally with Docker: health check green (Neon, storage, Jev and Bedrock reachable), sign-in under `/api`, and a real test run in Chromium against the bundled demo shop, with the browser's default 64 MB of shared memory (what Spaces give you). The `/api` proxy was checked through a local production build of the web app (sign-in, API calls and live run events).

## 1. The Space (backend)
1. huggingface.co > New Space > name it > SDK **Docker** > **Blank** > hardware **CPU basic (free)** > **Public** > Create.
2. Space > Settings > **Variables and secrets**, add as *Secrets* (same values as `backend/.env`):
   `AUTH_SECRET` (long random string, `openssl rand -hex 32`), `DATABASE_URL`, `DATABASE_URL_DIRECT`, `NEON_S3_ENDPOINT`,
   `NEON_S3_ACCESS_KEY_ID`, `NEON_S3_SECRET_ACCESS_KEY`, `NEON_S3_REGION`, `NEON_S3_BUCKET`, `TYPESAFE_API_KEY`,
   `JEV_API_TOKEN`, `BEDROCK_API_KEY`, `BEDROCK_REGION`, `BEDROCK_REASONING_MODEL_ID`
   (and `AUTH_EMAIL` / `AUTH_PASSWORD` if you changed them). Paste each value **without quotes** (`.env` files may have them; the Secrets form takes the text literally).
3. Create a Hugging Face **access token with Write permission** (Settings > Access Tokens).
4. From the repo root with everything committed: `deploy/hf/publish.sh https://huggingface.co/spaces/<you>/<space>`
   (username = your Hugging Face username, password = the token). The first build takes about 10 minutes (Logs tab).
5. Check `https://<you>-<space>.hf.space/api/health` answers.

## 2. The web app on Vercel (CLI)
From the `frontend` folder (`frontend/vercel.json` already sets the install command):
```
cd frontend
vercel login
vercel link                                   # create a new project; keep the defaults
printf '/api' | vercel env add NEXT_PUBLIC_API_URL production
printf 'https://<you>-<space>.hf.space' | vercel env add BACKEND_URL production
vercel --prod
```
`NEXT_PUBLIC_API_URL=/api` makes the browser call the same address it was loaded from; `BACKEND_URL` is where Vercel forwards
`/api`. Both must be set before the build. Open the Vercel address and sign in.

## 3. Using it
- The demo shop runs inside the Space: add an app with `http://localhost:8001` (the seeded Demo Shop already is).
  To test another site, add it as an app; it must be reachable from the internet.
- A free Space sleeps after a stretch without traffic (reports say 48 hours) and wakes on the next visit (about a minute).
  To keep it up for a demo week, point UptimeRobot or cron-job.org at `https://<you>-<space>.hf.space/api/health` every 30 minutes.
- Live run events pass through Vercel's proxy. If a connection is cut, the browser reconnects and resumes where it left off.
- If the Space restarts mid-run, that run is marked failed on startup; start it again. Nothing else is lost: runs, bugs and
  files live in Neon.
- Updating: commit, `deploy/hf/publish.sh <space url>` (backend), `vercel --prod` (web).
