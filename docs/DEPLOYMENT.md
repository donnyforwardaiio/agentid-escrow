# Deployment Guide — AgentID Backend

## Prerequisites
- GitHub account with this repo pushed
- Supabase account (free tier)
- Railway account (free tier)
- Node.js installed (for Railway CLI)

---

## Step 1 — Create Supabase Project

1. Go to https://supabase.com and sign in
2. Click **New Project**
3. Fill in:
   - **Name:** `agentid`
   - **Database Password:** generate a strong one and save it
   - **Region:** pick closest to you
4. Wait ~2 minutes for the project to spin up
5. Go to **Project Settings → Database**
6. Copy the **Connection String** (URI format):
   ```
   postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
   ```
   This is your `DATABASE_URL`
7. Go to **Project Settings → API**
8. Copy **Project URL** → `SUPABASE_URL`
9. Copy **anon/public key** → `SUPABASE_KEY`

---

## Step 2 — Generate SECRET_KEY

Run this in your terminal:

```bash
openssl rand -hex 32
```

Save the output — this is your `SECRET_KEY`.

---

## Step 3 — Create Railway Project

1. Go to https://railway.app and sign in
2. Click **New Project → Deploy from GitHub repo**
3. Connect your GitHub account and select **agentid-escrow**
4. Railway will detect the `railway.toml` automatically

---

## Step 4 — Add Environment Variables in Railway

In your Railway project dashboard, go to **Variables** and add:

| Variable | Value |
|---|---|
| `DATABASE_URL` | From Supabase Step 1 |
| `SECRET_KEY` | From Step 2 |
| `SUPABASE_URL` | From Supabase Step 1 |
| `SUPABASE_KEY` | From Supabase Step 1 |

---

## Step 5 — First Deploy

Railway auto-deploys on push to `main`. Trigger it manually:

```bash
# From your project root
git add .
git commit -m "Initial deploy"
git push origin main
```

Watch the deploy logs in the Railway dashboard.
The health check at `/health` must return 200 for the deploy to succeed.

---

## Step 6 — Run Migrations

After the first successful deploy, run migrations against your Supabase DB.

Copy your `DATABASE_URL` into a local `.env` file:

```bash
cd backend
cp .env.example .env
# Edit .env and set DATABASE_URL to your Supabase connection string
```

Then run:

```bash
make migrate
```

You should see:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, Initial schema
```

---

## Step 7 — Verify Live Deployment

Replace `YOUR_RAILWAY_URL` with the URL shown in your Railway dashboard:

```bash
curl https://YOUR_RAILWAY_URL/health
```

Expected response:

```json
{"status": "ok", "version": "0.1.0", "db_connected": true}
```

Test agent registration against the live API:

```bash
# Generate a test keypair (Python one-liner)
python3 -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
pk = Ed25519PrivateKey.generate()
print(pk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex())
"

# Register an agent
curl -X POST https://YOUR_RAILWAY_URL/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyFirstAgent",
    "owner_email": "you@example.com",
    "capabilities": ["code"],
    "public_key": "PASTE_PUBLIC_KEY_HEX_HERE"
  }'
```

---

## Step 8 — Add RAILWAY_TOKEN for CI/CD

1. In Railway dashboard go to **Account Settings → Tokens**
2. Create a new token named `github-actions`
3. In your GitHub repo go to **Settings → Secrets → Actions**
4. Add secret: `RAILWAY_TOKEN` = the token from Railway

From now on every push to `main` will:
1. Run the full test suite
2. Deploy to Railway only if tests pass

---

## Troubleshooting

**Deploy fails with "build error"**
- Check that `backend/requirements.txt` has no syntax errors
- Check Railway build logs for the specific pip install failure

**Health check fails after deploy**
- Check Railway deploy logs for Python tracebacks
- Verify `DATABASE_URL` environment variable is set correctly in Railway

**Migrations fail**
- Ensure your Supabase project is active (it sleeps after inactivity on free tier)
- Check that `DATABASE_URL` in your local `.env` matches the Supabase connection string exactly
- Supabase requires SSL — if you see SSL errors, append `?sslmode=require` to `DATABASE_URL`

**SSL connection error from Supabase**
```
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres?sslmode=require
```
