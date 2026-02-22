# 📄 Product Requirements Document (PRD)
## Investor-Doc-Finder
**Version:** 2.0  
**Date:** February 2026  
**IDE:** Project IDX (Antigravity) by Google  
**Stack:** Plain HTML + CSS + Vanilla JS · Firebase Auth · Firestore · Cloud Functions · Serper API · SEC EDGAR API · Firebase App Hosting  
**Version Control:** Git + GitHub

---

## 1. 🎯 Product Vision

**Investor-Doc-Finder** is a lightweight, fast web application that allows anyone — investors, analysts, students, researchers — to search for and instantly access official financial documents from any publicly listed company in the world, using plain English.

### The Core Promise
> Type **"Tesla Q3 2024 earnings"** → Get the exact document → **Open or download in one click.**

No complex navigation. No digging through investor relations pages. No registration walls. Just search and get the document.

---

## 2. 🧩 Problem Statement

Finding official financial documents today is painful:
- SEC EDGAR is powerful but hard to navigate for non-experts
- Each company has a different investor relations page layout
- Searching Google for filings often returns news articles, not the actual documents
- International company filings are scattered across different stock exchanges
- Users waste 10–30 minutes finding a single document

**Investor-Doc-Finder solves all of this in one search bar.**

---

## 3. 👤 Target Users

| User Type | Need |
|-----------|------|
| Retail Investor | Quick access to earnings reports before trading decisions |
| Financial Analyst | Batch access to multiple company filings |
| Student / Researcher | Academic research on public company financials |
| Portfolio Manager | Track filings across 20+ companies efficiently |
| Journalist | Verify financial facts from official sources |
| Startup Founder | Research competitor or investor financials |

---

## 4. ✨ Core Features (MVP v1.0)

### 4.1 🔍 Plain English Search
- Central search bar — the heart of the app
- User types naturally: *"Apple annual report 2023"*, *"Samsung Q2 2024 earnings"*, *"Reliance Industries 2024 annual report"*
- Serper API processes the query and finds matching documents from across the web
- Results show within 2–3 seconds
- Search works for **any publicly listed company in any country**

### 4.2 🏢 Company Autocomplete
- As user types, suggestions appear in a dropdown
- Pre-loaded dataset of 500+ companies including:
  - All S&P 500 companies (US)
  - FTSE 100 (UK)
  - Nifty 50 (India)
  - Major global blue chips (Samsung, Toyota, TSMC, etc.)
- Each suggestion shows: Company Name · Ticker Symbol · Country Flag · Exchange
- Fuzzy matching — "tsla" finds Tesla, "appl" finds Apple
- Keyboard navigable (arrow keys + enter)

### 4.3 🇺🇸 SEC EDGAR Integration (US Companies)
- Uses SEC **Submissions API** to fetch a company's **actual filings** with direct PDF/document links
- Flow: Ticker → CIK Lookup → Submissions API → Filter by form type & year → Direct document URLs
- Zero cost — EDGAR API is completely free
- Links point directly to the actual filing document on sec.gov
- Supports all major filing types:

| Filing | Description |
|--------|-------------|
| 10-K | Annual Report (PDF) |
| 10-Q | Quarterly Report (PDF) |
| 8-K | Material Events / Earnings Release |
| DEF 14A | Proxy Statement (shareholder vote) |
| S-1 | IPO Registration Statement |
| 20-F | Annual Report (Foreign Private Issuer) |

- Results show: Company name · Filing type · Ticker badge · Date filed · Direct document link
- For US companies, EDGAR results appear first before Serper results

### 4.4 🌍 Global Company Support (via Serper API)
- For non-US companies, Serper API searches for:
  - Official investor relations pages
  - Stock exchange filings (LSE, NSE, TSX, ASX, Euronext, TSE, etc.)
  - Annual report PDFs
  - Earnings presentation slides
- Only public companies — filters out private company results
- Prioritizes official company domains and stock exchange sites

### 4.5 📥 Document Actions
Every search result has three action buttons:

