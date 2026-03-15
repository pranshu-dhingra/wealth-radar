# WealthRadar — Demo Script
## Amazon Nova AI Hackathon · 3-Minute Video

> **Required hashtag:** `#AmazonNova` — display on screen during opening and closing cards.

---

## Recording Setup

| Setting | Value |
|---|---|
| Resolution | 1920 × 1080 (1080p) — required for text legibility |
| Browser zoom | 110% (Cmd/Ctrl + zoom until sidebar text is comfortable) |
| Font size | System UI ≥ 13pt; terminal 16pt Fira Code or Cascadia Code |
| Window | Maximised browser; hide OS dock/taskbar |
| Microphone | Cardioid mic, gain set so peaks at -12 dB |
| Recording tool | OBS Studio (screen capture + mic) or Loom |
| Cursor | Use a large highlighted cursor plugin (e.g. "Cursor Highlighter" OBS filter) |
| Pre-flight | Backend running on :8000, frontend on :3000, mock portal on :8080 |
| Demo mode | Have backend `daily_radar_scan` result cached — run once beforehand so it appears instantly |

### Pre-demo checklist
> **PowerShell note:** run each `cd` and command as separate lines (PowerShell does not support `&&`).

- [ ] Terminal 1 — start backend:
  ```powershell
  cd backend
  uvicorn app.main:app --reload
  ```
  Confirm 200 on `http://localhost:8000/health`
- [ ] Terminal 2 — start frontend:
  ```powershell
  cd frontend
  npm run dev
  ```
  Confirm `http://localhost:3000` loads
- [ ] Terminal 3 — start mock portal:
  ```powershell
  cd backend
  python mock_portal/serve.py
  ```
  Confirm `http://localhost:8080` serves
- [ ] Open `http://localhost:3000` in Chrome, full screen, dark mode
- [ ] Pre-type `CLT001` in a notepad so client ID is ready to paste
- [ ] Disable browser notifications, Slack/Teams, OS pop-ups
- [ ] Practice the click sequence at least twice at normal speed

---

## Segment 0:00 – 0:20 | Problem Statement + Introduction

### Screen
Splash card (dark background, logo centered):
> **WealthRadar** — AI Chief of Staff for Financial Advisors

Then cut to: WealthRadar dashboard loading on `localhost:3000`.

### Voice-over
> "The average financial advisor manages 150 clients. Every morning they face 12 open tabs,
> three compliance deadlines, and no idea which client needs them most today.
>
> WealthRadar changes that. It's a multi-agent AI system built on **Amazon Nova** that
> proactively monitors an entire book of business, detects compound financial triggers,
> and auto-prepares complete client action packages — before the advisor even opens their inbox.
>
> #AmazonNova"

### On-screen text overlay
- Logo + tagline: *"Your AI Chief of Staff"*
- Small badge: `#AmazonNova · Amazon Bedrock · Strands Agents`

---

## Segment 0:20 – 0:50 | Dashboard — Daily Radar Scan

### Actions
1. Dashboard is already visible. Point to the **Stats Bar** (top row).
2. Click **"Run Daily Scan"** button (top-right of header).
3. Watch the **Agent Activity** panel (bottom-right) stream live events.
4. After scan completes (~10–15 s), **Priority Action List** populates.
5. Briefly hover over the top 2–3 action cards to show priority scores.

### Voice-over
> "The Daily Radar Scan kicks off the Sentinel Agent, which scans all 50 clients in parallel.
> Watch the agent activity stream — these are live **Server-Sent Events** from our FastAPI backend.
>
> The result: a ranked priority list. The Sentinel scores every trigger using a compound
> priority formula — urgency, revenue impact, and a bonus for co-occurring triggers.
> Tier-A clients like the Johnsons get a 1.5× multiplier, so their flags always surface first.
>
> Notice the market alert panel on the right — S&P down 7.3% this week, CPI at 3.2%.
> These aren't just news items — they're mapped to specific clients whose portfolios are exposed."

### Technical callout
> *"The Sentinel Agent uses **Amazon Nova 2 Lite** via the Strands Agents SDK.
> Each trigger fires a scored `Trigger` object; compound co-occurrence adds 30 points per
> additional signal. Final score = `(urgency × 0.6) + (revenue × 0.2) + (compound × 0.2) × tier_multiplier`."*

---

## Segment 0:50 – 1:20 | Client Detail — Johnson Household Compound Triggers

### Actions
1. Click the **"Mark Johnson"** card (CLT001, Tier A, `$1.56M`).
2. Client detail page loads — **Overview tab** is default.
3. Point to the **Trigger signals** section — show `RMD_DUE`, `QCD_OPPORTUNITY`, `ESTATE_REVIEW_OVERDUE`.
4. Read one trigger aloud (e.g., RMD due: `$28,147.73` by March 15).
5. Click **"Portfolio"** tab — briefly show the Allocation Chart (dual donut: target vs current).
6. Click **"Planning"** tab — show the RMD card and QCD card computed from DOB.

