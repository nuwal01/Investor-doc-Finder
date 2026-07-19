"""
Two-step document verifier.

Step 1 HTTP : status 200, content-type check, size > MIN_SIZE_BYTES
Step 2 content : extract text from page 1 and confirm both
                 - a company-name token (from intent["company_name"]) appears
                 - a year from intent["fy_candidates"] appears

Supports PDF (primary) and HTML (fallback for EDGAR and similar sources that
don't offer PDF downloads). When HTML is returned, VerifyResult.is_pdf is False
so callers can decide whether that is acceptable for their use case.
"""

import io
import logging
import re
import time
import unicodedata
from typing import TypedDict
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def _normalize(s: str) -> str:
    """Fold accents to ASCII and lowercase, so 'Hermès' matches 'Hermes'."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()

# Words that appear in almost every corporate filing and carry no discriminating
# power when used alone.  Tokens in this set are stripped before the
# "all distinctive tokens must match" check so that "Arfin India Limited" only
# requires "arfin" to appear, not "india" or "limited".
_GENERIC_TOKENS: frozenset[str] = frozenset({
    "india", "limited", "ltd", "private", "pvt", "company", "co",
    "inc", "corp", "corporation", "group", "industries", "industry",
    "international", "national", "the", "and",
})


def _distinctive_tokens(name: str) -> list[str]:
    """Normalised, discriminating tokens of a company name (len > 2, non-generic).

    Falls back to all len>2 tokens when the name is composed entirely of generic
    words, so there is always something to match. Used for both the resolved
    company (``company_name``) and the originally-requested company
    (``raw_company``) so the two are compared on identical terms.

    Tokenises on periods, whitespace AND hyphens (not just whitespace) so the
    resolved name's punctuation surface-form can't diverge from the document's.
    A whitespace-only split let a DOTTED suffix survive the len>2 filter (``S.A.``
    -> ``"s.a."`` len 4, required) even though its un-dotted form ``"SA"`` (len 2)
    is already dropped — and glued dotted cores (``"R.R.Kabel"``) never matched a
    spaced document ("R R Kabel"). Splitting on ``.`` and ``-`` shatters both into
    the same tokens the un-dotted/spaced form yields (``S.A.``->``s``,``a`` dropped;
    ``R.R.Kabel``->``kabel``), fixing Avianca (S.A.), Turkcell (A.S.) and R R Kabel
    as one root cause. ``&`` is deliberately NOT a separator, so ``AT&T``/``S&P``/
    ``H&M`` keep their ampersand discriminator instead of collapsing to a generic.
    """
    toks = [n for n in (_normalize(t) for t in re.split(r"[.\s-]+", name)) if len(n) > 2]
    distinct = [t for t in toks if t not in _GENERIC_TOKENS]
    return distinct or toks

# Phrases that genuine annual reports almost always contain but newspapers,
# press notices, and unrelated PDFs (that merely mention the company + year)
# do not.  Used as a document-type gate after the company + FY checks pass.
# Apostrophes are normalised to straight quotes before matching.
_REPORT_MARKERS: tuple[str, ...] = (
    # India / Companies-Act phrasing
    "annual report",
    "directors' report",
    "balance sheet",
    "statement of profit and loss",
    "auditor's report",
    "notice of annual general meeting",
    # Global / IFRS / US / UK equivalents so the gate doesn't false-reject
    # legitimate non-Indian reports on the web_search path.
    "integrated report",
    "report and accounts",
    "statement of financial position",
    "statement of comprehensive income",
    "income statement",
    "cash flow statement",
    "independent auditor",   # stem: matches "auditor's"/"auditors'"/"independent auditors' report"
    # Portuguese equivalents — scoped to PT only; this is the one confirmed real
    # case (AMBIPAR's genuine Portuguese-language report failing this English-only
    # gate despite passing identity/FY). Written pre-folded (accents stripped) to
    # match _normalize()'s NFKD+ascii-ignore output, e.g. "relatório" -> "relatorio".
    # Not extended to Spanish/French/German without an equally confirmed real case.
    "relatorio anual",                       # "relatório anual" — annual report
    "balanco patrimonial",                   # "balanço patrimonial" — balance sheet
    "demonstracao do resultado",              # "demonstração do resultado" — income statement
    "demonstracoes financeiras",              # "demonstrações financeiras" — financial statements
    "demonstracao dos fluxos de caixa",       # "demonstração dos fluxos de caixa" — cash flow statement
    "relatorio dos auditores independentes",  # "relatório dos auditores independentes" — independent auditors' report
)

# ── Signal 3 (length) + Signal 5 (publisher) doc-type gates ──────────────────
# These REPLACED the former _STATEMENT_MARKERS substring-scan corroboration.
# Signals 1 (keyword dispersion) and 2 (numeric proximity / "maxRow") were
# measured DEAD this session and are deliberately not used: a genuine report's
# early pages are narrative, and its statement tables extract too variably to
# score — R R Kabel is a real 336-page report whose 2-column INR-crore statements
# yield a maxRow of 5, BELOW both confirmed false-accepts (Silknet 8, ijsrem 6).
#
# Signal 3 — page-count floor. Genuine operating-company reports run dozens–
# hundreds of pages (13-doc batch minimum: Hikma 33); the two confirmed
# false-accepts are short (ijsrem journal paper 7pp, Silknet investor deck 11pp).
# Floor 15 rejects both while clearing Hikma by the widest margin among the tested
# floors {15, 18, 20} — 18pp of headroom below the genuine minimum, i.e. the most
# room for a borderline-short genuine report. Only meaningful for PDFs; HTML has
# no page count and is carved out ONLY for authoritative regulatory sources
# (EDGAR/NSE — see _AUTHORITATIVE_SOURCES and _signal3_length_ok) whose content is
# a filing, not an arbitrary web page. A non-authoritative HTML source
# (web_search, company_site) does NOT get this exemption — it has no page count
# AND no regulatory guarantee, so Signal 3 fails closed for it instead.
# KNOWN, ACCEPTED GAP: fund/ETF "tailored shareholder reports" are genuine ~2-page
# annual reports and WOULD be wrongly rejected here — the fund pre-filter is a
# separate task, not built in this change.
_LENGTH_FLOOR_PAGES = 15

# Sources whose content is an official regulatory filing rather than an arbitrary
# web page — mirrors agent.py's _REGULATORY_SOURCES (tier-0 in _source_priority).
# Duplicated here rather than imported to avoid a circular import (agent.py
# imports verify.py). Only these sources get the total_pages=None exemption below.
_AUTHORITATIVE_SOURCES: frozenset[str] = frozenset({"edgar", "nse"})

# Signal 5 — publisher / journal self-identification. An academic paper names the
# company but is NOT its report (the ijsrem "Financial Performance Analysis of
# Infosys" paper). These markers fired UNIQUELY and correctly on that paper and
# nowhere else in the batch. Scoped to the FRONT MATTER (masthead / abstract
# region) only — a whole-document scan false-positives on incidental citations in
# genuine reports. Deliberately does NOT target Silknet (Signal 3 covers that);
# extending it to would be scope-creep back toward the dead maxRow approach.
# (human-readable label, regex). \bissn\b also matches the "issn" inside "e-issn"
# (hyphen is a non-word boundary), so no separate e-ISSN pattern is needed.
_JOURNAL_MARKERS: tuple[tuple[str, str], ...] = (
    ("ISSN", r"\bissn\b"),
    ("DOI", r"\bdoi\b\s*:?\s*10\."),   # a real DOI, e.g. "DOI: 10.55041/IJSREM65443"
    ("'international journal'", r"international journal"),
    ("'this paper …'", r"this paper (?:presents|proposes|examines|studies|analys[ei]s|reviews)"),
    ("'abstract' header", r"\babstract\b\s*[:\-—]?\s"),  # structured section header
    ("'impact factor'", r"impact factor"),
    ("SJIF rating", r"sjif rating"),
    ("peer-reviewed", r"peer[ -]reviewed"),
)
_JOURNAL_FRONTMATTER_CHARS = 4000     # masthead/abstract region only, not whole doc


def _signal3_length_ok(total_pages: int | None, source: str = "") -> tuple[bool, str]:
    """Signal 3 — length gate. A PDF must meet the page-count floor.

    HTML has no page count (``total_pages is None``). That used to auto-pass
    for EVERY HTML candidate regardless of source, because _verify_html never
    supplies total_pages — so a web_search/company_site press release got the
    same free pass as an authoritative EDGAR filing, with zero length evidence
    either way. The exemption is now restricted to authoritative regulatory
    sources (``_AUTHORITATIVE_SOURCES`` — edgar/nse, whose content is a filing,
    not an arbitrary web page); any other source with no page count fails
    closed instead of auto-passing. Independently disableable."""
    if total_pages is None:
        if source in _AUTHORITATIVE_SOURCES:
            return True, f"no page count ({source}, authoritative) — length gate carved out"
        return (
            False,
            f"no page count and source {source!r} is not authoritative "
            "— length gate cannot be satisfied",
        )
    if total_pages < _LENGTH_FLOOR_PAGES:
        return False, f"{total_pages} pages < {_LENGTH_FLOOR_PAGES}-page floor"
    return True, f"{total_pages} pages >= {_LENGTH_FLOOR_PAGES}-page floor"


def _signal5_publisher_ok(front_matter: str) -> tuple[bool, str]:
    """Signal 5 — publisher/journal self-identification gate. Rejects an academic
    or journal publication (which names the company but is not its report).
    ``front_matter`` must be the leading, normalised (lowercased, whitespace-
    collapsed) slice of the document so an incidental citation deep in a genuine
    report can't false-trip it. Independently disableable."""
    hits = [label for label, pat in _JOURNAL_MARKERS if re.search(pat, front_matter)]
    if hits:
        return False, "journal/publisher markers in front matter: " + ", ".join(hits)
    return True, "no journal/publisher markers"

