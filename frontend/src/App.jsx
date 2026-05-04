import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, ProtectedRoute } from './context/AuthContext';
import Landing from './pages/Landing';
import Auth from './pages/Auth';
import Search from './pages/Search';
import AdminFeedback from './pages/AdminFeedback';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/auth" element={<Auth />} />
          <Route
            path="/search"
            element={
              <ProtectedRoute>
                <Search />
              </ProtectedRoute>
            }
          />
          <Route path="/admin/feedback" element={<AdminFeedback />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
