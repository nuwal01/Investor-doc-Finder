# 🏗️ Complete Tech Stack — Investor-Doc-Finder
**Platform:** Project IDX (Antigravity) · Google Tools · Plain HTML/CSS/JS  
**Version:** 1.0 | Updated: 2026

---

## 🧠 The Golden Rule of This Stack
> No npm. No build tools. No frameworks. Just files.  
> Everything loads via CDN. Works in any browser. Deploys in one command.

---

## 📦 Full Tech Stack At a Glance

```
investor-doc-finder/
│
├── 🎨 FRONTEND          → Plain HTML + CSS + Vanilla JS
├── 🔐 AUTH              → Firebase Auth (Google Sign-In + Email)
├── 🗄️  DATABASE          → Firestore (NoSQL, real-time)
├── ⚙️  BACKEND           → Firebase Cloud Functions (Node.js)
├── 🔍 DOC SEARCH        → Serper API (global public companies)
├── 🇺🇸 US FILINGS        → SEC EDGAR API (free, no key)
├── 🚀 HOSTING           → Firebase App Hosting
├── 🤖 AI (optional)     → Gemini API (query understanding)
├── 🐙 VERSION CONTROL   → Git + GitHub
└── 🛠️  IDE               → Project IDX (Antigravity) by Google
```

---

## 1. 🎨 Frontend — Plain HTML + CSS + Vanilla JS

### Why Plain HTML/CSS/JS?
- Zero dependencies — no npm, no node_modules, no build step
- Tiny app size (just files)
- Works directly in Project IDX browser preview
- Easy to understand, modify, and maintain
- Uploads to GitHub as clean readable files
- Firebase SDK loads via CDN — no installation needed

### What You Write
| File | Purpose |
|------|---------|
| `index.html` | Home page — search bar, hero, autocomplete |
| `results.html` | Search results page |
| `dashboard.html` | User saved docs + search history |
| `login.html` | Firebase Auth UI |
| `css/style.css` | All styling |
| `css/animations.css` | Transitions, loaders |
| `js/app.js` | Main app logic |
| `js/auth.js` | Firebase Auth logic |
| `js/firestore.js` | Firestore read/write helpers |
| `js/search.js` | Serper API + EDGAR search logic |
| `js/autocomplete.js` | Company autocomplete logic |
| `js/companies.js` | S&P 500 + global companies data |
| `js/download.js` | Document open/download logic |

### CDN Libraries (No Install Needed)
```html
<!-- Firebase SDK -->
<script src="https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.7.0/firebase-auth-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.7.0/firebase-firestore-compat.js"></script>

<!-- Google Fonts (for nice typography) -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">

<!-- Optional: Icons -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
```

---

## 2. 🔐 Authentication — Firebase Auth

| Detail | Value |
|--------|-------|
| **Provider** | Firebase Authentication |
| **Login Methods** | Google Sign-In, Email + Password |
| **Guest Mode** | Search works without login |
| **Save Docs** | Requires login (Firestore) |
| **SDK** | Loaded via CDN (no install) |
| **Setup** | Firebase Console → Authentication → Enable providers |
| **Cost** | Free up to 10,000 MAU/month |

### How It Works in Vanilla JS
```javascript
// Google Sign-In — just one function
const provider = new firebase.auth.GoogleAuthProvider();
firebase.auth().signInWithPopup(provider);

// Listen for auth state
firebase.auth().onAuthStateChanged((user) => {
  if (user) { showDashboard(); }
  else { showLoginButton(); }
});
```

---

## 3. 🗄️ Database — Cloud Firestore

| Detail | Value |
|--------|-------|
| **Type** | NoSQL document database |
| **Real-time** | Yes — live updates |
| **Purpose** | Store user data, search history, saved docs |
| **SDK** | Loaded via CDN |
| **Free Tier** | 1GB storage, 50K reads/day, 20K writes/day |
| **Cost** | Free for MVP scale |

### Data Structure
```
Firestore Database
│
├── users/
│   └── {uid}/
│       ├── displayName: "John Doe"
│       ├── email: "john@gmail.com"
│       └── createdAt: timestamp
│
├── savedDocs/
│   └── {uid}/
│       └── docs/
│           └── {docId}/
│               ├── title: "Tesla 10-Q Q3 2024"
│               ├── company: "Tesla"
│               ├── type: "10-Q"
│               ├── url: "https://sec.gov/..."
│               └── savedAt: timestamp
│
└── searchHistory/
    └── {uid}/
        └── searches/
            └── {searchId}/
                ├── query: "Tesla Q3 2024 earnings"
                └── timestamp: timestamp
```

---

## 4. ⚙️ Backend — Firebase Cloud Functions

| Detail | Value |
|--------|-------|
| **Runtime** | Node.js 20 |
| **Type** | Serverless (only runs when called) |
| **Purpose** | Hide API keys, call Serper API, call EDGAR |
| **Free Tier** | 2 million invocations/month free |
| **Language** | JavaScript (Node.js) |

