"""
FNLog — FastAPI vaporwave web dashboard.
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path
import json
from jinja2 import Environment, FileSystemLoader

from fnlog.db import (
    get_sessions, get_career_totals, init_db, get_session,
    get_bests, get_win_streak, get_seasons,
)
from fnlog.config import MODES, RANKED_MODES, EPIC_NAME, WEB_PORT

app = FastAPI(title="FNLog", docs_url=None, redoc_url=None)
TEMPLATES_DIR = Path(__file__).parent / "templates"
ALL_MODES = {**MODES, **RANKED_MODES}


def render(name: str, **ctx) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
    return env.get_template(name).render(**ctx)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def dashboard(player: str = None, season: str = None):
    epic = player or EPIC_NAME
    sessions = get_sessions(epic, limit=30, season=season or None)
    totals   = get_career_totals(epic, season=season or None)
    bests    = get_bests(epic, season=season or None)
    streak   = get_win_streak(epic, season=season or None)
    all_seasons = get_seasons(epic)

    chart_labels, chart_kills, chart_wins, chart_kd = [], [], [], []
    for s in reversed(sessions[:15]):
        chart_labels.append(str(s["ended_at"])[:10])
        chart_kills.append(int(s["kills"] or 0))
        chart_wins.append(int(s["wins"] or 0))
        chart_kd.append(round(float(s["kd"] or 0), 2))

    total_matches  = int(totals.get("total_matches") or 0)
    total_wins     = int(totals.get("total_wins") or 0)
    total_kills    = int(totals.get("total_kills") or 0)
    total_minutes  = int(totals.get("total_minutes") or 0)
    total_sessions = int(totals.get("total_sessions") or 0)
    win_rate       = round((total_wins / total_matches * 100), 1) if total_matches else 0.0
    hours          = round(total_minutes / 60, 1)
    avg_kills      = round(total_kills / total_sessions, 1) if total_sessions else 0.0
    streak_current = int(streak.get("current", 0))
    streak_longest = int(streak.get("longest", 0))

    def best_stat(key, field):
        if key in bests:
            return {"val": bests[key].get(field, 0), "id": bests[key].get("id", 0), "date": str(bests[key].get("ended_at",""))[:10]}
        return {"val": 0, "id": 0, "date": ""}

    flat_sessions = []
    for s in sessions:
        flat_sessions.append({
            "id":             int(s["id"]),
            "ended_at":       str(s["ended_at"])[:10],
            "season":         str(s.get("season") or ""),
            "matches":        int(s["matches"] or 0),
            "wins":           int(s["wins"] or 0),
            "kills":          int(s["kills"] or 0),
            "kd":             round(float(s["kd"] or 0), 2),
            "win_rate":       round(float(s["win_rate"] or 0), 1),
            "minutes_played": int(s["minutes_played"] or 0),
            "notes":          str(s["notes"] or ""),
        })

    html = render("dashboard.html",
        epic_name=str(epic),
        current_season=str(season or ""),
        all_seasons=all_seasons,
        sessions=flat_sessions,
        total_sessions=total_sessions,
        total_matches=total_matches,
        total_wins=total_wins,
        total_kills=total_kills,
        win_rate=win_rate,
        hours=hours,
        avg_kills=avg_kills,
        streak_current=streak_current,
        streak_longest=streak_longest,
        best_kills=best_stat("most_kills", "kills"),
        best_kd=best_stat("best_kd", "kd"),
        best_wins=best_stat("most_wins", "wins"),
        chart_labels=json.dumps(chart_labels),
        chart_kills=json.dumps(chart_kills),
        chart_wins=json.dumps(chart_wins),
        chart_kd=json.dumps(chart_kd),
    )
    return HTMLResponse(html)


@app.get("/session/{session_id}", response_class=HTMLResponse)
async def session_detail(session_id: int):
    session = get_session(session_id)
    if not session:
        return HTMLResponse("<h1>Session not found</h1>", status_code=404)

    mode_rows = []
    for mode_key, d in (session.get("mode_deltas") or {}).items():
        if not isinstance(d, dict) or not d.get("matches"):
            continue
        mode_rows.append({
            "name":           str(ALL_MODES.get(mode_key, mode_key)),
            "matches":        int(d.get("matches") or 0),
            "wins":           int(d.get("wins") or 0),
            "kills":          int(d.get("kills") or 0),
            "kd":             round(float(d.get("kd") or 0), 2),
            "win_rate":       round(float(d.get("win_rate") or 0), 1),
            "minutes_played": int(d.get("minutes_played") or 0),
        })

    flat = {
        "id":             int(session["id"]),
        "started_at":     str(session["started_at"])[:16].replace("T", " "),
        "ended_at":       str(session["ended_at"])[:16].replace("T", " "),
        "duration_min":   int(session["duration_min"] or 0),
        "season":         str(session.get("season") or ""),
        "matches":        int(session["matches"] or 0),
        "wins":           int(session["wins"] or 0),
        "kills":          int(session["kills"] or 0),
        "kd":             round(float(session["kd"] or 0), 2),
        "win_rate":       round(float(session["win_rate"] or 0), 1),
        "minutes_played": int(session["minutes_played"] or 0),
        "notes":          str(session.get("notes") or ""),
    }

    html = render("session.html", session=flat, mode_rows=mode_rows)
    return HTMLResponse(html)


@app.get("/share/{session_id}", response_class=HTMLResponse)
async def share_card(session_id: int):
    session = get_session(session_id)
    if not session:
        return HTMLResponse("<h1>Session not found</h1>", status_code=404)

    mode_rows = []
    for mode_key, d in (session.get("mode_deltas") or {}).items():
        if not isinstance(d, dict) or not d.get("matches"):
            continue
        mode_rows.append({
            "name":     str(ALL_MODES.get(mode_key, mode_key)),
            "matches":  int(d.get("matches") or 0),
            "wins":     int(d.get("wins") or 0),
            "kills":    int(d.get("kills") or 0),
            "kd":       round(float(d.get("kd") or 0), 2),
            "win_rate": round(float(d.get("win_rate") or 0), 1),
        })

    flat = {
        "id":           int(session["id"]),
        "ended_at":     str(session["ended_at"])[:10],
        "season":       str(session.get("season") or ""),
        "epic_name":    str(session.get("epic_name") or EPIC_NAME),
        "matches":      int(session["matches"] or 0),
        "wins":         int(session["wins"] or 0),
        "kills":        int(session["kills"] or 0),
        "kd":           round(float(session["kd"] or 0), 2),
        "win_rate":     round(float(session["win_rate"] or 0), 1),
        "minutes_played": int(session["minutes_played"] or 0),
        "notes":        str(session.get("notes") or ""),
    }

    html = render("share.html", session=flat, mode_rows=mode_rows)
    return HTMLResponse(html)


@app.get("/api/sessions")
async def api_sessions(player: str = None, season: str = None, limit: int = 30):
    epic = player or EPIC_NAME
    return get_sessions(epic, limit=limit, season=season or None)


def run_web(host: str = "0.0.0.0", port: int = None, reload: bool = False):
    import uvicorn
    import webbrowser
    import threading
    p = port or WEB_PORT
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{p}")).start()
    uvicorn.run("fnlog.web:app", host=host, port=p, reload=False)