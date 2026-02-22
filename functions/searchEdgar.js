// ──────────────────────────────────────────────
// searchEdgar.js  –  SEC EDGAR Submissions API
// ──────────────────────────────────────────────
// Fetches ACTUAL company filings with PDF links when available.
// 1. Ticker → CIK (via company_tickers.json)
// 2. CIK → Filings (via Submissions API)
// 3. For each filing → check index.json for PDF documents

const fetch = require("node-fetch");

const USER_AGENT = "InvestorDocFinder/1.0 (contact@investordocfinder.com)";

// ── Ticker → CIK cache ──
let tickerMap = null;

async function loadTickerMap() {
    if (tickerMap) return tickerMap;
    const res = await fetch("https://www.sec.gov/files/company_tickers.json", {
        headers: { "User-Agent": USER_AGENT }
    });
    if (!res.ok) throw new Error("Failed to load SEC ticker map");
    const data = await res.json();
    tickerMap = {};
    for (const key of Object.keys(data)) {
        const entry = data[key];
        tickerMap[(entry.ticker || "").toUpperCase()] = {
            cik: entry.cik_str,
            name: entry.title
        };
    }
    return tickerMap;
}

async function findCIK(ticker) {
    const map = await loadTickerMap();
    return map[ticker.toUpperCase()] || null;
}

/**
 * For a given filing, fetch the filing index and find a PDF document.
 * Returns the PDF URL if found, otherwise returns the original URL.
 */
async function findPdfUrl(cik, accessionClean, originalUrl) {
    try {
        // Filing index JSON: lists all documents in the filing
        const accessionDashes = accessionClean.replace(
            /^(\d{10})(\d{2})(\d+)$/, '$1-$2-$3'
        );
        const indexUrl = `https://www.sec.gov/Archives/edgar/data/${cik}/${accessionClean}/index.json`;

        const res = await fetch(indexUrl, {
            headers: { "User-Agent": USER_AGENT, "Accept": "application/json" }
        });

        if (!res.ok) return originalUrl;

        const data = await res.json();
        const items = (data.directory && data.directory.item) || [];

        // Look for PDF files (prefer larger PDFs — they're the actual report)
        const pdfs = items
            .filter(item => item.name && item.name.toLowerCase().endsWith('.pdf'))
            .sort((a, b) => (parseInt(b.size) || 0) - (parseInt(a.size) || 0));

        if (pdfs.length > 0) {
            // Return the largest PDF (usually the full filing)
            return `https://www.sec.gov/Archives/edgar/data/${cik}/${accessionClean}/${pdfs[0].name}`;
        }

        return originalUrl;
    } catch (err) {
        return originalUrl;
    }
}

/**
 * Main: Search SEC EDGAR for actual company filings with PDF links.
 */
