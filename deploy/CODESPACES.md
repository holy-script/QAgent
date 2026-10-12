# Backend on GitHub Codespaces, web app on Vercel

```
browser --> Vercel (web app) --/api rewrite--> GitHub Codespace (API + Chromium + demo shop) --> Neon (database, files)
```
`.devcontainer/` builds the same Chromium image the other deployments use, installs the backend, and on every start runs
`deploy/codespaces/start.sh` (demo shop on 8001, API on 8000). The Vercel side is the same as in `deploy/HUGGINGFACE.md`.

Tested locally with Docker by mounting the repo and running the same create/start commands: API healthy, sign-in under `/api`,
a real browser test run against the demo shop, and a clean restart. Not tested inside an actual Codespace.

## Know before you start
- A Codespace is a development machine, not a host. It **stops after an idle period** (30 minutes by default) and the API is
  down until you open or start it again (the start script then brings the API back by itself).
  Raise the limit: github.com/settings/codespaces > Default idle timeout (up to 4 hours). Keeping the Codespace open in a
  browser tab keeps it active.
- Free personal accounts get about 120 core-hours a month (a 2-core machine = 60 hours of running time); with the GitHub Student pack it is about 180 (90 hours on 2 cores).
- A new Codespace gets a new address, so `BACKEND_URL` must be updated and the web app redeployed (the proxy address is
  read at build time).
- The port has to be **Public** so Vercel can reach it. GitHub may show a one-time "continue" page to browsers on a public
  port; if the web app shows errors reaching the API but the address works in a browser, that page is the likely cause, and
  the Hugging Face Space (`deploy/HUGGINGFACE.md`) is the fallback.

## Steps
1. github.com/settings/codespaces > **Secrets** > New secret, for each of these (repository access: this repo; values without
   quotes): `AUTH_SECRET` (long random string), `DATABASE_URL`, `DATABASE_URL_DIRECT`, `NEON_S3_ENDPOINT`,
   `NEON_S3_ACCESS_KEY_ID`, `NEON_S3_SECRET_ACCESS_KEY`, `NEON_S3_REGION`, `NEON_S3_BUCKET`, `TYPESAFE_API_KEY`,
   `JEV_API_TOKEN`, `BEDROCK_API_KEY`, `BEDROCK_REGION`, `BEDROCK_REASONING_MODEL_ID`
   (and `AUTH_EMAIL` / `AUTH_PASSWORD` if you changed them).
2. The repo on GitHub > **Code** > **Codespaces** > **...** > *New with options*: branch `ui-refresh` (or the one you merge to),
   machine type 2-core. Create. The first build takes a few minutes; the terminal ends with
   `QAgent API is up on port 8000`.
3. Open the **Ports** tab, right-click port 8000 > **Port Visibility** > **Public**. Copy its address
   (`https://<name>-8000.app.github.dev`) and check `<address>/api/health` answers.
4. Web app (from your machine):
   ```
   cd frontend
   vercel link
   printf '/api' | vercel env add NEXT_PUBLIC_API_URL production
   printf '<the address from step 3>' | vercel env add BACKEND_URL production
   vercel --prod
   ```
5. Open the Vercel address and sign in. The seeded Demo Shop runs inside the Codespace (`http://localhost:8001`).

## Day to day
- Codespace stopped? Open it from github.com/codespaces; the API restarts on its own (check the Ports tab; set visibility to
  Public again if GitHub reset it).
- Logs: `/tmp/qagent-api.log`, `/tmp/qagent-shop.log`. Restart: `bash deploy/codespaces/start.sh`.

## Keeping it up on the same address (4-hour idle limit + a free cron job)
The address (`https://<codespace-name>-8000.app.github.dev`) stays the same for as long as it is the same Codespace; only a
*stopped* Codespace is down. So: set the idle timeout to 4 hours (github.com/settings/codespaces), and have a free cron
service start it again whenever it has stopped.

1. Create a **classic** personal access token with only the `codespace` scope (github.com/settings/tokens). Treat it as a
   password; it can start and stop your Codespaces.
2. Add it as a Codespaces secret named `GH_PAT`. On each start the script then sets port 8000 back to Public by itself.
3. Find the Codespace name (the part before `-8000` in the port address, or github.com/codespaces).
4. On cron-job.org (free) create a job, every 10 minutes:
   - URL `https://api.github.com/user/codespaces/<codespace-name>/start`, method **POST**
   - Headers: `Authorization: Bearer <the token>`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`
   Starting a Codespace that is already running does nothing, so it is safe to repeat. After a stop, downtime is at most
   10 minutes, and the start script brings the API back up on its own.
5. Optional second job: GET `<address>/api/health` every 5 minutes to see in the cron history whether it is up.

Not tested here (it needs your account). If the start call returns an error, the cron history shows GitHub's message.
Every hour a Codespace runs counts against the quota, so pause the job when you do not need the backend.
