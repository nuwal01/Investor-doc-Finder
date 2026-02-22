# 🎨 Google Stitch Prompt Sheet
## Investor-Doc-Finder
**How to use:** Open Google Stitch in Project IDX → Paste each prompt below → Export HTML/CSS → Save to your file

---

## 📋 Global Design Instructions
> Paste this FIRST in Stitch before generating any page — it sets the consistent design system for all pages.

```
Design a professional financial web application called "Investor-Doc-Finder".

DESIGN SYSTEM:
- Theme: Dark professional finance theme
- Primary background: #0A0E1A (very dark navy)
- Secondary background: #111827 (dark card background)
- Accent color: #2563EB (electric blue)
- Accent hover: #1D4ED8
- Success green: #10B981
- Text primary: #F9FAFB (near white)
- Text secondary: #9CA3AF (muted gray)
- Border color: #1F2937
- Card background: #111827 with 1px border #1F2937
- Border radius: 12px on cards, 8px on buttons
- Font: 'Inter' from Google Fonts for body, 'Syne' for headings
- Subtle blue glow effects on interactive elements
- Clean, minimal, trustworthy — like Bloomberg or Refinitiv
- No gradients that look cheap — only subtle dark-to-darker gradients
- All buttons have hover transitions (0.2s ease)
- Box shadows: 0 4px 24px rgba(37, 99, 235, 0.08) on cards
```

---

## PAGE 1 — Home Page (`index.html`)

### Stitch Prompt:
```
Build a dark financial web app homepage for "Investor-Doc-Finder" using the design system above.

NAVBAR (top, full width, sticky):
- Left: Logo icon (document with magnifier) + text "Investor-Doc-Finder" in white bold
- Right: "Dashboard" link + "Sign In" button (blue, rounded)
- Background: #0A0E1A with bottom border #1F2937
- Height: 64px

HERO SECTION (center of page, generous padding):
- Small badge above heading: "🔍 500+ Companies · SEC EDGAR · 150+ Countries"
  styled as a pill with blue border and subtle blue background
- Main heading (large, 48px): "Find Any Investor Document" on one line,
  "Instantly." on second line in electric blue (#2563EB)
- Subheading (gray, 18px): "Search SEC filings, annual reports, earnings releases
  from any public company worldwide — in plain English."
- Large search bar below (full width, max 720px, centered):
  - Height: 56px, border radius: 14px
  - Dark background #111827, blue border on focus
  - Placeholder: 'Try "Tesla Q3 2024 earnings" or "Apple 10-K 2023"'
  - Blue search button on the right side of the bar labeled "Search"
  - Small microphone icon inside the bar on the right
- Below search bar: Example search chips (clickable pill buttons):
  "Tesla Q3 2024" · "Apple Annual Report" · "Samsung Earnings" · "Reliance 2024"
  styled as small dark pills with gray border, hover turns blue

STATS BAR (below hero, full width):
- 4 stats in a row with dividers between them:
  "500+ Companies" · "SEC EDGAR Direct" · "150+ Countries" · "Free to Use"
- Each stat has a small blue icon above the number
- Background slightly lighter than page: #111827

FEATURED COMPANIES SECTION:
- Section heading: "Popular Companies" (small, gray, uppercase, letter-spaced)
- Single horizontal scrollable row of company cards
- Each card: dark background, company ticker symbol (bold, white),
  company name (small, gray), country flag emoji
- Cards: AAPL · TSLA · MSFT · AMZN · GOOGL · META · NVDA · JPM · RELIANCE · SAMSUNG
- Hover effect: blue border glow

RECENT FILINGS TICKER (below featured companies):
- Label: "Latest Filings:" in gray
- Scrolling marquee of recent filing examples:
  "TSLA · 10-Q · Jan 2025" · "AAPL · 8-K · Feb 2025" etc.
- Subtle, not distracting — small text, muted colors

FOOTER:
- Dark background #0A0E1A
- Left: Logo + "Investor-Doc-Finder" + tagline
- Center: Links — Home · Dashboard · Login
- Right: "Data from SEC EDGAR & Serper API"
- Bottom bar: "© 2026 Investor-Doc-Finder · Built on Firebase"
```

---

## PAGE 2 — Search Results (`results.html`)