# Interim/quarterly self-descriptions used as the NEGATIVE document-type gate.
# Entries are regex, matched (via _earliest) against the LEADING region only, and
# a match REJECTS only when it precedes any _IDENTITY_MARKER there (see the gate
# below) — so an annual report that merely references interim data later (e.g.
# Toyota's "1H/2Q financial results briefing" line, which sits after its
# "Integrated Report 2023" cover) is not rejected.
#
# Generalized from 5 real interim filings across jurisdictions (checked 2026-07-12),
# NOT overfit to the one case that slipped through:
#   Apple Q1-FY23 10-Q (US)   "quarterly period ended", "three months ended"
#   Nestlé HY-2023 (CH)       "half-year report", "condensed interim financial
#                             statements", "six-month period ended"
#   Siemens HY-FY23 (DE)      "half-year financial report", "interim group
#                             management report", "condensed ... financial statements"
#   Infosys Q1-FY24 (IN)      "quarter ended", "interim condensed ... financial statements"
#   Tecpetrol Q1-2023 (AR)    "interim condensed financial statements",
#                             "three-month period ended"  ← the slip-through case
#
# Regression guard: every pattern requires an interim QUALIFIER (interim/condensed)
# or a SUB-ANNUAL period (quarter, half-year, or 3/6/9-month — never twelve/year).
# Bare "financial statements", "consolidated financial statements", "year ended"
# and "twelve months ended" do NOT match, so a genuine annual report's own
# statements aren't tripped. Deliberately EXCLUDES bare "q1".."q4" (annual reports'
# Financial-Highlights quarter tables); those stay caught by the URL filename gate.
# Separators tolerate hyphen/space and glued forms (ASCII-folding can drop a
# non-breaking hyphen, e.g. "six‑month" -> "sixmonth").
_QUARTERLY_MARKERS: tuple[str, ...] = (
    "first quarter", "second quarter", "third quarter", "fourth quarter",
    "quarterly report", "interim report",
    r"quarter(?:ly)?[ -](?:period[ -])?ended",                  # "quarter ended", "quarterly period ended"
    r"half[ -]?yearly?[ -](?:financial[ -])?report",            # "half-year report", "half-yearly report", "half-year financial report"
    r"(?:three|six|nine)[ -]?months?[ -](?:period[ -])?ended",  # 3/6/9-month(s) [period] ended — never twelve/year
    r"condensed(?:[ -](?:interim|consolidated|unaudited|half[ -]?year)){0,3}[ -]financial statements",
    r"interim(?:[ -](?:condensed|consolidated|unaudited))*[ -]financial statements",
    r"interim(?:[ -]group)?[ -]management report",
)

