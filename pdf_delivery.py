"""Resolve a verified result to downloadable PDF bytes + filename, in memory.

Shared by streamlit_app.py and api.py so the browser-download path is identical
across both frontends. No disk writes: an already-PDF source is fetched fresh
(verify.py doesn't retain its bytes) and an EDGAR HTML filing is converted on
demand via sources.edgar.convert_filing_to_pdf (which returns bytes).
"""

import requests

# Browser-y UA for the already-PDF fetch (some IR/CDN hosts 403 a bare client).
_DL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36"
}


def _filename(result: dict, url: str) -> str:
    base = url.rsplit("/", 1)[-1].split("?")[0]
    if base.lower().endswith(".pdf"):
        return base
    if result.get("source") == "edgar":
        return (base.rsplit(".", 1)[0] or "edgar_filing") + ".pdf"
    company = (result.get("company") or "document").strip().replace(" ", "_")
    fy = result.get("matched_fy") or result.get("fiscal_year") or ""
    return f"{company}_{fy}.pdf".replace("__", "_").strip("_")


def resolve_pdf(result: dict) -> tuple[bytes, str] | None:
    """Return (pdf_bytes, filename), or None if no PDF can be served (caller falls
    back to the raw link). May raise on a network/conversion error — callers wrap
    it and surface the failure rather than serving empty bytes.

      • is_pdf source (web_search / company_site): fetch the bytes fresh.
      • EDGAR: convert the HTML filing to PDF in memory (~8-14s for large filings).
      • any other HTML source: None.
    """
    url = result.get("url", "")
    if not url:
        return None
    if result.get("is_pdf"):
        resp = requests.get(url, headers=_DL_HEADERS, timeout=60)
        resp.raise_for_status()
        return resp.content, _filename(result, url)
    if result.get("source") == "edgar":
        from sources.edgar import convert_filing_to_pdf
        pdf = convert_filing_to_pdf(url)
        if pdf:
            return pdf, _filename(result, url)
    return None


if __name__ == "__main__":
    # ponytail: one runnable check for the filename branches (no network).
    assert _filename({"source": "edgar"}, "https://x/kos-20231231.htm") == "kos-20231231.pdf"
    assert _filename({"is_pdf": True}, "https://x/report.pdf?y=1") == "report.pdf"
    assert _filename({"company": "Hermès", "matched_fy": "2023"}, "https://x/doc") == "Hermès_2023.pdf"
    print("ok")
