"""
FNLog CLI — Fortnite Zero Build session tracker.
"""

import click
import json
import sys
import csv
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

from fnlog.config import EPIC_NAME, API_KEY, MODES, RANKED_MODES, WEB_PORT, CURRENT_SEASON, DISCORD_WEBHOOK
from fnlog.db import (
    init_db, save_snapshot, save_ranked_snapshot, save_session,
    get_sessions, get_latest_snapshot, get_career_totals,
    get_bests, get_win_streak, get_seasons, clean_empty_sessions,
)
from fnlog.api import get_stats, get_ranked_stats, compute_delta
from fnlog.discord import send_session_embed

console = Console()
ALL_MODES = {**MODES, **RANKED_MODES}

BANNER = """[bold #b44fff]
███████╗███╗   ██╗██╗      ██████╗  ██████╗
██╔════╝████╗  ██║██║     ██╔═══██╗██╔════╝
█████╗  ██╔██╗ ██║██║     ██║   ██║██║  ███╗
██╔══╝  ██║╚██╗██║██║     ██║   ██║██║   ██║
██║     ██║ ╚████║███████╗╚██████╔╝╚██████╔╝
╚═╝     ╚═╝  ╚═══╝╚══════╝ ╚═════╝  ╚═════╝[/bold #b44fff]
[#ff4fb8]Zero Build Session Tracker[/#ff4fb8] [#7070a0]// mskeith[/#7070a0]
"""

STATE_FILE = Path.home() / ".fnlog" / "active_session.json"

# Current season — update each new season


def _check_config():
    if not API_KEY:
        console.print("[red]FNLOG_API_KEY not set.[/red] Add it to your .env file.")
        sys.exit(1)
    if not EPIC_NAME:
        console.print("[red]FNLOG_EPIC_NAME not set.[/red] Add your Epic display name to .env")
        sys.exit(1)


def _save_state(data: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data))


def _load_state() -> dict | None:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return None


def _clear_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()


@click.group()
def main():
    """FNLog — Fortnite Zero Build session tracker."""
    init_db()


@main.command()
@click.option("--player", "-p", default=None)
@click.option("--season", "-s", default=None, help="Season tag e.g. Ch6S2")
def start(player, season):
    """Start a new session — snapshots your current stats."""
    console.print(BANNER)
    _check_config()

    epic = player or EPIC_NAME
    tag = season or CURRENT_SEASON

    if _load_state():
        console.print("[yellow]A session is already active.[/yellow] Run [cyan]fnlog end[/cyan] first.")
        sys.exit(1)

    console.print(f"[#7070a0]Fetching stats for[/#7070a0] [#00d4ff]{epic}[/#00d4ff][#7070a0]...[/#7070a0]")

    try:
        stats = get_stats(epic)
        ranked = get_ranked_stats(epic)
    except Exception as e:
        console.print(f"[red]API error:[/red] {e}")
        sys.exit(1)

    snap_id = save_snapshot(epic, stats, label="session_start")
    save_ranked_snapshot(epic, "ranked_br", ranked.get("ranked_br", {}), label="session_start")
    save_ranked_snapshot(epic, "ranked_reload", ranked.get("ranked_reload", {}), label="session_start")

    _save_state({
        "epic": epic,
        "season": tag,
        "started_at": datetime.now().isoformat(),
        "snap_start_id": snap_id,
    })

    overall = stats.get("overall", {})
    console.print(Panel(
        f"[bold #ff4fb8]Session started![/bold #ff4fb8]\n\n"
        f"[#7070a0]Player:[/#7070a0]  [#00d4ff]{epic}[/#00d4ff]\n"
        f"[#7070a0]Season:[/#7070a0]  [#b44fff]{tag}[/#b44fff]\n"
        f"[#7070a0]Time:[/#7070a0]    [#e0e0ff]{datetime.now().strftime('%I:%M %p')}[/#e0e0ff]\n\n"
        f"[#7070a0]Career at start:[/#7070a0]\n"
        f"  Matches: [#00f5d4]{overall.get('matches', 0)}[/#00f5d4]   "
        f"Wins: [#b44fff]{overall.get('wins', 0)}[/#b44fff]   "
        f"Kills: [#00d4ff]{overall.get('kills', 0)}[/#00d4ff]\n\n"
        f"[dim]Go play! Run [cyan]fnlog end[/cyan] when you're done.[/dim]",
        title="[bold #b44fff]FNLog[/bold #b44fff]",
        border_style="#2a2a4a",
    ))


