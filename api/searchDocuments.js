const { parseQuery } = require("../functions/parseQuery");
const { searchEdgar } = require("../functions/searchEdgar");
const { searchSerper } = require("../functions/searchSerper");

module.exports = async (req, res) => {
    // Enable CORS
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET,OPTIONS");

    if (req.method === "OPTIONS") {
        return res.status(200).end();
    }

    try {
        const query = req.query.q || "";
        if (!query) {
            return res.status(400).json({ error: "Missing query parameter 'q'" });
        }

        console.log(`[Vercel API] Searching for: "${query}"`);

        // 1. Parse natural language
        const parsed = parseQuery(query);
        console.log(`   Parsed:`, parsed);

        // 2. Run searches in parallel
        const [edgarResults, serperResults] = await Promise.all([
            searchEdgar(parsed),
            searchSerper(parsed),
        ]);

        // 3. Merge results (prioritize Serper for PDFs)
        let allResults = [];
        const seenUrls = new Set();

        [...serperResults, ...edgarResults].forEach((r) => {
            if (!r || !r.url) return;
            const normalizedUrl = r.url.split('#')[0].split('?')[0]; // remove hash/query for dedupe
            if (!seenUrls.has(normalizedUrl)) {
                seenUrls.add(normalizedUrl);
                allResults.push(r);
            }
        });

        // 4. Filter for PDFs exclusively
        const pdfResults = allResults.filter(r => r.url.toLowerCase().endsWith('.pdf'));
        const htmlResults = allResults.filter(r => !r.url.toLowerCase().endsWith('.pdf'));

        let finalResults;
        if (pdfResults.length > 0) {
            finalResults = pdfResults;
            console.log(`   ✅ Returning ${finalResults.length} PDF results`);
        } else {
            // Fallback to HTML but flag heavily
            finalResults = htmlResults.map(r => ({
                ...r,
                description: "⚠️ No PDF available — " + (r.description || "HTML document")
            }));
            console.log(`   ⚠️ No PDFs, returning ${finalResults.length} HTML results`);
        }

        res.status(200).json({ results: finalResults });

    } catch (error) {
        console.error("Vercel Search Error:", error);
        res.status(500).json({ error: error.message });
    }
};
