import { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  updateProfile,
} from 'firebase/auth';
import { auth } from '../firebase-config';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Set up Firebase auth state listener
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      if (firebaseUser) {
        const userData = {
          uid: firebaseUser.uid,
          email: firebaseUser.email,
          displayName: firebaseUser.displayName,
          photoURL: firebaseUser.photoURL,
        };
        setUser(userData);
        sessionStorage.setItem('investor_doc_finder_user', JSON.stringify(userData));
      } else {
        setUser(null);
        sessionStorage.removeItem('investor_doc_finder_user');
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  /**
   * Sign in with email and password
   */
  const signInWithEmail = async (email, password) => {
    try {
      const userCredential = await signInWithEmailAndPassword(auth, email, password);
      const userData = {
        uid: userCredential.user.uid,
        email: userCredential.user.email,
        displayName: userCredential.user.displayName,
        photoURL: userCredential.user.photoURL,
      };

      setUser(userData);
      sessionStorage.setItem('investor_doc_finder_user', JSON.stringify(userData));
      return userData;
    } catch (error) {
      console.error('Sign in error:', error);
      throw error;
    }
  };

  /**
   * Sign up with email and password
   */
  const signUpWithEmail = async (email, password, firstName, lastName) => {
    try {
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);

      // Update display name
      const displayName = `${firstName} ${lastName}`;
      await updateProfile(userCredential.user, { displayName });

      const userData = {
        uid: userCredential.user.uid,
        email: userCredential.user.email,
        displayName: displayName,
        photoURL: userCredential.user.photoURL,
      };

      setUser(userData);
      sessionStorage.setItem('investor_doc_finder_user', JSON.stringify(userData));
      return userData;
    } catch (error) {
      console.error('Sign up error:', error);
      throw error;
    }
  };

  /**
   * Sign in with Google
   */
  const signInWithGoogle = async () => {
    try {
      const provider = new GoogleAuthProvider();
      const userCredential = await signInWithPopup(auth, provider);
      const userData = {
        uid: userCredential.user.uid,
        email: userCredential.user.email,
        displayName: userCredential.user.displayName,
        photoURL: userCredential.user.photoURL,
      };

      setUser(userData);
      sessionStorage.setItem('investor_doc_finder_user', JSON.stringify(userData));
      return userData;
    } catch (error) {
      console.error('Google sign in error:', error);
      throw error;
    }
  };

  /**
   * Sign out
   */
  const signOut = async () => {
    try {
      await firebaseSignOut(auth);
      setUser(null);
      sessionStorage.removeItem('investor_doc_finder_user');
    } catch (error) {
      console.error('Sign out error:', error);
      throw error;
    }
  };

  const value = {
    user,
    loading,
    signInWithEmail,
    signUpWithEmail,
    signInWithGoogle,
    signOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Custom hook to use auth context
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

/**
 * Protected Route component
 * Redirects to /auth if user is not authenticated
 */
export function ProtectedRoute({ children }) {
  const navigate = useNavigate();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      navigate('/auth', { replace: true });
    }
  }, [user, loading, navigate]);

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        fontSize: '18px',
        color: 'var(--text-secondary)'
      }}>
        Loading...
      </div>
    );
  }

  return user ? children : null;
}