# Annual-report identity markers. Kept in sync with the discriminating subset of
# _REPORT_MARKERS (statement names like "balance sheet"/"income statement" are
# omitted because condensed interim statements carry them too).
_IDENTITY_MARKERS: tuple[str, ...] = (
    "annual report", "directors report", "integrated report",
    "report and accounts", "notice of annual general meeting",
)

# Cover-page phrases that appear verbatim on EVERY SEC annual filing (10-K / 20-F /
# 40-F) and essentially nowhere else — a glossy IR PDF does not say "Commission File
# Number" or "exact name of registrant". Verified 2026-07-11 against three real
# filings: Kosmos 10-K (acc 0001509991-24-000029), ASML 20-F (0000937966-24-000008),
# Shopify 40-F (0001594805-24-000007) — all three contain both phrases; the
# auditor's-report phrase and 10-K "Item" headers were checked too and REJECTED
# (auditor report absent in the 40-F and at 65% depth in the 10-K, i.e. past a
# page-1-of-7 window; "Item 1A/7/8" exist only in the 10-K, not 20-F/40-F).
_SEC_REGULATORY_MARKERS: tuple[str, ...] = (
    "commission file number",
    "exact name of registrant",
)


def _sec_gate_applies(source: str, intent: dict) -> bool:
    """The SEC-regulatory marker gate applies ONLY to a web_search candidate for a
    company with a resolved CIK — i.e. a CONFIRMED SEC filer. Scoped on `cik` alone,
    NOT on the LLM-parsed country: a company with no CIK isn't a confirmed SEC filer
    regardless of what country the LLM guessed, and trusting country=='US' falsely
    rejected Hikma (UK, no CIK, misparsed US) whose legit annual report has no SEC
    cover markers. The scope spec ("no tier-0 candidate verified yet") is implied for
    free: with the tier-0 short-circuit in agent.py, a web_search candidate only reaches
    verify() when EDGAR produced NO verified candidate — so no agent.py plumbing is
    needed. Cannot be true for any company without a CIK (India, non-US/non-IN, or a
    mis-parsed non-filer), nor for edgar/aggregators/nse/company_site (source != 'web_search')."""
    return source == "web_search" and bool(intent.get("cik"))


def _earliest(patterns: tuple[str, ...], text: str) -> tuple[int, str] | None:
    """Return (position, pattern) of the earliest-matching pattern, or None."""
    best: tuple[int, str] | None = None
    for p in patterns:
        m = re.search(p, text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), p)
    return best

MIN_SIZE_BYTES = 50_000
HTML_READ_LIMIT = 250_000   # bytes; EDGAR 10-Ks can be 10 MB — read enough for p.1 content
BODY_READ_MAX_SEC = 15      # wall-clock cap on the body download alone, enforced
                            # independently of the connect/header timeout=30 on the
                            # GET. A candidate whose body takes longer is aborted (no
                            # retry); the caller moves on to the next candidate.

HEADERS = {
    "User-Agent": "IDF research trade@ostwal.in",
    "Accept-Encoding": "gzip, deflate",
}


class VerifyResult(TypedDict):
    ok: bool
    reason: str
    matched_fy: str | None
    is_pdf: bool        # True only when content-type was application/pdf
    content_type: str   # raw content-type header value


