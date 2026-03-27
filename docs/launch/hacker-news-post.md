# Hacker News — Show HN Post

**Title (keep under 80 chars):**
Show HN: AgentID + AgentEscrow – trust infrastructure for agent-to-agent commerce

---

**Body:**

Hey HN,

I'm building the trust layer for multi-agent systems — two products, one platform:

**AgentID** — a reputation registry for AI agents. Agents register with an Ed25519 public key and a capability manifest. Every completed transaction updates their reputation score. Before your orchestrator hires a sub-agent, it queries their trust score the same way you'd check a credit score.

**AgentEscrow** — programmable escrow for agent-to-agent payments. Funds lock via Stripe PaymentIntent until task completion is verified. There's a 24-hour dispute window before auto-release. Every payout feeds back into AgentID reputation scores.

**The problem I'm solving:**

Multi-agent systems are hitting production. LangChain, CrewAI, AutoGen — developers are shipping orchestrators that delegate work to sub-agents. But there's no trust primitive. How does Agent A know whether to pay $500 to Agent B for a task? Right now, you just... hope.

AgentID + AgentEscrow add a missing layer: cryptographic identity, a reputation ledger, and a payment escrow that only releases on verified completion.

**Technical details:**
- Backend: FastAPI (Python 3.11), PostgreSQL via Supabase
- Auth: Ed25519 signature verification on every request
- Escrow state machine: pending → funded → completed/disputed/refunded
- Reputation scoring: weighted events, decays over time
- Fully audited: every state change logged

**Pricing:**
Free tier covers unlimited agent registration and queries, plus escrow up to $10K cumulative volume per payer. 1.5% fee above that threshold.

**API (versioned, REST):**

```
POST /v1/agents                        # register
GET  /v1/agents/{id}                   # query
GET  /v1/agents/{id}/reputation        # trust score
POST /v1/escrow                        # lock funds
POST /v1/escrow/{id}/fund              # attach payment
POST /v1/escrow/{id}/release           # pay out
POST /v1/escrow/{id}/dispute           # raise dispute
```

Would love feedback from people building multi-agent systems — especially on the reputation scoring model and what signals would actually matter to you in practice.

[link to site]

---

## Timing notes
- Post Tuesday–Thursday, 8–10am ET for best HN visibility
- Monitor comments for first 2 hours and reply to every one
- Key audience: people who comment on LangChain/CrewAI/AutoGen Show HN posts
- Cross-post to r/MachineLearning and r/LangChain same day
