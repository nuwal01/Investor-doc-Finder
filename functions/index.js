// ──────────────────────────────────────────────
// functions/index.js  –  Cloud Functions entry point
// ──────────────────────────────────────────────

const functions = require("firebase-functions");
const admin = require("firebase-admin");
const cors = require("cors");

const { parseQuery } = require("./parseQuery");
const { searchEdgar } = require("./searchEdgar");
const { searchSerper } = require("./searchSerper");

// Initialise Firebase Admin
admin.initializeApp();
const db = admin.firestore();

// CORS middleware (allow all origins during development)
const corsHandler = cors({ origin: true });

// ─────────────────────────────────────────────────
// 1.  searchDocuments  –  main search Cloud Function
// ─────────────────────────────────────────────────
exports.searchDocuments = functions.https.onRequest((req, res) => {
    corsHandler(req, res, async () => {
        try {
            const query = req.query.q || req.body.q || "";
            if (!query) {
                return res.status(400).json({ error: "Missing query parameter 'q'." });
            }

            // Parse the natural-language query
            const parsed = parseQuery(query);

            // Run searches in parallel
            const serperKey = process.env.SERPER_API_KEY ||
                (functions.config().serper && functions.config().serper.key) || "";

            const [edgarResults, serperResults] = await Promise.all([
                parsed.isUS ? searchEdgar(parsed) : Promise.resolve([]),
                searchSerper(parsed, serperKey)
            ]);

            // Merge, de-duplicate by URL
            const seen = new Set();
            const allResults = [];

            // Serper first (likely has PDFs), then EDGAR
            for (const doc of [...serperResults, ...edgarResults]) {
                if (!doc.url || seen.has(doc.url)) continue;
                seen.add(doc.url);
                allResults.push(doc);
            }

            // Separate PDFs from HTML
            const pdfResults = allResults.filter(r => r.url.toLowerCase().endsWith('.pdf'));
            const htmlResults = allResults.filter(r => !r.url.toLowerCase().endsWith('.pdf'));

            // Show ONLY PDFs. If none found, fall back to HTML with a note.
            let results;
            if (pdfResults.length > 0) {
                results = pdfResults;
            } else {
                // No PDFs found — show HTML results but mark them
                results = htmlResults.map(r => ({
                    ...r,
                    description: "⚠️ No PDF available — " + (r.description || "HTML document")
                }));
            }

            return res.status(200).json({
                query: query,
                parsed: parsed,
                count: results.length,
                results: results
            });
        } catch (err) {
            console.error("searchDocuments error:", err);
            return res.status(500).json({ error: "Internal server error." });
        }
    });
});

// ─────────────────────────────────────────────────
// 2.  saveDocument  –  Save a doc to Firestore
// ─────────────────────────────────────────────────
exports.saveDocument = functions.https.onRequest((req, res) => {
    corsHandler(req, res, async () => {
        try {
            // Verify Firebase Auth token
            const authHeader = req.headers.authorization;
            if (!authHeader || !authHeader.startsWith("Bearer ")) {
                return res.status(401).json({ error: "Unauthorized." });
            }

            const idToken = authHeader.split("Bearer ")[1];
            const decoded = await admin.auth().verifyIdToken(idToken);
            const uid = decoded.uid;

            const { title, company, ticker, docType, url, date, source } = req.body;

            if (!url) return res.status(400).json({ error: "Missing document URL." });

            const docRef = db.collection("savedDocs").doc(uid)
                .collection("docs").doc();

            await docRef.set({
                title: title || "",
                company: company || "",
                ticker: ticker || "",
                docType: docType || "",
                url: url,
                date: date || "",
                source: source || "",
                savedAt: admin.firestore.FieldValue.serverTimestamp()
            });

            return res.status(200).json({ id: docRef.id, message: "Document saved." });
        } catch (err) {
            console.error("saveDocument error:", err);
            return res.status(500).json({ error: "Failed to save document." });
        }
    });
});

// ─────────────────────────────────────────────────
// 3.  getHistory  –  Get search history for user
// ─────────────────────────────────────────────────
exports.getHistory = functions.https.onRequest((req, res) => {
    corsHandler(req, res, async () => {
        try {
            const authHeader = req.headers.authorization;
            if (!authHeader || !authHeader.startsWith("Bearer ")) {
                return res.status(401).json({ error: "Unauthorized." });
            }

            const idToken = authHeader.split("Bearer ")[1];
            const decoded = await admin.auth().verifyIdToken(idToken);
            const uid = decoded.uid;

            const snap = await db.collection("searchHistory").doc(uid)
                .collection("searches")
                .orderBy("searchedAt", "desc")
                .limit(20)
                .get();

            const history = snap.docs.map(d => ({ id: d.id, ...d.data() }));

            return res.status(200).json({ history });
        } catch (err) {
            console.error("getHistory error:", err);
            return res.status(500).json({ error: "Failed to load history." });
        }
    });
});
