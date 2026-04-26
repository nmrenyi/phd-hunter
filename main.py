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
    args = parser.parse_args()

    from agent.db import init_db, get_all_universities
    init_db()

    if args.report_only:
        from agent.report import generate
        path = generate()
        print(f"\nReport saved: {path}")
        return

    if args.resume:
        from agent.crawl import crawl_all
        from agent.report import generate
        crawl_all()
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


if __name__ == "__main__":
    main()
