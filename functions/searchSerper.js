// ──────────────────────────────────────────────
// searchSerper.js  –  Serper.dev Google Search API
// ──────────────────────────────────────────────
// Searches for actual company investor documents:
//   - Annual reports (10-K PDFs)
//   - Quarterly reports (10-Q PDFs)
//   - Investor presentations / decks
//   - Earnings reports

const fetch = require("node-fetch");

const SERPER_URL = "https://google.serper.dev/search";

/**
 * Build a targeted search query for actual PDF investor documents.
 * Key: we search for filetype:pdf ONLY (not htm) and avoid sec.gov
 * because SEC files are HTML. PDFs are on company IR pages.
 */
function buildSearchQuery(parsed) {
    const parts = [];

    if (parsed.company) parts.push(`"${parsed.company}"`);
    if (parsed.ticker) parts.push(parsed.ticker);

    switch (parsed.docType) {
        case "10-K":
            parts.push("annual report 10-K filetype:pdf");
            break;
        case "10-Q":
            parts.push("quarterly report 10-Q filetype:pdf");
            break;
        case "investor-presentation":
            parts.push("investor presentation filetype:pdf");
            break;
        case "earnings":
            parts.push("earnings report OR earnings release filetype:pdf");
            break;
        case "DEF 14A":
            parts.push("proxy statement filetype:pdf");
            break;
        case "S-1":
            parts.push("S-1 registration statement filetype:pdf");
            break;
        case "8-K":
            parts.push("8-K report filetype:pdf");
            break;
        default:
            parts.push("annual report OR investor presentation filetype:pdf");
            break;
    }

    if (parsed.quarter) parts.push(parsed.quarter);
    if (parsed.year) parts.push(parsed.year);

    return parts.join(" ");
}

/**
 * Search Serper for investor documents.
 */
async function searchSerper(parsed, apiKey) {
    if (!apiKey) {
        console.log("   Serper: No API key – skipping.");
        return [];
    }

    try {
        const query = buildSearchQuery(parsed);
        console.log(`   Serper query: ${query}`);

        const response = await fetch(SERPER_URL, {
            method: "POST",
            headers: {
                "X-API-KEY": apiKey,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ q: query, num: 10 })
        });

        if (!response.ok) {
            const errText = await response.text();
            console.error(`   Serper API error: ${response.status} ${errText}`);
            return [];
        }

        const data = await response.json();
        const organic = data.organic || [];

        const results = organic.map(item => {
            const url = item.link || "";
            const isPdf = url.toLowerCase().endsWith('.pdf');
            return {
                title: (item.title || "").replace(/^\[PDF\]\s*/i, ""),
                url: url,
                type: detectDocType(item.title, item.snippet, parsed.docType),
                company: parsed.company || "",
                ticker: parsed.ticker || "",
                date: extractDate(item.snippet) || item.date || "",
                source: "Google Search",
                description: (isPdf ? "📄 PDF — " : "📃 ") + (item.snippet || ""),
                format: isPdf ? "PDF" : "HTML"
            };
        }).filter(r => r.url);

        // Filter out irrelevant results
        const companyLower = (parsed.company || "").toLowerCase();
        const tickerLower = (parsed.ticker || "").toLowerCase();
        const filtered = results.filter(r => {
            const titleLower = r.title.toLowerCase();
            const urlLower = r.url.toLowerCase();
            const combined = titleLower + " " + urlLower;

            // Must mention the company name or ticker in title or URL
            const mentionsCompany = companyLower && combined.includes(companyLower);
            const mentionsTicker = tickerLower && combined.includes(tickerLower);
            const isRelevant = mentionsCompany || mentionsTicker;

            // Blacklist irrelevant domains
            const blacklist = ["university", "edu/", "reddit.com", "quora.com",
                "wikipedia.org", "investopedia.com", "youtube.com"];
            const isBlacklisted = blacklist.some(b => urlLower.includes(b));

            return isRelevant && !isBlacklisted;
        });

        // Sort: PDFs first
        filtered.sort((a, b) => (b.format === "PDF" ? 1 : 0) - (a.format === "PDF" ? 1 : 0));

        return filtered;

    } catch (err) {
        console.error("   Serper search error:", err.message);
        return [];
    }
}

function detectDocType(title, snippet, fallback) {
    const text = ((title || "") + " " + (snippet || "")).toLowerCase();
    if (text.includes("10-k") || text.includes("annual report")) return "10-K";
    if (text.includes("10-q") || text.includes("quarterly")) return "10-Q";
    if (text.includes("8-k")) return "8-K";
    if (text.includes("earnings")) return "Earnings";
    if (text.includes("investor presentation") || text.includes("investor day")) return "Presentation";
    if (text.includes("proxy") || text.includes("def 14a")) return "Proxy";
    if (text.includes("20-f")) return "20-F";
    if (text.includes("s-1") || text.includes("ipo")) return "S-1";
    return fallback || "Document";
}

function extractDate(text) {
    if (!text) return "";
    const match = text.match(/\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b/i);
    return match ? match[0] : "";
}

module.exports = { searchSerper };
