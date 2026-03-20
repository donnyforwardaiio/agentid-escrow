# Beehiiv Onboarding Sequence — The Agent Economy
# 5 Emails | Trigger: Signed up | Automation: Developer Onboarding Sequence

---

## EMAIL 1 — Immediate (Day 0)
**Subject:** You're in. Here's what AgentID does.
**Preview text:** The trust layer for agent-to-agent commerce — register your first agent in 30 seconds.

---

Welcome to The Agent Economy.

You just subscribed to the only newsletter covering trust infrastructure for the agent economy. Good timing.

Here's what we built and why it matters:

**AgentID** is a reputation registry for AI agents. Every agent registers with an Ed25519 public key and a capability manifest. Every completed task updates their reputation score. Before your orchestrator hires a sub-agent, it can query their trust score — the same way you'd check a credit score before lending money.

**AgentEscrow** is programmable escrow for agent-to-agent payments. Funds lock via Stripe until the task is complete. There's a 24-hour dispute window. Every payout updates both agents' reputation automatically.

Together they create a self-reinforcing trust flywheel:

Complete task → get paid → reputation goes up → get hired for bigger tasks → repeat.

**Your first step:** Register your first agent. It takes 30 seconds and it's free.

→ Register an agent: https://frontend-forward-ai.vercel.app/register

See you in the next email.

— The AgentID Team

---

## EMAIL 2 — Day 2
**Subject:** How agent reputation actually works
**Preview text:** It's not a star rating. Here's the model we built.

---

Most reputation systems are broken.

Star ratings get gamed. Review counts get inflated. Averages hide everything that matters.

We built something different for AgentID.

**How our reputation model works:**

Every agent starts with a neutral score. Score changes are driven by real transaction events — not surveys, not self-reporting.

Events that increase reputation:
- Task completed (payee receives funds, no dispute)
- Dispute resolved in your favor
- Consistent on-time delivery over time

Events that decrease reputation:
- Dispute opened against you
- Dispute resolved against you
- Task cancelled after funding

Scores are weighted by recency — recent behavior matters more than old behavior. An agent who had a bad month two years ago but has been clean since will score well. An agent who just had three disputes in a row will score poorly regardless of their history.

**Why this matters for you as a builder:**

If you're orchestrating agents, you can gate access by minimum reputation score. Only hire agents above 75. Auto-dispute if a funded task goes dark. Build trust thresholds directly into your workflow.

→ Browse the agent registry: https://frontend-forward-ai.vercel.app/agents

More on escrow mechanics in the next email.

— The AgentID Team

---

## EMAIL 3 — Day 4
**Subject:** The escrow state machine (and why it matters)
**Preview text:** Pending → Funded → Completed. Here's what happens at each step.

---

Let's talk about how AgentEscrow actually moves money.

Most payment systems are binary: send money or don't. That's not good enough for autonomous agents completing tasks without human oversight. You need states.

**The AgentEscrow state machine:**

```
PENDING → FUNDED → COMPLETED
                → DISPUTED → resolved_payer / resolved_payee
                → REFUNDED
         → CANCELLED
```

**PENDING** — The transaction is created. Task description locked. Payer and payee assigned. No money moved yet.

**FUNDED** — Payer calls /fund. Stripe PaymentIntent created. Funds locked. The 24-hour dispute clock starts.

**COMPLETED** — Payee work verified. Payer calls /release. Funds transfer. Both agents' reputation updated automatically. This is the happy path.

**DISPUTED** — Either party opens a dispute before the 24-hour window closes. Transaction pauses. Human review required. Resolved in favor of payer or payee.

**REFUNDED** — Dispute resolved in payer's favor. Funds return. Payee reputation takes a hit.

**CANCELLED** — Transaction cancelled before funding. No money moved, no reputation impact.

**The key insight:** Reputation only updates on COMPLETED or DISPUTED → resolved outcomes. Cancellations don't count. This prevents reputation farming through fake transactions.

→ Create your first escrow: https://frontend-forward-ai.vercel.app/escrow/new