| Button | Action |
|--------|--------|
| 🔗 **Open** | Opens document in a new browser tab |
| ⬇️ **Download** | Direct one-click download of PDF/file |
| 🔖 **Save** | Saves to user's personal library (login required) |

### 4.6 🔐 User Authentication (Firebase Auth)
- **Google Sign-In** — one click, instant login
- **Email + Password** — traditional login
- **Guest Mode** — search and view documents without logging in
- Saving documents and viewing history requires login
- Logout from any page

### 4.7 🗄️ Personal Library (Firestore)
- Saved documents stored per user in Firestore
- View all saved docs on Dashboard page
- Each saved doc shows: title, company, doc type, date saved, direct link
- Delete saved docs anytime
- No storage limits for reasonable use

### 4.8 🕐 Search History (Firestore)
- Last 20 searches stored automatically per logged-in user
- Visible on Dashboard
- Click any past search to re-run it instantly
- Clear history option

### 4.9 📱 Responsive Design
- Works on desktop, tablet, and mobile
- Mobile-first CSS design
- Touch-friendly buttons and search bar
- Fast loading — no heavy frameworks

---

## 5. 🖥️ Pages & Screens

### Page 1: Home / Landing (`index.html`)
**Purpose:** First impression + search entry point

**Elements:**
- App logo + name "Investor-Doc-Finder"
- Tagline: *"Find any investor document from any public company, instantly."*
- Large central search bar with autocomplete
- Example searches (clickable chips): "Tesla Q3 2024", "Apple 10-K 2023", "Samsung annual report"
- Featured companies row (logos of popular companies)
- Stats bar: "500+ Companies · SEC EDGAR · 150+ Countries · Free"
- Login button (top right)
- Footer with links

### Page 2: Search Results (`results.html`)
**Purpose:** Display matching documents

**Elements:**
- Search bar at top (pre-filled with query, editable)
- Filter bar: All · 10-K · 10-Q · 8-K · Annual Report · Earnings · Other
- Sort: Most Recent · Most Relevant
- Results list — each card shows:
  - Document title
  - Company name + ticker + country flag
  - Document type badge (10-K, Annual Report, etc.)
  - Date (filed or published)
  - Source domain (sec.gov, company.com, etc.)
  - Open · Download · Save buttons
- Pagination (10 results per page)
- "No results" state with suggestions
- Loading skeleton while fetching

### Page 3: Dashboard (`dashboard.html`)
**Purpose:** User's personal document hub

**Elements:**
- Welcome message with user name + photo (Firebase Auth)
- Saved Documents section (grid of saved doc cards)
- Recent Searches section (list of last 20 queries)
- Quick search bar
- Empty state if no saved docs yet
- Logout button

### Page 4: Login (`login.html`)
**Purpose:** Authentication

**Elements:**
- App logo
- "Sign in to save documents and view history"
- Google Sign-In button (Firebase Auth)
- Email + Password form
- "Continue as Guest" link (goes to home)
- Note: Search works without login

### Page 5: Company Profile (`company.html`)
**Purpose:** All filings for one specific company

**Elements:**
- Company name, ticker, exchange, country flag
- Company description (1–2 lines)
- Filing type filter tabs: All · 10-K · 10-Q · 8-K · etc.
- Year filter dropdown
- Chronological list of all filings
- Each filing: type · date · period · Open · Download buttons

---

## 6. 🔧 Technical Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      FRONTEND                            │
│           Plain HTML + CSS + Vanilla JS                  │
│     (Designed with Google Stitch, coded in IDX)          │
│           Hosted on Firebase App Hosting                 │
│                                                          │
│  index.html  results.html  dashboard.html  login.html   │
│  css/style.css    js/app.js    js/search.js              │
└────────────────────────┬────────────────────────────────┘
                         │ Firebase SDK (CDN)
              ┌──────────┴──────────┐
              │                     │
    ┌─────────▼──────┐   ┌─────────▼──────────┐
    │  Firebase Auth │   │     Firestore        │
    │  Google Sign-In│   │  - savedDocs         │
    │  Email/Password│   │  - searchHistory     │
    └────────────────┘   │  - users             │
                         └────────────────────┘
                         │
              ┌──────────▼──────────┐
              │   Cloud Functions   │
              │   (Node.js)         │
              │  Hides all API keys │
              └────┬──────────┬────┘
                   │          │
        ┌──────────▼──┐  ┌───▼────────────┐
        │  Serper API  │  │  SEC EDGAR API │
        │  (Global)    │  │  (US, Free)    │
        └─────────────┘  └────────────────┘
