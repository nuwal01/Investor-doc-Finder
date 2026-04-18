# Investor Doc Finder

> **Instantly locate official financial reports from public companies using natural language queries — across 54+ countries and 16 sectors.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Overview

Investor Doc Finder is a full-stack web application that enables users to quickly locate and access official financial reports from public companies through natural language queries. Simply type what you're looking for, and get direct PDF links sourced from official investor relations pages, stock exchanges, and SEC EDGAR.

### Key Features

- **Natural Language Search** — Plain English queries like "Tesla Q3 2024 earnings" or "HDFC Bank annual report 2023"
- **Global Coverage** — 54 single-country markets + 31 multilateral combinations (85 country/region combos, 60+ exchanges)
- **Multilingual Queries** — Groq Llama 3.3 70B generates native-language search queries (Arabic, Russian, Chinese, Turkish, Portuguese, and more)
- **Sector Intelligence** — 16 business sectors auto-detected for search optimization
- **3-Tier IR Crawling** — httpx (static) → Playwright (JS-rendered) → Gemini 2.0 Flash Vision (AI-guided navigation)
- **Parallel Execution** — Exchange, IR crawl, and web search run simultaneously with early exit on high-confidence match (score ≥ 0.70)
- **Confidence Scoring** — Every result is scored 0–1 across 10 factors (year match, PDF type, domain trust, doc-type keywords, language) and labelled high / medium / low
- **Bulk Search** — Up to 50 companies in a single request; 5 concurrent × 3 parallel phases = 15 simultaneous tasks
- **Search History** — Every search auto-saved to Firestore per user (last 50); browse, re-open, or delete from the History tab
- **Document Library** — Star any result card to save it permanently; manage from the Library tab
- **Firebase Authentication** — Email/password + Google OAuth; all data scoped per user account
- **SSE Streaming** — Real-time progress (0–100%) with phase-by-phase status updates streamed to the browser
- **QuickPicks** — One-click preset searches (Apple, Tesla, Microsoft, Reliance) to try the app instantly
- **Doc Type Filters** — Switch between Annual Report, Quarterly, and Presentation before searching
- **Company Autocomplete** — Suggestions with ticker symbols as you type
- **Open & Download** — Every result card has Open (new tab) and Download buttons
- **Responsive Design** — Works on desktop and mobile

## Tech Stack

### Frontend
- **React (Vite)** — Fast SPA with JSX
- **Firebase** — Authentication and user data
- **Pages**: Landing, Auth, Search
- **Components**: SearchBar, ResultCard, StatusLog, HistoryPanel, LibraryPanel, Navbar, DocTypePills, QuickPicks

### Backend — Node.js API
- **Node.js + Express + TypeScript** — RESTful endpoints for search and autocomplete
- **Helmet + express-rate-limit** — Security headers and rate limiting
- **Compromise NLP** — Natural language parsing
- **Cheerio** — HTML parsing for static IR pages

### Backend — Python AI Search Engine
- **FastAPI + asyncio** — Async search pipeline with SSE streaming
- **Groq Llama 3.3 70B** — Entity normalization, doc-type classification, multilingual query generation
- **Gemini 2.0 Flash Vision** — AI-guided IR page navigation (screenshots + iterative click instructions)
- **Playwright + BeautifulSoup4** — Headless Chromium for JS-rendered pages; httpx for static HTML
- **Firebase Admin** — Token verification and Firestore persistence (history + library)
- **OpenFIGI** — Company entity resolution (ticker, exchange MIC, ISIN, country)
- **Finnhub** — Company profiles and investor relations URL discovery
- **Serper** — Parallel Google search execution (all queries fired concurrently)
- **annualreports.com** — High-reliability first-pass source for listed company reports

### External Integrations
- **SEC EDGAR** — US company filings (10-K, 10-Q, 8-K)
- **60+ Global Exchanges** — BSE/NSE (India), LSE (UK), MOEX (Russia), DFM/ADX (UAE), B3 (Brazil), KAP (Turkey), JPX (Japan), Euronext, and more

## Installation

### Prerequisites
- Node.js 18+
- Python 3.10+
- npm

### Quick Start

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/investor-doc-finder.git
cd investor-doc-finder
```

2. **Install Node.js backend dependencies**

```bash
cd backend
npm install
```

3. **Install Python backend dependencies**

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

4. **Install frontend dependencies**

```bash
cd frontend
npm install
```

5. **Configure environment variables**

Create a `.env` file in the `backend` directory:

```env
PORT=3001
NODE_ENV=development