async function searchEdgar(parsed) {
    try {
        if (!parsed.ticker) {
            console.log("   EDGAR: No ticker found, skipping.");
            return [];
        }

        // Step 1: Resolve ticker → CIK
        const company = await findCIK(parsed.ticker);
        if (!company) {
            console.log(`   EDGAR: Ticker "${parsed.ticker}" not found.`);
            return [];
        }

        const cik = String(company.cik);
        const cikPadded = cik.padStart(10, "0");
        const companyName = company.name;
        console.log(`   EDGAR: Found ${companyName} (CIK: ${cik})`);

        // Step 2: Fetch filings list
        const subUrl = `https://data.sec.gov/submissions/CIK${cikPadded}.json`;
        const res = await fetch(subUrl, {
            headers: { "User-Agent": USER_AGENT, "Accept": "application/json" }
        });
        if (!res.ok) return [];

        const data = await res.json();
        const recent = data.filings && data.filings.recent;
        if (!recent) return [];

        // Step 3: Filter filings by form type and year
        const targetForm = (parsed.docType || "").toUpperCase();
        const targetYear = parsed.year || "";
        const matchedFilings = [];

        for (let i = 0; i < recent.form.length && matchedFilings.length < 5; i++) {
            const form = recent.form[i];
            const filingDate = recent.filingDate[i] || "";
            const accession = recent.accessionNumber[i] || "";
            const primaryDoc = recent.primaryDocument[i] || "";
            const primaryDesc = recent.primaryDocDescription[i] || "";

            // Filter by form type — EXACT match only (allow amendments too)
            if (targetForm && targetForm !== "EARNINGS") {
                const formUpper = form.toUpperCase().replace(/\s/g, "");
                const target = targetForm.replace(/\s/g, "");
                // Match exact form or amendment (e.g. 10-K matches 10-K and 10-K/A)
                if (formUpper !== target && formUpper !== target + "/A") continue;
            }

            // Filter by year
            if (targetYear && !filingDate.startsWith(targetYear)) continue;

            const accessionClean = accession.replace(/-/g, "");
            const htmlUrl = `https://www.sec.gov/Archives/edgar/data/${cik}/${accessionClean}/${primaryDoc}`;

            matchedFilings.push({
                form, filingDate, accessionClean, primaryDoc, primaryDesc, htmlUrl,
                companyName, cik
            });
        }

        // Step 4: For each matched filing, check for PDF version (in parallel)
        console.log(`   EDGAR: Checking ${matchedFilings.length} filings for PDFs...`);

        const results = await Promise.all(matchedFilings.map(async (filing) => {
            const pdfUrl = await findPdfUrl(filing.cik, filing.accessionClean, filing.htmlUrl);
            const isPdf = pdfUrl.toLowerCase().endsWith('.pdf');

            return {
                title: `${filing.companyName} — ${filing.form} (${filing.filingDate})`,
                url: pdfUrl,
                type: filing.form,
                company: filing.companyName,
                ticker: parsed.ticker,
                date: filing.filingDate,
                source: "SEC EDGAR",
                description: isPdf
                    ? `📄 PDF — ${filing.primaryDesc || filing.form + ' filing'}`
                    : `📃 HTML — ${filing.primaryDesc || filing.form + ' filing'}`,
                format: isPdf ? "PDF" : "HTML"
            };
        }));

        // If no results with filters, try without year filter
        if (results.length === 0 && targetForm) {
            console.log(`   EDGAR: No ${targetForm} in ${targetYear}, trying all years...`);
            const fallback = [];
            for (let i = 0; i < recent.form.length && fallback.length < 3; i++) {
                const form = recent.form[i];
                const formUpper = form.toUpperCase().replace(/\s/g, "");
                const target = targetForm.replace(/\s/g, "");
                if (formUpper !== target && formUpper !== target + "/A") continue;

                const accessionClean = recent.accessionNumber[i].replace(/-/g, "");
                const primaryDoc = recent.primaryDocument[i] || "";
                const htmlUrl = `https://www.sec.gov/Archives/edgar/data/${cik}/${accessionClean}/${primaryDoc}`;
                const pdfUrl = await findPdfUrl(cik, accessionClean, htmlUrl);
                const isPdf = pdfUrl.toLowerCase().endsWith('.pdf');

                fallback.push({
                    title: `${companyName} — ${form} (${recent.filingDate[i]})`,
                    url: pdfUrl,
                    type: form,
                    company: companyName,
                    ticker: parsed.ticker,
                    date: recent.filingDate[i],
                    source: "SEC EDGAR",
                    description: isPdf
                        ? `📄 PDF — ${recent.primaryDocDescription[i] || form + ' filing'}`
                        : `📃 HTML — ${recent.primaryDocDescription[i] || form + ' filing'}`,
                    format: isPdf ? "PDF" : "HTML"
                });
            }
            return fallback;
        }

        console.log(`   EDGAR: Returning ${results.length} results (${results.filter(r => r.format === 'PDF').length} PDFs)`);
        return results;

    } catch (err) {
        console.error("   EDGAR search error:", err.message);
        return [];
    }
}

module.exports = { searchEdgar };