### Voice-over
> "Mark Johnson — 77 years old, $1.56 million under management, Tier A.
> WealthRadar has detected three simultaneous triggers that compound each other:
>
> **First** — his 2026 RMD of $28,147 has not been distributed. IRS deadline is approaching.
> **Second** — he's QCD-eligible and has gifted zero dollars this year against a $111,000 limit.
> Directing the RMD to charity satisfies both obligations and eliminates the tax.
> **Third** — his trust document is *missing*. With a parent recently deceased,
> this is an estate risk that needs resolution before any inheritance is distributed.
>
> No single trigger is critical in isolation. Together, they demand immediate action.
> That's the compound intelligence WealthRadar provides."

### Technical callout
> *"Trigger detection lives in `trigger_engine.py`. It runs 12 independent detectors,
> then scores the combination. The `ESTATE_REVIEW_OVERDUE` trigger fires because
> `trust.status == 'missing'`. The `QCD_OPPORTUNITY` trigger cross-references
> `age >= 70.5 AND rmd_eligible AND qcd_amount_gifted_ytd == 0`."*

---

## Segment 1:20 – 1:50 | Live Agent Stream — Doc Intelligence on Trust PDF

### Actions
1. Stay on CLT001 client detail page.
2. Click the **"Actions"** tab.
3. Click **"Prepare Meeting Pack"** button.
4. Watch the **Agent Steps pipeline** light up:
   - 🔍 Sentinel: ✓ done (already ran)
   - 📄 Doc Agent: spinning (active)
   - 🌐 Scout: pending
   - ✍️ Composer: pending
5. Watch the event stream panel — narrate the doc agent events as they appear.

### Voice-over
> "Clicking Prepare Meeting kicks off the full **four-agent orchestration pipeline**.
>
> The Document Intelligence Agent — built on **Nova 2 Lite multimodal** — is now
> analyzing Johnson's trust document. Watch the live stream: it's extracting trustee
> designations, identifying the missing successor trustee clause, and flagging
> the pour-over will conflict.
>
> This is **extended thinking** in action — we set `thinking_level='medium'` for
> trust analysis, which gives Nova 2 Lite additional reasoning budget to work through
> complex legal document structure before surfacing its findings."

### Technical callout
> *"`doc_agent.py` uses `BedrockModel` from the Strands SDK with `thinking_level='medium'`
> for trust analysis. Documents are base64-encoded and passed as `image` blocks in the
> Bedrock Converse API — Nova 2 Lite handles both the PDF text and any embedded scans.
> The agent also indexes document embeddings into our FAISS store using
> **Nova Multimodal Embeddings** (`amazon.nova-2-multimodal-embeddings-v1:0`) for
> cross-modal semantic search."*

---

## Segment 1:50 – 2:15 | Nova Act — Scout Agent Fetching Treasury Yields

### Actions
1. Agent Steps pipeline: Doc Agent turns ✓, Scout Agent starts spinning.
2. The Scout Agent event appears in the stream: `"Navigating to treasury.gov..."`
3. **Optional — split screen**: show `localhost:8080` mock portal side-by-side
   (or show the SSE event text describing the navigation).
4. Stream shows: `"Extracted yields: 3M=4.32%, 2Y=4.18%, 10Y=4.41%, 30Y=4.60%"`
5. Briefly explain what the Scout does with this data.

### Voice-over
> "The Scout Agent uses **Nova Act** — Amazon's browser-use AI SDK —
> to navigate real websites and extract live data.
>
> Right now it's fetching the current Treasury yield curve from treasury.gov.
> Nova Act launches a headless browser, navigates to the yield curve page,
> and uses an AI `act()` call to locate and extract the most recent row of rates.
>
> These live yields are fed directly into Johnson's Roth conversion analysis —
> the 10-year rate of 4.41% affects the hurdle rate calculation for whether
> a Roth conversion makes sense this year."

### Technical callout
> *"`scout_agent.py` uses `NovaAct(nova_act_api_key=..., url='https://home.treasury.gov/...')`.
> Data extraction uses `act_get()` with a Pydantic schema (`TreasuryYields`) so the
> output is typed and validated before being passed downstream. A mock fallback is
> always available if the Nova Act API key is not configured."*

---

## Segment 2:15 – 2:40 | Composer — Meeting Pack + Outreach Email

### Actions
1. Agent Steps: Scout ✓, Composer starts spinning.
2. Stream shows Composer generating content.
3. Meeting prep result appears in the **Approval Workflow** panel.
4. Scroll through the meeting prep content:
   - Client snapshot + key metrics
   - Trigger summary with action recommendations
   - Talking points for RMD/QCD/estate conversation
5. Click **"Draft Outreach"** to show the email draft.
6. Point out the **Approve / Edit / Regenerate** buttons.