def verify(candidate: dict, intent: dict) -> VerifyResult:
    url = candidate["url"]
    logger.info(f"Verifying candidate from {candidate['source']}: {url}")

    skip_co = candidate.get("skip_company_check", False)

    # ── Step 0: URL/filename year pre-check (fast — no download) ──────────────
    # If the URL names a 4-digit year (19xx/20xx) that matches none of the
    # requested FY candidates, this is the wrong report — e.g. a "2024-Annual-
    # Report.pdf" answering a 2023 query. Reject before spending a download.
    # Skip only when the URL names no plausible year at all. Trusted-source URLs
    # (StockDiscovery) are keyed by a numeric company ID that can look like a
    # year and use 2-digit filenames, so they are exempt from this check.
    if not skip_co:
        fy_candidates = intent.get("fy_candidates", [])
        fy_years  = {y for fy in fy_candidates for y in re.findall(r"\d{4}", fy)}
        url_years = set(re.findall(r"(?:19|20)\d{2}", url))
        if url_years and fy_years and not (url_years & fy_years):
            return _fail(
                f"URL year {sorted(url_years)} does not match requested "
                f"FY candidates {fy_candidates}"
            )

        # Quarterly/interim signal in the URL → wrong document type; reject before
        # downloading. The "annual" exception and the Q-token / "quarter" checks
        # are scoped to the FILENAME so a "/q4/" directory (where 10-Ks are filed),
        # a "q4cdn.com" host, or an "/annual-reports/" path segment don't distort
        # the decision. Q-tokens cover both orders (Q1 and 1Q) and glued forms.
        url_l = unquote(url).replace("+", " ").lower()
        fname = url_l.split("?")[0].split("#")[0].rsplit("/", 1)[-1]
        if not re.search(r"\bannual\b", fname):
            qm = re.search(r"(?<![a-z])(?:q[1-4]|[1-4]q)", fname)
            if qm:
                return _fail(f"URL contains quarterly signal: {qm.group(0)}")
            if re.search(r"\bquarter\b", fname):
                return _fail("URL contains quarterly signal: quarter")
            for sig in ("quarterly", "interim"):
                if sig in url_l:
                    return _fail(f"URL contains quarterly signal: {sig}")
            if re.search(r"half[-_\s]?year", url_l):
                return _fail("URL contains quarterly signal: half-year")

    # ── Step 1: HTTP fetch ───────────────────────────────────────────────
    # NOTE: timing is diagnostic only. These are stream=True calls, so elapsed
    # measures connection + response-header time, NOT the body download (that
    # happens later at resp.content / iter_content, below).
    source_name = candidate.get("source", "?")
    try:
        start = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        elapsed = time.time() - start
        logger.info(f"[TIMING] source={source_name} elapsed={elapsed:.1f}s status=ok")
    except requests.Timeout:
        elapsed = time.time() - start
        logger.info(f"[TIMING] source={source_name} elapsed={elapsed:.1f}s status=timeout")
        return _fail("Request timed out")
    except requests.exceptions.SSLError as e:
        # Windows Python often lacks the issuer cert for smaller company sites.
        # Retry without verification — we validate content ourselves below.
        elapsed = time.time() - start
        logger.info(f"[TIMING] source={source_name} elapsed={elapsed:.1f}s status=error")
        logger.info(f"[TIMING] source={source_name} SSL_RETRY_TRIGGERED exception={type(e).__name__}")
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            start = time.time()
            resp = requests.get(url, headers=HEADERS, timeout=30, stream=True, verify=False)
            elapsed = time.time() - start
            logger.info(f"[TIMING] source={source_name} elapsed={elapsed:.1f}s status=ok")
            logger.warning(f"SSL cert invalid, retried without verify: {url[:70]}")
        except requests.Timeout:
            elapsed = time.time() - start
            logger.info(f"[TIMING] source={source_name} elapsed={elapsed:.1f}s status=timeout")
            return _fail("Request timed out")
        except Exception as exc:
            elapsed = time.time() - start
            logger.info(f"[TIMING] source={source_name} elapsed={elapsed:.1f}s status=error")
            return _fail(f"HTTP error: {exc}")
    except Exception as exc:
        elapsed = time.time() - start
        logger.info(f"[TIMING] source={source_name} elapsed={elapsed:.1f}s status=error")
        return _fail(f"HTTP error: {exc}")

    if resp.status_code != 200:
        resp.close()
        return _fail(f"HTTP {resp.status_code}")

    content_type = resp.headers.get("content-type", "").lower()
    is_pdf = "application/pdf" in content_type
    is_html = "text/html" in content_type

    if not is_pdf and not is_html:
        resp.close()
        return _fail(f"Unsupported content-type: {content_type!r}", content_type=content_type)

    # Size guard: use Content-Length header when available, else read-and-measure
    declared_size = int(resp.headers.get("content-length", 0))
    if declared_size and declared_size < MIN_SIZE_BYTES:
        resp.close()
        return _fail(
            f"Too small per Content-Length: {declared_size} bytes (min {MIN_SIZE_BYTES})",
            content_type=content_type,
        )

    # Read content: full for PDF (pypdf needs it), limited for HTML. Both paths
    # stream in chunks so the BODY_READ_MAX_SEC wall-clock cap can be checked
    # between chunks — independent of the connect/header timeout on the GET.
    body_start = time.time()
    # EDGAR inline-XBRL .htm places a variable-size XBRL metadata block ahead of the
    # human-readable cover page, so the 250KB HTML cap truncates the registrant line
    # at random relative to doc structure (confirmed by byte-offset forensic: 2022
    # 20-F failed identity, 2023/2024 passed, purely on where the cap landed). Read
    # EDGAR filings in full; BODY_READ_MAX_SEC (15s) stays the only cap for them.
    # ponytail: source-scoped exception; widen only if another source shows the same.
    body_limit = None if (is_pdf or candidate.get("source") == "edgar") else HTML_READ_LIMIT
    # Accumulate chunks in a list and join once (O(n)). The previous
    # `content += chunk` pattern is O(n²) for large bodies: a 27 MB PDF spent
    # ~17s in byte-concatenation alone (CPU, not network) — tripping the 15s cap
    # even though the download itself took ~3s. Joining is ~2000× faster here and
    # leaves the cap check, the read-limit, and every constant unchanged.
    chunks: list[bytes] = []
    bytes_read = 0
    body_timed_out = False
    for chunk in resp.iter_content(chunk_size=8192):
        chunks.append(chunk)
        bytes_read += len(chunk)
        if time.time() - body_start > BODY_READ_MAX_SEC:
            body_timed_out = True
            break
        if body_limit is not None and bytes_read >= body_limit:
            break
    content = b"".join(chunks)
    resp.close()
    body_elapsed = time.time() - body_start

    if body_timed_out:
        logger.warning(
            f"body_read_timeout candidate={source_name} "
            f"body_read_elapsed={body_elapsed:.1f}s (max {BODY_READ_MAX_SEC}s)"
        )
        return _fail(
            f"Body read exceeded {BODY_READ_MAX_SEC}s cap",
            content_type=content_type, is_pdf=is_pdf,
        )

    logger.info(f"[TIMING] source={source_name} body_read_elapsed={body_elapsed:.1f}s")

    if not declared_size and len(content) < MIN_SIZE_BYTES:
        return _fail(
            f"Too small: {len(content)} bytes (min {MIN_SIZE_BYTES})",
            content_type=content_type,
        )

    logger.info(
        f"HTTP OK — content-type: {'PDF' if is_pdf else 'HTML'}, "
        f"size: {len(content):,} bytes"
    )

    # ── Step 2: content check ────────────────────────────────────────────
    if is_pdf:
        return _verify_pdf(content, intent, content_type, skip_co, source=source_name)
    return _verify_html(content, intent, content_type, skip_co, source=source_name)