# Search & AI
SERPER_API_KEY=your_serper_api_key
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
FINNHUB_API_KEY=your_finnhub_api_key

# SEC EDGAR (required — identify yourself to avoid rate limits)
SEC_USER_AGENT=YourName your@email.com

# Firebase Admin (Python backend auth + Firestore)
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json
```

Create a `.env` file in the `frontend` directory:

```env
VITE_BACKEND_URL=http://localhost:8000

# Firebase Web SDK (get these from Firebase Console → Project Settings)
VITE_FIREBASE_API_KEY=your_firebase_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id
```

6. **Start the servers**

**Node.js backend (port 3001):**
```bash
cd backend
npm run dev
```

**Python AI backend (port 8000):**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Frontend (port 5173):**
```bash
cd frontend
npm run dev
```

7. **Open the app**

Navigate to [http://localhost:5173](http://localhost:5173)

## API Documentation

See [docs/API.md](docs/API.md) for full documentation.

### Quick Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/search` | POST | Search for a document (Node.js) |
| `/api/autocomplete` | GET | Company name suggestions |
| `/search` | POST | AI-powered search with SSE stream (Python) |
| `/bulk-search` | POST | Search up to 50 companies with SSE stream (Python) |
| `/user/history` | GET | List all past searches for the authenticated user |
| `/user/history` | DELETE | Clear all search history |
| `/user/history/{id}` | DELETE | Delete a single history entry |
| `/user/library` | GET | List all saved documents |
| `/user/library` | POST | Save a document to the library |
| `/user/library/{id}` | DELETE | Remove a document from the library |
| `/user/profile` | GET | Authenticated user profile info |

### Example Search Request

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Apple 10-K 2024"}'
```

## Project Structure

```
investor-doc-finder/
├── backend/
│   ├── src/                        # Node.js Express backend
│   │   ├── data/                   # S&P 500 company data
│   │   ├── routes/                 # search, autocomplete routes
│   │   ├── services/               # Business logic
│   │   ├── types/                  # TypeScript types
│   │   └── index.ts                # Express app entry
│   ├── phases/                     # Python AI search phases
│   │   ├── entity_resolver.py      # OpenFIGI + country routing (54 countries)
│   │   ├── exchange_direct.py      # Direct exchange search
│   │   ├── ir_crawler.py           # IR website crawler
│   │   └── web_search.py           # Serper + Groq multilingual search
│   ├── utils/                      # Python utilities
│   │   ├── query_parser.py         # NLP + sector detection
│   │   ├── pdf_validator.py        # PDF URL validation
│   │   └── sse_manager.py          # SSE event streaming
│   ├── agent.py                    # Parallel phase orchestrator
│   ├── main.py                     # FastAPI entry point
│   ├── auth_middleware.py          # Firebase token verification
│   ├── requirements.txt            # Python dependencies
│   ├── package.json                # Node.js dependencies
│   └── tsconfig.json
│
├── frontend/
│   ├── src/
│   │   ├── pages/                  # Landing, Auth, Search
│   │   ├── components/             # UI components
│   │   ├── context/                # React context (auth, search state)
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── utils/                  # API client, helpers
│   │   ├── firebase-config.js      # Firebase initialization
│   │   └── main.jsx                # App entry point
│   ├── public/
│   ├── package.json
│   └── vite.config.js
│
├── docs/
│   └── API.md                      # Full API documentation
├── prd.md                          # Product Requirements Document
├── tech stack.md                   # Tech stack decisions
└── README.md
```

## Search Pipeline

```
User Query → Query Parser
    Extracts: company_name, doc_type, year, sector (16 sectors)
    LLM fallback: Groq classifies doc type if regex is uncertain
    ↓
Phase 1: Entity Resolution  (always sequential — required first)
    OpenFIGI  → ticker, exchange MIC, ISIN, country code
    Finnhub   → company profile, investor relations URL
    Groq LLM  → name normalization fallback
    Serper    → IR URL discovery fallback
    ↓
Phases 2–4: PARALLEL EXECUTION (asyncio.create_task)
    ├─ Phase 2: Exchange Direct
    │     SEC EDGAR, BSE, NSE, KAP, JPX, Euronext, LSE, DFM, ADX,
    │     SGX, Bursa, SET, JSE, NGX, Tadawul, and more (20+ exchanges)
    │
    ├─ Phase 3: IR Website Crawl  (3 tiers, tried in sequence)
    │     Tier 1 — httpx (static HTML, timeout 25s)
    │     Tier 2 — Playwright headless Chromium (JS pages, 35s)
    │     Tier 3 — Gemini 2.0 Flash Vision (screenshot → AI navigation, 45s)
    │
    └─ Phase 4: Web Search
          annualreports.com  (first-pass, most reliable)
          Standard queries   (6 English templates)
          Groq multilingual  (4 native-language queries via Llama 3.3 70B)
          Region queries     (exchange-specific: site:bseindia.com, etc.)
          All Serper searches run in parallel
    ↓