### Why Cloud Functions?
Your **Serper API key must NEVER be in frontend code** — anyone could steal it.  
Cloud Functions keep the key secret on the server side.

### Functions You'll Write
```
functions/
├── index.js              ← Exports all functions
├── searchSerper.js       ← Calls Serper API (hides API key)
├── searchEdgar.js        ← Calls SEC EDGAR API
└── parseQuery.js         ← Optional: Gemini query parsing
```

### Example Cloud Function
```javascript
// functions/searchSerper.js
exports.searchDocuments = functions.https.onCall(async (data, context) => {
  const response = await fetch("https://google.serper.dev/search", {
    method: "POST",
    headers: {
      "X-API-KEY": process.env.SERPER_API_KEY, // secret, safe here
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ q: data.query, num: 10 })
  });
  return await response.json();
});
```

---

## 5. 🔍 Document Search — Serper API

| Detail | Value |
|--------|-------|
| **Purpose** | Search Google for investor docs from ANY public company worldwide |
| **Website** | https://serper.dev |
| **Free Tier** | 2,500 searches/month free |
| **Paid** | $50/month for 30,000 searches |
| **Response** | Title, URL, snippet, source domain, date |
| **Key Storage** | Firebase Cloud Functions environment variable (never in frontend) |

### Smart Query Strategy
Each document type gets a **targeted search query**:
| Doc Type | Query Built |
|----------|-------------|
| 10-K | `"Apple" 10-K annual report filetype:pdf site:sec.gov` |
| 10-Q | `"Apple" 10-Q quarterly report filetype:pdf site:sec.gov` |
| Investor Presentation | `"Apple" investor presentation filetype:pdf` |
| Earnings | `"Apple" earnings report filetype:pdf` |
| Proxy | `"Apple" proxy statement DEF 14A filetype:pdf site:sec.gov` |

### What Serper Finds
- Investor presentation PDFs (from company IR pages)
- Earnings report PDFs
- Annual reports from annualreports.com
- Global company filings (non-US)
- Quarterly results (non-SEC sources)

---

## 6. 🇺🇸 US Filings — SEC EDGAR Submissions API

| Detail | Value |
|--------|-------|
| **Purpose** | Fetch **actual filing documents** (PDFs) for US companies |
| **Cost** | Completely FREE — no API key needed |
| **Rate Limit** | 10 requests/second |
| **Official Source** | https://data.sec.gov |

### How It Works (3-Step Process)
```
Step 1: Ticker → CIK
  GET https://www.sec.gov/files/company_tickers.json
  "AAPL" → CIK 320193

Step 2: CIK → All Filings
  GET https://data.sec.gov/submissions/CIK0000320193.json
  Returns: form types, dates, accession numbers, primary documents

Step 3: Build Direct Document URL
  https://www.sec.gov/Archives/edgar/data/320193/{accession}/{primaryDoc}
  → Opens the actual 10-K PDF / HTML filing
```

### Filing Types Supported
| Code | Description |
|------|-------------|
| 10-K | Annual Report |
| 10-Q | Quarterly Report |
| 8-K | Current/Material Events |
| DEF 14A | Proxy Statement |
| S-1 | IPO Registration |
| 20-F | Foreign Private Issuer Annual Report |
| 6-K | Foreign Private Issuer Report |

---

## 7. 🚀 Hosting — Firebase App Hosting

| Detail | Value |
|--------|-------|
| **Type** | Static + Dynamic hosting with CDN |
| **Deploy Command** | `firebase deploy` |
| **Custom Domain** | Yes (free SSL included) |
| **Free Tier** | Generous — perfect for MVP |
| **Speed** | Global CDN — fast worldwide |

### Deploy Steps
```bash
# One-time setup
firebase login
firebase init hosting

# Every deploy after that
firebase deploy --only hosting
```

### firebase.json Config
```json
{
  "hosting": {
    "public": "public",
    "ignore": ["firebase.json", "**/.*", "**/node_modules/**"],
    "rewrites": [
      { "source": "**", "destination": "/index.html" }
    ]
  }
}
```

---

## 8. 🤖 AI Enhancement — Gemini API (Optional)

| Detail | Value |
|--------|-------|
| **Purpose** | Parse natural language queries into structured search |
| **Example** | "Tesla Q3 earnings 2024" → `{company: "Tesla", type: "10-Q", year: 2024}` |
| **Free Tier** | Yes — Google AI Studio free tier |
| **Integration** | Via Cloud Function (keeps API key secret) |

---

## 9. 🐙 Version Control — Git + GitHub

### Why GitHub?
- Free code hosting
- Version history (never lose your work)
- Easy collaboration
- GitHub Pages (alternate free hosting option)
- Shows your work to employers/investors
- README makes the project professional

### Setup in Project IDX
```bash
# One-time Git setup
git config --global user.name "Your Name"
git config --global user.email "your@email.com"

# Initialize repo
git init
git add .
git commit -m "Initial commit — Investor-Doc-Finder v1.0"

# Connect to GitHub
git remote add origin https://github.com/yourusername/investor-doc-finder.git
git branch -M main
git push -u origin main
```

