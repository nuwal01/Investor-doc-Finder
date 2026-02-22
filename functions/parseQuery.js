// ──────────────────────────────────────────────
// parseQuery.js  –  Parse natural-language search queries
// ──────────────────────────────────────────────
// Input:   "Tesla Q3 2024 earnings"
// Output:  { company, ticker, docType, year, quarter, isUS }

// Quick lookup: well‑known US tickers
const US_TICKERS = {
    apple: "AAPL", microsoft: "MSFT", alphabet: "GOOGL", google: "GOOGL",
    amazon: "AMZN", nvidia: "NVDA", tesla: "TSLA", meta: "META",
    berkshire: "BRK.B", unitedhealth: "UNH", johnson: "JNJ",
    jpmorgan: "JPM", visa: "V", procter: "PG", mastercard: "MA",
    "home depot": "HD", chevron: "CVX", abbvie: "ABBV", "eli lilly": "LLY",
    merck: "MRK", "coca-cola": "KO", pepsi: "PEP", pepsico: "PEP",
    broadcom: "AVGO", pfizer: "PFE", walmart: "WMT", costco: "COST",
    disney: "DIS", "walt disney": "DIS", "mcdonald": "MCD",
    abbott: "ABT", danaher: "DHR", netflix: "NFLX", intel: "INTC",
    amd: "AMD", adobe: "ADBE", salesforce: "CRM", oracle: "ORCL",
    cisco: "CSCO", qualcomm: "QCOM", paypal: "PYPL", boeing: "BA",
    "goldman sachs": "GS", "morgan stanley": "MS", caterpillar: "CAT",
    "3m": "MMM", "general electric": "GE", "general motors": "GM",
    ford: "F", uber: "UBER", airbnb: "ABNB", snap: "SNAP",
    spotify: "SPOT", palantir: "PLTR", coinbase: "COIN",
};

// SEC filing types the user might mention
const FILING_KEYWORDS = {
    "10-k": "10-K",
    "10k": "10-K",
    "annual": "10-K",
    "annual report": "10-K",
    "10-q": "10-Q",
    "10q": "10-Q",
    "quarterly": "10-Q",
    "8-k": "8-K",
    "8k": "8-K",
    "earnings": "earnings",
    "proxy": "DEF 14A",
    "def 14a": "DEF 14A",
    "s-1": "S-1",
    "ipo": "S-1",
    "20-f": "20-F",
    "20f": "20-F",
};

function parseQuery(raw) {
    const q = (raw || "").trim();
    const lower = q.toLowerCase();

    // ── Detect year ────────────────────────────
    const yearMatch = lower.match(/\b(20\d{2})\b/);
    const year = yearMatch ? yearMatch[1] : "";

    // ── Detect quarter ─────────────────────────
    const qtrMatch = lower.match(/\bq([1-4])\b/);
    const quarter = qtrMatch ? `Q${qtrMatch[1]}` : "";

    // ── Detect filing / doc type ───────────────
    let docType = "";
    for (const [keyword, type] of Object.entries(FILING_KEYWORDS)) {
        if (lower.includes(keyword)) {
            docType = type;
            break;
        }
    }

    // ── Detect company ─────────────────────────
    let company = "";
    let ticker = "";
    let isUS = false;

    // Check for known US tickers first
    for (const [name, tick] of Object.entries(US_TICKERS)) {
        if (lower.includes(name)) {
            company = name.charAt(0).toUpperCase() + name.slice(1);
            ticker = tick;
            isUS = true;
            break;
        }
    }

    // If no known company matched, take the first "word(s)" before any keyword
    if (!company) {
        let cleaned = lower;
        // Remove known tokens so what remains is likely the company name
        [year, quarter, docType, "earnings", "report", "filing", "annual", "quarterly"]
            .filter(Boolean)
            .forEach(tok => { cleaned = cleaned.replace(tok.toLowerCase(), ""); });

        company = cleaned.trim().replace(/\s+/g, " ");
        if (company) {
            company = company.split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
        }
    }

    return { company, ticker, docType, year, quarter, isUS, raw: q };
}

module.exports = { parseQuery };