# ── internal helpers ─────────────────────────────────────────────────────────

def _verify_pdf(content: bytes, intent: dict, content_type: str,
                skip_company_check: bool = False, source: str = "") -> VerifyResult:
    try:
        reader = PdfReader(io.BytesIO(content))
        if not reader.pages:
            return _fail("PDF has no pages", content_type=content_type, is_pdf=True)
        # Annual reports often open with graphic-only cover pages that yield no
        # extractable text.  Scan the first 7 pages (or all if fewer) so company
        # tokens and the fiscal year can be found in headers, footers, the TOC,
        # or the first body page.
        n_pages = min(7, len(reader.pages))
        pages = [reader.pages[i].extract_text() or "" for i in range(n_pages)]
        page_text = " ".join(pages)
        # Cover / front matter — where a report names its OWN fiscal year. Used
        # for the year check so a comparative year buried deep in the document
        # can't make a later report answer an earlier-year query.
        head_text = " ".join(pages[:2])
        logger.info(
            f"PDF text extraction: read {n_pages} of {len(reader.pages)} page(s), "
            f"{len(page_text):,} chars extracted"
        )
    except Exception as exc:
        return _fail(f"pypdf error: {exc}", content_type=content_type, is_pdf=True)

    return _check_text(page_text, intent, content_type, is_pdf=True,
                       skip_company_check=skip_company_check, year_text=head_text,
                       source=source, total_pages=len(reader.pages))


def _verify_html(content: bytes, intent: dict, content_type: str,
                 skip_company_check: bool = False, source: str = "") -> VerifyResult:
    logger.warning(
        "Document is HTML not PDF — verifying text content. "
        "Add a PDF source for this company to get a proper PDF result."
    )
    try:
        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text(" ", strip=True)          # full text: identity / FY / quarterly
    except Exception as exc:
        return _fail(f"HTML parse error: {exc}", content_type=content_type, is_pdf=False)

    return _check_text(text, intent, content_type, is_pdf=False,
                       skip_company_check=skip_company_check, source=source)


def _token_present(tok: str, text: str) -> bool:
    """True if ``tok`` occurs in ``text`` as a standalone token.

    Uses alphanumeric-boundary lookarounds instead of ``\\b``. ``\\b`` is defined
    as a word/non-word transition, so a token ENDING in a period (a punctuated
    abbreviation like ``n.v.``, ``s.a.``, ``s.p.a.``, ``a.s.``) can never match:
    after the trailing ``.`` the next char is whitespace, and ``.``→space is not a
    ``\\b`` boundary. That made e.g. resolved name ``ASML Holding N.V.`` fail
    identity verification whenever the LLM resolver included the suffix, even
    though the document text literally contains ``n.v.``. ``(?<![a-z0-9])``/
    ``(?![a-z0-9])`` require only that the token not abut another alphanumeric,
    which reproduces ``\\b`` behaviour for punctuation-free tokens (``asml`` still
    won't match inside ``wasml``/``asmlx``) while matching trailing-period ones.
    Both token and text are already lowercased/ASCII-folded by callers.
    """
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(tok) + r"(?![a-z0-9])", text))


