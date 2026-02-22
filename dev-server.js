// ──────────────────────────────────────────────
// dev-server.js  –  Local development server
// ──────────────────────────────────────────────
// Serves the frontend on http://localhost:3000
// AND runs Cloud Functions logic at /api/searchDocuments
// so you can test the full flow locally.
//
// Usage:   node dev-server.js
// Then:    open http://localhost:3000

const http = require("http");
const fs = require("fs");
const path = require("path");
const url = require("url");

// Load environment variables from .env
const envPath = path.join(__dirname, ".env");
if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, "utf-8");
    envContent.split("\n").forEach(line => {
        const match = line.match(/^\s*([\w]+)\s*=\s*"?([^"]*)"?\s*$/);
        if (match) process.env[match[1]] = match[2];
    });
}

// Import Cloud Functions logic
const { parseQuery } = require("./functions/parseQuery");
const { searchEdgar } = require("./functions/searchEdgar");
const { searchSerper } = require("./functions/searchSerper");

const PORT = process.env.PORT || 3000;

// MIME types
const MIME = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
};

const server = http.createServer(async (req, res) => {
    const parsed = url.parse(req.url, true);
    const pathname = parsed.pathname;

    // ── API: Search Documents ──────────────────
    if (pathname === "/api/searchDocuments") {
        res.setHeader("Access-Control-Allow-Origin", "*");
        res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
        res.setHeader("Content-Type", "application/json");

        if (req.method === "OPTIONS") { res.writeHead(200); res.end(); return; }

        const query = parsed.query.q || "";
        if (!query) {
            res.writeHead(400);
            res.end(JSON.stringify({ error: "Missing query parameter 'q'." }));
            return;
        }

        try {
            console.log(`\n🔍  Searching: "${query}"`);
            const parsedQuery = parseQuery(query);
            console.log("   Parsed:", JSON.stringify(parsedQuery));

            const serperKey = process.env.SERPER_API_KEY || "";

            const [edgarResults, serperResults] = await Promise.all([
                parsedQuery.isUS ? searchEdgar(parsedQuery) : Promise.resolve([]),
                searchSerper(parsedQuery, serperKey)
            ]);

            console.log(`   EDGAR: ${edgarResults.length} results`);
            console.log(`   Serper: ${serperResults.length} results`);

            // Merge & deduplicate — Serper first (has PDFs)
            const seen = new Set();
            const allResults = [];
            for (const doc of [...serperResults, ...edgarResults]) {
                if (!doc.url || seen.has(doc.url)) continue;
                seen.add(doc.url);
                allResults.push(doc);
            }

            // Filter: ONLY show PDF links
            const pdfResults = allResults.filter(r => r.url.toLowerCase().endsWith('.pdf'));
            const htmlResults = allResults.filter(r => !r.url.toLowerCase().endsWith('.pdf'));

            let results;
            if (pdfResults.length > 0) {
                results = pdfResults;
                console.log(`   ✅ Total: ${results.length} PDF results (${htmlResults.length} HTML filtered out)`);
            } else {
                results = htmlResults.map(r => ({
                    ...r,
                    description: "⚠️ No PDF available — " + (r.description || "HTML document")
                }));
                console.log(`   ⚠️ No PDFs found, showing ${results.length} HTML results`);
            }

            res.writeHead(200);
            res.end(JSON.stringify({ query, parsed: parsedQuery, count: results.length, results }));
        } catch (err) {
            console.error("   ❌ Error:", err.message);
            res.writeHead(500);
            res.end(JSON.stringify({ error: "Internal server error." }));
        }
        return;
    }

    // ── Static file server ─────────────────────
    let filePath = pathname === "/" ? "/index.html" : pathname;
    filePath = path.join(__dirname, filePath);

    // Security: prevent directory traversal
    if (!filePath.startsWith(__dirname)) {
        res.writeHead(403); res.end("Forbidden"); return;
    }

    const ext = path.extname(filePath);
    const contentType = MIME[ext] || "application/octet-stream";

    fs.readFile(filePath, (err, data) => {
        if (err) {
            if (err.code === "ENOENT") {
                res.writeHead(404);
                res.end("Not Found");
            } else {
                res.writeHead(500);
                res.end("Server Error");
            }
            return;
        }
        res.writeHead(200, { "Content-Type": contentType });
        res.end(data);
    });
});

server.listen(PORT, () => {
    console.log(`\n${"═".repeat(50)}`);
    console.log(`  🚀  Investor Doc Finder – Dev Server`);
    console.log(`${"═".repeat(50)}`);
    console.log(`  Frontend:  http://localhost:${PORT}`);
    console.log(`  Search API: http://localhost:${PORT}/api/searchDocuments?q=...`);
    console.log(`  Serper Key: ${process.env.SERPER_API_KEY ? "✅ Loaded" : "❌ Missing"}`);
    console.log(`${"═".repeat(50)}\n`);
});