### Stitch Prompt:
```
Build a dark financial search results page for "Investor-Doc-Finder" using the design system above.

NAVBAR: Same as homepage — sticky, logo left, Dashboard + Sign In right.

SEARCH BAR (top of page, below navbar):
- Pre-filled search bar showing the search query
- Same style as homepage search bar but slightly smaller (48px height)
- "Search" button on right
- Below bar: show result count — "8 results for Tesla Q3 2024 earnings" in gray

FILTER BAR (horizontal, below search):
- Label "Filter:" in gray
- Pill filter buttons: "All" (active, blue filled) · "10-K" · "10-Q" · "8-K" · 
  "Annual Report" · "Earnings" · "Proxy"
- Sort dropdown on the far right: "Most Recent ▾"
- Thin bottom border below filter bar

RESULTS LIST (main content area):
Show 3 example result cards stacked vertically. Each card:
- Background: #111827, border: 1px solid #1F2937, border-radius: 12px
- Padding: 20px, margin-bottom: 12px
- TOP ROW:
  - Left: Document type badge (e.g. "10-Q" in blue pill) + Company name bold white
    + Ticker in gray ("TSLA") + 🇺🇸 flag
  - Right: Date filed ("Jan 15, 2025") in small gray text
- MIDDLE ROW:
  - Document title in white (e.g. "Tesla, Inc. Form 10-Q for Quarter Ended September 30, 2024")
  - Source domain badge: small gray pill "sec.gov" with lock icon
- BOTTOM ROW (action buttons, right-aligned):
  - "🔗 Open" button — dark bg, white text, blue border, hover blue fill
  - "⬇ Download" button — blue bg, white text
  - "🔖 Save" button — dark bg, gray text, gray border, hover shows blue
- Hover effect on entire card: subtle blue left border (4px) appears

PAGINATION (bottom):
- "← Previous · 1 · 2 · 3 · Next →" centered
- Current page highlighted in blue

LOADING STATE (skeleton):
- Show 3 skeleton cards with animated gray shimmer effect
- Represents loading state while API fetches

EMPTY STATE:
- Centered illustration area (just a simple icon placeholder)
- Heading: "No documents found"
- Subtext: "Try searching with different keywords or check the company name"
- Blue "Try Again" button
```

---

## PAGE 3 — Dashboard (`dashboard.html`)

### Stitch Prompt:
```
Build a dark financial user dashboard page for "Investor-Doc-Finder" using the design system above.

NAVBAR: Same sticky navbar. "Dashboard" link is highlighted/active. "Sign Out" button replaces "Sign In".

WELCOME HEADER (top of page content):
- Left: User avatar circle (blue initials placeholder "JD") + "Welcome back, John" in white bold
  + "john@gmail.com" in gray small below
- Right: "Search Documents" blue button linking to homepage

STATS ROW (4 cards in a grid):
- Card 1: "Saved Documents" — number "12" large blue, label gray
- Card 2: "Searches Made" — number "47" large, label gray
- Card 3: "Companies Tracked" — number "8" large, label gray
- Card 4: "Last Active" — "Today" large, label gray
- Each card: dark bg #111827, blue icon top-left, border #1F2937

SAVED DOCUMENTS SECTION:
- Section heading: "📁 Saved Documents" bold white + "12 docs" badge gray right
- Search/filter bar: small search input + "All Types ▾" dropdown filter
- Grid of document cards (2 columns on desktop, 1 on mobile):
  Each card:
  - Document type badge (blue pill: "10-K")
  - Company name bold + ticker gray
  - Document title (truncated to 2 lines)
  - Saved date small gray
  - Bottom: "Open" small link button + "Download" small link + red "Remove" small link
  - Hover: slight blue glow border

RECENT SEARCHES SECTION (below saved docs):
- Section heading: "🕐 Recent Searches" bold white
- List of 5 recent search items:
  Each item: search query text (white) + date (gray right) + "Search Again →" link blue
  Thin divider between items
- "Clear History" link in red small text at bottom right

EMPTY DASHBOARD STATE:
- Centered content if no saved docs:
  - Large document icon placeholder
  - "No saved documents yet"
  - "Search for investor documents and save them here"
  - Blue "Start Searching" button
```

---

## PAGE 4 — Login Page (`login.html`)

### Stitch Prompt:
```
Build a dark financial login page for "Investor-Doc-Finder" using the design system above.

FULL PAGE LAYOUT:
- Left half (desktop): Dark navy background with branding
  - Large logo icon centered
  - App name "Investor-Doc-Finder" in large white bold
  - Tagline: "Find any investor document from any public company, instantly."
  - 3 feature bullets below with blue checkmarks:
    ✓ SEC EDGAR direct access
    ✓ Global company support  
    ✓ Save & organize documents
  - Bottom: subtle grid pattern or dot pattern background texture

- Right half (desktop): slightly lighter dark card (#111827)
  centered login form

LOGIN FORM (right side, centered vertically):
- Heading: "Welcome Back" white bold 28px
- Subtext: "Sign in to save documents and view history" gray

- GOOGLE SIGN-IN BUTTON (full width, prominent):
  White background, black text, Google "G" logo icon left
  "Continue with Google" text
  Height: 48px, border-radius: 10px
  Hover: slight shadow

- Divider: ——— or ———

- Email input field:
  Label: "Email" gray small above
  Dark input bg, white text, blue border on focus
  Placeholder: "your@email.com"

- Password input field:
  Label: "Password" gray small above
  Dark input bg, show/hide password eye icon right
  Placeholder: "••••••••"

- "Forgot password?" link aligned right, blue small

- SIGN IN BUTTON (full width, blue, bold):
  "Sign In" text, height 48px

- Bottom text: "Don't have an account? Sign Up" — "Sign Up" in blue

- GUEST MODE link below form:
  "Continue without signing in →" in gray, underline on hover
  Small note: "Search works without login. Sign in only needed to save documents."

MOBILE: Stack both halves vertically, hide left branding half, show only form.
```

