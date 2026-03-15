# WealthRadar — AI Chief of Staff for Financial Advisors

## Project Overview
WealthRadar is a multi-agent AI system for the Amazon Nova AI Hackathon (deadline: March 16, 2026).
It proactively monitors a financial advisor's book of business, detects compound triggers across
portfolios, life events, and market conditions, and auto-prepares complete client action packages.

## Tech Stack
- **Backend**: Python 3.12, FastAPI, uvicorn
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Recharts
- **AI/ML**: Amazon Bedrock (Nova 2 Lite, Nova Multimodal Embeddings), Nova Act SDK, Strands Agents SDK
- **Vector Store**: FAISS (local, no external DB needed)
- **Orchestration**: Strands Agents SDK (agents-as-tools pattern + Graph orchestration)

## AWS Model IDs
- Nova 2 Lite: `us.amazon.nova-2-lite-v1:0` (cross-region) or `amazon.nova-2-lite-v1:0`
- Nova Multimodal Embeddings: `amazon.nova-2-multimodal-embeddings-v1:0`
- Nova Act: Separate SDK (`pip install nova-act`), uses its own API key via NOVA_ACT_API_KEY env var

## Project Structure
```
wealth-radar/
├── CLAUDE.md
├── .env                               # Credentials (NEVER commit)
├── .gitignore
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app
│   │   ├── config.py                  # Env config with pydantic-settings
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── clients.py             # Client CRUD endpoints
│   │   │   ├── agents.py              # Agent trigger endpoints (SSE)
│   │   │   ├── portfolio.py           # Portfolio analysis endpoints
│   │   │   ├── search.py              # Embedding search endpoints
│   │   │   └── websocket.py           # Real-time agent stream
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py        # Supervisor agent (Strands)
│   │   │   ├── sentinel_agent.py      # Trigger detection
│   │   │   ├── doc_agent.py           # Document intelligence (Nova 2 Lite multimodal)
│   │   │   ├── scout_agent.py         # Browser automation (Nova Act)
│   │   │   └── composer_agent.py      # Action package generation
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── rmd_calculator.py      # IRS Uniform Lifetime Table
│   │   │   ├── drift_calculator.py    # Portfolio drift (5% threshold)
│   │   │   ├── tlh_scanner.py         # Tax-loss harvesting (wash sale rules)
│   │   │   ├── roth_analyzer.py       # Roth conversion optimizer
│   │   │   ├── qcd_calculator.py      # Qualified Charitable Distribution
│   │   │   └── trigger_engine.py      # Compound trigger detection
│   │   ├── embeddings/
│   │   │   ├── __init__.py
│   │   │   ├── indexer.py             # Nova Embeddings indexing
│   │   │   └── search.py             # FAISS cross-modal search
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── bedrock.py             # Bedrock client singleton
│   │   │   └── nova_act.py            # Nova Act wrapper
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── client.py              # Pydantic schemas
│   │   │   ├── portfolio.py
│   │   │   ├── action.py
│   │   │   └── trigger.py
│   │   └── data/
│   │       ├── clients.json           # 50 synthetic client profiles
│   │       ├── holdings.json          # Portfolio holdings per account
│   │       ├── transactions.json      # Recent transactions
│   │       ├── market_events.json     # Market triggers
│   │       └── documents/             # Sample PDFs (trust docs, statements)
│   └── tests/
│       ├── test_tools.py
│       ├── test_agents.py
│       └── test_api.py
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx               # Dashboard home
│   │   │   ├── globals.css
│   │   │   ├── clients/
│   │   │   │   ├── page.tsx
│   │   │   │   └── [id]/page.tsx
│   │   │   └── meeting-prep/[id]/page.tsx
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn components
│   │   │   ├── dashboard/
│   │   │   │   ├── action-card.tsx
│   │   │   │   ├── priority-list.tsx
│   │   │   │   ├── radar-visualization.tsx
│   │   │   │   └── stats-bar.tsx
│   │   │   ├── portfolio/
│   │   │   │   ├── allocation-chart.tsx
│   │   │   │   ├── drift-heatmap.tsx
│   │   │   │   └── holdings-table.tsx
│   │   │   ├── agents/
│   │   │   │   ├── agent-stream.tsx
│   │   │   │   └── approval-modal.tsx
│   │   │   └── layout/
│   │   │       ├── sidebar.tsx
│   │   │       ├── header.tsx
│   │   │       └── nav.tsx
│   │   ├── hooks/
│   │   │   ├── use-agent-stream.ts
│   │   │   ├── use-clients.ts
│   │   │   └── use-portfolio.ts
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── types.ts
│   │   │   └── utils.ts
│   │   └── data/
│   │       └── mock-data.ts
│   └── public/
│       └── logo.svg
└── scripts/
    ├── generate_synthetic_data.py
    ├── index_documents.py
    └── test_bedrock.py
```

