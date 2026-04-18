import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';

export default function Landing() {
  const [scrolled, setScrolled] = useState(false);
  const [activeChipIndex, setActiveChipIndex] = useState(0);
  const navigate = useNavigate();

  const demoChips = [
    'Apple annual report 2023',
    'Tesla Q3 2023',
    'Reliance Industries AR 2023',
  ];

  // Scroll listener for nav
  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 60);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Chip cycling animation
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveChipIndex((prev) => (prev + 1) % demoChips.length);
    }, 2400);

    return () => clearInterval(interval);
  }, [demoChips.length]);

  // Smooth scroll handler
  const handleNavLinkClick = (e) => {
    e.preventDefault();
    const href = e.currentTarget.getAttribute('href');
    if (href.startsWith('#')) {
      const element = document.querySelector(href);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  return (
    <div>
      <Navbar scrolled={scrolled} onLinkClick={handleNavLinkClick} />

      {/* Hero Section */}
      <section className="hero">
        <div className="hero-content">
          <div className="hero-badge">
            <span className="pulse-dot"></span>
            Live search across 40+ exchanges
          </div>

          <h1 className="hero-title">
            FIND ANY <span className="accent">INVESTOR DOCUMENT</span>
          </h1>

          <p className="hero-subtitle">
            Annual reports, quarterly filings, and investor presentations from companies worldwide.
            Powered by AI. Results in under 30 seconds.
          </p>

          <div className="hero-cta">
            <Link to="/auth" className="btn-primary">
              Start Searching
            </Link>
            <a href="#coverage" className="btn-ghost" onClick={handleNavLinkClick}>
              View Coverage
            </a>
          </div>

          <div className="demo-chips">
            {demoChips.map((chip, index) => (
              <span
                key={index}
                className={`demo-chip ${index === activeChipIndex ? 'active' : ''}`}
              >
                {chip}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Stats Strip */}
      <section className="stats">
        <div className="stat">
          <span className="stat-value">40+</span>
          <span className="stat-label">Exchanges</span>
        </div>
        <div className="stat">
          <span className="stat-value">3-Tier</span>
          <span className="stat-label">Search AI</span>
        </div>
        <div className="stat">
          <span className="stat-value">15+</span>
          <span className="stat-label">Languages</span>
        </div>
        <div className="stat">
          <span className="stat-value">&lt;30s</span>
          <span className="stat-label">Avg. Search</span>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="section">
        <h2 className="section-title">Features</h2>
        <p className="section-subtitle">
          Everything you need to find investor documents quickly and accurately
        </p>

        <div className="features-grid">
          <div className="feature-card">
            <span className="feature-icon">◈</span>
            <h3 className="feature-title">Global Coverage</h3>
            <p className="feature-desc">
              Search across 40+ stock exchanges including NYSE, NASDAQ, LSE, NSE India, and more.
            </p>
          </div>

          <div className="feature-card">
            <span className="feature-icon">◉</span>
            <h3 className="feature-title">AI-Powered Search</h3>
            <p className="feature-desc">
              Three-tier AI system finds documents even when company names are ambiguous or misspelled.
            </p>
          </div>

          <div className="feature-card">
            <span className="feature-icon">◎</span>
            <h3 className="feature-title">Confidence Scoring</h3>
            <p className="feature-desc">
              Every result includes a confidence score so you know exactly how reliable the match is.
            </p>
          </div>

          <div className="feature-card">
            <span className="feature-icon">⬡</span>
            <h3 className="feature-title">Multiple Doc Types</h3>
            <p className="feature-desc">
              Find annual reports, quarterly filings, 10-K/10-Q forms, and investor presentations.
            </p>
          </div>

          <div className="feature-card">
            <span className="feature-icon">◇</span>
            <h3 className="feature-title">Fast Results</h3>
            <p className="feature-desc">
              Get your document in under 30 seconds on average. Real-time status updates as we search.
            </p>
          </div>

          <div className="feature-card">
            <span className="feature-icon">▣</span>
            <h3 className="feature-title">Direct Links</h3>
            <p className="feature-desc">
              All results link directly to official sources like SEC EDGAR or company IR pages.
            </p>
          </div>
        </div>
      </section>

      <div className="gap-border"></div>

      {/* Coverage Section */}
      <section id="coverage" className="section">
        <h2 className="section-title">Global Coverage</h2>
        <p className="section-subtitle">
          We search across major exchanges in every region
        </p>

        <div className="coverage-grid">
          <div className="region-card">
            <span className="region-flag">🇺🇸</span>
            <h3 className="region-name">United States</h3>
            <p className="region-count">NYSE, NASDAQ, SEC EDGAR</p>
          </div>

          <div className="region-card">
            <span className="region-flag">🇬🇧</span>
            <h3 className="region-name">United Kingdom</h3>
            <p className="region-count">LSE, Companies House</p>
          </div>

          <div className="region-card">
            <span className="region-flag">🇮🇳</span>
            <h3 className="region-name">India</h3>
            <p className="region-count">NSE, BSE</p>
          </div>

          <div className="region-card">
            <span className="region-flag">🇪🇺</span>
            <h3 className="region-name">Europe</h3>
            <p className="region-count">Euronext, Frankfurt, Zurich</p>
          </div>

          <div className="region-card">
            <span className="region-flag">🇨🇳</span>
            <h3 className="region-name">China & Hong Kong</h3>
            <p className="region-count">HKEX, Shanghai, Shenzhen</p>
          </div>

          <div className="region-card">
            <span className="region-flag">🇯🇵</span>
            <h3 className="region-name">Japan</h3>
            <p className="region-count">Tokyo Stock Exchange</p>
          </div>

          <div className="region-card">
            <span className="region-flag">🇦🇺</span>
            <h3 className="region-name">Australia</h3>
            <p className="region-count">ASX</p>
          </div>

          <div className="region-card">
            <span className="region-flag">🇦🇪</span>
            <h3 className="region-name">Middle East</h3>
            <p className="region-count">DFM, ADX, Tadawul</p>
          </div>
        </div>
      </section>

      <div className="gap-border"></div>

      {/* How It Works Section */}
      <section id="how" className="section">
        <h2 className="section-title">How It Works</h2>
        <p className="section-subtitle">
          Four simple steps to find any investor document
        </p>

        <div className="steps-container">
          <div className="step">
            <div className="step-number">1</div>
            <div className="step-content">
              <h3>Enter Your Query</h3>
              <p>
                Type the company name, document type, and year. Our AI understands natural language,
                so "Apple annual report 2023" works perfectly.
              </p>
            </div>
            <div className="step-connector"></div>
          </div>

          <div className="step">
            <div className="step-number">2</div>
            <div className="step-content">
              <h3>AI Entity Recognition</h3>
              <p>
                Our first AI tier identifies the company, document type, and year. It handles ambiguous
                names and even typos.
              </p>
            </div>
            <div className="step-connector"></div>
          </div>

          <div className="step">
            <div className="step-number">3</div>
            <div className="step-content">
              <h3>Multi-Source Search</h3>
              <p>
                We search across SEC EDGAR, company IR pages, and stock exchange databases simultaneously.
                Real-time status updates keep you informed.
              </p>
            </div>
            <div className="step-connector"></div>
          </div>

          <div className="step">
            <div className="step-number">4</div>
            <div className="step-content">
              <h3>Get Your Document</h3>
              <p>
                Results appear with confidence scores and direct links. Open in your browser or download
                immediately.
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="gap-border"></div>

      {/* Info Sections */}
      <section className="section">
        <div className="features-grid">
          <div className="feature-card">
            <h3 className="feature-title">ABOUT</h3>
            <p className="feature-desc" style={{ marginTop: '1.5rem', fontSize: '1.1rem' }}>
              IDF is an agentic document retrieval system built for 
              institutional investors and analysts. It finds annual reports, 
              quarterly filings, investor presentations, and earnings 
              transcripts from any company — globally.
              <br /><br />
              The AI agent identifies the company, determines the exchange, 
              locates the IR website, and retrieves the exact PDF — handling 
              name changes, delisted firms, state-owned enterprises, and 
              non-English pages automatically.
            </p>
            <div style={{ borderTop: '1px solid var(--border)', marginTop: '1.5rem' }}></div>
            <ul className="perk-list no-margin" style={{ marginTop: '1.5rem', color: 'var(--text-secondary)' }}>
              <li style={{ marginBottom: '0.8rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: 'var(--accent-light)', fontSize: '1.2rem' }}>→</span> Annual Reports
              </li>
              <li style={{ marginBottom: '0.8rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: 'var(--accent-light)', fontSize: '1.2rem' }}>→</span> Quarterly Filings  
              </li>
              <li style={{ marginBottom: '0.8rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: 'var(--accent-light)', fontSize: '1.2rem' }}>→</span> Investor Presentations
              </li>
              <li style={{ marginBottom: '0.8rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: 'var(--accent-light)', fontSize: '1.2rem' }}>→</span> Earnings Transcripts
              </li>
            </ul>
            <div className="ai-stack" style={{ 
              marginTop: '1.5rem', 
              padding: '12px', 
              borderTop: '1px solid var(--border)', 
              fontSize: '0.9rem', 
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-muted)'
            }}>
              Agentic Retrieval · Vision Extraction · Multilingual Search · 3-Tier Pipeline
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta-section">
        <h2>READY TO START SEARCHING?</h2>
        <p>Join researchers, investors, and analysts using Investor-Doc-Finder every day</p>
        <Link to="/auth" className="btn-primary">
          Get Started Now
        </Link>
      </section>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-logo">Investor-Doc-Finder</div>
        <p className="footer-credit">
          Every filing. Every exchange. Every language. Found in seconds.
        </p>
      </footer>
    </div>
  );
}