def _name_core_words(name: str) -> list[str]:
    """The requested name's core words for single-token corroboration.

    Split like _distinctive_tokens (periods/whitespace/hyphens) but KEEP short
    words — in "R R Kabel" the two "r" words ARE the distinguishing part the
    single surviving token lost. Then trim words documents render
    inconsistently: right-trim corporate-form/generic tails ("Ltd", "JSC",
    "S.A." fragments — _GENERIC_TOKENS members or <=3 chars; length-based on
    purpose, no bespoke suffix dictionary), and left-trim GENERIC words only
    ("The Sasol Group" -> core "sasol") — the left side never length-trims, so
    a short leading "R R ..." is preserved. Without the left trim, a generic
    lead-in makes the core spuriously multi-word and arms the corroboration
    guard with a phrase ("the sasol") real covers don't carry (double-pollution
    false-reject, confirmed synthetically 2026-07-12). Never trims the last
    remaining word.
    """
    words = [w for w in (_normalize(t) for t in re.split(r"[.\s-]+", name)) if w]
    while len(words) > 1 and words[0] in _GENERIC_TOKENS:
        words.pop(0)
    while len(words) > 1 and (words[-1] in _GENERIC_TOKENS or len(words[-1]) <= 3):
        words.pop()
    return words


def _phrase_present(words: list[str], text: str) -> bool:
    """True if `words` appear contiguously in order in `text`, any punctuation/
    whitespace between them ("r r kabel" matches "R R KABEL", "R.R.Kabel",
    "R-R-Kabel"), bounded so substrings of larger words don't count."""
    pat = r"(?<![a-z0-9])" + r"[^a-z0-9]+".join(re.escape(w) for w in words) + r"(?![a-z0-9])"
    return bool(re.search(pat, text))


def _fy_year_set(fy_candidates: list[str]) -> set[int]:
    """All calendar years a set of fiscal-year labels spans. '2023' -> {2023};
    'FY2023-24' -> {2023, 2024} (split / non-calendar fiscal years)."""
    ys: set[int] = set()
    for fy in fy_candidates:
        m = re.search(r"(20\d{2})\s*-\s*(\d{2,4})", fy)
        if m:
            a = int(m.group(1)); b = m.group(2)
            ys.add(a); ys.add(int(b) if len(b) == 4 else int(str(a)[:2] + b))
        ys.update(int(y) for y in re.findall(r"(?:19|20)\d{2}", fy))
    return ys


