import { Link } from 'react-router-dom';

export default function Navbar({ scrolled, onLinkClick }) {
  return (
    <nav className={`nav ${scrolled ? 'nav--scrolled' : ''}`}>
      <div className="nav-container">
        <Link to="/" className="nav-logo">Investor-Doc-Finder</Link>

        <ul className="nav-links">
          <li>
            <a href="#features" onClick={onLinkClick}>Features</a>
          </li>
          <li>
            <a href="#coverage" onClick={onLinkClick}>Coverage</a>
          </li>
          <li>
            <a href="#how" onClick={onLinkClick}>How It Works</a>
          </li>
        </ul>

        <Link to="/auth" className="nav-cta">Sign In</Link>
      </div>
    </nav>
  );
}
