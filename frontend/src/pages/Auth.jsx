import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Auth() {
  const [activeTab, setActiveTab] = useState('signin');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [passwordStrength, setPasswordStrength] = useState(0);

  // Form states
  const [signInForm, setSignInForm] = useState({
    email: '',
    password: '',
  });

  const [signUpForm, setSignUpForm] = useState({
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const navigate = useNavigate();
  const { signInWithEmail, signUpWithEmail, signInWithGoogle } = useAuth();

  // Calculate password strength
  useEffect(() => {
    const pwd = signUpForm.password;
    if (!pwd) {
      setPasswordStrength(0);
      return;
    }

    let score = 0;
    if (pwd.length >= 8) score++;
    if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++;
    if (/\d/.test(pwd)) score++;
    if (/[^a-zA-Z\d]/.test(pwd)) score++;

    setPasswordStrength(score);
  }, [signUpForm.password]);

  const handleSignIn = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await signInWithEmail(signInForm.email, signInForm.password);
      navigate('/search');
    } catch (err) {
      setError(err.message || 'Failed to sign in');
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e) => {
    e.preventDefault();
    setError('');

    // Validate passwords match
    if (signUpForm.password !== signUpForm.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    // Validate password strength
    if (passwordStrength < 2) {
      setError('Please use a stronger password');
      return;
    }

    setLoading(true);

    try {
      await signUpWithEmail(
        signUpForm.email,
        signUpForm.password,
        signUpForm.firstName,
        signUpForm.lastName
      );
      navigate('/search');
    } catch (err) {
      setError(err.message || 'Failed to create account');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError('');
    setLoading(true);

    try {
      await signInWithGoogle();
      navigate('/search');
    } catch (err) {
      setError(err.message || 'Failed to sign in with Google');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="split-panel">
        {/* Left Panel */}
        <div className="auth-left-panel">
          <div>
            <div className="auth-logo">Investor-Doc-Finder</div>
            <h2 className="auth-left-title">
              Find any investor document in under 30 seconds
            </h2>

            <ul className="perk-list">
              <li className="perk-item">
                <span className="perk-icon">✓</span>
                <div className="perk-text">
                  <h4>40+ Global Exchanges</h4>
                  <p>Search across NYSE, NASDAQ, LSE, NSE, and more</p>
                </div>
              </li>

              <li className="perk-item">
                <span className="perk-icon">✓</span>
                <div className="perk-text">
                  <h4>AI-Powered Search</h4>
                  <p>Three-tier AI finds documents even with typos</p>
                </div>
              </li>

              <li className="perk-item">
                <span className="perk-icon">✓</span>
                <div className="perk-text">
                  <h4>Confidence Scoring</h4>
                  <p>Know exactly how reliable each result is</p>
                </div>
              </li>

              <li className="perk-item">
                <span className="perk-icon">✓</span>
                <div className="perk-text">
                  <h4>Direct Links</h4>
                  <p>All results link to official sources</p>
                </div>
              </li>
            </ul>
          </div>

          <div className="auth-footer">
            © 2024 Investor-Doc-Finder • Powered by Claude 4.6
          </div>
        </div>

        {/* Right Panel */}
        <div className="auth-right-panel">
          <div className="auth-card">
            {/* Tab Switcher */}
            <div className="tab-switcher">
              <button
                className={`tab-btn ${activeTab === 'signin' ? 'active' : ''}`}
                onClick={() => {
                  setActiveTab('signin');
                  setError('');
                }}
              >
                Sign In
              </button>
              <button
                className={`tab-btn ${activeTab === 'signup' ? 'active' : ''}`}
                onClick={() => {
                  setActiveTab('signup');
                  setError('');
                }}
              >
                Sign Up
              </button>
            </div>

            {/* Sign In Panel */}
            <div className={`tab-panel ${activeTab === 'signin' ? 'active' : ''}`}>
              <form onSubmit={handleSignIn}>
                <div className="form-group">
                  <label htmlFor="signin-email">Email</label>
                  <input
                    type="email"
                    id="signin-email"
                    placeholder="you@example.com"
                    value={signInForm.email}
                    onChange={(e) =>
                      setSignInForm({ ...signInForm, email: e.target.value })
                    }
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="signin-password">Password</label>
                  <input
                    type="password"
                    id="signin-password"
                    placeholder="••••••••"
                    value={signInForm.password}
                    onChange={(e) =>
                      setSignInForm({ ...signInForm, password: e.target.value })
                    }
                    required
                  />
                </div>

                {error && <div className="form-error visible">{error}</div>}

                <button
                  type="submit"
                  className={`submit-btn ${loading ? 'loading' : ''}`}
                  disabled={loading}
                >
                  <span className="btn-text">Sign In</span>
                  <div className="spinner"></div>
                </button>
              </form>

              <div className="divider">or</div>

              <button className="google-btn" onClick={handleGoogleSignIn} disabled={loading}>
                <svg className="google-icon" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
                Continue with Google
              </button>
            </div>

            {/* Sign Up Panel */}
            <div className={`tab-panel ${activeTab === 'signup' ? 'active' : ''}`}>
              <form onSubmit={handleSignUp}>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="signup-firstname">First Name</label>
                    <input
                      type="text"
                      id="signup-firstname"
                      placeholder="John"
                      value={signUpForm.firstName}
                      onChange={(e) =>
                        setSignUpForm({ ...signUpForm, firstName: e.target.value })
                      }
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="signup-lastname">Last Name</label>
                    <input
                      type="text"
                      id="signup-lastname"
                      placeholder="Doe"
                      value={signUpForm.lastName}
                      onChange={(e) =>
                        setSignUpForm({ ...signUpForm, lastName: e.target.value })
                      }
                      required
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="signup-email">Email</label>
                  <input
                    type="email"
                    id="signup-email"
                    placeholder="you@example.com"
                    value={signUpForm.email}
                    onChange={(e) =>
                      setSignUpForm({ ...signUpForm, email: e.target.value })
                    }
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="signup-password">Password</label>
                  <div className="password-strength-wrapper">
                    <input
                      type="password"
                      id="signup-password"
                      placeholder="••••••••"
                      value={signUpForm.password}
                      onChange={(e) =>
                        setSignUpForm({ ...signUpForm, password: e.target.value })
                      }
                      required
                    />
                    <div className="password-strength-bar">
                      <div className={`password-strength-fill strength-${passwordStrength}`}></div>
                    </div>
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="signup-confirm">Confirm Password</label>
                  <input
                    type="password"
                    id="signup-confirm"
                    placeholder="••••••••"
                    value={signUpForm.confirmPassword}
                    onChange={(e) =>
                      setSignUpForm({ ...signUpForm, confirmPassword: e.target.value })
                    }
                    required
                  />
                </div>

                {error && <div className="form-error visible">{error}</div>}

                <button
                  type="submit"
                  className={`submit-btn ${loading ? 'loading' : ''}`}
                  disabled={loading}
                >
                  <span className="btn-text">Create Account</span>
                  <div className="spinner"></div>
                </button>
              </form>

              <div className="divider">or</div>

              <button className="google-btn" onClick={handleGoogleSignIn} disabled={loading}>
                <svg className="google-icon" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
                Continue with Google
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
