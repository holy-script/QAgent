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

## A free machine to run it on
Chromium needs real memory, so a normal "free web hosting" tier is too small; you want a small virtual machine.
- **Oracle Cloud "Always Free"** (best fit): an ARM VM with 2 OCPU / 12 GB (reports say the old 4 / 24 GB allowance is being reduced; check Oracle's Always Free page). Sign-up needs a card for identity checks and the ARM VMs are sometimes out of capacity in a region; retry another time or region. Everything in `docker-compose.yml` has ARM images (the Playwright base image, Node, Caddy, Python).
- **Google Cloud e2-micro / AWS or Azure 12-month free tiers**: 1 GB of memory is too little for the browser plus the backend. Only workable with a swap file and one run at a time.
- **Your own machine**: a spare laptop or Raspberry Pi 5 (8 GB) at home with a Cloudflare Tunnel gives the same result for nothing.

On the VM: install Docker (`curl -fsSL https://get.docker.com | sh`), open ports 80 and 443 in the cloud firewall, clone the repo, then follow the steps above.