### .gitignore (Important — protects secrets)
```
# Never push these to GitHub
.env
.env.local
firebase-debug.log
functions/node_modules/
.firebase/
*.key
serviceAccountKey.json
```

### Recommended GitHub Files
| File | Purpose |
|------|---------|
| `README.md` | Project description, setup guide, screenshots |
| `LICENSE` | MIT License (open source) |
| `.gitignore` | Ignore secrets and temp files |
| `CONTRIBUTING.md` | How others can contribute |
| `.github/workflows/` | Auto-deploy on push (CI/CD) |

### README.md Should Include
- App description + screenshot
- Tech stack badges
- Setup instructions
- Environment variables needed
- Live demo link (Firebase Hosting URL)
- License

---

## 10. 🛠️ IDE — Project IDX (Antigravity)

| Detail | Value |
|--------|-------|
| **Full Name** | Project IDX by Google (codename: Antigravity) |
| **URL** | https://idx.google.com |
| **Type** | Cloud-based VS Code IDE |
| **Built-in** | Terminal, Git, Browser Preview, Extensions |
| **Google Stitch** | AI UI builder — generates HTML/CSS from prompts |
| **Firebase Integration** | Built-in Firebase emulator support |

### Useful IDX Features
- **Browser Preview** — see your app live as you code
- **Terminal** — run `firebase deploy` directly
- **Git Panel** — commit and push to GitHub without terminal
- **Google Stitch** — describe UI in English, get HTML/CSS code
- **AI Assistant** — Gemini-powered code help built in

---

## 11. 📊 Complete Stack Summary Table

| Category | Technology | Cost | Why Chosen |
|----------|-----------|------|-----------|
| Frontend | HTML + CSS + Vanilla JS | Free | Simple, small, no build needed |
| Icons | Font Awesome (CDN) | Free | Easy icons without install |
| Fonts | Google Fonts (CDN) | Free | Beautiful typography |
| Auth | Firebase Auth | Free tier | Easy Google login |
| Database | Cloud Firestore | Free tier | Real-time, easy queries |
| Backend | Cloud Functions (Node.js) | Free tier | Serverless, hides API keys |
| Search | Serper API | Free 2,500/mo | Finds global company docs |
| US Filings | SEC EDGAR API | Completely free | Official US filings |
| AI (optional) | Gemini API | Free tier | Smart query parsing |
| Hosting | Firebase App Hosting | Free tier | One-click deploy, CDN |
| Version Control | Git + GitHub | Free | Code backup + sharing |
| IDE | Project IDX (Antigravity) | Free | Google tools built-in |

---

## 12. 🗓️ Complete Build Order

```
WEEK 1 — Foundation
├── Day 1: Set up Project IDX → create project → connect GitHub
├── Day 2: Use Google Stitch → generate HTML/CSS for all pages
├── Day 3: Style with CSS → make it look great
└── Day 4: Add company autocomplete (vanilla JS + companies.js)

WEEK 2 — Firebase Integration
├── Day 5: Set up Firebase project → enable Auth + Firestore
├── Day 6: Add Google Sign-In to login.html
├── Day 7: Connect Firestore → save/load search history
└── Day 8: User dashboard page

WEEK 3 — Search & Documents
├── Day 9:  Write Cloud Function → SEC EDGAR search
├── Day 10: Write Cloud Function → Serper API search
├── Day 11: Connect search.js → call Cloud Functions
└── Day 12: Results page → open in tab + download button

WEEK 4 — Polish & Deploy
├── Day 13: Test all features end-to-end
├── Day 14: Write README.md → push to GitHub
├── Day 15: Configure Firebase App Hosting
└── Day 16: firebase deploy → LIVE! 🎉
```

---

## 13. 💰 Cost Estimate (MVP Launch)

| Service | Free Tier | When You'd Pay |
|---------|-----------|---------------|
| Firebase Auth | 10K users/month | After 10K users |
| Firestore | 50K reads/day | High traffic |
| Cloud Functions | 2M calls/month | Very high traffic |
| Firebase Hosting | 10GB/month bandwidth | Large files |
| Serper API | 2,500 searches/month | After 2,500 searches |
| SEC EDGAR | Unlimited | Never (always free) |
| GitHub | Unlimited public repos | Never (free) |
| Project IDX | Free | Never (free) |

**Total cost to launch MVP: $0** 🎉

---

## 14. 🔐 Security Checklist

- [ ] Serper API key stored in Cloud Functions env variables only
- [ ] Gemini API key stored in Cloud Functions env variables only  
- [ ] `.env` file added to `.gitignore` before first commit
- [ ] Firestore security rules set (users can only see their own data)
- [ ] Firebase Auth required before saving documents
- [ ] No sensitive keys anywhere in HTML/CSS/JS files
- [ ] GitHub repo can be public (no secrets in code)

---

*Tech Stack Document v1.0 | Investor-Doc-Finder | Project IDX (Antigravity)*