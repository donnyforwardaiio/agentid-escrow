# AgentID + AgentEscrow — Trust Layer for the Agent Economy

## What This Project Is
We are building the foundational trust infrastructure for
agent-to-agent commerce. Two products, one platform:

**AgentID** — Reputation registry and identity layer for AI agents
- Agents register with a public key and capability manifest
- Every transaction updates their reputation score
- Other agents query before hiring/trusting

**AgentEscrow** — Secure escrow for agent-to-agent transactions
- Funds locked until task completion verified
- Auto-releases after 24h dispute window
- Every transaction feeds back into AgentID reputation

## Tech Stack
- Backend: FastAPI (Python 3.11+)
- Database: PostgreSQL via Supabase (free tier)
- Frontend: Next.js 14 + shadcn/ui + Tailwind CSS
- Agent Auth: Ed25519 keypair signing
- Hosting: Railway (backend) + Vercel (frontend)
- Email: Beehiiv (newsletter/onboarding)
- CI/CD: GitHub Actions

## Project Structure
```
agentid-escrow/
├── CLAUDE.md           ← you are here
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models/
│   │   ├── routes/
│   │   ├── services/
│   │   └── schemas/
│   ├── tests/
│   ├── alembic/
│   ├── requirements.txt
│   └── Makefile
├── frontend/
│   ├── app/
│   ├── components/
│   └── package.json
├── docs/
└── .github/
    └── workflows/
```

## Key Commands
- `cd backend && make dev`      → start backend locally
- `cd backend && make test`     → run test suite
- `cd backend && make migrate`  → run DB migrations
- `cd frontend && npm run dev`  → start frontend locally

## Core Architecture Rules
1. Every agent action logs to audit trail — no exceptions
2. Escrow state changes must be atomic (use DB transactions)
3. Never store private keys — public keys only in registry
4. All API endpoints must have tests before shipping
5. API is versioned: all routes start with /v1/
6. Agent requests authenticated by Ed25519 signature verification

## Business Context
- Targeting developer community building multi-agent systems
- Free tier: unlimited agent registration, basic reputation queries
- Paid: verified capability badges, webhook notifications, enterprise SLA
- Revenue model: 1.5% transaction fee on escrow above $10K cumulative per user
- Competitors: none yet — we are establishing the category

## Current Build Phase
▶ PHASE 1: AgentID MVP (backend only)
  □ Database schema + migrations
  □ Agent registration endpoint
  □ Reputation scoring system
  □ Agent query endpoints
  □ Ed25519 authentication
  □ Full test suite
  □ Deploy to Railway

○ PHASE 2: AgentEscrow MVP
○ PHASE 3: Frontend Dashboard
○ PHASE 4: Marketing Automation
○ PHASE 5: Framework Integrations

## Environment Variables Needed
```
DATABASE_URL=          ← from Supabase
SECRET_KEY=            ← generate with: openssl rand -hex 32
SUPABASE_URL=          ← from Supabase dashboard
SUPABASE_KEY=          ← from Supabase dashboard
STRIPE_SECRET_KEY=     ← from Stripe (Phase 2)
STRIPE_WEBHOOK_SECRET= ← from Stripe (Phase 2)
```

## Definition of Done for Each Feature
- Endpoint works locally
- Test written and passing
- Error cases handled
- Logged to audit trail
- Documented in /docs