@main.command()
@click.option("--notes", "-n", default=None)
def end(notes):
    """End the active session — calculates deltas and saves results."""
    console.print(BANNER)
    _check_config()

    state = _load_state()
    if not state:
        console.print("[yellow]No active session.[/yellow] Run [cyan]fnlog start[/cyan] first.")
        sys.exit(1)

    epic = state["epic"]
    started_at = state["started_at"]
    snap_start_id = state["snap_start_id"]
    season = state.get("season", CURRENT_SEASON)

    console.print(f"[#7070a0]Fetching end stats for[/#7070a0] [#00d4ff]{epic}[/#00d4ff][#7070a0]...[/#7070a0]")

    try:
        stats_end = get_stats(epic)
        ranked_end = get_ranked_stats(epic)
    except Exception as e:
        console.print(f"[red]API error:[/red] {e}")
        sys.exit(1)

    snap_end_id = save_snapshot(epic, stats_end, label="session_end")
    save_ranked_snapshot(epic, "ranked_br", ranked_end.get("ranked_br", {}), label="session_end")
    save_ranked_snapshot(epic, "ranked_reload", ranked_end.get("ranked_reload", {}), label="session_end")

    from fnlog.db import get_snapshot, get_conn
    snap_start = get_snapshot(snap_start_id)
    if not snap_start:
        console.print("[red]Could not load start snapshot.[/red]")
        sys.exit(1)

    deltas = compute_delta(snap_start["data"], stats_end)

    # Ranked deltas
    with get_conn() as conn:
        rs = conn.execute(
            "SELECT * FROM ranked_snapshots WHERE epic_name=? AND label='session_start' ORDER BY id DESC LIMIT 2",
            (epic,)
        ).fetchall()
        re_ = conn.execute(
            "SELECT * FROM ranked_snapshots WHERE epic_name=? AND label='session_end' ORDER BY id DESC LIMIT 2",
            (epic,)
        ).fetchall()

    ranked_start_map = {r["mode"]: json.loads(r["data"]) for r in rs}
    ranked_end_map   = {r["mode"]: json.loads(r["data"]) for r in re_}

    for mode in ["ranked_br", "ranked_reload"]:
        rs_data = ranked_start_map.get(mode, {})
        re_data = ranked_end_map.get(mode, {})
        if rs_data and re_data:
            rd = compute_delta({mode: rs_data}, {mode: re_data})
            deltas.update(rd)

    ov = deltas.get("overall", {})
    matches        = ov.get("matches", sum(d.get("matches", 0) for d in deltas.values() if isinstance(d, dict)))
    wins           = ov.get("wins", 0)
    kills          = ov.get("kills", 0)
    minutes_played = ov.get("minutes_played", 0)
    kd             = ov.get("kd", 0.0)
    win_rate       = ov.get("win_rate", 0.0)
    kpm            = ov.get("kills_per_match", 0.0)

    ended_at = datetime.now()
    started_dt = datetime.fromisoformat(started_at)
    duration_min = int((ended_at - started_dt).total_seconds() / 60)

    if not notes:
        notes = Prompt.ask("[#7070a0]Session notes (optional)[/#7070a0]", default="")

    session_id = save_session({
        "epic_name":       epic,
        "started_at":      started_at,
        "ended_at":        ended_at.isoformat(),
        "duration_min":    duration_min,
        "notes":           notes or None,
        "season":          season,
        "matches":         matches,
        "wins":            wins,
        "kills":           kills,
        "top10":           ov.get("top10", 0),
        "minutes_played":  minutes_played,
        "mode_deltas":     {k: v for k, v in deltas.items() if k != "overall"},
        "kd":              kd,
        "win_rate":        win_rate,
        "kills_per_match": kpm,
        "snap_start_id":   snap_start_id,
        "snap_end_id":     snap_end_id,
    })

    _clear_state()

    kd_color = "#00f5d4" if kd >= 1.0 else "#ff4fb8"
    mode_lines = []
    for mode, d in deltas.items():
        if mode == "overall" or not isinstance(d, dict) or d.get("matches", 0) == 0:
            continue
        name = ALL_MODES.get(mode, mode)
        mode_lines.append(
            f"  [#ff4fb8]{name:<22}[/#ff4fb8]"
            f"  M:[#e0e0ff]{d['matches']}[/#e0e0ff]"
            f"  W:[#b44fff]{d['wins']}[/#b44fff]"
            f"  K:[#00d4ff]{d['kills']}[/#00d4ff]"
            f"  K/D:[{kd_color}]{d['kd']:.2f}[/{kd_color}]"
            f"  Win%:[#ff4fb8]{d['win_rate']:.1f}%[/#ff4fb8]"
        )

    summary = (
        f"[bold #ff4fb8]Session Complete! // #{session_id}[/bold #ff4fb8]\n\n"
        f"[#7070a0]Season:[/#7070a0]    [#b44fff]{season}[/#b44fff]\n"
        f"[#7070a0]Duration:[/#7070a0]  [#e0e0ff]{duration_min} min[/#e0e0ff]\n"
        f"[#7070a0]Matches:[/#7070a0]   [#e0e0ff]{matches}[/#e0e0ff]\n"
        f"[#7070a0]Wins:[/#7070a0]      [#b44fff]{wins}[/#b44fff]\n"
        f"[#7070a0]Kills:[/#7070a0]     [#00d4ff]{kills}[/#00d4ff]\n"
        f"[#7070a0]K/D:[/#7070a0]       [{kd_color}]{kd:.2f}[/{kd_color}]\n"
        f"[#7070a0]Win Rate:[/#7070a0]  [#ff4fb8]{win_rate:.1f}%[/#ff4fb8]\n"
        f"[#7070a0]Mins:[/#7070a0]      [#e0e0ff]{minutes_played}[/#e0e0ff]\n"
    )
    if mode_lines:
        summary += "\n[#7070a0]── Mode Breakdown ──[/#7070a0]\n" + "\n".join(mode_lines)
    summary += f"\n\n[dim]View at http://localhost:{WEB_PORT}/session/{session_id}[/dim]"
    summary += f"\n[dim]Share at http://localhost:{WEB_PORT}/share/{session_id}[/dim]"

    # Discord notification
    if DISCORD_WEBHOOK:
        flat_session = {
            "id": session_id, "epic_name": epic, "season": season,
            "matches": matches, "wins": wins, "kills": kills,
            "kd": kd, "win_rate": win_rate, "minutes_played": minutes_played,
            "notes": notes or "",
        }
        flat_modes = []
        for mk, d in deltas.items():
            if mk == "overall" or not isinstance(d, dict) or not d.get("matches"):
                continue
            from fnlog.config import MODES, RANKED_MODES
            all_m = {**MODES, **RANKED_MODES}
            flat_modes.append({
                "name": all_m.get(mk, mk),
                "matches": d.get("matches", 0), "wins": d.get("wins", 0),
                "kills": d.get("kills", 0), "kd": d.get("kd", 0.0),
                "win_rate": d.get("win_rate", 0.0),
            })
        sent = send_session_embed(flat_session, flat_modes)
        if sent:
            console.print("[#7070a0]Discord notification sent.[/#7070a0]")

    console.print(Panel(summary, title="[bold #b44fff]FNLog[/bold #b44fff]", border_style="#b44fff"))


