# WealthRadar

**AI Chief of Staff for Financial Advisors** — Amazon Nova AI Hackathon submission (deadline: March 16, 2026).

WealthRadar proactively monitors a financial advisor's entire book of business, detects compound
triggers across portfolios, life events, and market conditions, and auto-prepares complete client
action packages — so the advisor walks into every meeting already prepared.

---

## Features

- **Sentinel Agent** — scans all 50 client profiles every run, firing 12 trigger types
- **Compound trigger scoring** — priority = urgency × 0.6 + revenue × 0.2 + compound_bonus × 0.2
- **Doc Agent** — multimodal PDF analysis via Amazon Nova 2 Lite (trust docs, statements)
- **Scout Agent** — browser automation via Nova Act (treasury.gov, SEC EDGAR)
- **Composer Agent** — generates meeting agendas, email drafts, and action packages
- **Real-time streaming** — SSE + WebSocket so the UI shows agent thoughts as they happen

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, uvicorn |
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| AI / LLM | Amazon Bedrock — Nova 2 Lite (`us.amazon.nova-2-lite-v1:0`) |
| Embeddings | Amazon Nova Multimodal Embeddings + FAISS |
| Agent SDK | Strands Agents SDK (agents-as-tools pattern) |
| Browser AI | Nova Act SDK |

---

## Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- AWS account with Bedrock access (Nova 2 Lite + Nova Multimodal Embeddings enabled)
- Nova Act API key

### 1. Clone & configure

```bash
git clone <repo-url>
cd wealth-radar
cp .env.example .env
# Edit .env — fill in AWS credentials and NOVA_ACT_API_KEY
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Verify Bedrock connectivity:

```bash
cd ..
python scripts/test_bedrock.py
```

Start the API server:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### 4. Generate synthetic data (first run)

```bash
python scripts/generate_synthetic_data.py
python scripts/index_documents.py
```

---

## Project Structure

```
wealth-radar/
├── backend/
│   ├── app/
│   │   ├── agents/       # Strands agents (orchestrator, sentinel, doc, scout, composer)
│   │   ├── api/          # FastAPI routers (clients, agents, portfolio, search, websocket)
│   │   ├── embeddings/   # FAISS indexer + search
│   │   ├── models/       # Pydantic v2 schemas
│   │   ├── services/     # Bedrock client, Nova Act wrapper
│   │   ├── tools/        # Financial calculation tools (RMD, TLH, Roth, QCD, drift)
│   │   └── data/         # JSON data files + document PDFs
│   └── tests/
├── frontend/
│   └── src/
│       ├── app/          # Next.js App Router pages
│       ├── components/   # UI components (dashboard, portfolio, agents, layout)
│       ├── hooks/        # React hooks for data fetching
│       └── lib/          # API client, types, utils
└── scripts/              # Data generation + index building + Bedrock smoke test
```

---

## Domain Rules Implemented

- **RMD age**: 73 (born 1951–1959) / 75 (born 1960+) per IRS Pub 590-B
- **Portfolio drift threshold**: 5% absolute per asset class
- **Wash sale window**: 61-day total (30 days before + day of + 30 days after)
- **QCD limit**: $111,000 (2026), eligibility at age 70½
- **Client tiers**: A ($1M+), B ($500K–$1M), C ($200K–$500K), D (<$200K)
