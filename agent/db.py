import json
import sqlite3
from .config import DB_PATH


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS universities (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            website     TEXT,
            sources     TEXT DEFAULT '[]',
            rank_qs     INTEGER,
            rank_times  INTEGER,
            rank_arwu   INTEGER,
            status      TEXT DEFAULT 'pending',
            faculty_urls TEXT DEFAULT '[]',
            phd_urls     TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS professors (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id     INTEGER NOT NULL,
            page_url          TEXT UNIQUE NOT NULL,
            name              TEXT,
            title             TEXT,
            department        TEXT,
            research_summary  TEXT,
            match_score       INTEGER DEFAULT 0,
            match_reason      TEXT,
            contact           TEXT,
            status            TEXT DEFAULT 'pending',
            FOREIGN KEY (university_id) REFERENCES universities(id)
        );

        CREATE TABLE IF NOT EXISTS phd_programs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            university_id INTEGER NOT NULL,
            page_url      TEXT UNIQUE NOT NULL,
            programs_json TEXT DEFAULT '[]',
            status        TEXT DEFAULT 'pending',
            FOREIGN KEY (university_id) REFERENCES universities(id)
        );
        """)


# ── Universities ─────────────────────────────────────────────────────────────

def upsert_university(name, website=None, sources=None,
                      rank_qs=None, rank_times=None, rank_arwu=None):
    with _conn() as c:
        c.execute("""
        INSERT INTO universities (name, website, sources, rank_qs, rank_times, rank_arwu)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            website    = COALESCE(excluded.website, website),
            sources    = excluded.sources,
            rank_qs    = COALESCE(excluded.rank_qs, rank_qs),
            rank_times = COALESCE(excluded.rank_times, rank_times),
            rank_arwu  = COALESCE(excluded.rank_arwu, rank_arwu)
        """, (name, website, json.dumps(sources or []), rank_qs, rank_times, rank_arwu))


def get_all_universities() -> list:
    with _conn() as c:
        return c.execute("SELECT * FROM universities ORDER BY id").fetchall()


def get_pending_universities() -> list:
    # Include 'crawling': a process that crashed left universities in that state
    with _conn() as c:
        return c.execute(
            "SELECT * FROM universities WHERE status IN ('pending', 'error', 'crawling') ORDER BY id"
        ).fetchall()


def set_university_crawling(uni_id: int, faculty_urls: list, phd_urls: list):
    with _conn() as c:
        c.execute(
            "UPDATE universities SET status='crawling', faculty_urls=?, phd_urls=? WHERE id=?",
            (json.dumps(faculty_urls), json.dumps(phd_urls), uni_id),
        )


def set_university_status(uni_id: int, status: str):
    with _conn() as c:
        c.execute("UPDATE universities SET status=? WHERE id=?", (status, uni_id))


# ── Professors ────────────────────────────────────────────────────────────────

def touch_professor(university_id: int, page_url: str):
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO professors (university_id, page_url) VALUES (?, ?)",
            (university_id, page_url),
        )


def save_professor(page_url: str, name: str, title: str, department: str,
                   research_summary: str, match_score: int, match_reason: str,
                   contact: str):
    with _conn() as c:
        c.execute("""
        UPDATE professors SET
            name=?, title=?, department=?, research_summary=?,
            match_score=?, match_reason=?, contact=?, status='done'
        WHERE page_url=?
        """, (name, title, department, research_summary,
              match_score, match_reason, contact, page_url))


def professor_is_done(page_url: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM professors WHERE page_url=? AND status='done'", (page_url,)
        ).fetchone()
        return row is not None


def phd_page_is_done(page_url: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM phd_programs WHERE page_url=? AND status='done'", (page_url,)
        ).fetchone()
        return row is not None


def get_matched_professors(threshold: int) -> list:
    with _conn() as c:
        return c.execute("""
        SELECT p.*, u.name AS uni_name, u.website AS uni_website,
               u.rank_qs, u.rank_times, u.rank_arwu, u.sources
        FROM professors p
        JOIN universities u ON p.university_id = u.id
        WHERE p.match_score >= ? AND p.status = 'done'
        ORDER BY u.name, p.match_score DESC
        """, (threshold,)).fetchall()


# ── PhD programs ──────────────────────────────────────────────────────────────

def touch_phd_page(university_id: int, page_url: str):
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO phd_programs (university_id, page_url) VALUES (?, ?)",
            (university_id, page_url),
        )


def save_phd_page(page_url: str, programs: list):
    with _conn() as c:
        c.execute(
            "UPDATE phd_programs SET programs_json=?, status='done' WHERE page_url=?",
            (json.dumps(programs), page_url),
        )


def get_all_phd_programs() -> list:
    with _conn() as c:
        return c.execute("""
        SELECT ph.*, u.name AS uni_name, u.website AS uni_website,
               u.rank_qs, u.rank_times, u.rank_arwu, u.sources
        FROM phd_programs ph
        JOIN universities u ON ph.university_id = u.id
        WHERE ph.status = 'done'
        ORDER BY u.name
        """).fetchall()
