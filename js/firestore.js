// ──────────────────────────────────────────────
// firestore.js  –  All Firestore read / write helpers
// ──────────────────────────────────────────────
// Depends on: app.js (which exposes `db` and `auth`)

const FirestoreService = (() => {

    // ── Save a document ────────────────────────
    async function saveDocument(doc) {
        const user = auth.currentUser;
        if (!user) throw new Error('You must be signed in to save documents.');

        const docRef = db.collection('savedDocs').doc(user.uid)
            .collection('docs').doc();

        await docRef.set({
            title: doc.title || '',
            company: doc.company || '',
            ticker: doc.ticker || '',
            docType: doc.docType || '',
            url: doc.url || '',
            source: doc.source || '',
            date: doc.date || '',
            savedAt: firebase.firestore.FieldValue.serverTimestamp()
        });

        return docRef.id;
    }

    // ── Get saved documents for current user ───
    async function getSavedDocs() {
        const user = auth.currentUser;
        if (!user) return [];

        const snap = await db.collection('savedDocs').doc(user.uid)
            .collection('docs')
            .orderBy('savedAt', 'desc')
            .limit(50)
            .get();

        return snap.docs.map(d => ({ id: d.id, ...d.data() }));
    }

    // ── Delete a saved document ────────────────
    async function deleteSavedDoc(docId) {
        const user = auth.currentUser;
        if (!user) throw new Error('You must be signed in.');

        await db.collection('savedDocs').doc(user.uid)
            .collection('docs').doc(docId)
            .delete();
    }

    // ── Record a search in history ─────────────
    async function recordSearch(query, resultsCount) {
        const user = auth.currentUser;
        if (!user) return;                       // silent no-op for anonymous users

        const ref = db.collection('searchHistory').doc(user.uid)
            .collection('searches').doc();

        await ref.set({
            query,
            resultsCount: resultsCount || 0,
            searchedAt: firebase.firestore.FieldValue.serverTimestamp()
        });
    }

    // ── Get search history ─────────────────────
    async function getSearchHistory() {
        const user = auth.currentUser;
        if (!user) return [];

        const snap = await db.collection('searchHistory').doc(user.uid)
            .collection('searches')
            .orderBy('searchedAt', 'desc')
            .limit(20)
            .get();

        return snap.docs.map(d => ({ id: d.id, ...d.data() }));
    }

    // ── Create / update user profile ───────────
    async function ensureUserProfile() {
        const user = auth.currentUser;
        if (!user) return;

        const userRef = db.collection('users').doc(user.uid);
        const snap = await userRef.get();

        if (!snap.exists) {
            await userRef.set({
                displayName: user.displayName || '',
                email: user.email || '',
                photoURL: user.photoURL || '',
                createdAt: firebase.firestore.FieldValue.serverTimestamp()
            });
        }
    }

    // Public API
    return {
        saveDocument,
        getSavedDocs,
        deleteSavedDoc,
        recordSearch,
        getSearchHistory,
        ensureUserProfile
    };
})();
