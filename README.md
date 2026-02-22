# Investor Doc Finder

A full-stack web app for searching, viewing, and saving investor documents — SEC filings, earnings reports, annual reports, and more — for any public company worldwide.

**Live URL:** _[Add after deployment]_

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML + CSS + Vanilla JS |
| Auth | Firebase Auth (Google Sign-In + Email/Password) |
| Database | Cloud Firestore |
| Backend | Firebase Cloud Functions (Node.js 20) |
| Search | Serper API (global) + SEC EDGAR API (US filings) |
| Hosting | Firebase Hosting |

---

## Features

- 🔍 **Smart Search** — Type natural language queries like "Tesla Q3 2024 earnings" or "Apple 10-K 2023"
- 📄 **Dual Sources** — Searches SEC EDGAR for US filings + Serper for global documents
- 💾 **Save Documents** — Save any result to your personal dashboard (requires login)
- 📊 **Search History** — Track your last 20 searches
- 🔐 **Secure** — Firebase Auth with Google Sign-In and Email/Password
- 📱 **Responsive** — Works on desktop, tablet, and mobile

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
│   ├── style.css           # Main styles (dark navy + blue theme)
│   └── responsive.css      # Mobile breakpoints
├── js/
│   ├── app.js              # Firebase init + shared helpers
│   ├── auth.js             # Login/logout/sign-up logic
│   ├── firestore.js        # Save/load/delete documents
│   ├── search.js           # Call Cloud Functions, render results
│   ├── autocomplete.js     # Company name suggestions
│   ├── companies.js        # S&P 500 company data
│   └── download.js         # Open + download logic
├── functions/
│   ├── index.js            # Cloud Functions entry point
│   ├── parseQuery.js       # Natural language query parser
│   ├── searchEdgar.js      # SEC EDGAR API integration
│   ├── searchSerper.js     # Serper API integration
│   └── package.json        # Node.js dependencies
├── firebase.json           # Hosting + Functions config
├── firestore.rules         # Firestore security rules
├── .env                    # API keys (not committed)
└── .gitignore              # Ignores secrets + node_modules
```

---

## Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Investor-doc-Finder.git
   cd Investor-doc-Finder
   ```

2. **Install Cloud Functions dependencies**
   ```bash
   cd functions
   npm install
   cd ..
   ```

3. **Configure Firebase**
   - Create a Firebase project at [console.firebase.google.com](https://console.firebase.google.com)
   - Enable Authentication (Google + Email/Password)
   - Create a Firestore database
   - Copy your Firebase config to `js/app.js`

4. **Set Serper API key**
   ```bash
   firebase functions:config:set serper.key="YOUR_SERPER_API_KEY"
   ```

5. **Deploy**
   ```bash
   firebase deploy
   ```

---

## Environment Variables

| Variable | Where | Description |
|----------|-------|-------------|
| `SERPER_API_KEY` | `.env` / Functions config | Serper.dev API key for Google search |
| Firebase Config | `js/app.js` | Firebase project credentials |
| Cloud Function URL | `js/search.js` | Deployed function endpoint |

---

## Security

- API keys are stored in Cloud Functions environment variables (never exposed to the client)
- Firestore rules enforce per-user access only
- `.env` is in `.gitignore` and never committed

---

## License

MIT