@main.command()
def status():
    """Show the current active session status."""
    state = _load_state()
    if not state:
        console.print("[#7070a0]No active session.[/#7070a0] Run [cyan]fnlog start[/cyan] to begin.")
        return
    started = datetime.fromisoformat(state["started_at"])
    elapsed = int((datetime.now() - started).total_seconds() / 60)
    console.print(
        f"[bold #ff4fb8]Active session[/bold #ff4fb8] for [#00d4ff]{state['epic']}[/#00d4ff] "
        f"— [#b44fff]{state.get('season','')}[/#b44fff] "
        f"— started [#e0e0ff]{started.strftime('%I:%M %p')}[/#e0e0ff] "
        f"([#00f5d4]{elapsed} min ago[/#00f5d4])"
    )


@main.command()
@click.option("--limit", "-n", default=10)
@click.option("--season", "-s", default=None)
def history(limit, season):
    """Show recent session history."""
    sessions = get_sessions(EPIC_NAME, limit=limit, season=season)
    if not sessions:
        console.print("[#7070a0]No sessions recorded yet.[/#7070a0]")
        return

    title = f"Session History — {EPIC_NAME}"
    if season:
        title += f" // {season}"

    table = Table(box=box.SIMPLE_HEAD, header_style="bold #b44fff", title=title, title_style="#ff4fb8")
    table.add_column("ID", style="#7070a0")
    table.add_column("Date", style="#7070a0")
    table.add_column("Season", style="#b44fff")
    table.add_column("M")
    table.add_column("W", style="#b44fff")
    table.add_column("K", style="#00d4ff")
    table.add_column("K/D")
    table.add_column("Win%", style="#ff4fb8")
    table.add_column("Mins", style="#7070a0")
    table.add_column("Notes", style="dim")

    for s in sessions:
        kd_color = "#00f5d4" if s["kd"] >= 1.0 else "#ff4fb8"
        table.add_row(
            str(s["id"]),
            s["ended_at"][:10],
            s.get("season") or "—",
            str(s["matches"]),
            str(s["wins"]),
            str(s["kills"]),
            f"[{kd_color}]{s['kd']:.2f}[/{kd_color}]",
            f"{s['win_rate']:.1f}%",
            str(s["minutes_played"]),
            s.get("notes") or "—",
        )
    console.print(table)


