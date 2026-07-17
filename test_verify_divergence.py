"""
Regression tests for verify.py's company-identity DIVERGENCE gate on the
`company_site` source path.

Background: the divergence gate in verify._check_text is the AMBIPAR/MBAPL
protection — when the resolver overrides the requested company to a *different*,
real company, the document must still name the REQUESTED company (raw_company)
or be rejected, even though it genuinely names the RESOLVED company. The gate is
source-agnostic (company_site takes the non-trusted branch), but had NO committed
regression coverage for company_site — this file adds it.

Fully offline: representative annual-report front-matter text is fed straight to
_check_text; no network, no PDF, no live fetch. The gate was ALSO verified live
against the real Ambipar company-site report during investigation (2026-07-17,
verify._verify_pdf(source="company_site")); this test locks that behaviour in
deterministically so it can't silently regress.
"""

import verify

# Representative extracted text of a company-site annual report's front matter,
# modelled on Ambipar's 2022 integrated report (which passes verification live):
# it names the company, states its fiscal year, and carries genuine financial-
# statement content, so the MATCHING case clears every downstream gate too.
_DOC = (
    "AMBIPAR Integrated Report 2022. "
    "Consolidated financial statements for the year ended December 31, 2022. "
    "Balance sheet. Income statement. Statement of comprehensive income. "
    "Independent auditor's report to the shareholders of Ambipar."
)


def _check(raw_company, company_name="Ambipar"):
    """Run the real verify gate on the company_site path with the given intent."""
    intent = {
        "company_name": company_name,
        "raw_company": raw_company,
        "fy_candidates": ["2022"],
        "country": "BR",
        "cik": None,
    }
    return verify._check_text(
        _DOC, intent, "text/html", is_pdf=False, source="company_site",
    )


def test_company_site_matching_company_passes():
    """Normal resolution (requested == resolved): the divergence gate is a no-op
    and a genuine company-site report verifies."""
    r = _check(raw_company="Ambipar")
    assert r["ok"] is True, r


def test_company_site_divergent_reliance_rejected():
    """AMBIPAR/MBAPL class: requested 'Reliance Industries' but the document is
    Ambipar's — they share no distinctive token, so the divergence gate must
    reject even though the doc genuinely names the resolved company."""
    r = _check(raw_company="Reliance Industries")
    assert r["ok"] is False
    assert "does not match the requested company" in r["reason"], r


def test_company_site_divergent_tullow_rejected():
    """Second divergent case (requested 'Tullow Oil'): same rejection, confirming
    the gate is not Reliance-specific."""
    r = _check(raw_company="Tullow Oil")
    assert r["ok"] is False
    assert "does not match the requested company" in r["reason"], r
