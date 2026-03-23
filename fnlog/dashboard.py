"""
FNLog — Textual terminal dashboard.
Synthwave/vaporwave TUI with live stats, bests, streaks, season filter.
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable, Label, Select
from textual.containers import Horizontal, Vertical, ScrollableContainer
from rich.text import Text
from rich.panel import Panel
from rich import box

from fnlog.config import MODES, RANKED_MODES, CURRENT_SEASON
from fnlog.db import (
    get_sessions, get_career_totals, init_db,
    get_bests, get_win_streak, get_seasons,
)

ALL_MODES = {**MODES, **RANKED_MODES}

CSS = """
Screen { background: #0d0d1a; color: #e0e0ff; }
Header { background: #1a1a2e; color: #b44fff; text-style: bold; }
Footer { background: #1a1a2e; color: #7070a0; }

.box {
    background: #1a1a2e;
    border: tall #2a2a4a;
    padding: 1 2;
    margin: 0 1 1 1;
}

.title { color: #ff4fb8; text-style: bold; padding: 0 0 1 0; }
.purple { color: #b44fff; text-style: bold; }
.teal   { color: #00f5d4; text-style: bold; }
.cyan   { color: #00d4ff; text-style: bold; }
.pink   { color: #ff4fb8; text-style: bold; }
.muted  { color: #7070a0; }

DataTable { background: #0d0d1a; color: #e0e0ff; margin: 0 1; }
DataTable > .datatable--header { background: #1a1a2e; color: #b44fff; text-style: bold; }
DataTable > .datatable--cursor { background: #2a2a4a; color: #00f5d4; }

Select { margin: 0 1 1 1; width: 30; }
"""

BANNER = """\
[bold #b44fff]███████╗███╗   ██╗██╗      ██████╗  ██████╗[/bold #b44fff]
[bold #b44fff]██╔════╝████╗  ██║██║     ██╔═══██╗██╔════╝[/bold #b44fff]
[bold #b44fff]█████╗  ██╔██╗ ██║██║     ██║   ██║██║  ███╗[/bold #b44fff]
[bold #b44fff]██╔══╝  ██║╚██╗██║██║     ██║   ██║██║   ██║[/bold #b44fff]
[bold #b44fff]██║     ██║ ╚████║███████╗╚██████╔╝╚██████╔╝[/bold #b44fff]
[bold #b44fff]╚═╝     ╚═╝  ╚═══╝╚══════╝ ╚═════╝  ╚═════╝[/bold #b44fff]
[#ff4fb8]Zero Build Session Tracker[/#ff4fb8] [#7070a0]// press R to refresh // Q to quit[/#7070a0]"""


class FNLogDashboard(App):
    CSS = CSS
    TITLE = "FNLog // Zero Build Tracker"
    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh")]

    def __init__(self, epic_name: str = "", season: str = None):
        super().__init__()
        self.epic_name = epic_name
        self.season = season
        self._seasons = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Static(BANNER, id="banner"),
            Static("", id="career-bar"),
            Static("", id="highlights-bar"),
            Label("── Recent Sessions ──────────────────────────────────────────", classes="title"),
            DataTable(id="sessions-table"),
            Label("── Last Session Mode Breakdown ──────────────────────────────", classes="title"),
            Static("", id="mode-panel"),
        )
        yield Footer()

    def on_mount(self) -> None:
        init_db()
        self._seasons = get_seasons(self.epic_name)
        self._load_data()

    def action_refresh(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        sessions = get_sessions(self.epic_name, limit=20, season=self.season)
        totals   = get_career_totals(self.epic_name, season=self.season)
        bests    = get_bests(self.epic_name, season=self.season)
        streak   = get_win_streak(self.epic_name, season=self.season)
        self._render_career(totals, streak)
        self._render_highlights(bests, streak)
        self._render_sessions_table(sessions)
        self._render_mode_panel(sessions)

    def _render_career(self, totals: dict, streak: dict) -> None:
        ts   = int(totals.get("total_sessions") or 0)
        tm   = int(totals.get("total_matches") or 0)
        tw   = int(totals.get("total_wins") or 0)
        tk   = int(totals.get("total_kills") or 0)
        tmin = int(totals.get("total_minutes") or 0)
        wr   = round((tw / tm * 100), 1) if tm else 0.0
        hrs  = round(tmin / 60, 1)
        season_label = f" [#b44fff]// {self.season}[/#b44fff]" if self.season else ""

        bar = (
            f"[bold #ff4fb8]{self.epic_name}[/bold #ff4fb8]{season_label}  "
            f"[#7070a0]Sessions:[/#7070a0][#00f5d4]{ts}[/#00f5d4]  "
            f"[#7070a0]Matches:[/#7070a0][#00f5d4]{tm}[/#00f5d4]  "
            f"[#7070a0]Wins:[/#7070a0][#b44fff]{tw}[/#b44fff]  "
            f"[#7070a0]Kills:[/#7070a0][#00d4ff]{tk}[/#00d4ff]  "
            f"[#7070a0]Win%:[/#7070a0][#ff4fb8]{wr}%[/#ff4fb8]  "
            f"[#7070a0]Hours:[/#7070a0][#00f5d4]{hrs}h[/#00f5d4]"
        )
        self.query_one("#career-bar", Static).update(bar)

    def _render_highlights(self, bests: dict, streak: dict) -> None:
        sc = int(streak.get("current", 0))
        sl = int(streak.get("longest", 0))

        parts = [
            f"[#7070a0]Streak:[/#7070a0] [#ff4fb8]{sc} current[/#ff4fb8] [#7070a0](best {sl})[/#7070a0]"
        ]

        labels = {
            "most_kills":   ("Most Kills", "kills", "#00d4ff"),
            "best_kd":      ("Best K/D",   "kd",    "#00f5d4"),
            "most_wins":    ("Most Wins",  "wins",  "#b44fff"),
        }
        for key, (label, field, color) in labels.items():
            if key in bests:
                val = bests[key].get(field, 0)
                sid = bests[key].get("id", "?")
                fmt = f"{val:.2f}" if field == "kd" else str(val)
                parts.append(
                    f"[#7070a0]{label}:[/#7070a0] [{color}]{fmt}[/{color}] [#7070a0](#{sid})[/#7070a0]"
                )

        self.query_one("#highlights-bar", Static).update("  ".join(parts))

    def _render_sessions_table(self, sessions: list) -> None:
        table = self.query_one("#sessions-table", DataTable)
        table.clear(columns=True)
        table.add_columns("#", "Date", "Season", "M", "W", "K", "K/D", "Win%", "Mins", "Notes")

        for s in sessions:
            kd_color = "#00f5d4" if s["kd"] >= 1.0 else "#ff4fb8"
            wr_color = "#b44fff" if s["win_rate"] >= 10 else "#7070a0"
            table.add_row(
                str(s["id"]),
                s["ended_at"][:10],
                s.get("season") or "—",
                str(s["matches"]),
                Text(str(s["wins"]), style="#b44fff bold"),
                Text(str(s["kills"]), style="#00d4ff"),
                Text(f"{s['kd']:.2f}", style=kd_color),
                Text(f"{s['win_rate']:.1f}%", style=wr_color),
                str(s["minutes_played"]),
                s.get("notes") or "—",
            )

    def _render_mode_panel(self, sessions: list) -> None:
        real = [s for s in sessions if s["matches"] > 0]
        if not real:
            self.query_one("#mode-panel", Static).update("[#7070a0]No sessions with match data yet.[/#7070a0]")
            return

        last = real[0]
        deltas = last.get("mode_deltas", {})
        if not deltas:
            self.query_one("#mode-panel", Static).update("[#7070a0]No mode data for last session.[/#7070a0]")
            return

        lines = [f"[#7070a0]Session #{last['id']} — {last['ended_at'][:10]}[/#7070a0]"]
        for mode, d in deltas.items():
            if not isinstance(d, dict) or not d.get("matches"):
                continue
            name = ALL_MODES.get(mode, mode)
            kd_color = "#00f5d4" if d["kd"] >= 1.0 else "#ff4fb8"
            lines.append(
                f"  [#ff4fb8]{name:<22}[/#ff4fb8]"
                f"  [#7070a0]M:[/#7070a0][#e0e0ff]{d['matches']}[/#e0e0ff]"
                f"  [#7070a0]W:[/#7070a0][#b44fff]{d['wins']}[/#b44fff]"
                f"  [#7070a0]K:[/#7070a0][#00d4ff]{d['kills']}[/#00d4ff]"
                f"  [#7070a0]K/D:[/#7070a0][{kd_color}]{d['kd']:.2f}[/{kd_color}]"
                f"  [#7070a0]Win%:[/#7070a0][#ff4fb8]{d['win_rate']:.1f}%[/#ff4fb8]"
            )
        self.query_one("#mode-panel", Static).update("\n".join(lines))


def run_dashboard(epic_name: str, season: str = None):
    app = FNLogDashboard(epic_name=epic_name, season=season)
    app.run()
