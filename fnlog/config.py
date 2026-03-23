"""
FNLog — Configuration and mode definitions.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY        = os.getenv("FNLOG_API_KEY", "")
EPIC_NAME      = os.getenv("FNLOG_EPIC_NAME", "")
DB_PATH        = Path(os.getenv("FNLOG_DB_PATH", str(Path.home() / ".fnlog" / "sessions.db")))
WEB_PORT       = int(os.getenv("FNLOG_WEB_PORT", "7420"))
CURRENT_SEASON = os.getenv("FNLOG_SEASON", "Ch6S2")
DISCORD_WEBHOOK = os.getenv("FNLOG_DISCORD_WEBHOOK", "")

# Fortnite-API.com mode keys → display names
MODES = {
    "overall": "All Modes",
    "solo":    "ZB Solos",
    "duo":     "ZB Duos",
    "trio":    "ZB Trios",
    "squad":   "ZB Squads",
    "ltm":     "ZB Reload / LTM",
}

TRACKED_MODES = ["overall", "solo", "duo", "trio", "squad", "ltm"]

RANKED_MODES = {
    "ranked_br":     "ZB Ranked BR",
    "ranked_reload": "ZB Ranked Reload",
}

API_BASE = "https://fortnite-api.com/v2"

COLORS = {
    "purple":  "#b44fff",
    "pink":    "#ff4fb8",
    "teal":    "#00f5d4",
    "cyan":    "#00d4ff",
    "dark_bg": "#0d0d1a",
    "card_bg": "#1a1a2e",
    "border":  "#2a2a4a",
    "text":    "#e0e0ff",
    "muted":   "#7070a0",
}