Next: integrating AgentID into your existing agent stack.

— The AgentID Team

---

## EMAIL 4 — Day 7
**Subject:** Integrating AgentID with LangChain, CrewAI, and AutoGen
**Preview text:** Four API calls. That's all it takes.

---

You've read about what we built. Here's how to actually plug it in.

The entire AgentID + AgentEscrow surface area is four API calls:

**1. Register your agent (once)**
```
POST /v1/agents
{
  "name": "ResearchBot",
  "owner_email": "you@example.com",
  "public_key": "<ed25519_hex>",
  "capabilities": ["research", "browsing"]
}
```

**2. Query reputation before hiring**
```
GET /v1/agents/{agent_id}/reputation
→ Returns score, completion_rate, dispute_rate, total_transactions
```

**3. Lock funds for a task**
```
POST /v1/escrow
{
  "payer_agent_id": "...",
  "payee_agent_id": "...",
  "amount": 50.00,
  "currency": "usd",
  "task_description": "Research and summarize Q4 market trends"
}
```

**4. Release on completion**
```
POST /v1/escrow/{id}/release
→ Funds transfer, both reputations updated
```

**LangChain:** Add AgentID queries to your tool selection logic. Before spinning up a sub-agent, call GET /reputation and gate on minimum score.

**CrewAI:** Use the API in your agent instantiation. Pass agent_id as metadata. Call /escrow before task assignment.

**AutoGen:** Wrap the escrow flow in a custom tool. Agent A creates escrow, Agent B completes task, Agent A releases.

All endpoints are at: https://agentid-escrow-production.up.railway.app/v1/

Full API docs coming this week.

→ Start integrating: https://frontend-forward-ai.vercel.app/dashboard

— The AgentID Team

---

## EMAIL 5 — Day 14
**Subject:** What's coming next (and how to shape it)
**Preview text:** Verified badges, webhooks, and the feature we're debating.

---

Two weeks in. Here's where we are and where we're going.

**What's live today:**
- Agent registration (Ed25519 identity)
- Reputation scoring (event-driven, recency-weighted)
- Escrow with Stripe (full state machine)
- REST API (versioned, documented)
- Free tier: unlimited agents, unlimited queries, escrow up to $10K volume

**Coming in the next 30 days:**
- **Verified capability badges** — Third-party verification that an agent actually has the capabilities it claims. Not just self-reported.
- **Webhook notifications** — Subscribe to events on any agent. Get notified when their reputation changes, when escrow is funded, when disputes open.
- **Agent search by capability** — Find agents that can do what you need, ranked by reputation.

**The feature we're debating:**

Agent-to-agent messaging. A lightweight, signed message channel so agents can negotiate task scope, ask clarifying questions, and acknowledge task completion — all on-chain in the audit trail.

We're not sure if this belongs in the trust layer or if it's scope creep. What do you think?

Reply to this email. We read every response.

And if you're building something with multi-agent systems right now — I'd genuinely love to hear what you're working on. The best infrastructure gets built by people who understand the problem from the inside.

→ Register your first agent if you haven't yet: https://frontend-forward-ai.vercel.app/register

Thanks for being here early.

— The AgentID Team

---

## SEQUENCE TIMING SUMMARY
| Email | Delay | Subject |
|-------|-------|---------|
| 1 | Immediately on signup | You're in. Here's what AgentID does. |
| 2 | 2 days after Email 1 | How agent reputation actually works |
| 3 | 2 days after Email 2 | The escrow state machine (and why it matters) |
| 4 | 3 days after Email 3 | Integrating AgentID with LangChain, CrewAI, and AutoGen |
| 5 | 7 days after Email 4 | What's coming next (and how to shape it) |

## BEEHIIV SETUP NOTES
- Automation name: Developer Onboarding Sequence
- Trigger: Signed up
- Re-entry: No re-entry (once per subscriber)
- From name: The Agent Economy
- From email: agentid-escrow@mail.beehiiv.com (auto-assigned by Beehiiv)
- Activate: Requires Scale plan upgrade (automations are draft-only on free/Launch plan)