## Coding Conventions
- Python: Use type hints everywhere. Pydantic v2 for all models. Async FastAPI endpoints.
- TypeScript: Strict mode. Use interfaces, not types, for object shapes.
- All financial calculations must include the formula/rule source as a code comment.
- Every Strands @tool function needs a complete docstring (Strands uses it for the LLM).
- Error handling: Never let an agent crash silently. Log all Bedrock API calls.
- Use python-dotenv to load .env. Never hardcode credentials.

## Domain Rules (MUST be coded correctly)
- RMD age: 73 (born 1951-1959), 75 (born 1960+). Use IRS Uniform Lifetime Table III.
- Portfolio drift threshold: 5% absolute for major asset classes.
- Wash sale window: 30 days before AND after sale (61-day total window).
- QCD eligibility: age 70½+, limit $105,000 (2024) / $108,000 (2025) / $111,000 (2026).
- Tax-loss harvesting: Only in taxable accounts. Never in IRAs.
- Roth conversion: Pro-rata rule applies across ALL Traditional IRA balances.
- Client tiers: A ($1M+ AUM), B ($500K-$1M), C ($200K-$500K), D (<$200K).
- Meeting frequency: A=4x/year, B=2-3x, C=1-2x, D=1x.

## Trigger Priority Scoring
- Each trigger has base_urgency (0-100) and revenue_impact (0-100)
- Priority = (base_urgency × 0.6) + (revenue_impact × 0.2) + (compound_bonus × 0.2)
- compound_bonus = 30 per additional co-occurring trigger
- Client tier multiplier: A=1.5, B=1.2, C=1.0, D=0.8

## Individual Triggers
1. RMD_DUE — RMD-eligible, not yet distributed this year
2. RMD_APPROACHING — Turns RMD age within 12 months
3. PORTFOLIO_DRIFT — Any asset class >5% from target
4. TLH_OPPORTUNITY — Tax-loss harvesting >$1,000 in taxable accounts
5. ROTH_WINDOW — In gap years: retired + pre-SS + pre-RMD
6. QCD_OPPORTUNITY — Age 70½+, takes RMD, gives to charity
7. ESTATE_REVIEW_OVERDUE — Documents >3 years old or missing
8. MEETING_OVERDUE — Past meeting frequency for their tier
9. LIFE_EVENT_RECENT — Major event in last 90 days with unresolved items
10. BENEFICIARY_REVIEW — Not reviewed in 2+ years
11. MARKET_EVENT — Market event impacts client's positions
12. APPROACHING_MILESTONE — Approaching key age (59½, 62, 65, 70½, 73, 75)

## API Patterns
- Use SSE (Server-Sent Events) for agent streaming, not polling.
- WebSocket at /ws/agent-stream for bidirectional real-time updates.
- All agent endpoints return StreamingResponse with event-stream content type.
- Run Strands agents in asyncio thread pool (they're synchronous).
- Format: `data: {"type": "status"|"tool_call"|"result"|"done", "content": "...", "agent": "..."}\n\n`

## Bedrock API Usage
- Use Converse API (not InvokeModel) for Nova 2 Lite text/multimodal
- Use InvokeModel for Nova Multimodal Embeddings
- Cross-region model ID: `us.amazon.nova-2-lite-v1:0`
- Embeddings model ID: `amazon.nova-2-multimodal-embeddings-v1:0`
- Set temperature=0 for tool calling, 0.3 for analysis, 0.7 for content generation
- Extended thinking: use "medium" for financial analysis, "low" for simple tasks

## Strands Agent Patterns
- Use @tool decorator from strands for all tool functions
- Tool functions accept and return strings (JSON serialized)
- Tool docstrings are used by the LLM — make them detailed
- Agents-as-tools: wrap each specialist agent in a @tool for the orchestrator
- BedrockModel(model_id="us.amazon.nova-2-lite-v1:0", region_name="us-east-1")

## Nova Act Usage
- Install: pip install nova-act
- Set NOVA_ACT_API_KEY environment variable
- Use NovaAct context manager for browser sessions
- act() for actions, act_get() with Pydantic schema for data extraction
- Never pass passwords through act() — use Playwright directly
- Always implement fallback (mock data) in case Nova Act is unavailable
- For demo: use public sites (treasury.gov, SEC EDGAR) + mock portal

## What NOT to Build
- No real authentication (mock advisor login is fine)
- No real database (JSON files are sufficient for 50 clients)
- No real financial API integrations (synthetic data only)
- No production deployment (localhost demo is expected)
- No real email sending (generate drafts only, show in UI)

## Frontend Design
- Dark theme: slate-900 background, teal (#00D4B4) accent
- Color coding: green=healthy, amber=monitor, red=action-required
- Bloomberg terminal aesthetic meets modern SaaS
- shadcn/ui for components, Recharts for charts, TanStack Table for data grids
- SSE streaming for real-time agent activity display
- Skeleton loaders for all async data
- Mock data fallback if backend is unavailable
