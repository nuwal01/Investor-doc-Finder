# CLAUDE.md

> This file is loaded automatically into context at the start of every Claude Code
> session. Keep it accurate, factual, and concise — treat it like onboarding docs
> for a new engineer joining the project.

## Project description

IDF (Investor Doc Finder) is a Python agent that locates publicly available investor documents — annual reports, 10-K filings — for companies worldwide. Given a free-text query like `"Apple 2022 annual report"`, the agent parses intent, resolves company identifiers, queries the appropriate source (SEC EDGAR for US companies, NSE for Indian companies, web search as fallback), verifies the returned document, and caches the result.

## Tech stack

- Language: Python 3.11
- Orchestration: LangGraph (stateful agent graph)
- LLM providers: Google Generative AI (`google-generativeai`), OpenAI (`openai`)
- HTTP clients: `requests`, `httpx`
- PDF handling: `pypdf`
- HTML parsing: `beautifulsoup4`, `lxml`
- UI: Streamlit (`streamlit_app.py`)
- Caching: SQLite (`cache.db`) via `cache.py`
- Config: `python-dotenv` (`.env` file)
- Testing: `pytest`

## Running & testing

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env

# Run the CLI (defaults to "Apple 2022 annual report")
python main.py
python main.py "Reliance Industries 2022 annual report"
python main.py --step1   # Step-1 regression, no LLM

# Run the Streamlit web UI
streamlit run streamlit_app.py

# Run tests
pytest
```

## Important file locations

- CLI entry point: `main.py`
- Streamlit UI: `streamlit_app.py`
- API layer: `api.py`
- LangGraph agent graph: `agent.py`
- Query intent parsing: `intent.py`
- Company ID resolution: `resolver.py`
- Document verification: `verify.py`
- LLM abstraction: `llm_client.py`
- SQLite cache: `cache.py` / `cache.db`
- Data sources: `sources/` (edgar, nse, web_search, aggregators)
- Static data: `data/` (company_map.csv, edgar_tickers.json)
- Environment config: `.env` (see `.env.example`)

## Coding conventions

- Follow PEP 8; use type hints throughout.
- Module-level `logger = logging.getLogger(__name__)` — no `print()` in library code.
- Each source adapter in `sources/` must implement the protocol defined in `sources/base.py`.
- Keep agent graph nodes pure: each node returns a dict of state updates only.
- Do not commit `.env` or `cache.db`.

## Working agreement

- At the start of any task, read PROGRESS.md to see current state before doing anything.
- After completing a step, update PROGRESS.md with what was done and what's next.
- Always run pytest before saying a task is complete.