@main.command()
@click.option("--season", "-s", default=None)
def stats(season):
    """Show all-time or season bests and career summary."""
    console.print(BANNER)
    totals = get_career_totals(EPIC_NAME, season=season)
    bests  = get_bests(EPIC_NAME, season=season)
    streak = get_win_streak(EPIC_NAME, season=season)
    seasons = get_seasons(EPIC_NAME)

    tm = int(totals.get("total_matches") or 0)
    tw = int(totals.get("total_wins") or 0)
    tk = int(totals.get("total_kills") or 0)
    tmin = int(totals.get("total_minutes") or 0)
    ts = int(totals.get("total_sessions") or 0)
    wr = round((tw / tm * 100), 1) if tm else 0.0
    hrs = round(tmin / 60, 1)

    label = f"Season {season}" if season else "All Time"
    summary = (
        f"[bold #ff4fb8]{label} — {EPIC_NAME}[/bold #ff4fb8]\n\n"
        f"[#7070a0]Sessions:[/#7070a0]  [#00f5d4]{ts}[/#00f5d4]\n"
        f"[#7070a0]Matches:[/#7070a0]   [#00f5d4]{tm}[/#00f5d4]\n"
        f"[#7070a0]Wins:[/#7070a0]      [#b44fff]{tw}[/#b44fff]\n"
        f"[#7070a0]Kills:[/#7070a0]     [#00d4ff]{tk}[/#00d4ff]\n"
        f"[#7070a0]Win Rate:[/#7070a0]  [#ff4fb8]{wr}%[/#ff4fb8]\n"
        f"[#7070a0]Hours:[/#7070a0]     [#00f5d4]{hrs}h[/#00f5d4]\n\n"
        f"[#7070a0]Win Streak:[/#7070a0] Current [#b44fff]{streak['current']}[/#b44fff]  "
        f"Best [#ff4fb8]{streak['longest']}[/#ff4fb8]\n"
    )

    if bests:
        summary += "\n[#7070a0]── Best Sessions ──[/#7070a0]\n"
        if "most_kills" in bests:
            b = bests["most_kills"]
            summary += f"  [#ff4fb8]Most Kills:[/#ff4fb8]   [#00d4ff]{b['kills']}[/#00d4ff] kills — Session #{b['id']} ({b['ended_at'][:10]})\n"
        if "best_kd" in bests:
            b = bests["best_kd"]
            summary += f"  [#ff4fb8]Best K/D:[/#ff4fb8]     [#00f5d4]{b['kd']:.2f}[/#00f5d4] — Session #{b['id']} ({b['ended_at'][:10]})\n"
        if "most_wins" in bests:
            b = bests["most_wins"]
            summary += f"  [#ff4fb8]Most Wins:[/#ff4fb8]    [#b44fff]{b['wins']}[/#b44fff] wins — Session #{b['id']} ({b['ended_at'][:10]})\n"
        if "most_matches" in bests:
            b = bests["most_matches"]
            summary += f"  [#ff4fb8]Most Matches:[/#ff4fb8] [#00f5d4]{b['matches']}[/#00f5d4] — Session #{b['id']} ({b['ended_at'][:10]})\n"

    if seasons:
        summary += f"\n[#7070a0]Seasons tracked:[/#7070a0] [#b44fff]{', '.join(seasons)}[/#b44fff]"

    console.print(Panel(summary, title="[bold #b44fff]FNLog Stats[/bold #b44fff]", border_style="#b44fff"))