```

---

## 7. 📁 Complete Project Folder Structure

```
investor-doc-finder/
│
├── 📄 index.html                  ← Home page
├── 📄 results.html                ← Search results
├── 📄 dashboard.html              ← User dashboard
├── 📄 login.html                  ← Auth page
├── 📄 company.html                ← Company profile page
│
├── 📁 css/
│   ├── style.css                  ← Main styles
│   ├── animations.css             ← Transitions & loaders
│   └── responsive.css             ← Mobile breakpoints
│
├── 📁 js/
│   ├── app.js                     ← App init, routing, shared logic
│   ├── auth.js                    ← Firebase Auth (login/logout/state)
│   ├── firestore.js               ← Firestore helpers (save/load/delete)
│   ├── search.js                  ← Calls Cloud Functions, handles results
│   ├── autocomplete.js            ← Dropdown suggestions logic
│   ├── companies.js               ← S&P 500 + global companies data
│   └── download.js                ← Open in tab + download logic
│
├── 📁 functions/                  ← Firebase Cloud Functions (Node.js)
│   ├── index.js                   ← Exports all functions
│   ├── searchSerper.js            ← Serper API handler (hides key)
│   ├── searchEdgar.js             ← SEC EDGAR API handler
│   └── package.json               ← Functions dependencies only
│
├── 📁 assets/
│   ├── logo.svg                   ← App logo
│   ├── favicon.ico
│   └── og-image.png               ← Social share preview image
│
├── 📄 firebase.json               ← Firebase hosting + functions config
├── 📄 firestore.rules             ← Firestore security rules
├── 📄 firestore.indexes.json      ← Firestore query indexes
├── 📄 .firebaserc                 ← Firebase project alias
├── 📄 .gitignore                  ← Ignores .env, node_modules, secrets
├── 📄 .env                        ← API keys (NEVER commit to GitHub)
├── 📄 README.md                   ← Project docs for GitHub
├── 📄 LICENSE                     ← MIT License
└── 📄 CONTRIBUTING.md             ← Contribution guide

Total files: ~25 files. Clean. Simple. Manageable.
```

---

## 8. 🗂️ Firestore Data Model

### `users` collection
```
users/{uid}
  ├── displayName    : "John Doe"
  ├── email          : "john@gmail.com"
  ├── photoURL       : "https://..."
  ├── createdAt      : timestamp
  └── searchCount    : 42
```

### `savedDocs` collection
```
savedDocs/{uid}/docs/{docId}
  ├── title          : "Tesla 10-Q Q3 2024"
  ├── company        : "Tesla"
  ├── ticker         : "TSLA"
  ├── docType        : "10-Q"
  ├── url            : "https://sec.gov/..."
  ├── source         : "sec.gov"
  ├── country        : "US"
  └── savedAt        : timestamp
```

### `searchHistory` collection
```
searchHistory/{uid}/searches/{searchId}
  ├── query          : "Tesla Q3 2024 earnings"
  ├── resultsCount   : 8
  └── searchedAt     : timestamp
```

---

## 9. 🔑 API Details

### Serper API
| Detail | Info |
|--------|------|
| Website | https://serper.dev |
| Purpose | Search Google for investor docs globally |
| Endpoint | `POST https://google.serper.dev/search` |
| Free Tier | 2,500 searches/month |
| Key Location | Cloud Functions env variable only |
| Query Example | `"Samsung 2024 annual report filetype:pdf"` |