def _check_text(text: str, intent: dict, content_type: str, is_pdf: bool,
                skip_company_check: bool = False,
                year_text: str | None = None, source: str = "",
                total_pages: int | None = None) -> VerifyResult:
    text_lower = _normalize(text)

    # ── Company-name check ───────────────────────────────────────────────────
    company_name = intent.get("company_name", "")
    distinctive  = _distinctive_tokens(company_name)
    requested    = _distinctive_tokens(intent.get("raw_company", ""))

    def _present(tok: str) -> bool:
        return _token_present(tok, text_lower)

    # Requested-vs-resolved divergence gate — SHARED by both the trusted and the
    # non-trusted branches. When the resolved ``company_name`` and the user's
    # ``raw_company`` share NO distinctive token, the resolver likely swapped in a
    # different company; the document must then still name the REQUESTED company or
    # we reject. When they share a token (a normal resolution) the gate is a no-op.
    # This catches a resolver override to a wrong-but-real company whose OWN report
    # naturally contains its own name — the AMBIPAR/MBAPL mechanism — no matter
    # which source produced the candidate (a wrong-but-real company reached via
    # edgar/web_search/company_site would otherwise pass the company_name check
    # below just as silently as it did via the aggregators trusted path).
    diverged     = bool(requested and distinctive
                        and not (set(requested) & set(distinctive)))
    requested_ok = (not diverged) or any(_present(t) for t in requested)

    if skip_company_check:
        # Trusted-source path (e.g. a StockDiscovery URL keyed by a resolver ID).
        # "Trusted" suppresses *document-authenticity* skepticism only — the
        # report-markers doc-type gate further below — because the host is a known
        # filings mirror. It must NOT suppress confirming WHO the document is
        # about, so we still require the document to name (1) the resolved company
        # (``company_name``, lenient any()-match — the host is trusted) and (2) the
        # requested company via the shared divergence gate above.
        resolved_ok  = (not distinctive) or any(_present(t) for t in distinctive)
        if not resolved_ok or not requested_ok:
            logger.warning(
                f"Trusted-source company-identity mismatch — requested "
                f"{intent.get('raw_company')!r}, resolved {company_name!r}; "
                f"document names neither as required (resolved_ok={resolved_ok}, "
                f"requested_ok={requested_ok})"
            )
            return _fail(
                f"Trusted source but document company does not match the requested "
                f"company (requested {intent.get('raw_company')!r}, "
                f"resolved {company_name!r})",
                content_type=content_type, is_pdf=is_pdf,
            )
    else:
        if not distinctive:
            return _fail(
                "No company name tokens to check",
                content_type=content_type, is_pdf=is_pdf,
            )
        # Require ALL distinctive tokens — stronger than the old any() which
        # let generic words like "india" or "limited" count as a match.
        matched = [tok for tok in distinctive if _present(tok)]
        if len(matched) < len(distinctive):
            missing = set(distinctive) - set(matched)
            return _fail(
                f"Company tokens missing: {sorted(missing)} (had {company_name!r})",
                content_type=content_type,
                is_pdf=is_pdf,
            )
        # Additive divergence gate: the all-tokens check above confirms the doc
        # names the RESOLVED company — but if the resolver overrode to a
        # wrong-but-real company, that company's own report satisfies it while
        # naming nobody the user asked for. When resolved/requested diverge, the
        # document must also name the requested company.
        if not requested_ok:
            logger.warning(
                f"Non-trusted company-identity mismatch — requested "
                f"{intent.get('raw_company')!r}, resolved {company_name!r}; "
                f"document names the resolved company but not the requested one"
            )
            return _fail(
                f"Document company does not match the requested company "
                f"(requested {intent.get('raw_company')!r}, resolved {company_name!r})",
                content_type=content_type,
                is_pdf=is_pdf,
            )

        # Single-token corroboration guard. When the name collapsed to ONE
        # distinctive token, identity so far rests on a single word — the AMBIPAR
        # failure shape (real-but-insufficient signal). "R R Kabel Ltd" ->
        # ['kabel']: any cable-maker's report contains "kabel". So require the
        # requested name's core words ("r r kabel") to appear contiguously in the
        # document text as corroboration. Applies to EVERY single-token collapse
        # (no length/commonness cutoff — a cutoff just recreates the common-word-
        # dictionary problem one level up); it self-skips when the requested core
        # is itself one word (Shopify, Sasol, Hermès...) because then the phrase
        # IS the already-matched token and adds nothing. Multi-token identity
        # (2+ tokens) is untouched. Uses text_lower — for PDFs that is the
        # leading region (first 7 pages); the token evidence lives there too.
        # Corroborate against the REQUESTED name's core, falling back to the
        # RESOLVED name's core. Live finding (batch 2026-07-12): under degraded
        # LLM parsing raw_company can arrive polluted with the whole query
        # ("R R Kabel Ltd 2023 annual report"), making the requested-core phrase
        # unsatisfiable and false-rejecting the genuine document — while
        # company_name stayed clean. Either full-name form appearing contiguously
        # confirms the lone token wasn't coincidental; a wrong company's document
        # contains neither (wrong-resolution is the divergence gate's job above).
        if len(distinctive) == 1:
            cores = [_name_core_words(n) for n in
                     (intent.get("raw_company", ""), company_name) if n]
            cores = [c for c in cores if c]
            # Guard is meaningful only when EVERY available name form has a
            # multi-word core: a single-word core (Shopify, Sasol, Avianca) is
            # already fully represented by the matched token, and a polluted
            # counterpart form must not re-arm the guard against it.
            if cores and all(len(c) >= 2 for c in cores) \
                    and not any(_phrase_present(c, text_lower) for c in cores):
                return _fail(
                    f"Single-token identity ({distinctive[0]!r}) lacks corroboration: "
                    f"name core(s) {[' '.join(c) for c in cores]} not found "
                    f"contiguously in document",
                    content_type=content_type,
                    is_pdf=is_pdf,
                )

    # Fiscal year: at least one fy_candidate year must appear — but only in the
    # first pages (cover / front matter) for PDFs. A year that shows up ONLY deep
    # in the document is almost always a prior-year comparative, not the report's
    # own FY. year_text carries the first 2 pages for PDFs; HTML has no page
    # concept, so it falls back to the full extracted text.
    year_source = year_text if year_text is not None else text
    fy_candidates: list[str] = intent.get("fy_candidates", [])
    matched_fy: str | None = None

    # Primary-fiscal-year gate (PDF cover / front-matter only). The requested year
    # must be the document's PRIMARY reporting year — the most-recent year stated in
    # a "year/period/months ended ... YYYY" phrase on the cover — NOT a prior-year
    # COMPARATIVE column. Fixes the Avianca case: its statements are headed "...year
    # ended December 31, 2024 and December 31, 2023", so a 2023 request must not be
    # satisfied by the 2023 comparative when the document's own year is 2024. max()
    # picks the current period (comparatives are prior/smaller); a publication year
    # or boilerplate (e.g. "...Act of 1934", zip codes) is not in an "ended" phrase
    # so can't distort it. Verified against real covers: Avianca->2024 (rejects 2023),
    # Shopify->2022 (accepts — 2022 is a valid prior-year candidate), Hermès->2023
    # (accepts, ignoring a nearby 2024 publication date). Scoped to PDFs (year_text
    # present): EDGAR HTML's year_source is the FULL text whose notes carry subsequent-
    # events "months ended ... 2024" phrases that would poison max(), and its cover
    # sits behind an XBRL preamble anyway — so it keeps the original check. PDF covers
    # with no "ended" phrase (glossy reports: R R Kabel, Tullow) also fall through.
    if year_text is not None:
        flat = re.sub(r"\s+", " ", year_source)
        ended_years = [
            int(y)
            for m in re.finditer(r"(?:year|years|period|months)\s+(?:then\s+)?ended(.{0,70})", flat, re.I)
            for y in re.findall(r"(?:19|20)\d{2}", m.group(1))
        ]
        if ended_years:
            primary_fy = max(ended_years)
            if primary_fy in _fy_year_set(fy_candidates):
                matched_fy = next(
                    (fy for fy in fy_candidates if primary_fy in _fy_year_set([fy])), None
                )
            else:
                return _fail(
                    f"Document's primary fiscal year {primary_fy} (from a 'year ended' "
                    f"cover phrase) is not among requested {fy_candidates} — "
                    f"comparative-year match rejected",
                    content_type=content_type,
                    is_pdf=is_pdf,
                )

    if matched_fy is None:
        for fy in fy_candidates:
            years = re.findall(r"\d{4}", fy)
            if any(yr in year_source for yr in years):
                matched_fy = fy
                break

    if not matched_fy:
        return _fail(
            f"No year from {fy_candidates} found in first pages of document",
            content_type=content_type,
            is_pdf=is_pdf,
        )

    # ── Document-type gate ───────────────────────────────────────────────────
    # Company + FY can both match in a newspaper public notice or a press
    # release that merely references the company.  Require at least one phrase
    # that genuine annual reports contain.  Skipped for trusted-source URLs
    # (skip_company_check) whose path already asserts the document type, e.g.
    # StockDiscovery's ".../Annual Report/AR-21.pdf".
    if not skip_company_check:
        # Collapse runs of whitespace (PDF extraction and HTML text nodes inject
        # newlines/double-spaces mid-phrase) and normalise curly apostrophes, so
        # multi-word markers like "statement of profit and loss" still match.
        normalized = re.sub(r"\s+", " ", text_lower).replace("’", "'").replace("‘", "'")
        if not any(marker in normalized for marker in _REPORT_MARKERS):
            return _fail(
                "no annual-report document markers found — likely wrong document type",
                content_type=content_type,
                is_pdf=is_pdf,
            )

        # The check above passes on a single report-NAME marker — and the bare
        # "annual report" substring is one — so a publication announcement / AGM
        # notice that merely REFERENCES a report slips through as if it were the
        # report (the Tullow-2024 case). Require the document to actually BE a
        # report via two independent HARD gates that replaced the former
        # _STATEMENT_MARKERS corroboration (Signals 1 & 2 measured dead — see the
        # gate definitions up top): reject if EITHER Signal 5 (publisher/journal
        # self-identification) or Signal 3 (page-count floor) fails. Signal 5 is
        # checked first so a journal article (ijsrem, which fails both) is reported
        # as a publisher-gate rejection rather than merely "too short"; Silknet (a
        # genuine-company deck, passes Signal 5) is caught by Signal 3 on length.
        s5_ok, s5_reason = _signal5_publisher_ok(normalized[:_JOURNAL_FRONTMATTER_CHARS])
        s3_ok, s3_reason = _signal3_length_ok(total_pages, source)
        logger.info(
            f"[DOCTYPE] source={source} pages={total_pages} "
            f"signal5_pub={s5_ok} ({s5_reason}); signal3_len={s3_ok} ({s3_reason})"
        )
        if not s5_ok:
            return _fail(
                f"Signal 5 publisher gate failed — {s5_reason}",
                content_type=content_type,
                is_pdf=is_pdf,
            )
        if not s3_ok:
            return _fail(
                f"Signal 3 length gate failed — {s3_reason}",
                content_type=content_type,
                is_pdf=is_pdf,
            )

        # Negative document-type gate (precedence-based): reject a quarterly/
        # interim doc only when a quarterly marker LEADS the front matter — i.e.
        # appears with no annual-report identity marker before it. This trusts the
        # document's leading title over an incidental later mention (e.g. a
        # quarterly release that name-drops "annual report" in a disclaimer), while
        # sparing a genuine annual report that summarises quarters after its title.
        # PDFs scan the first 2 pages (year_text); HTML has no pages, so bound the
        # scan to a leading slice rather than the whole document.
        reject_region = year_source if year_text is not None else year_source[:3000]
        head_flat = re.sub(r"\s+", " ", _normalize(reject_region)).replace("'", "")
        q_hit  = _earliest(_QUARTERLY_MARKERS, head_flat)
        id_hit = _earliest(_IDENTITY_MARKERS, head_flat)
        if q_hit and (id_hit is None or q_hit[0] < id_hit[0]):
            return _fail(
                f"Quarterly/interim document rejected: matched negative marker '{q_hit[1]}'",
                content_type=content_type,
                is_pdf=is_pdf,
            )

        # SEC-regulatory marker gate — ADDITIONAL acceptance gate, applied ONLY to a
        # web_search fallback in the US/has-cik population (see _sec_gate_applies).
        # When EDGAR (tier-0) yielded no verified candidate for a US/cik company and
        # we're falling back to a web_search PDF, require a genuine SEC-filing cover
        # marker so a non-regulatory PDF isn't accepted in the regulated population.
        # Not a comparison — no tier-0 competitor exists in this scoped case. Same
        # failure path as every other gate (reject → next candidate / give_up).
        if _sec_gate_applies(source, intent) and not any(
            m in normalized for m in _SEC_REGULATORY_MARKERS
        ):
            return _fail(
                "SEC-regulatory cover markers absent (US/cik web_search fallback) — "
                f"not a recognizable SEC filing: {list(_SEC_REGULATORY_MARKERS)}",
                content_type=content_type,
                is_pdf=is_pdf,
            )

    kind = "PDF" if is_pdf else "HTML"
    logger.info(f"Content check passed ({kind}) — matched FY: {matched_fy}")
    return VerifyResult(
        ok=True,
        reason=f"Verified ({kind})",
        matched_fy=matched_fy,
        is_pdf=is_pdf,
        content_type=content_type,
    )


def _fail(
    reason: str,
    content_type: str = "",
    is_pdf: bool = False,
) -> VerifyResult:
    logger.warning(f"Verify failed: {reason}")
    return VerifyResult(
        ok=False,
        reason=reason,
        matched_fy=None,
        is_pdf=is_pdf,
        content_type=content_type,
    )