Early Exit:  any phase scores ≥ 0.70 → cancel others, return immediately
Otherwise  → return best result (minimum threshold 0.50)
    ↓
PDF Validation (10-factor scoring):
    year match, PDF content-type, trusted exchange domain,
    doc-type keywords, language (English +0.15), company name in URL,
    content size, quarterly rejection, press-release penalty
    ↓
Save result to Firestore → stream final result + "done" via SSE
```

**Performance:**
- Average: **4–8 seconds** per search (parallel phases)
- High-confidence early exit: **2–3 seconds**
- Bulk (50 companies): **~5–8 minutes** vs ~15 min sequential

## Global Coverage

**54 single-country markets** including USA (SEC EDGAR), UK (LSE), India (BSE+NSE), UAE (DFM+ADX), Russia (MOEX), Brazil (B3), China (SSE+SZSE), Saudi Arabia (Tadawul), and 46 more.

**31 multilateral combinations** for dual-listed companies (e.g., UK/Russia → LSE + MOEX).

**16 sectors** auto-detected: Financial Services, Energy, Materials, Technology/Media, Healthcare, Real Estate, and more.

**10 languages** for search queries: English, Arabic, Russian, Turkish, Portuguese, French, German, Spanish, Chinese, Hindi.

## Authentication

Sign in with **email + password** or **Google OAuth** — no setup required for Google sign-in.

| Method | Details |
|--------|---------|
| Email / Password | Register with first name, last name, email, password. Password strength indicator shown during sign-up. |
| Google OAuth | One-click sign-in via Firebase Google provider. |

After sign-in, the session is persisted in `sessionStorage` so a page refresh keeps you logged in. All data (history, library) is scoped to your Firebase UID — other users cannot see your data.

**Protected routes**: The Search page requires authentication. Unauthenticated visits redirect to `/auth`.

---

## Search History

Every search run by an authenticated user is automatically saved to Firestore and accessible from the **History** tab in the app. The list shows the **last 50 searches**, newest first.

**What is stored per entry:**
- Company name, document type, and year
- Direct URL to the found PDF
- Source (exchange name, IR website, or web search)
- Confidence level (high / medium / low) and numeric score (0–1)
- Country and sector tags
- Timestamp (`fetched_at`)

**What you can do:**
- Browse all past searches in a card list with full metadata
- Click **Open Document** to re-open any previously found PDF
- Delete individual entries or **Clear All History** in one click
- History is private — scoped to the logged-in Firebase user

**Backend endpoints:**
```
GET    /user/history              → list last 50 entries (newest first)
DELETE /user/history              → clear all entries
DELETE /user/history/{searchId}   → remove a single entry
```

---

## Document Library

The Library is a curated collection of documents you want to keep. Unlike history (automatic), the library is **opt-in** — you save a result by clicking the star button on any result card.

**How to save:**
1. Run a search and get a result card
2. Click **⭐ Save** on the result card
3. The document is saved to your Firestore library immediately

**What is stored:**
- All the same fields as history (URL, company, type, year, source, confidence, score, country, sector)
- A `saved_at` timestamp (separate from when it was originally searched)

**What you can do:**
- View all saved documents from the **Library** tab
- Open any document directly from the library
- Remove individual documents with the trash button

**Backend endpoints:**
```
GET    /user/library              → list all saved documents
POST   /user/library              → save a document (called by the Save button)
DELETE /user/library/{docId}      → remove a saved document
```

---

## Bulk Search

Bulk search lets you find documents for **up to 50 companies** in a single API call. Results are streamed back in real-time as each company completes.

**How it works:**
- Submit a list of queries (one per company)
- The backend runs up to 5 companies concurrently (semaphore-limited)
- Each company runs its own 3-phase parallel search (exchange → IR crawl → web search)
- Total concurrency: **5 companies × 3 phases = up to 15 simultaneous tasks**
- Results stream back via SSE as each company finishes — no waiting for all 50 to complete

**Performance:**
- 50 companies sequential: ~15 minutes
- 50 companies with bulk search: **~5–8 minutes** (2–3× speedup)

**Request format:**
```bash
curl -X POST http://localhost:8000/bulk-search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <firebase_token>" \
  -d '{
    "companies": [
      {"query": "Apple annual report 2024"},
      {"query": "HDFC Bank annual report 2023"},
      {"query": "Gazprom annual report 2023"}
    ]
  }'
