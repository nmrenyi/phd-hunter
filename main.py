"""
PhD Professor & Program Matching Agent
Driven by qwen3.5:9b running locally via Ollama.

Usage:
  python main.py                 # full run: rankings → crawl → report
  python main.py --resume        # skip ranking fetch, continue crawl from checkpoint
  python main.py --report-only   # regenerate report from existing DB data
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)


def main():
    parser = argparse.ArgumentParser(description="PhD matching agent")
    parser.add_argument("--resume", action="store_true",
                        help="Skip ranking fetch; crawl only pending universities")
    parser.add_argument("--report-only", action="store_true",
                        help="Regenerate report.md from existing DB data")
    parser.add_argument("--limit", type=int, default=0, metavar="N",
                        help="Process at most N universities (useful for testing)")
    parser.add_argument("--test", action="store_true",
                        help="Seed 2 universities and run a quick end-to-end test")
    args = parser.parse_args()

    from agent.db import init_db
    init_db()

    if args.report_only:
        from agent.report import generate
        path = generate()
        print(f"\nReport saved: {path}")
        return

    if args.test:
        _run_test()
        return

    if args.resume:
        from agent.crawl import crawl_all
        from agent.report import generate
        crawl_all(limit=args.limit)
        path = generate()
        print(f"\nReport saved: {path}")
        return

    # Full pipeline via LangGraph
    from agent.graph import build_graph
    graph = build_graph()
    result = graph.invoke({
        "phase": "fetch_rankings",
        "universities_total": 0,
        "report_path": "",
    })
    print(f"\nDone. Report saved: {result['report_path']}")


def _run_test():
    """Wipe DB, seed 2 universities, run the full pipeline on them."""
    import sqlite3
    from agent.config import DB_PATH
    from agent.db import init_db, upsert_university
    from agent.crawl import crawl_all
    from agent.report import generate

    # Start clean so leftover data never pollutes test results
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()

    test_unis = [
        ("EPFL", "https://www.epfl.ch/en"),
        ("ETH Zurich", "https://ethz.ch/en"),
    ]
    print("Seeding test universities:", [u[0] for u in test_unis])
    for name, website in test_unis:
        upsert_university(name, website=website, sources=["test"])

    crawl_all(limit=len(test_unis))
    path = generate()
    print(f"\nTest run complete. Report saved: {path}")


if __name__ == "__main__":
    main()
