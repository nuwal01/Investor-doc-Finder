// ──────────────────────────────────────────────
// parseQuery.js  –  Parse natural-language search queries
// ──────────────────────────────────────────────
// Input:   "Tesla Q3 2024 earnings"
// Output:  { company, ticker, docType, year, quarter, isUS }

const US_TICKERS = {
    "apple": "AAPL", "microsoft": "MSFT", "alphabet": "GOOGL", "google": "GOOGL",
    "amazon": "AMZN", "nvidia": "NVDA", "tesla": "TSLA", "meta": "META",
    "berkshire": "BRK-B", "unitedhealth": "UNH", "johnson": "JNJ",
    "jpmorgan": "JPM", "jp morgan": "JPM", "visa": "V", "procter": "PG",
    "mastercard": "MA", "home depot": "HD", "chevron": "CVX", "abbvie": "ABBV",
    "eli lilly": "LLY", "merck": "MRK", "coca-cola": "KO", "coca cola": "KO",
    "pepsi": "PEP", "pepsico": "PEP", "broadcom": "AVGO", "pfizer": "PFE",
    "walmart": "WMT", "costco": "COST", "disney": "DIS", "walt disney": "DIS",
    "mcdonald": "MCD", "mcdonalds": "MCD", "abbott": "ABT", "netflix": "NFLX",
    "intel": "INTC", "amd": "AMD", "adobe": "ADBE", "salesforce": "CRM",
    "oracle": "ORCL", "cisco": "CSCO", "qualcomm": "QCOM", "paypal": "PYPL",
    "boeing": "BA", "goldman sachs": "GS", "morgan stanley": "MS",
    "caterpillar": "CAT", "3m": "MMM", "general electric": "GE",
    "general motors": "GM", "ford": "F", "uber": "UBER", "airbnb": "ABNB",
    "snap": "SNAP", "spotify": "SPOT", "palantir": "PLTR", "coinbase": "COIN",
    "apple inc": "AAPL", "apple inc.": "AAPL", "microsoft corp": "MSFT",
    "amazon.com": "AMZN", "tesla inc": "TSLA", "meta platforms": "META",
    "nvidia corp": "NVDA", "nvidia corporation": "NVDA",
    "berkshire hathaway": "BRK-B", "johnson & johnson": "JNJ",
    "unitedhealth group": "UNH", "procter & gamble": "PG", "procter and gamble": "PG",
    "the home depot": "HD", "eli lilly and company": "LLY",
    "coca-cola company": "KO", "walt disney company": "DIS",
    "goldman sachs group": "GS", "bank of america": "BAC",
    "wells fargo": "WFC", "citigroup": "C", "morgan stanley": "MS",
    "american express": "AXP", "ibm": "IBM", "nike": "NKE",
    "starbucks": "SBUX", "target": "TGT", "lowes": "LOW", "lowe's": "LOW",
    "moderna": "MRNA", "roku": "ROKU", "snowflake": "SNOW",
    "crowdstrike": "CRWD", "datadog": "DDOG", "shopify": "SHOP",
    "square": "SQ", "block": "SQ", "zoom": "ZM",
    "twilio": "TWLO", "atlassian": "TEAM", "servicenow": "NOW",
    "workday": "WDAY", "palo alto": "PANW", "palo alto networks": "PANW",
    "fortinet": "FTNT", "zscaler": "ZS", "okta": "OKTA",
    "dell": "DELL", "hp": "HPQ", "hewlett packard": "HPE",
    "accenture": "ACN", "deloitte": "ACN",
    "at&t": "T", "verizon": "VZ", "t-mobile": "TMUS",
    "comcast": "CMCSA", "exxon": "XOM", "exxon mobil": "XOM",
    "shell": "SHEL", "bp": "BP", "conocophillips": "COP",
    "lockheed martin": "LMT", "raytheon": "RTX", "northrop grumman": "NOC",
};

// Also accept raw tickers that look like tickers (1-5 uppercase letters)
function looksLikeTicker(word) {
    return /^[A-Z]{1,5}(-[A-Z])?$/.test(word);
}

const FILING_KEYWORDS = {
    "10-k": "10-K", "10k": "10-K", "10 k": "10-K", "10 -k": "10-K",
    "annual report": "10-K", "annual": "10-K",
    "10-q": "10-Q", "10q": "10-Q", "10 q": "10-Q", "10 -q": "10-Q",
    "quarterly report": "10-Q", "quarterly": "10-Q",
    "8-k": "8-K", "8k": "8-K", "8 k": "8-K",
    "earnings": "earnings",
    "earnings report": "earnings",
    "earnings call": "earnings",
    "investor presentation": "investor-presentation",
    "investor deck": "investor-presentation",
    "presentation": "investor-presentation",
    "proxy": "DEF 14A", "def 14a": "DEF 14A",
    "proxy statement": "DEF 14A",
    "s-1": "S-1", "s 1": "S-1", "ipo": "S-1",
    "20-f": "20-F", "20f": "20-F", "20 f": "20-F",
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
    // Check longest keywords first to avoid partial matches
    const sortedKeywords = Object.keys(FILING_KEYWORDS).sort((a, b) => b.length - a.length);
    for (const keyword of sortedKeywords) {
        if (lower.includes(keyword)) {
            docType = FILING_KEYWORDS[keyword];
            break;
        }
    }

    // ── Detect company / ticker ────────────────
    let company = "";
    let ticker = "";
    let isUS = false;

    // First, check if user directly typed a ticker (e.g. "AAPL 10-K")
    const words = q.split(/\s+/);
    for (const word of words) {
        if (looksLikeTicker(word)) {
            // Verify it's a real ticker in our map
            const mapValues = Object.values(US_TICKERS);
            if (mapValues.includes(word)) {
                ticker = word;
                // Find company name
                for (const [name, tick] of Object.entries(US_TICKERS)) {
                    if (tick === word) { company = name.charAt(0).toUpperCase() + name.slice(1); break; }
                }
                isUS = true;
                break;
            }
        }
    }

    // If no direct ticker match, check known company names (longest match first)
    if (!ticker) {
        const sortedNames = Object.keys(US_TICKERS).sort((a, b) => b.length - a.length);
        for (const name of sortedNames) {
            if (lower.includes(name)) {
                company = name.split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
                ticker = US_TICKERS[name];
                isUS = true;
                break;
            }
        }
    }

    // If still no company, extract what's left after removing known tokens
    if (!company) {
        let cleaned = lower;
        [year, quarter, docType, "earnings", "report", "filing", "annual", "quarterly",
            "investor", "presentation", "inc", "inc.", "corp", "corporation", "company", "ltd",
            "10-k", "10-q", "8-k", "10 k", "10 q", "8 k", "for", "year", "of", "the",
            "investor-presentation", "def 14a", "proxy", "statement"]
            .filter(Boolean)
            .forEach(tok => { cleaned = cleaned.replace(new RegExp(tok.toLowerCase(), "g"), ""); });
        company = cleaned.trim().replace(/\s+/g, " ");
        if (company) {
            company = company.split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
        }
    }

    return { company, ticker, docType, year, quarter, isUS, raw: q };
}

module.exports = { parseQuery };