```

**SSE events streamed per company:**
```
{"type": "company_start",  "query": "Apple..."}
{"type": "company_result", "query": "Apple...", "url": "...", "score": 0.91, "source": "SEC EDGAR"}
{"type": "company_error",  "query": "...", "error": "Not found"}
{"type": "bulk_complete",  "total": 3, "found": 2, "failed": 1}
```

---

## Supported Document Types

| Type | Example Keywords | SEC Form |
|------|-----------------|----------|
| Annual Report | `annual`, `10-K`, `yearly`, `AR` | 10-K |
| Quarterly Report | `quarterly`, `Q1`–`Q4`, `10-Q`, `earnings` | 10-Q |
| Investor Presentation | `investor presentation`, `deck`, `slides` | — |

> The query parser uses keyword matching first, then falls back to Groq LLM classification if no keyword is matched. If no year is found in the query, it defaults to the previous calendar year.

## Confidence Scoring

Every result is scored **0.0 – 1.0** by `pdf_validator.py` across 10 factors before being returned:

| Factor | Effect |
|--------|--------|
| `application/pdf` content-type | +0.40 |
| Trusted exchange domain (bseindia.com, kap.org.tr, etc.) | +0.30 floor |
| Exact year match in URL | +0.30 |
| Fiscal year variant in URL (FY2024, 2023-24) | +0.30 |
| Doc-type keyword in URL (annual, ar20, 10-k) | +0.30 |
| URL ends in `.pdf` | +0.20 |
| Content size 100 KB – 50 MB | +0.20 |
| Company name words in URL | +0.20 bonus |
| English URL signal (`_en_`, `-en-`, `english`) | +0.15 |
| Non-English URL signal | -0.10 |
| Prior year in URL | -0.20 |
| URL contains quarterly/interim/governance keywords (annual search only) | hard reject |
| URL is a credit rating agency (CRISIL, ICRA, CARE…) | score 0.0 |

Scores map to confidence labels: **high** (≥ 0.70), **medium** (0.50–0.69), **low** (< 0.50). Results below 0.50 are not returned.

---

## Deployment

### Frontend (Vercel)

1. Push to GitHub
2. Import in [Vercel](https://vercel.com)
3. Set environment variable: `VITE_API_URL` = your backend URL

### Node.js Backend (Railway / Render)

1. Connect GitHub repo, set root to `backend`
2. Build command: `npm install && npm run build`
3. Start command: `npm start`

### Python Backend (Railway / Render)

1. Set root to `backend`
2. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Set all API key environment variables

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `SERPER_API_KEY` | Yes | Google search via Serper API |
| `GROQ_API_KEY` | Yes | Groq Llama 3.3 70B — entity normalization, doc-type classification, multilingual queries |
| `GEMINI_API_KEY` | Yes | Gemini 2.0 Flash Vision — AI-guided IR page navigation |
| `FINNHUB_API_KEY` | Yes | Company profiles and investor relations URL lookup |
| `SEC_USER_AGENT` | Yes | Required by SEC EDGAR (format: `Name email@domain.com`) |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Yes | Path to Firebase Admin SDK service account JSON |
| `PORT` | No | Node.js server port (default 3001) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins for Node.js backend |

### Frontend (`frontend/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_BACKEND_URL` | Python FastAPI backend URL (default `http://localhost:8000`) |
| `VITE_FIREBASE_API_KEY` | Firebase Web SDK API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | Firebase storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging sender ID |
| `VITE_FIREBASE_APP_ID` | Firebase app ID |

> Get the Firebase Web SDK values from **Firebase Console → Project Settings → Your apps → Web app**.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [SEC EDGAR](https://www.sec.gov/edgar) for public access to US filings
- [OpenFIGI](https://www.openfigi.com) for global company/exchange mapping
- [Groq](https://groq.com) for fast Llama 3.3 70B inference
- [Google Gemini](https://deepmind.google/technologies/gemini/) for Vision-based IR page navigation
- [Serper](https://serper.dev) for Google Search API
- [Finnhub](https://finnhub.io) for investor relations data
- [annualreports.com](https://www.annualreports.com) for reliable annual report hosting

---

**Built for investors, analysts, and researchers worldwide.**
