"""
SEC EDGAR source for annual filings: 10-K (US domestic), 20-F (foreign
private issuers), 40-F (Canadian issuers under MJDS).

EDGAR API notes:
- Submissions JSON (no key): https://data.sec.gov/submissions/CIK{10-digit-cik}.json
- REQUIRES a descriptive User-Agent header — bare/missing UA returns 403.
- Filing document URL: https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{primary_doc}
- CIK must be zero-padded to 10 digits in the URL.
- Rate limit: ~10 req/s; we never hammer it in this source.

Form fallback: the submissions JSON lists every recent filing regardless of
form type, so one API call serves all form queries. We scan for a 10-K first;
zero matches → rescan the same list for a 20-F (ASML, Turkcell and other
foreign private issuers file 20-F instead of 10-K); zero again → rescan for a
40-F (Canadian MJDS filers such as Shopify). The candidate note always names
the form type found so downstream consumers can tell a 20-F from a 10-K.

Primary document is usually XBRL-tagged HTML (.htm), NOT a PDF.
This source returns HTML candidates; verify.py handles them with its HTML fallback.
If the filing happens to include a PDF, it is listed first (preferred).
"""

import logging
import os
import shutil
from pathlib import Path

import pdfkit
import requests
from bs4 import BeautifulSoup

from .base import Candidate

logger = logging.getLogger(__name__)

DATA_API = "https://data.sec.gov"
WWW = "https://www.sec.gov"

# Converted EDGAR PDFs persist here (project root, alongside cache.db) so a cache
# hit reuses the file instead of paying the ~45s reconversion. The previous temp
# location (%TEMP%) is cleared on reboot / by cleanup tools, which made every
# post-reboot cache hit reconvert the largest filings.
_PDF_CACHE_DIR = Path(__file__).resolve().parent.parent / "converted_pdfs"

# EDGAR rejects requests without a meaningful User-Agent.
EDGAR_HEADERS = {
    "User-Agent": "IDF research trade@ostwal.in",
    "Accept-Encoding": "gzip, deflate",
}

# Annual-report form types in retry order. The suffix is appended to the
# candidate note so the UI can distinguish a foreign filer's 20-F/40-F from a
# domestic 10-K.
_FORM_FALLBACK: tuple[tuple[str, str], ...] = (
    ("10-K", ""),
    ("20-F", " (foreign private issuer)"),
    ("40-F", " (foreign private issuer, Canadian MJDS)"),
)


# ── HTML→PDF conversion ────────────────────────────────────────────────────────
# EDGAR primary docs are XBRL-tagged .htm, never native PDF (confirmed: no PDF
# exhibit exists for these filings). When an EDGAR HTML filing is the verified
# winner, agent.py converts it to a local PDF here before returning, so the user
# gets the regulatory document as a PDF. Verification still runs against the HTML
# upstream; conversion only reformats the SAME document.

# wkhtmltopdf is a system binary (not a pip package). Prefer it on PATH; fall
# back to the default Windows install location used by the winget package.
# ponytail: hardcoded Windows fallback — add other-OS paths if IDF ever runs off Windows.
_WKHTMLTOPDF = shutil.which("wkhtmltopdf") or r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"

# Tags whose resources wkhtmltopdf tries to fetch while rendering. EDGAR
# inline-XBRL .htm references a viewer script / images / stylesheets, some with
# schemes wkhtmltopdf can't resolve — a FATAL ProtocolUnknownError (not a
# per-resource load error `load-error-handling` can swallow). Strip them.
_RESOURCE_TAGS = ["script", "link", "img", "iframe", "object", "embed",
                  "svg", "video", "audio", "source", "picture"]

_PDF_OPTS = {
    "quiet": "", "encoding": "UTF-8", "disable-javascript": None,
    "load-error-handling": "ignore", "load-media-error-handling": "ignore",
}


