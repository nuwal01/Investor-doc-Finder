// ──────────────────────────────────────────────
// searchEdgar.js  –  SEC EDGAR Full-Text Search
// ──────────────────────────────────────────────
// Free API — no key required.
// Docs: https://efts.sec.gov/LATEST/search-index?q=...
// User-Agent header required by SEC fair-use policy.

const fetch = require("node-fetch");

const EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index";
const EDGAR_FILING_URL = "https://www.sec.gov/cgi-bin/browse-edgar";
const USER_AGENT = "InvestorDocFinder/1.0 (contact@investordocfinder.com)";

/**
 * Search SEC EDGAR for filings.
 * @param {{ company:string, ticker:string, docType:string, year:string }} parsed
 * @returns {Promise<Array<{title,url,type,company,date,source}>>}
 */
async function searchEdgar(parsed) {
    try {
        // Build search query
        const queryParts = [];
        if (parsed.ticker) queryParts.push(parsed.ticker);
        else if (parsed.company) queryParts.push(parsed.company);
        if (parsed.docType && parsed.docType !== "earnings") queryParts.push(parsed.docType);
        if (parsed.year) queryParts.push(parsed.year);

        const q = queryParts.join(" ");

        // Determine form types for the query
        let forms = "";
        if (parsed.docType && parsed.docType !== "earnings") {
            forms = `&forms=${encodeURIComponent(parsed.docType)}`;
        }

        // Date range filter
        let dateRange = "";
        if (parsed.year) {
            dateRange = `&dateRange=custom&startdt=${parsed.year}-01-01&enddt=${parsed.year}-12-31`;
        }

        const url = `https://efts.sec.gov/LATEST/search-index?q=${encodeURIComponent(q)}${forms}${dateRange}&from=0&size=10`;

        const response = await fetch(url, {
            headers: { "User-Agent": USER_AGENT, "Accept": "application/json" }
        });

        if (!response.ok) {
            // Fallback: try the full-text search API
            return await searchEdgarFullText(parsed);
        }

        const data = await response.json();
        const hits = (data.hits && data.hits.hits) || [];

        return hits.map(hit => {
            const src = hit._source || {};
            return {
                title: src.display_names ? src.display_names.join(", ") : (src.file_description || `SEC Filing`),
                url: `https://www.sec.gov/Archives/edgar/data/${src.entity_id}/${src.file_name || ""}`,
                type: src.form_type || parsed.docType || "Filing",
                company: src.display_names ? src.display_names[0] : (parsed.company || ""),
                date: src.file_date || src.period_of_report || "",
                source: "SEC EDGAR"
            };
        });
    } catch (err) {
        console.error("EDGAR search error:", err.message);
        return await searchEdgarFullText(parsed);
    }
}

/**
 * Fallback: Use EDGAR full-text search (EFTS) API
 */
async function searchEdgarFullText(parsed) {
    try {
        const queryParts = [];
        if (parsed.company) queryParts.push(`"${parsed.company}"`);
        if (parsed.ticker) queryParts.push(parsed.ticker);
        if (parsed.docType && parsed.docType !== "earnings") queryParts.push(parsed.docType);

        const q = queryParts.join(" ");

        const url = `https://efts.sec.gov/LATEST/search-index?q=${encodeURIComponent(q)}&from=0&size=10`;

        const response = await fetch(url, {
            headers: { "User-Agent": USER_AGENT, "Accept": "application/json" }
        });

        if (!response.ok) return [];

        const data = await response.json();
        const hits = (data.hits && data.hits.hits) || [];

        return hits.map(hit => {
            const src = hit._source || {};
            return {
                title: src.display_names ? src.display_names.join(", ") : `SEC Filing`,
                url: `https://www.sec.gov/Archives/edgar/data/${src.entity_id || ""}/${src.file_name || ""}`,
                type: src.form_type || parsed.docType || "Filing",
                company: src.display_names ? src.display_names[0] : (parsed.company || ""),
                date: src.file_date || "",
                source: "SEC EDGAR"
            };
        });
    } catch (err) {
        console.error("EDGAR fulltext fallback error:", err.message);
        return [];
    }
}

module.exports = { searchEdgar };
