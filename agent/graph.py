from typing import TypedDict

from langgraph.graph import END, StateGraph

from .crawl import crawl_all
from .db import init_db
from .rankings import fetch_all_rankings
from .report import generate


class State(TypedDict):
    phase: str
    universities_total: int
    report_path: str


def _fetch_rankings(state: State) -> State:
    count = fetch_all_rankings()
    return {**state, "phase": "crawl", "universities_total": count}


def _crawl(state: State) -> State:
    crawl_all()
    return {**state, "phase": "report"}


def _report(state: State) -> State:
    path = generate()
    return {**state, "phase": "done", "report_path": path}


def build_graph():
    init_db()

    g = StateGraph(State)
    g.add_node("fetch_rankings", _fetch_rankings)
    g.add_node("crawl", _crawl)
    g.add_node("report", _report)

    g.set_entry_point("fetch_rankings")
    g.add_edge("fetch_rankings", "crawl")
    g.add_edge("crawl", "report")
    g.add_edge("report", END)

    return g.compile()