---

## PAGE 5 — Company Profile (`company.html`)

### Stitch Prompt:
```
Build a dark financial company profile page for "Investor-Doc-Finder" using the design system above.

NAVBAR: Same sticky navbar.

COMPANY HEADER (top section, full width):
- Background: #111827 with subtle blue gradient overlay
- Left: Large company initial avatar (blue circle, white letter "T")
  + Company name bold large white: "Tesla, Inc."
  + Ticker badge: "TSLA" blue pill
  + Exchange badge: "NASDAQ" gray pill
  + Country: 🇺🇸 United States
- Right: "🔔 Follow Company" button (outlined blue) + "⬇ Download All" button (blue filled)
- Below company name: brief description gray text
  "Electric vehicle and clean energy company. Designs and manufactures EVs, battery storage, solar panels."

QUICK STATS ROW (4 stats below header):
- "Total Filings: 247" · "Latest: 10-Q Jan 2025" · "On SEC EDGAR: Yes" · "Exchange: NASDAQ"
- Dark cards, blue icon each

FILINGS SECTION:
- Section heading: "📄 All Filings" bold white

- FILTER TABS (horizontal pill tabs):
  "All" (active blue) · "10-K" · "10-Q" · "8-K" · "DEF 14A" · "S-1" · "Other"

- YEAR FILTER (right side of filter row):
  Dropdown "Year: 2024 ▾" with options 2024, 2023, 2022, 2021, 2020

- FILINGS TABLE / LIST:
  Each filing row:
  - Filing type badge (colored pill: 10-K=blue, 10-Q=green, 8-K=orange)
  - Filing title (white, truncated)
  - Period covered (gray: "Q3 2024", "FY 2023")
  - Date filed (gray: "Jan 15, 2025")
  - Action buttons right: "Open" outlined small + "Download" blue small
  - Thin divider between rows
  - Hover: row background slightly lighter + left blue border

  Show 8 example rows with realistic Tesla filing data.

- LOAD MORE button (centered, outlined blue): "Load More Filings"

RELATED COMPANIES SECTION (bottom):
- "You might also search:" heading gray
- Row of company chips: RIVN · NIO · GM · F · LCID
  Each chip: dark bg, ticker bold, company name small, hover blue border
```

---

## 🎯 Stitch Tips for Best Results

### Before You Generate Each Page:
1. Paste the **Global Design Instructions** first
2. Then paste the specific page prompt
3. Click **Generate**
4. If result isn't perfect — click **"Refine"** and add:
   - *"Make the search bar bigger"*
   - *"Make cards more compact"*
   - *"Add more spacing between sections"*

### After Stitch Generates:
- Click **"Export"** or **"Copy Code"**
- Paste into your HTML file in Project IDX
- The CSS will be either inline `<style>` or a separate block — move it to `css/style.css`

### Common Refinement Prompts:
```
"Make it more compact and dense — financial data style"
"Add a loading skeleton animation to the results cards"
"Make the search bar more prominent and centered"
"Add subtle hover glow effects to all interactive elements"
"Make mobile responsive with hamburger menu on navbar"
"Add smooth fade-in animation when page loads"
```

---

## ✅ Checklist — After Stitch Generates All Pages

- [ ] index.html — Home page ✓
- [ ] results.html — Search results ✓
- [ ] dashboard.html — User dashboard ✓
- [ ] login.html — Auth page ✓
- [ ] company.html — Company profile ✓
- [ ] All CSS moved to css/style.css
- [ ] Google Fonts link added to all pages
- [ ] Navbar is consistent across all pages
- [ ] Mobile responsive on all pages
- [ ] Pushed to GitHub after UI is complete

---

## 🔜 After Stitch — What You Build Next

Once Stitch gives you all 5 pages:

```
1. Add Firebase CDN scripts to all HTML files
2. Write js/auth.js  → Google Sign-In
3. Write js/firestore.js → Save/load documents
4. Write js/search.js → Call Serper + EDGAR
5. Write js/autocomplete.js → Company suggestions
6. Write Cloud Functions → Hide API keys
7. firebase deploy → GO LIVE 🚀
```

---

*Stitch Prompt Sheet v1.0 | Investor-Doc-Finder | Project IDX (Antigravity)*