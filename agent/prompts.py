from .config import CV_PATH

# Loaded once; used as a constant in all matching prompts
USER_PROFILE = CV_PATH.read_text(encoding="utf-8")

# ── Find entry points ─────────────────────────────────────────────────────────

ENTRY_POINTS_SYS = """\
You are a web navigator. Given a university homepage (as cleaned text with links), \
identify two sets of URLs:
1. faculty_urls — pages that list multiple professors / research staff \
   (e.g. department pages, faculty directories, "people" pages)
2. phd_urls — pages about PhD / doctoral program admissions

Return ONLY valid JSON, no other text:
{"faculty_urls": ["url1", "url2"], "phd_urls": ["url1", "url2"]}

Only include URLs that are literally present in the provided content. \
Limit to the 10 most relevant for each category."""

ENTRY_POINTS_USER = """\
University: {university_name}
Homepage: {homepage_url}

--- PAGE CONTENT ---
{text}
--- END ---

Return JSON."""

# ── Find professor links from a directory page ────────────────────────────────

PROF_LINKS_SYS = """\
You are navigating an academic website to find individual professor profile pages.

Given a page, return two lists:
- professor_urls: URLs of individual faculty member profile pages (one person per page, \
  e.g. /people/john-doe, /faculty/jane-smith). Include up to 60.
- deeper_urls: URLs of pages that likely LIST multiple professors — e.g. anchor text \
  contains "people", "faculty", "staff", "members", "researchers", "group", "team", \
  "directory". Only populate this if professor_urls is empty. Include up to 5.

Only include URLs that are literally present in the provided content. \
Do NOT invent or guess URLs.

Return ONLY valid JSON:
{"professor_urls": ["url1", "url2"], "deeper_urls": ["url3"]}"""

PROF_LINKS_USER = """\
Page URL: {url}

--- PAGE CONTENT ---
{text}
--- END ---

Return JSON."""

# ── Extract professor profile ─────────────────────────────────────────────────

PROF_EXTRACT_SYS = """\
You are extracting structured data from an academic professor's profile page.

Return ONLY valid JSON:
{
  "name": "Full Name",
  "title": "e.g. Associate Professor",
  "department": "Department name",
  "research_summary": "2-3 sentences describing research topics and methods",
  "contact": "email address or empty string"
}

If this page does not belong to a professor or researcher, return: {"skip": true}"""

PROF_EXTRACT_USER = """\
Profile URL: {url}

--- PAGE CONTENT ---
{text}
--- END ---

Return JSON."""

# ── Match professor to applicant ──────────────────────────────────────────────

MATCH_SYS = """\
You are evaluating how well a professor's research matches a PhD applicant's profile.

=== APPLICANT PROFILE ===
""" + USER_PROFILE + """
=== END PROFILE ===

Score the fit 1–5:
5 = Excellent — directly overlapping research, ideal advisor candidate
4 = Good — clearly related area with real synergies
3 = Moderate — adjacent field, some overlap
2 = Weak — different area, only methodological similarity
1 = No match — completely different field

Return ONLY valid JSON:
{"score": 4, "reason": "One sentence explaining the fit."}"""

MATCH_USER = """\
Professor: {name} ({title})
Department: {department}
University: {university}

Research: {research_summary}

Return match JSON."""

# ── Extract PhD programs ──────────────────────────────────────────────────────

PHD_EXTRACT_SYS = """\
You are extracting doctoral program information from a graduate admissions page.

Return ONLY valid JSON:
{
  "programs": [
    {
      "program_name": "PhD in Computer Science",
      "department": "Department of Computer Science",
      "deadline": "December 15, 2026",
      "funding": "Fully funded / Partial / Self-funded / unknown",
      "stipend": "$X/year or unknown",
      "focus_areas": "AI, NLP, systems, ...",
      "application_url": "direct URL or empty string"
    }
  ]
}

Include only PhD/doctoral programs, not master's. \
If no PhD programs found, return {"programs": []}."""

PHD_EXTRACT_USER = """\
University: {university_name}
Page URL: {url}

--- PAGE CONTENT ---
{text}
--- END ---

Return JSON."""
