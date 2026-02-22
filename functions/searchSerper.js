// ──────────────────────────────────────────────
// searchSerper.js  –  Serper.dev Google Search API
// ──────────────────────────────────────────────
// Requires SERPER_API_KEY set as a Firebase Functions
// environment variable (or defineSecret).

const fetch = require("node-fetch");

const SERPER_URL = "https://google.serper.dev/search";

/**
 * Search Serper for investor documents.
 * @param {{ company:string, docType:string, year:string, quarter:string, raw:string }} parsed
 * @param {string} apiKey  – Serper API key (from env)
 * @returns {Promise<Array<{title,url,type,company,date,source}>>}
 */
async function searchSerper(parsed, apiKey) {
    if (!apiKey) {
        console.warn("SERPER_API_KEY not set – skipping Serper search.");
        return [];
    }

    try {
        // Build a targeted search query
        const queryParts = [];
        if (parsed.company) queryParts.push(parsed.company);
        if (parsed.docType) queryParts.push(parsed.docType);
        if (parsed.quarter) queryParts.push(parsed.quarter);
        if (parsed.year) queryParts.push(parsed.year);

        // Append "investor" or "filetype:pdf" to get relevant results
        queryParts.push("investor report filetype:pdf");

        const query = queryParts.join(" ");

        const response = await fetch(SERPER_URL, {
            method: "POST",
            headers: {
                "X-API-KEY": apiKey,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                q: query,
                num: 10
            })
        });

        if (!response.ok) {
            console.error("Serper API error:", response.status, await response.text());
            return [];
        }

        const data = await response.json();
        const organic = data.organic || [];

        return organic.map(item => ({
            title: item.title || "",
            url: item.link || "",
            type: detectDocType(item.title, item.snippet, parsed.docType),
            company: parsed.company || "",
            date: item.date || extractDate(item.snippet) || "",
            source: "Serper (Google)"
        }));
    } catch (err) {
        console.error("Serper search error:", err.message);
        return [];
    }
}

/**
 * Try to detect the document type from the result title / snippet.
 */
function detectDocType(title, snippet, fallback) {
    const combined = ((title || "") + " " + (snippet || "")).toLowerCase();
    if (combined.includes("10-k") || combined.includes("annual report")) return "10-K";
    if (combined.includes("10-q") || combined.includes("quarterly")) return "10-Q";
    if (combined.includes("8-k")) return "8-K";
    if (combined.includes("earnings")) return "Earnings";
    if (combined.includes("proxy") || combined.includes("def 14a")) return "Proxy";
    if (combined.includes("20-f")) return "20-F";
    if (combined.includes("s-1") || combined.includes("ipo")) return "S-1";
    return fallback || "Document";
}

/**
 * Crude date extraction from snippet text.
 */
function extractDate(text) {
    if (!text) return "";
    const match = text.match(
        /\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b/i
    );
    return match ? match[0] : "";
}

module.exports = { searchSerper };