def _strip_resources(html: str) -> str:
    """Remove resource-loading tags and neutralise remaining src/href so
    wkhtmltopdf never attempts a network fetch during rendering.

    Also drops <a> hrefs: keeping the thousands of internal XBRL navigation
    anchors roughly doubles render time on a large filing (measured ~48s vs ~22s
    on ASML's 26 MB 20-F) and adds nothing to the delivered text.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_RESOURCE_TAGS):
        tag.decompose()
    for t in soup.find_all(src=True):
        del t["src"]
    for t in soup.find_all(href=True):
        del t["href"]
    return str(soup)


def convert_filing_to_pdf(url: str) -> str | None:
    """Fetch an EDGAR primary-doc .htm and render it to a local PDF.

    Returns the local file path on success, or None if the wkhtmltopdf binary is
    missing or conversion fails (the caller then falls back to the HTML URL). The
    output filename is derived from the filing URL and reused if already present,
    so a repeat request (e.g. a cache hit) doesn't re-render.

    ponytail: images/styling are intentionally dropped — verify.py validates
    TEXT (company / fiscal year / SEC cover markers), which conversion preserves.
    Large filings are slow (~44s for ASML's 26 MB 20-F, ~8s for Kosmos); this
    runs after verification, off the MAX_WALL_SEC critical path.
    """
    if not os.path.exists(_WKHTMLTOPDF):
        logger.warning(f"EDGAR→PDF: wkhtmltopdf not found at {_WKHTMLTOPDF!r} — returning HTML")
        return None

    stem = url.rsplit("/", 1)[-1].rsplit(".", 1)[0] or "edgar_filing"
    out_path = os.path.join(_PDF_CACHE_DIR, f"{stem}.pdf")
    if os.path.exists(out_path):
        logger.info(f"EDGAR→PDF: reusing persisted conversion {out_path}")
        return out_path

    try:
        os.makedirs(_PDF_CACHE_DIR, exist_ok=True)
        resp = requests.get(url, headers=EDGAR_HEADERS, timeout=30)
        resp.raise_for_status()
        html = _strip_resources(resp.text)
        cfg = pdfkit.configuration(wkhtmltopdf=_WKHTMLTOPDF)
        pdfkit.from_string(html, out_path, configuration=cfg, options=_PDF_OPTS)
        logger.info(f"EDGAR→PDF: converted {url} → {out_path}")
        return out_path
    except Exception as exc:
        logger.error(f"EDGAR→PDF: conversion failed for {url}: {exc}")
        if os.path.exists(out_path):  # drop a partial file so a retry re-converts
            try:
                os.remove(out_path)
            except OSError:
                pass
        return None


class EDGARSource:
    name = "edgar"

    def supports(self, intent: dict) -> bool:
        # Foreign private issuers (20-F/40-F filers) are handled here whenever
        # a CIK resolved, regardless of home country.
        return intent.get("country") == "US" or bool(intent.get("cik"))

    def find_candidates(self, intent: dict) -> list[Candidate]:
        return fetch_10k_candidates(intent)


def fetch_10k_candidates(intent: dict) -> list[Candidate]:
    """
    Query EDGAR for the annual filing matching intent["fiscal_year"].

    Resolution:
      1. Pull submissions JSON for the company's CIK (single API call).
      2. Scan recent filings for a 10-K whose reportDate year == fiscal_year.
      3. Zero 10-K matches → rescan for a 20-F, then a 40-F, before giving
         up on EDGAR entirely.
      4. Prefer a PDF exhibit if one exists; always also return the HTML
         primary doc.
    """
    cik_raw = intent.get("cik", "")
    if not cik_raw:
        logger.warning("EDGAR: no CIK in intent — skipping")
        return []

    cik_padded = cik_raw.lstrip("0").zfill(10)   # 10-digit zero-padded for API URL
    cik_int = int(cik_raw.lstrip("0") or "0")     # integer for archive path
    target_year = intent.get("fiscal_year")

    logger.info(f"EDGAR: fetching submissions for CIK {cik_padded} (looking for FY{target_year})")

    try:
        url = f"{DATA_API}/submissions/CIK{cik_padded}.json"
        resp = requests.get(url, headers=EDGAR_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error(f"EDGAR: submissions API call failed: {exc}")
        return []

    company_name = data.get("name", "unknown")
    logger.info(f"EDGAR: entity name = {company_name!r}")

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])

    for form_type, filer_note in _FORM_FALLBACK:
        total = sum(1 for f in forms if f == form_type)
        logger.info(f"EDGAR: {total} {form_type} filing(s) in recent submissions")
        if total == 0:
            continue
        candidates = _match_form(
            recent, form_type, filer_note, company_name, target_year, cik_int
        )
        if candidates:
            return candidates
        logger.info(
            f"EDGAR: no {form_type} with reportDate year {target_year} — trying next form type"
        )

    logger.warning(f"EDGAR: no 10-K / 20-F / 40-F found for FY{target_year}")
    return []


def _match_form(
    recent: dict,
    form_type: str,
    filer_note: str,
    company_name: str,
    target_year: int | None,
    cik_int: int,
) -> list[Candidate]:
    """Scan the recent-filings arrays for form_type matching the target year."""
    forms = recent.get("form", [])
    report_dates = recent.get("reportDate", [])
    filing_dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    candidates: list[Candidate] = []

    for i, ft in enumerate(forms):
        if ft != form_type:
            continue

        report_date = report_dates[i] if i < len(report_dates) else ""
        filing_date = filing_dates[i] if i < len(filing_dates) else ""
        accession = accessions[i] if i < len(accessions) else ""
        primary_doc = primary_docs[i] if i < len(primary_docs) else ""

        # Match on reportDate year (fiscal year end) — more reliable than filingDate year
        # for companies whose fiscal year doesn't follow the calendar year.
        report_year = report_date[:4] if report_date else ""
        if target_year and report_year != str(target_year):
            logger.debug(f"EDGAR: skipping {form_type} with reportDate {report_date}")
            continue

        if not accession or not primary_doc:
            logger.warning(f"EDGAR: {form_type} at index {i} missing accession or primary doc")
            continue

        acc_clean = accession.replace("-", "")
        logger.info(
            f"EDGAR: matched {form_type} — reportDate {report_date}, "
            f"filed {filing_date}, accession {accession}"
        )

        base_note = f"EDGAR {form_type}: {company_name} FY{target_year}{filer_note}"

        # Check for a PDF version in the filing index (preferred over HTML)
        pdf_url = _find_pdf_in_filing(cik_int, acc_clean, accession, form_type)
        if pdf_url:
            candidates.append(
                Candidate(
                    url=pdf_url,
                    source="edgar",
                    note=f"{base_note} — PDF, filing {accession} (reportDate {report_date})",
                )
            )

        # Always add the HTML primary doc as a fallback
        html_url = f"{WWW}/Archives/edgar/data/{cik_int}/{acc_clean}/{primary_doc}"
        candidates.append(
            Candidate(
                url=html_url,
                source="edgar",
                note=f"{base_note} — HTML primary doc, filing {accession} (reportDate {report_date})",
            )
        )

        break  # Take only the first (most-recent) year match

    return candidates


def _find_pdf_in_filing(
    cik_int: int, acc_clean: str, accession: str, form_type: str
) -> str | None:
    """
    Fetch the filing index and return a PDF exhibit URL to prefer over the HTML
    primary document, or None if the filing has no PDF.

    Preference order among PDFs:
      1. A .pdf whose index description (or type) mentions "annual report" — the
         glossy report itself, as filed by many foreign private issuers.
      2. Any other .pdf, largest first. Glossy annual reports dominate a filing
         by size, so small technical/legal exhibit PDFs (e.g. an EX-96 mineral
         report) sort last. The HTML primary doc is always kept as a fallback
         candidate by the caller, so a wrong-guess PDF is caught by verify.py.
    """
    base = f"{WWW}/Archives/edgar/data/{cik_int}/{acc_clean}"
    exhibits = _parse_filing_index(base, accession)
    pdfs = [e for e in exhibits if e["name"].lower().endswith(".pdf")]
    if not pdfs:
        logger.debug("EDGAR: no PDF exhibit in filing index — HTML primary doc will be used")
        return None

    def _rank(e: dict) -> tuple:
        haystack = f"{e['description']} {e['type']}".lower()
        is_annual = "annual report" in haystack
        return (0 if is_annual else 1, -e["size"])

    pdfs.sort(key=_rank)
    best = pdfs[0]
    full_url = f"{base}/{best['name']}"
    logger.info(
        f"EDGAR: preferring PDF exhibit {best['name']!r} "
        f"(description={best['description']!r}, type={best['type']!r}) over HTML primary doc"
    )
    return full_url


def _parse_filing_index(base: str, accession: str) -> list[dict]:
    """
    Return the filing's documents as [{name, description, type, size}].

    Primary source: the human filing index ``{accession}-index.htm`` — its table
    (Seq | Description | Document | Type | Size) is the only endpoint that
    carries the per-exhibit *description* the spec matches "annual report" on.
    Fallback: the ``index.json`` directory listing (filenames + sizes only, no
    descriptions) when the HTML index can't be fetched or parsed.
    """
    try:
        resp = requests.get(f"{base}/{accession}-index.htm", headers=EDGAR_HEADERS, timeout=10)
        if resp.status_code == 200:
            rows = _rows_from_index_htm(resp.text)
            if rows:
                return rows
        else:
            logger.debug(f"EDGAR: -index.htm returned {resp.status_code}")
    except Exception as exc:
        logger.debug(f"EDGAR: -index.htm fetch/parse failed: {exc}")

    try:
        resp = requests.get(f"{base}/index.json", headers=EDGAR_HEADERS, timeout=10)
        if resp.status_code == 200:
            items = resp.json().get("directory", {}).get("item", [])
            return [
                {
                    "name": it.get("name", ""),
                    "description": "",
                    "type": it.get("type", ""),
                    "size": int(it.get("size") or 0),
                }
                for it in items
            ]
    except Exception as exc:
        logger.debug(f"EDGAR: index.json fetch failed: {exc}")

    return []


def _rows_from_index_htm(html: str) -> list[dict]:
    """Parse the {accession}-index.htm document tables into exhibit dicts."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        desc = tds[1].get_text(" ", strip=True)
        # The Document cell holds "<a>filename</a> &nbsp; iXBRL" — take the first
        # whitespace-delimited token so the "iXBRL" annotation is dropped.
        doc_text = tds[2].get_text(" ", strip=True)
        name = doc_text.split()[0] if doc_text else ""
        dtype = tds[3].get_text(" ", strip=True)
        size_txt = tds[4].get_text(strip=True).replace(",", "")
        size = int(size_txt) if size_txt.isdigit() else 0
        if name:
            rows.append({"name": name, "description": desc, "type": dtype, "size": size})
    return rows