@main.command()
@click.option("--player", "-p", default=None)
@click.option("--season", "-s", default=None)
def dashboard(player, season):
    """Launch the Textual terminal dashboard."""
    from fnlog.dashboard import run_dashboard
    run_dashboard(player or EPIC_NAME, season=season)


@main.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=None, type=int)
def web(host, port):
    """Launch the vaporwave web dashboard."""
    p = port or WEB_PORT
    console.print(f"[#b44fff]FNLog web dashboard[/#b44fff] → [#00d4ff]http://localhost:{p}[/#00d4ff]")
    from fnlog.web import run_web
    run_web(host=host, port=p)


@main.command()
@click.option("--player", "-p", default=None)
def clean(player):
    """Delete sessions with 0 matches (test/empty sessions)."""
    epic = player or EPIC_NAME
    n = clean_empty_sessions(epic)
    if n:
        console.print(f"[#00f5d4]Deleted {n} empty session(s) for {epic}.[/#00f5d4]")
    else:
        console.print(f"[#7070a0]No empty sessions found for {epic}.[/#7070a0]")


@main.command()
@click.option("--season", "-s", default=None)
def seasons(season):
    """List all seasons with recorded sessions."""
    all_seasons = get_seasons(EPIC_NAME)
    if not all_seasons:
        console.print("[#7070a0]No seasons recorded yet.[/#7070a0]")
        return
    console.print(f"\n[bold #ff4fb8]Seasons tracked for {EPIC_NAME}:[/bold #ff4fb8]")
    for s in all_seasons:
        totals = get_career_totals(EPIC_NAME, season=s)
        tm = int(totals.get("total_matches") or 0)
        tw = int(totals.get("total_wins") or 0)
        ts = int(totals.get("total_sessions") or 0)
        wr = round((tw / tm * 100), 1) if tm else 0.0
        console.print(
            f"  [#b44fff]{s:<12}[/#b44fff]"
            f"  [#7070a0]Sessions:[/#7070a0] [#00f5d4]{ts}[/#00f5d4]"
            f"  [#7070a0]Matches:[/#7070a0] [#e0e0ff]{tm}[/#e0e0ff]"
            f"  [#7070a0]Wins:[/#7070a0] [#b44fff]{tw}[/#b44fff]"
            f"  [#7070a0]Win%:[/#7070a0] [#ff4fb8]{wr}%[/#ff4fb8]"
        )


@main.command("export")
@click.option("--season", "-s", default=None, help="Filter by season.")
@click.option("--output", "-o", default=None, help="Output file path (default: fnlog_export.csv)")
@click.option("--player", "-p", default=None)
def export_csv(season, output, player):
    """Export session history to CSV."""

    epic = player or EPIC_NAME
    sessions = get_sessions(epic, limit=9999, season=season)
    real = [s for s in sessions if s["matches"] > 0]

    if not real:
        console.print("[#7070a0]No sessions to export.[/#7070a0]")
        return

    out_path = Path(output) if output else Path("fnlog_export_" + epic + ("_" + season if season else "") + ".csv")

    fieldnames = ["id", "date", "season", "matches", "wins", "kills", "kd",
                  "win_rate", "kills_per_match", "minutes_played", "duration_min", "notes"]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in reversed(real):
            writer.writerow({
                "id":             s["id"],
                "date":           s["ended_at"][:10],
                "season":         s.get("season") or "",
                "matches":        s["matches"],
                "wins":           s["wins"],
                "kills":          s["kills"],
                "kd":             round(s["kd"], 2),
                "win_rate":       round(s["win_rate"], 1),
                "kills_per_match": round(s["kills_per_match"], 2),
                "minutes_played": s["minutes_played"],
                "duration_min":   s.get("duration_min") or 0,
                "notes":          s.get("notes") or "",
            })

    console.print(f"[#00f5d4]Exported {len(real)} session(s) to[/#00f5d4] [#b44fff]{out_path}[/#b44fff]")