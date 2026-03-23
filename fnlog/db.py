"""
FNLog — SQLite database layer.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from fnlog.config import DB_PATH


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            epic_name   TEXT NOT NULL,
            taken_at    TEXT NOT NULL,
            label       TEXT,
            data        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            epic_name       TEXT NOT NULL,
            started_at      TEXT NOT NULL,
            ended_at        TEXT NOT NULL,
            duration_min    INTEGER,
            notes           TEXT,
            season          TEXT DEFAULT '',
            matches         INTEGER DEFAULT 0,
            wins            INTEGER DEFAULT 0,
            kills           INTEGER DEFAULT 0,
            top10           INTEGER DEFAULT 0,
            minutes_played  INTEGER DEFAULT 0,
            mode_deltas     TEXT DEFAULT '{}',
            kd              REAL DEFAULT 0.0,
            win_rate        REAL DEFAULT 0.0,
            kills_per_match REAL DEFAULT 0.0,
            snap_start_id   INTEGER,
            snap_end_id     INTEGER
        );

        CREATE TABLE IF NOT EXISTS ranked_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            epic_name   TEXT NOT NULL,
            taken_at    TEXT NOT NULL,
            label       TEXT,
            mode        TEXT NOT NULL,
            data        TEXT NOT NULL
        );
        """)
        # Migrate: add season column if missing
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN season TEXT DEFAULT ''")
        except Exception:
            pass


def save_snapshot(epic_name: str, data: dict, label: str = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO snapshots (epic_name, taken_at, label, data) VALUES (?,?,?,?)",
            (epic_name, datetime.now().isoformat(), label, json.dumps(data))
        )
        return cur.lastrowid


def save_ranked_snapshot(epic_name: str, mode: str, data: dict, label: str = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO ranked_snapshots (epic_name, taken_at, label, mode, data) VALUES (?,?,?,?,?)",
            (epic_name, datetime.now().isoformat(), label, mode, json.dumps(data))
        )
        return cur.lastrowid


def get_snapshot(snap_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM snapshots WHERE id=?", (snap_id,)).fetchone()
        if row:
            return {**dict(row), "data": json.loads(row["data"])}
    return None


def get_latest_snapshot(epic_name: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE epic_name=? ORDER BY id DESC LIMIT 1",
            (epic_name,)
        ).fetchone()
        if row:
            return {**dict(row), "data": json.loads(row["data"])}
    return None


def save_session(session: dict) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO sessions (
                epic_name, started_at, ended_at, duration_min, notes, season,
                matches, wins, kills, top10, minutes_played,
                mode_deltas, kd, win_rate, kills_per_match,
                snap_start_id, snap_end_id
            ) VALUES (
                :epic_name, :started_at, :ended_at, :duration_min, :notes, :season,
                :matches, :wins, :kills, :top10, :minutes_played,
                :mode_deltas, :kd, :win_rate, :kills_per_match,
                :snap_start_id, :snap_end_id
            )
        """, {**session, "mode_deltas": json.dumps(session.get("mode_deltas", {})),
              "season": session.get("season", "")})
        return cur.lastrowid


def _row_to_session(row) -> dict:
    d = dict(row)
    md = d.get("mode_deltas", "{}")
    d["mode_deltas"]     = json.loads(md) if isinstance(md, str) else (md or {})
    d["kd"]              = float(d.get("kd") or 0.0)
    d["win_rate"]        = float(d.get("win_rate") or 0.0)
    d["kills_per_match"] = float(d.get("kills_per_match") or 0.0)
    d["matches"]         = int(d.get("matches") or 0)
    d["wins"]            = int(d.get("wins") or 0)
    d["kills"]           = int(d.get("kills") or 0)
    d["minutes_played"]  = int(d.get("minutes_played") or 0)
    d["top10"]           = int(d.get("top10") or 0)
    d["season"]          = str(d.get("season") or "")
    return d


def get_sessions(epic_name: str, limit: int = 50, season: str = None) -> list[dict]:
    with get_conn() as conn:
        if season:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE epic_name=? AND season=? ORDER BY id DESC LIMIT ?",
                (epic_name, season, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE epic_name=? ORDER BY id DESC LIMIT ?",
                (epic_name, limit)
            ).fetchall()
        return [_row_to_session(row) for row in rows]


def get_session(session_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row:
            return _row_to_session(row)
    return None


def get_career_totals(epic_name: str, season: str = None) -> dict:
    with get_conn() as conn:
        if season:
            row = conn.execute("""
                SELECT COUNT(*) as total_sessions, SUM(matches) as total_matches,
                       SUM(wins) as total_wins, SUM(kills) as total_kills,
                       SUM(minutes_played) as total_minutes
                FROM sessions WHERE epic_name=? AND season=?
            """, (epic_name, season)).fetchone()
        else:
            row = conn.execute("""
                SELECT COUNT(*) as total_sessions, SUM(matches) as total_matches,
                       SUM(wins) as total_wins, SUM(kills) as total_kills,
                       SUM(minutes_played) as total_minutes
                FROM sessions WHERE epic_name=?
            """, (epic_name,)).fetchone()
        return dict(row) if row else {}


def get_bests(epic_name: str, season: str = None) -> dict:
    """Return best session stats for highlights."""
    sessions = get_sessions(epic_name, limit=9999, season=season)
    real = [s for s in sessions if s["matches"] > 0]
    if not real:
        return {}
    return {
        "most_kills":    max(real, key=lambda s: s["kills"]),
        "best_kd":       max(real, key=lambda s: s["kd"]),
        "most_wins":     max(real, key=lambda s: s["wins"]),
        "most_matches":  max(real, key=lambda s: s["matches"]),
    }


def get_win_streak(epic_name: str, season: str = None) -> dict:
    """Calculate current and longest win streaks (sessions with at least 1 win)."""
    sessions = list(reversed(get_sessions(epic_name, limit=9999, season=season)))
    real = [s for s in sessions if s["matches"] > 0]

    current = 0
    for s in reversed(real):
        if s["wins"] > 0:
            current += 1
        else:
            break

    longest = 0
    run = 0
    for s in real:
        if s["wins"] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    return {"current": current, "longest": longest}


def get_seasons(epic_name: str) -> list[str]:
    """Return list of all seasons that have sessions."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT season FROM sessions WHERE epic_name=? AND season != '' ORDER BY season DESC",
            (epic_name,)
        ).fetchall()
        return [r["season"] for r in rows]


def clean_empty_sessions(epic_name: str) -> int:
    """Delete sessions with 0 matches. Returns count deleted."""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM sessions WHERE epic_name=? AND matches=0", (epic_name,)
        )
        return cur.rowcount
