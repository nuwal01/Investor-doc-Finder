# Financial Report Finder

> **Instantly locate official financial reports from public companies using natural language queries.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 🚀 Overview

Financial Report Finder is a web application that enables users to quickly locate and access official financial reports from public companies through natural language queries. Simply type what you're looking for, and get direct links to SEC filings and investor documents.

### Key Features

- 🔍 **Natural Language Search** - Search using plain English (e.g., "Tesla Q3 2024 earnings")
- 📊 **SEC EDGAR Integration** - Direct access to official SEC filings (10-K, 10-Q, 8-K, etc.)
- 🏢 **100+ Companies** - Pre-configured support for S&P 500 companies
- ⚡ **Company Autocomplete** - Quick suggestions as you type
- 📱 **Responsive Design** - Works on desktop and mobile
- 🎨 **Modern UI** - Neumorphic design with smooth animations

## 📷 Screenshots

*Coming soon...*

## 🛠️ Tech Stack

### Frontend
- **Next.js 16** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS 4** - Utility-first styling
- **Lucide Icons** - Beautiful icon set
- **Playwright** - E2E testing

### Backend
- **Node.js + Express** - RESTful API
- **TypeScript** - Type-safe backend
- **Compromise NLP** - Natural language processing
- **Cheerio** - HTML parsing
- **Jest** - Unit testing

## 📦 Installation

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Quick Start

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/investor-doc-finder.git
cd investor-doc-finder
```

2. **Install Backend Dependencies**

```bash
cd backend
npm install
```

3. **Install Frontend Dependencies**

```bash
cd ../frontend
npm install
```

4. **Configure Environment Variables**

Create a `.env` file in the `backend` directory:

```env
PORT=3001
NODE_ENV=development
```

Create a `.env.local` file in the `frontend` directory:

```env
NEXT_PUBLIC_API_URL=http://localhost:3001/api
```

5. **Start the Development Servers**

**Backend:**
```bash
cd backend
npm run dev
```

**Frontend (in a new terminal):**
```bash
cd frontend
npm run dev
```

6. **Open the Application**

Navigate to [http://localhost:3000](http://localhost:3000) in your browser.

## 🧪 Running Tests

### Backend Unit Tests

```bash
cd backend
npm test
```

### Frontend E2E Tests

```bash
cd frontend
npm run test:e2e        # Run tests in headless mode
npm run test:e2e:ui     # Run tests with Playwright UI
```

## 📖 API Documentation

See [docs/API.md](docs/API.md) for complete API documentation.

### Quick API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/search` | POST | Search for documents |
| `/api/autocomplete` | GET | Company suggestions |

### Example Search Request

```bash
curl -X POST http://localhost:3001/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Apple 10-K 2024"}'
```

## 📁 Project Structure

```
investor-doc-finder/
├── backend/
│   ├── src/
│   │   ├── data/           # Static data (S&P 500 companies)
│   │   ├── routes/         # API route handlers
│   │   ├── services/       # Business logic
│   │   ├── types/          # TypeScript types
│   │   └── index.ts        # Express app entry point
│   ├── package.json
│   └── tsconfig.json
│
├── frontend/
│   ├── app/                # Next.js App Router
│   │   ├── page.tsx        # Homepage
│   │   ├── layout.tsx      # Root layout
│   │   └── globals.css     # Global styles
│   ├── components/         # Reusable UI components
│   ├── lib/                # Utilities and API client
│   ├── e2e/                # Playwright E2E tests
│   ├── public/             # Static assets
│   ├── package.json
│   └── playwright.config.ts
│
├── docs/
│   └── API.md              # API documentation
│
├── prd.md                  # Product Requirements Document
└── README.md               # This file
```

## 🔧 Configuration

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `3001` |
| `NODE_ENV` | Environment (development/production) | `development` |

### Frontend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL | `http://localhost:3001/api` |

## 🚀 Deployment

### Frontend (Vercel)

1. Push your code to GitHub
2. Import project in [Vercel](https://vercel.com)
3. Set environment variables:
   - `NEXT_PUBLIC_API_URL`: Your backend URL

### Backend (Railway/Render)

1. Create a new project on [Railway](https://railway.app) or [Render](https://render.com)
2. Connect your GitHub repository
3. Set the root directory to `backend`
4. Configure environment variables:
   - `PORT`: Will be auto-assigned
   - `NODE_ENV`: `production`

## 📋 Supported Document Types

| Type | Keywords | SEC Form |
|------|----------|----------|
| Annual Report | `annual`, `10-K` | 10-K |
| Quarterly Report | `quarterly`, `Q1-4`, `10-Q` | 10-Q |
| Current Report | `current`, `8-K` | 8-K |
| Proxy Statement | `proxy` | DEF 14A |
| Investor Presentation | `investor presentation`, `deck` | - |
| ESG Report | `ESG`, `sustainability` | - |

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting a PR.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [SEC EDGAR](https://www.sec.gov/edgar) for providing public access to company filings
- [Compromise](https://github.com/spencermountain/compromise) for NLP capabilities
- [Vercel](https://vercel.com) for Next.js and hosting inspiration

---

**Made with ❤️ for investors, analysts, and researchers**
