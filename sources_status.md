# IDF Sources Status

Living document — update as quirks are discovered in production.

---

## SEC EDGAR (sources/edgar.py) — Status: WORKING

**What it does:** Fetches 10-K filings via the EDGAR Submissions JSON API.

**Quirks:**
- **Mandatory User-Agent** — requests without a descriptive `User-Agent` header return 403.
  Header must include contact info (e.g. `"IDF research trade@ostwal.in"`). This is an SEC
  policy requirement, not a bug. See: https://www.sec.gov/os/accessing-edgar-data
- **HTML not PDF** — Apple and most large US filers submit their 10-K as XBRL-tagged HTML
  (`.htm`), not as a PDF. verify.py handles HTML with its fallback path (`is_pdf=False`).
  The web_search source (Step 3) will surface the PDF glossy annual report.
- **PDF check in filing index** — some smaller filers do attach PDF versions. The source
  checks `{accession}-index.json` for type=="10-K" with a .pdf extension and lists that
  first if found.
- **reportDate vs filingDate** — filtering uses `reportDate` (fiscal year end) not
  `filingDate`. A December FY company files its 2022 10-K in early 2023; using
  `filingDate.startswith("2022")` would miss it.
- **Pagination** — `filings.recent` contains the most recent ~1000 filings. Very old filings
  (e.g. asking for 2000 report) require fetching `CIK{cik}-submissions-001.json` etc.
  Not yet implemented; will surface as "no candidates" for old requests.
- **Rate limit** — ~10 req/s per the SEC guidelines. Current code makes at most 2 requests
  per query (submissions + optional index). No throttling needed yet.

---

## NSE/BSE (sources/nse.py) — Status: STUB (Step 6)

Planned: NSE XBRL filings and BSE archives.

**Known issues:**
- NSE's public endpoints require proper session cookies — a plain GET is blocked.
- BSE has an undocumented API that changes without notice.

---

## Indian Aggregators (sources/aggregators.py) — Status: STUB (Step 6)

Planned: Stock Discovery (`stockdiscovery.in`), Screener (`screener.in`), etc.

---

## Web Search (sources/web_search.py) — Status: STUB (Step 3)

Planned fallback chain: Tavily API → Serper → Exa.
Page parsing: requests+BeautifulSoup first; Firecrawl only for JS-rendered pages.

---

## Notes on PDF vs HTML

| Source       | Format   | verify path     |
|-------------|----------|-----------------|
| EDGAR        | HTML     | HTML fallback   |
| NSE/BSE      | PDF/HTML | PDF primary     |
| Aggregators  | PDF      | PDF primary     |
| Web search   | PDF      | PDF primary     |

IDF's user-facing goal is a PDF. For EDGAR queries, the glossy IR PDF lives on the
company's investor-relations website and will be found by web_search (Step 3).
The EDGAR HTML 10-K is a valid fallback for regulatory-filing queries.
