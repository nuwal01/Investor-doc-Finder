// ──────────────────────────────────────────────
// auth.js  –  Login / Sign-up page logic
// ──────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const googleBtn = document.getElementById('googleSignInBtn');
    const emailForm = document.getElementById('emailLoginForm');
    const toggleLink = document.getElementById('toggleSignUp');
    const authError = document.getElementById('authError');
    const submitBtn = emailForm ? emailForm.querySelector('button[type="submit"]') : null;

    let isSignUp = false;   // false = Sign In mode, true = Sign Up mode

    // If user is already logged in, redirect to dashboard
    firebase.auth().onAuthStateChanged(user => {
        if (user) window.location.href = 'dashboard.html';
    });

    // ── Google Sign-In ─────────────────────────
    if (googleBtn) {
        googleBtn.addEventListener('click', async () => {
            try {
                const provider = new firebase.auth.GoogleAuthProvider();
                await firebase.auth().signInWithPopup(provider);
                // onAuthStateChanged will redirect
            } catch (err) {
                showError(err.message);
            }
        });
    }

    // ── Email / Password ──────────────────────
    if (emailForm) {
        emailForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value;

            if (!email || !password) return showError('Please fill in all fields.');

            try {
                if (isSignUp) {
                    await firebase.auth().createUserWithEmailAndPassword(email, password);
                } else {
                    await firebase.auth().signInWithEmailAndPassword(email, password);
                }
                // onAuthStateChanged will redirect
            } catch (err) {
                showError(friendlyError(err.code));
            }
        });
    }

    // ── Toggle Sign In ↔ Sign Up ──────────────
    if (toggleLink) {
        toggleLink.addEventListener('click', (e) => {
            e.preventDefault();
            isSignUp = !isSignUp;
            toggleLink.textContent = isSignUp ? 'Sign In' : 'Sign Up';
            if (submitBtn) submitBtn.textContent = isSignUp ? 'Create Account' : 'Sign In';
            // Update helper text
            const parent = toggleLink.closest('p');
            if (parent) {
                parent.childNodes[0].textContent = isSignUp
                    ? 'Already have an account? '
                    : "Don't have an account? ";
            }
            hideError();
        });
    }

    // ── Helpers ────────────────────────────────
    function showError(msg) {
        if (!authError) return;
        authError.textContent = msg;
        authError.style.display = 'block';
    }

    function hideError() {
        if (!authError) return;
        authError.textContent = '';
        authError.style.display = 'none';
    }

    function friendlyError(code) {
        const map = {
            'auth/user-not-found': 'No account found with that email.',
            'auth/wrong-password': 'Incorrect password.',
            'auth/email-already-in-use': 'That email is already registered.',
            'auth/weak-password': 'Password must be at least 6 characters.',
            'auth/invalid-email': 'Please enter a valid email address.',
            'auth/too-many-requests': 'Too many attempts. Please try again later.',
        };
        return map[code] || 'Something went wrong. Please try again.';
    }
});
