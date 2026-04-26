"""Generate the final markdown report from DB results."""
import json
import logging
from collections import defaultdict

from .config import MATCH_THRESHOLD, REPORT_PATH
from .db import get_all_phd_programs, get_all_universities, get_matched_professors

logger = logging.getLogger(__name__)


def _rank_str(row: dict) -> str:
    parts = []
    if row.get("rank_qs"):
        parts.append(f"QS #{row['rank_qs']}")
    if row.get("rank_times"):
        parts.append(f"Times #{row['rank_times']}")
    if row.get("rank_arwu"):
        parts.append(f"ARWU #{row['rank_arwu']}")
    return " · ".join(parts) if parts else "Ranked"


def generate() -> str:
    REPORT_PATH.parent.mkdir(exist_ok=True)

    professors = get_matched_professors(MATCH_THRESHOLD)
    phd_rows = get_all_phd_programs()
    all_unis = {u["name"]: dict(u) for u in get_all_universities()}

    profs_by_uni: dict[str, list] = defaultdict(list)
    for p in professors:
        profs_by_uni[p["uni_name"]].append(dict(p))

    phd_by_uni: dict[str, list] = defaultdict(list)
    for row in phd_rows:
        programs = json.loads(row["programs_json"] or "[]")
        if programs:
            phd_by_uni[row["uni_name"]].extend(programs)

    uni_names = sorted(set(list(profs_by_uni) + list(phd_by_uni)))

    lines: list[str] = [
        "# PhD Program & Professor Match Report\n",
        f"*Match threshold: {MATCH_THRESHOLD}/5 — generated for Ren Yi*\n",
        f"- Universities crawled: {len(all_unis)}",
        f"- Matched professors: {len(professors)}",
        f"- Universities with matches: {len(uni_names)}\n",
        "---\n",
    ]

    for uni_name in uni_names:
        uni = all_unis.get(uni_name, {})
        website = uni.get("website", "")
        header = f"[{uni_name}]({website})" if website else uni_name
        lines.append(f"## {header}\n")
        lines.append(f"*{_rank_str(uni)}*\n")

        # PhD programs
        phds = phd_by_uni.get(uni_name, [])
        if phds:
            lines.append("### PhD Programs\n")
            for prog in phds:
                name = prog.get("program_name") or "PhD Program"
                lines.append(f"#### {name}\n")
                for label, key in [
                    ("Department", "department"),
                    ("Deadline", "deadline"),
                    ("Funding", "funding"),
                    ("Stipend", "stipend"),
                    ("Focus areas", "focus_areas"),
                ]:
                    val = prog.get(key, "")
                    if val and val.lower() != "unknown":
                        lines.append(f"**{label}:** {val}  ")
                app_url = prog.get("application_url", "")
                if app_url:
                    lines.append(f"\n[Apply / Program page]({app_url})\n")
                lines.append("")

        # Matched professors
        profs = profs_by_uni.get(uni_name, [])
        if profs:
            lines.append("### Matched Professors\n")
            for prof in sorted(profs, key=lambda x: -(x.get("match_score") or 0)):
                score = prof.get("match_score", 0)
                name = prof.get("name") or "Unknown"
                score_label = f"[{score}/5]"
                lines.append(f"#### {name} {score_label}\n")

                meta = " · ".join(filter(None, [prof.get("title"), prof.get("department")]))
                if meta:
                    lines.append(f"*{meta}*\n")

                if prof.get("research_summary"):
                    lines.append(f"{prof['research_summary']}\n")

                if prof.get("match_reason"):
                    lines.append(f"**Why a match:** {prof['match_reason']}\n")

                if prof.get("contact"):
                    lines.append(f"**Contact:** {prof['contact']}  ")

                if prof.get("page_url"):
                    lines.append(f"[Profile]({prof['page_url']})\n")

                lines.append("")

        lines.append("---\n")

    text = "\n".join(lines)
    REPORT_PATH.write_text(text, encoding="utf-8")
    logger.info("Report written to %s (%d universities, %d professors)",
                REPORT_PATH, len(uni_names), len(professors))
    return str(REPORT_PATH)
