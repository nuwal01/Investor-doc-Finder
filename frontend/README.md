# Investor-Doc-Finder (Frontend)

React + Vite frontend for the Investor Doc Finder application with sage green design system.

## Quick Start

```bash
cd frontend
npm install
npm run dev
```

Visit **http://localhost:5173** in your browser.

## Features

- **Landing Page**: Marketing page with hero, features, coverage sections
- **Authentication**: Split-panel auth with password strength indicator
- **Search Interface**: SSE-based streaming search with real-time updates
- **Sage Green Design**: Custom design system with forest sage palette

## Routes

- `/` - Landing page
- `/auth` - Sign in / Sign up
- `/search` - Protected search interface (requires auth)

## Tech Stack

- React 18 + Vite 8
- React Router DOM
- Server-Sent Events (SSE)
- Firebase stubs (ready for integration)

## Project Structure

```
src/
├── pages/          Landing, Auth, Search
├── components/     Navbar, SearchBar, DocTypePills, etc.
├── hooks/          useSSESearch (SSE streaming)
├── context/        AuthContext (Firebase stubs)
└── utils/          Helper functions
```

## Backend Integration

Backend should run at `http://localhost:8000` with POST /search endpoint returning SSE stream.

## Testing Checklist

- [ ] Landing page animations work (chip cycling, scroll nav)
- [ ] Auth tab switching and password strength work
- [ ] Sign in saves to sessionStorage and redirects
- [ ] Protected route redirects when not authenticated
- [ ] Search streams SSE status updates
- [ ] Results display with confidence badges
- [ ] Sign out clears session

Built with Claude 4.6