### Voice-over
> "The Composer Agent assembles the complete action package.
> It has context from all three upstream agents: confirmed triggers from Sentinel,
> document findings from Doc, and live market data from Scout.
>
> The result: a structured meeting prep with client snapshot, ordered talking points,
> and specific action items with dollar amounts already calculated.
>
> And here's the outreach email — personalized to Johnson, referencing the
> specific RMD deadline and the charitable giving strategy. The advisor can
> approve it as-is, edit inline, or ask for a regeneration.
>
> This entire package — which would take an advisor two to three hours to prepare
> manually — was assembled in under 90 seconds."

### Technical callout
> *"`composer_agent.py` calls `generate_meeting_prep()` and `generate_outreach_email()`
> as Strands `@tool` functions. The model uses `temperature=0.7` for content generation
> (creative) vs `temperature=0` for tool-calling decisions. All four agents are
> wired together as **agents-as-tools** in the Strands Agents SDK — the Orchestrator
> wraps each specialist as a `@tool` it can call in sequence."*

---

## Segment 2:40 – 2:55 | Architecture Diagram

### Screen
Switch to `architecture.svg` (open in browser tab or show as full-screen image).

### Voice-over
> "Here's the full system architecture.
>
> At the center: the **Orchestrator**, a Strands supervisor agent that routes tasks
> to four specialists as tools.
>
> **Sentinel** runs the trigger engine — 12 detectors, compound scoring, 50-client scan.
> **Doc Agent** uses Nova 2 Lite multimodal with extended thinking for PDF intelligence.
> **Scout** uses Nova Act for live web data extraction from treasury.gov and SEC EDGAR.
> **Composer** synthesizes all findings into advisor-ready deliverables.
>
> The embedding layer uses **Nova Multimodal Embeddings** and a local FAISS index
> for cross-modal semantic search across clients, documents, and financial records.
> The frontend is Next.js 14 with real-time SSE streaming from a FastAPI backend."

---

## Segment 2:55 – 3:00 | Closing

### Screen
Closing card (dark, centered):
- **WealthRadar** logo
- *"From 150 clients. To 1 clear priority."*
- `#AmazonNova`
- Tech stack row: `Amazon Nova 2 Lite · Nova Act · Nova Embeddings · Strands Agents · FAISS`

### Voice-over
> "WealthRadar — built for the Amazon Nova AI Hackathon.
> From 150 clients, to one clear priority.
> #AmazonNova."

---

## Full Script (Condensed for Teleprompter)

```
[0:00] The average advisor manages 150 clients — 12 open tabs, no clear priority.
       WealthRadar fixes that. Multi-agent AI on Amazon Nova. #AmazonNova.

[0:20] Run Daily Scan. Sentinel Agent scans 50 clients in parallel via SSE.
       Compound priority formula. Tier-A gets 1.5× multiplier. Top threats surface first.
       Market alerts — S&P -7.3%, CPI 3.2% — mapped to specific client exposures.

[0:50] Mark Johnson. $1.56M, age 77, Tier A. Three co-occurring triggers:
       RMD $28,147 overdue — QCD limit $111K untouched — trust document MISSING.
       Alone: monitor. Together: act today.

[1:20] Prepare Meeting Pack. Four-agent pipeline fires.
       Doc Agent on Nova 2 Lite — extended thinking, medium budget.
       Analyzing johnson_trust.pdf. Missing successor trustee. Pour-over will conflict.
       Findings embedded into FAISS via Nova Multimodal Embeddings.

[1:50] Scout Agent — Nova Act. Headless browser, treasury.gov.
       Live yield curve: 10Y = 4.41%. Fed held at 4.50%. Roth hurdle rate recalculated.
       Typed extraction via Pydantic schema. Mock fallback always available.

[2:15] Composer assembles the package. Temperature 0.7. All upstream context included.
       Meeting prep: snapshot, talking points, dollar amounts calculated.
       Outreach email: personalized, deadline-aware. Approve / Edit / Regenerate.
       Two-hour prep job — done in 90 seconds.

[2:40] Architecture: Orchestrator as Strands supervisor. Four agents-as-tools.
       Nova 2 Lite text + multimodal. Nova Act browser automation.
       Nova Embeddings + FAISS. FastAPI SSE + Next.js 14.

[2:55] WealthRadar. From 150 clients, to one clear priority. #AmazonNova.
```

---

## Editing Notes

- **Lower thirds** (optional): Show client ID + trigger count as a subtle overlay during client detail segment.
- **Zoom** during agent stream: crop to the event stream panel at 1:30 to make text readable.
- **Speed ramp**: If agent pipeline takes > 30 s, speed up to 2× during the waiting period, slow back to 1× when results appear.
- **Music**: Low-key ambient electronic (no vocals). Fade out at 2:40 for architecture narration.
- **Captions**: Auto-generate with DaVinci Resolve or CapCut; proof carefully for "Nova Act", "Roth", "QCD", "RMD".
- **Thumbnail**: Dashboard screenshot with priority list visible + "#AmazonNova" badge overlay.
