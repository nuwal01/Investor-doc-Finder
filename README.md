# IDF — Investor Doc Finder

Python agent that locates verified investor documents (annual reports, 10-K /
20-F / 40-F filings) for companies worldwide from SEC EDGAR, India sources, and
web search, behind a content-verification gate.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then fill in LLM / search API keys
```

### System dependency: wkhtmltopdf (required for EDGAR PDF conversion)

EDGAR primary filings are XBRL-tagged HTML, never native PDF. When an EDGAR
HTML filing is the verified result, IDF converts it to PDF via `pdfkit`, which
drives the **wkhtmltopdf** binary. This is a system executable, *not* a pip
package — `pip install pdfkit` alone is not enough.

Install the binary:

| OS | Command |
|----|---------|
| Windows | `winget install --id wkhtmltopdf.wkhtmltox -e --source winget` |
| macOS | `brew install --cask wkhtmltopdf` |
| Debian/Ubuntu | `sudo apt install wkhtmltopdf` |

IDF finds it on `PATH`, falling back to the default Windows install location
(`C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`). **If wkhtmltopdf is
missing, EDGAR results are still returned — as the HTML URL instead of a
converted PDF** (conversion degrades gracefully, it never fails the query).

## Running

```bash
python main.py "Reliance Industries 2022 annual report"
streamlit run streamlit_app.py
pytest
```

See `CLAUDE.md` for architecture and file layout.
