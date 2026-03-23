"""
FNLog — Textual terminal dashboard.
Retrowave/synthwave aesthetic with live session and career stats.
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, DataTable, Label
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual import events
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich import box
from datetime import datetime

from fnlog.config import MODES, RANKED_MODES, COLORS
from fnlog.db import get_sessions, get_career_totals, init_db, get_conn

VAPORWAVE_CSS = """
Screen {
    background: #0d0d1a;
    color: #e0e0ff;
}

Header {
    background: #1a1a2e;
    color: #b44fff;
    text-style: bold;
}

Footer {
    background: #1a1a2e;
    color: #7070a0;
}

.title {
    color: #b44fff;
    text-style: bold;
    text-align: center;
    padding: 0 1;
}

.stat-card {
    background: #1a1a2e;
    border: tall #2a2a4a;
    padding: 1 2;
    margin: 0 1;
    min-width: 18;
}

.stat-value {
    color: #00f5d4;
    text-style: bold;
    text-align: center;
}

.stat-label {
    color: #7070a0;
    text-align: center;
}

.stat-value-pink {
    color: #ff4fb8;
    text-style: bold;
    text-align: center;
}

.stat-value-purple {
    color: #b44fff;
    text-style: bold;
    text-align: center;
}

.stat-value-cyan {
    color: #00d4ff;
    text-style: bold;
    text-align: center;
}

.section-header {
    color: #ff4fb8;
    text-style: bold;
    padding: 1 1 0 1;
}

.panel {
    background: #1a1a2e;
    border: tall #2a2a4a;
    margin: 0 1 1 1;
    padding: 1;
}

DataTable {
    background: #0d0d1a;
    color: #e0e0ff;
}

DataTable > .datatable--header {
    background: #1a1a2e;
    color: #b44fff;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #2a2a4a;
    color: #00f5d4;
}
"""

BANNER = """[bold #b44fff]
███████╗███╗   ██╗██╗      ██████╗  ██████╗
██╔════╝████╗  ██║██║     ██╔═══██╗██╔════╝
█████╗  ██╔██╗ ██║██║     ██║   ██║██║  ███╗
██╔══╝  ██║╚██╗██║██║     ██║   ██║██║   ██║
██║     ██║ ╚████║███████╗╚██████╔╝╚██████╔╝
╚═╝     ╚═╝  ╚═══╝╚══════╝ ╚═════╝  ╚═════╝[/bold #b44fff]
[#ff4fb8]Zero Build Session Tracker[/#ff4fb8] [#7070a0]// by mskeith[/#7070a0]"""


def mode_display(mode_key: str) -> str:
    all_modes = {**MODES, **RANKED_MODES}
    return all_modes.get(mode_key, mode_key)


class StatCard(Static):
    def __init__(self, label: str, value: str, color_class: str = "stat-value", **kwargs):
        super().__init__(**kwargs)
        self._label = label
        self._value = value
        self._color_class = color_class

    def compose(self) -> ComposeResult:
        yield Label(self._value, classes=self._color_class)
        yield Label(self._label, classes="stat-label")


class FNLogDashboard(App):
    CSS = VAPORWAVE_CSS
    TITLE = "FNLog // Zero Build Tracker"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    epic_name: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Static(BANNER, id="banner"),
            Static("", id="career-row"),
            Label("── Recent Sessions ──────────────────────────────────────", classes="section-header"),
            DataTable(id="sessions-table"),
            Label("── Mode Breakdown (Last Session) ────────────────────────", classes="section-header"),
            Static("", id="mode-panel"),
        )
        yield Footer()

    def on_mount(self) -> None:
        init_db()
        self._load_data()

    def action_refresh(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        sessions = get_sessions(self.epic_name, limit=20)
        totals = get_career_totals(self.epic_name)
        self._render_career(totals, sessions)
        self._render_sessions_table(sessions)
        self._render_mode_panel(sessions)

    def _render_career(self, totals: dict, sessions: list) -> None:
        ts = totals.get("total_sessions", 0) or 0
        tm = totals.get("total_matches", 0) or 0
        tw = totals.get("total_wins", 0) or 0
        tk = totals.get("total_kills", 0) or 0
        tmin = totals.get("total_minutes", 0) or 0
        wr = round((tw / tm * 100), 1) if tm else 0.0
        hrs = round(tmin / 60, 1)

        career = (
            f"[bold #ff4fb8]CAREER STATS[/bold #ff4fb8]  "
            f"[#7070a0]Sessions:[/#7070a0] [#00f5d4]{ts}[/#00f5d4]  "
            f"[#7070a0]Matches:[/#7070a0] [#00f5d4]{tm}[/#00f5d4]  "
            f"[#7070a0]Wins:[/#7070a0] [#b44fff]{tw}[/#b44fff]  "
            f"[#7070a0]Kills:[/#7070a0] [#00d4ff]{tk}[/#00d4ff]  "
            f"[#7070a0]Win%:[/#7070a0] [#ff4fb8]{wr}%[/#ff4fb8]  "
            f"[#7070a0]Hours:[/#7070a0] [#00f5d4]{hrs}[/#00f5d4]"
        )
        self.query_one("#career-row", Static).update(career)

    def _render_sessions_table(self, sessions: list) -> None:
        table = self.query_one("#sessions-table", DataTable)
        table.clear(columns=True)
        table.add_columns("ID", "Date", "Matches", "Wins", "Kills", "K/D", "Win%", "Mins", "Notes")

        for s in sessions:
            date = s["ended_at"][:10]
            kd_color = "#00f5d4" if s["kd"] >= 1.0 else "#ff4fb8"
            wr_color = "#b44fff" if s["win_rate"] >= 10 else "#7070a0"
            table.add_row(
                str(s["id"]),
                date,
                str(s["matches"]),
                Text(str(s["wins"]), style="#b44fff bold"),
                Text(str(s["kills"]), style="#00d4ff"),
                Text(f"{s['kd']:.2f}", style=kd_color),
                Text(f"{s['win_rate']:.1f}%", style=wr_color),
                str(s["minutes_played"]),
                s.get("notes") or "—",
            )

    def _render_mode_panel(self, sessions: list) -> None:
        if not sessions:
            self.query_one("#mode-panel", Static).update("[#7070a0]No sessions recorded yet.[/#7070a0]")
            return

        last = sessions[0]
        deltas = last.get("mode_deltas", {})
        if not deltas:
            self.query_one("#mode-panel", Static).update("[#7070a0]No mode data for last session.[/#7070a0]")
            return

        lines = []
        for mode, d in deltas.items():
            name = mode_display(mode)
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


def run_dashboard(epic_name: str):
    app = FNLogDashboard()
    app.epic_name = epic_name
    app.run()
