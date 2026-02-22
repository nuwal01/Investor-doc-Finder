// ──────────────────────────────────────────────
// app.js  –  Shared initialisation & helpers
// ──────────────────────────────────────────────

// Firebase project config (from Firebase Console → Project Settings → Your apps)
const firebaseConfig = {
    apiKey: "AIzaSyCAaWur6dOtV4CuoPqJpOqp4zs3GWap9E8",
    authDomain: "investor-doc-finder.firebaseapp.com",
    projectId: "investor-doc-finder",
    storageBucket: "investor-doc-finder.firebasestorage.app",
    messagingSenderId: "615109960564",
    appId: "1:615109960564:web:904b07e37729cb068ac221",
    measurementId: "G-61DVJJB6R6"
};

// Initialise Firebase (compat SDK loaded via CDN)
firebase.initializeApp(firebaseConfig);

// Expose commonly used services
const auth = firebase.auth();
const db = firebase.firestore();

// ──────────────────────────────────────────────
// UI helpers available to every page
// ──────────────────────────────────────────────

/** Show / hide elements that require authentication */
function updateNavForAuth(user) {
    // Elements marked .auth-required  → show when logged in
    document.querySelectorAll('.auth-required').forEach(el => {
        el.style.display = user ? '' : 'none';
        if (user) el.classList.remove('hidden');
        else el.classList.add('hidden');
    });

    // Login button → hide when logged in
    const loginBtn = document.getElementById('loginBtn');
    if (loginBtn) loginBtn.style.display = user ? 'none' : '';

    // Logout button → show when logged in
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.style.display = user ? '' : 'none';
        if (user) logoutBtn.classList.remove('hidden');
        else logoutBtn.classList.add('hidden');
    }

    // Dashboard username
    const userName = document.getElementById('userName');
    if (userName && user) {
        userName.textContent = user.displayName || user.email || 'Investor';
    }
}

// Listen for auth state changes on every page
firebase.auth().onAuthStateChanged(user => {
    updateNavForAuth(user);
});

// Logout handler (button exists on most pages)
const logoutBtn = document.getElementById('logoutBtn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
        await firebase.auth().signOut();
        window.location.href = 'index.html';
    });
}

// ──────────────────────────────────────────────
// Toast notification helper (used by save buttons)
// ──────────────────────────────────────────────
function showToast(message) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
}