### SEC EDGAR API (Submissions API)
| Detail | Info |
|--------|------|
| Website | https://data.sec.gov |
| Purpose | Fetch actual filing documents (PDFs) for US companies |
| Cost | Completely FREE — no key needed |
| Rate Limit | 10 requests/second |
| Ticker Map | `https://www.sec.gov/files/company_tickers.json` → maps ticker to CIK |
| Submissions | `https://data.sec.gov/submissions/CIK{number}.json` → actual filings list |
| Document URL | `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primaryDoc}` |

### Firebase (All Services)
| Detail | Info |
|--------|------|
| Auth | Firebase Auth (Google + Email) |
| Database | Cloud Firestore |
| Functions | Node.js 20, HTTP callable |
| Hosting | Firebase App Hosting |
| SDK | Loaded via CDN tags (no npm on frontend) |

---

## 10. 🛡️ Firestore Security Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Users can only read/write their own profile
    match /users/{userId} {
      allow read, write: if request.auth != null
                         && request.auth.uid == userId;
    }

    // Users can only access their own saved docs
    match /savedDocs/{userId}/docs/{docId} {
      allow read, write, delete: if request.auth != null
                                  && request.auth.uid == userId;
    }

    // Users can only access their own search history
    match /searchHistory/{userId}/searches/{searchId} {
      allow read, write, delete: if request.auth != null
                                  && request.auth.uid == userId;
    }

    // Block all other access
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

---

## 11. 🐙 GitHub Setup & Structure

### Repository: `investor-doc-finder`
**Visibility:** Public (safe — no secrets in code)

### GitHub Files
| File | Purpose |
|------|---------|
| `README.md` | App description, screenshots, setup guide, live link |
| `LICENSE` | MIT License — open source |
| `.gitignore` | Ignores `.env`, `functions/node_modules/`, `.firebase/` |
| `CONTRIBUTING.md` | How to contribute to the project |

### .gitignore (Critical)
```
# Secrets — NEVER push these
.env
.env.local
.env.production
serviceAccountKey.json
*.key

# Firebase generated
.firebase/
firebase-debug.log
firestore-debug.log

# Functions dependencies
functions/node_modules/

# OS files
.DS_Store
Thumbs.db
```

### README.md Must Include
- App name + logo
- Live demo link (Firebase Hosting URL)
- Screenshot/GIF of the app
- Tech stack badges (HTML · CSS · JS · Firebase · Serper)
- Features list
- How to set up locally
- Environment variables needed
- How to deploy

### GitHub Actions (Auto-Deploy on Push)
```yaml
# .github/workflows/deploy.yml
name: Deploy to Firebase
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: FirebaseExtended/action-hosting-deploy@v0
        with:
          repoToken: ${{ secrets.GITHUB_TOKEN }}
          firebaseServiceAccount: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}
          channelId: live
```

---

## 12. 🚀 Build Order (Step-by-Step)

### Phase 1 — Setup (Day 1)
- [ ] Open Project IDX → New Project → Blank HTML/JS
- [ ] Create GitHub repo `investor-doc-finder`
- [ ] Connect IDX project to GitHub (Git panel in IDX)
- [ ] Create Firebase project at console.firebase.google.com
- [ ] Enable Firebase Auth (Google + Email/Password)
- [ ] Create Firestore database (production mode)
- [ ] Create folder structure as defined above

### Phase 2 — Frontend UI (Days 2–4)
- [ ] Use Google Stitch → describe each page → export HTML/CSS
- [ ] Build `index.html` — hero + search bar
- [ ] Build `results.html` — results cards layout
- [ ] Build `dashboard.html` — saved docs + history
- [ ] Build `login.html` — auth UI
- [ ] Add `style.css` — consistent design system
- [ ] Add `responsive.css` — mobile support
- [ ] Add company autocomplete UI

### Phase 3 — Firebase Integration (Days 5–7)
- [ ] Add Firebase CDN scripts to all HTML files
- [ ] Write `js/auth.js` — Google Sign-In, logout, auth state
- [ ] Write `js/firestore.js` — save docs, load history
- [ ] Wire login page to Firebase Auth
- [ ] Wire dashboard to Firestore data
- [ ] Test: login → save doc → see in dashboard

