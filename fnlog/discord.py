"""
FNLog — Discord webhook notifications.
Fires a rich embed on session end if FNLOG_DISCORD_WEBHOOK is set.
"""

import httpx
from datetime import datetime
from fnlog.config import DISCORD_WEBHOOK, COLORS


def send_session_embed(session: dict, mode_rows: list[dict] = None) -> bool:
    """
    Post a session summary embed to Discord.
    Returns True on success, False if webhook not configured or request fails.
    """
    if not DISCORD_WEBHOOK:
        return False

    kd = session.get("kd", 0.0)
    wins = session.get("wins", 0)
    kills = session.get("kills", 0)
    matches = session.get("matches", 0)
    win_rate = session.get("win_rate", 0.0)
    minutes = session.get("minutes_played", 0)
    session_id = session.get("id", "?")
    epic = session.get("epic_name", "Unknown")
    season = session.get("season", "")
    notes = session.get("notes", "")

    # Pick embed color based on performance
    if wins > 0 and kd >= 2.0:
        color = 0xb44fff   # purple — elite
    elif wins > 0:
        color = 0x00f5d4   # teal — winner
    elif kd >= 1.0:
        color = 0x00d4ff   # cyan — decent
    else:
        color = 0xff4fb8   # pink — rough session

    # Build mode breakdown field
    mode_text = ""
    if mode_rows:
        for m in mode_rows:
            if m.get("matches", 0) == 0:
                continue
            mode_text += (
                f"**{m['name']}** — "
                f"{m['matches']}M / {m['wins']}W / {m['kills']}K / "
                f"{m['kd']:.2f} K/D / {m['win_rate']:.1f}%\n"
            )

    fields = [
        {"name": "Matches", "value": str(matches), "inline": True},
        {"name": "Wins", "value": str(wins), "inline": True},
        {"name": "Kills", "value": str(kills), "inline": True},
        {"name": "K/D", "value": f"{kd:.2f}", "inline": True},
        {"name": "Win Rate", "value": f"{win_rate:.1f}%", "inline": True},
        {"name": "Time Played", "value": f"{minutes} min", "inline": True},
    ]

    if season:
        fields.append({"name": "Season", "value": season, "inline": True})

    if mode_text:
        fields.append({"name": "Mode Breakdown", "value": mode_text.strip(), "inline": False})

    if notes:
        fields.append({"name": "Notes", "value": notes, "inline": False})

    title = f"Session #{session_id} complete"
    if wins > 0:
        title += f" — {wins} WIN{'S' if wins > 1 else ''}! 👑"

    payload = {
        "embeds": [{
            "title": title,
            "description": f"**{epic}** // Zero Build",
            "color": color,
            "fields": fields,
            "footer": {"text": f"FNLog // {datetime.now().strftime('%B %d, %Y')}"},
            "thumbnail": {"url": "https://fortnite-api.com/images/cosmetics/br/cid_001_athena_commando_f_default/icon.png"},
        }]
    }

    try:
        resp = httpx.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        return resp.status_code in (200, 204)
    except Exception:
        return False
