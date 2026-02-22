# Investor Doc Finder

A full-stack web app for searching, viewing, and saving investor documents — SEC filings (10-K, 10-Q, 8-K), earnings reports, investor presentations, and more — for any public company worldwide.

**Live URL:** _[Add after deployment]_

---

## How It Works

```
User types: "Apple 10-K 2024"
        ↓
Query Parser extracts: { company: Apple, ticker: AAPL, docType: 10-K, year: 2024 }
        ↓
SEC Submissions API: ticker → CIK 320193 → fetch filings → filter 10-K + 2024
        ↓
Result: Apple's actual 10-K filing with direct link to sec.gov document
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML + CSS + Vanilla JS |
| Auth | Firebase Auth (Google Sign-In + Email/Password) |
| Database | Cloud Firestore |
| Backend | Firebase Cloud Functions (Node.js 20) |
| US Filings | SEC EDGAR Submissions API (free, no key) |
| Global Search | Serper API (targeted PDF search) |
| Hosting | Firebase Hosting |

---

## Features

- 🔍 **Smart Search** — Natural language queries: "Tesla Q3 2024 earnings", "MSFT 10-K 2023"
- 📄 **Actual Documents** — Links to real filing PDFs on sec.gov, not generic search results
- 🏢 **80+ Companies** — Pre-mapped tickers for instant CIK resolution (Apple, Tesla, NVIDIA, etc.)
- 📊 **All Filing Types** — 10-K (annual), 10-Q (quarterly), 8-K, earnings, investor presentations, proxy statements
- 🌍 **Global Support** — Non-US companies searched via Serper with targeted filetype:pdf queries
- 💾 **Save Documents** — Save any result to your personal dashboard
- 📋 **Search History** — Track your last 20 searches
- 🔐 **Secure** — Firebase Auth + per-user Firestore rules

---

## Project Structure

```
Investor-doc-Finder/
├── index.html              # Home page with hero + search bar
├── results.html            # Search results grid
├── dashboard.html          # Saved docs + search history
├── login.html              # Firebase Auth UI
├── company.html            # Company filings view
├── css/
│   ├── style.css           # Dark navy + blue theme
│   └── responsive.css      # Mobile breakpoints
├── js/
│   ├── app.js              # Firebase init + shared helpers
│   ├── auth.js             # Login/logout/sign-up logic
│   ├── firestore.js        # Save/load/delete documents
│   ├── search.js           # Call Cloud Functions, render results
│   ├── autocomplete.js     # Company name suggestions
│   ├── companies.js        # Company data
│   └── download.js         # Open + download logic
├── functions/
│   ├── index.js            # Cloud Functions entry point
│   ├── parseQuery.js       # NLP query parser (80+ tickers)
│   ├── searchEdgar.js      # SEC Submissions API (ticker→CIK→filings)
│   ├── searchSerper.js     # Serper targeted search
│   └── package.json        # Node.js dependencies
├── dev-server.js           # Local development server
├── firebase.json           # Hosting + Functions config
├── firestore.rules         # Firestore security rules
└── .env                    # API keys (gitignored)
```

---

## Setup

1. **Clone & install**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Investor-doc-Finder.git
   cd Investor-doc-Finder
   cd functions && npm install && cd ..
   npm install
   ```

2. **Create `.env`** with your Serper key:
   ```
   SERPER_API_KEY="your_serper_api_key"
   ```

3. **Test locally:**
   ```bash
   node dev-server.js
   # Open http://localhost:3000
   ```

4. **Deploy to Firebase:**
   ```bash
   firebase login
   firebase use investor-doc-finder
   firebase functions:config:set serper.key="your_key"
   firebase deploy
   ```

---

## Search Architecture

| Source | When Used | How It Works |
|--------|----------|-------------|
| **SEC EDGAR** | US companies (80+ tickers mapped) | Ticker → CIK → Submissions API → actual filing docs |
| **Serper** | Global companies + presentations | Targeted `filetype:pdf site:sec.gov` queries |

---

## License

MIT