### Phase 4 — Search & Documents (Days 8–11)
- [ ] Set up Firebase Cloud Functions
- [ ] Write `functions/searchEdgar.js` — SEC EDGAR search
- [ ] Write `functions/searchSerper.js` — Serper API search
- [ ] Set Serper API key: `firebase functions:config:set serper.key="YOUR_KEY"`
- [ ] Write `js/search.js` — call functions, display results
- [ ] Write `js/autocomplete.js` — company suggestions
- [ ] Write `js/download.js` — open tab + download
- [ ] Test full search flow end-to-end

### Phase 5 — Polish & Deploy (Days 12–14)
- [ ] Test on mobile (responsive check)
- [ ] Add loading states and error handling
- [ ] Write `README.md` for GitHub
- [ ] Add `.gitignore` — verify no secrets in repo
- [ ] Push all code to GitHub: `git push origin main`
- [ ] Configure `firebase.json` for App Hosting
- [ ] Run `firebase deploy`
- [ ] Test live URL
- [ ] Add live URL to GitHub README

---

## 13. 🔄 User Flow Diagram

```
User opens app (index.html)
        │
        ▼
Types query in search bar
"Tesla Q3 2024 earnings"
        │
        ├─── Autocomplete shows Tesla suggestions
        │
        ▼
Clicks Search button
        │
        ▼
Cloud Function fires
        │
        ├─── Is it a US company? ──YES──► SEC EDGAR API
        │                                      │
        └─── Global company? ────YES──► Serper API
                                               │
                                    Both results merged
                                               │
                                               ▼
                                    results.html loads
                                    Shows 10 documents
                                               │
                              ┌────────────────┼────────────────┐
                              ▼                ▼                ▼
                           Open             Download          Save
                        (new tab)        (direct PDF)    (login check)
                                                               │
                                                    ┌──────────▼──────────┐
                                                    │  Logged in?         │
                                                    │  YES → Save to      │
                                                    │        Firestore    │
                                                    │  NO  → Show login   │
                                                    │        prompt       │
                                                    └─────────────────────┘
```

---

## 14. 📊 MVP Success Metrics

| Metric | Target (Month 1) |
|--------|-----------------|
| Successful searches | > 500 |
| Documents opened/downloaded | > 200 |
| Registered users | > 50 |
| Search success rate | > 85% |
| Page load time | < 2 seconds |
| Mobile usability score | > 90/100 |

---

## 15. 🔮 Future Roadmap (Post-MVP)

### v1.1
- Gemini AI — smarter query understanding
- Document summarization (AI reads filing, gives 3-line summary)
- Email alerts for new filings from saved companies

### v1.2
- Watchlist — track specific companies
- Compare filings side-by-side (e.g., Q1 vs Q2)
- Export saved docs list to CSV

### v2.0
- Chrome Extension — find filings while browsing any website
- API for developers (let others build on top)
- Premium plan — unlimited searches, team sharing

---

## 16. 💰 Full Cost Breakdown

| Service | Free Tier Limit | Cost After Free Tier |
|---------|----------------|---------------------|
| Firebase Auth | 10,000 MAU/month | $0.0055 per MAU |
| Firestore | 1GB · 50K reads · 20K writes/day | $0.06/100K reads |
| Cloud Functions | 2M invocations/month | $0.40/million |
| Firebase App Hosting | 10GB bandwidth/month | $0.15/GB |
| Serper API | 2,500 searches/month | $50/month (30K searches) |
| SEC EDGAR API | Unlimited | Always free |
| GitHub | Unlimited public repos | Always free |
| Project IDX | Free | Free |

### 💡 Bottom Line
**Cost to build and launch MVP = $0**  
You only start paying when you have real user traction — which is the right time to pay.

---

*PRD Version 2.0 | Investor-Doc-Finder | Plain HTML + CSS + JS | Project IDX (Antigravity)*  
*Stack: HTML · CSS · Vanilla JS · Firebase Auth · Firestore · Cloud Functions · Serper API · SEC EDGAR · GitHub*