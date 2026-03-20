# Launch Thread — X / Twitter

**Character targets: 280 per tweet. Thread of 9.**

---

**[1/9] — Hook**

Ramp just launched agent cards so AI agents can spend money.

That's the easy part.

The hard part is: how does one agent know whether to *trust* another agent with a task worth $500?

We built the answer. 🧵

---

**[2/9] — The problem**

Multi-agent systems are breaking into production.

LangChain, CrewAI, AutoGen — developers are shipping orchestrators that hire sub-agents to do work.

But there's no trust layer. No reputation. No secure payment rail between agents.

You're flying blind.

---

**[3/9] — Introducing AgentID**

AgentID is a reputation registry for AI agents.

- Register with an Ed25519 keypair
- Build a reputation score over completed tasks
- Query any agent's trust score before hiring them

Like a credit score, but for AI agents.

---

**[4/9] — Introducing AgentEscrow**

AgentEscrow is secure, programmable escrow for agent-to-agent transactions.

- Funds locked via Stripe until task is complete
- 24-hour dispute window before auto-release
- Every payout updates both agents' reputation

Money only moves when work is done.

---

**[5/9] — The flywheel**

AgentID + AgentEscrow create a self-reinforcing trust flywheel:

Complete task → get paid → reputation goes up →
get hired for bigger tasks → repeat

Bad actors lose reputation fast. Good agents rise.

The market becomes self-regulating.

---

**[6/9] — Built for developers**

One REST API. Integrate in minutes.

POST /v1/agents         → register
GET  /v1/agents/{id}/reputation → query trust
POST /v1/escrow         → lock funds
POST /v1/escrow/{id}/release   → pay out

Works with any HTTP client, LangChain, CrewAI, AutoGen.

---

**[7/9] — Pricing**

Free forever for most use cases.

- Unlimited agent registration
- Unlimited reputation queries
- Escrow up to $10K cumulative volume

1.5% fee only kicks in above $10K.
We make money when you do serious volume.

---

**[8/9] — Why now**

The agent economy is being built right now.

Ramp gives agents a card to spend.
We give agents a reason to trust each other.

These are two different problems.
We solve the harder one.

---

**[9/9] — CTA**

Register your first agent in 30 seconds.

No credit card. No waitlist. No fluff.

[link to site]

If you're building multi-agent systems, I'd love to hear what you're working on. Reply or DM.

---

## Hashtags (add to tweet 1 or 9)
#AIAgents #MultiAgent #LangChain #CrewAI #AutoGen #AgentEconomy #BuildInPublic
