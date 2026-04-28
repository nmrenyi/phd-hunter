# PhD Hunter

An autonomous agent that crawls 100+ top-ranked universities, reads faculty profiles, and scores each professor's research fit against your CV — running entirely on a local LLM, no cloud API costs.

Built to solve a real problem: finding the right PhD advisors across hundreds of universities is tedious and time-consuming. This agent does it overnight.

## How it works

```
University rankings (Wikipedia)
        ↓
  SQLite checkpoint DB
        ↓
  Per-university crawl
  ├── Homepage → discover faculty directories + PhD admission pages
  ├── Faculty pages → collect individual professor profile URLs
  └── Each profile → LLM extracts name / title / research summary
        ↓
  LLM scores research fit against your CV (1–5)
        ↓
  report.md  (professors scoring ≥ 4, with PhD program info)
```

The pipeline is a three-node [LangGraph](https://github.com/langchain-ai/langgraph) state machine. Every university and professor page is checkpointed in SQLite, so the agent can resume from any crash or interruption.

## Stack

| Concern | Choice |
|---|---|
| LLM | [Ollama](https://ollama.com) · `qwen3.5:9b` locally |
| Orchestration | LangGraph state machine |
| Web fetching | httpx → Playwright fallback for JS-heavy sites |
| Persistence | SQLite (crash-safe, resumable) |
| HTML parsing | BeautifulSoup + lxml |

## Setup

```bash
# 1. Install uv  →  https://docs.astral.sh/uv/
# 2. Pull the model
ollama pull qwen3.5:9b

# 3. Put your CV in cv/cv.md  (plain markdown, any structure)

# 4. Install dependencies and run
uv run python main.py
```

## Usage

```
python main.py                 # full run: seed rankings → crawl → report
python main.py --resume        # skip ranking phase, continue crawl from checkpoint
python main.py --report-only   # regenerate report.md from existing DB (read-only)
python main.py --limit N       # cap to N universities (useful for testing)
python main.py --test          # wipe DB, seed EPFL + ETH Zurich, run end-to-end
```

## Output

`data/report.md` — one section per university, matched professors first:

```markdown
## EPFL

### Antoine Bosselut [5/5]
*Tenure Track Assistant Professor · NLP Lab*

Research on NLP systems that model, represent, and reason about human and world knowledge.

**Why a match:** Directly aligns with applicant's work on LLMs, RAG, and knowledge extraction.

**Contact:** antoine.bosselut@epfl.ch
```

### Real results

Run across 107 universities (~10 hours on an M-series Mac): **43 professors matched** across 17 universities, including EPFL, CMU, UT Austin, HKUST, and UNSW.

## Configuration

Edit `agent/config.py` to change the LLM model, match threshold, or rate limits:

```python
LLM_MODEL = "qwen3.5:9b"   # any model available in Ollama
MATCH_THRESHOLD = 4         # minimum score (out of 5) to appear in report
REQUEST_DELAY = 1.0         # seconds between requests to the same domain
```
