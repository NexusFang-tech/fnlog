"""
FNLog — Fortnite-API.com client.
Pulls stats for all Zero Build modes including ZB Ranked BR and ZB Ranked Reload.
"""

import httpx
from fnlog.config import API_KEY, API_BASE, TRACKED_MODES


def _headers() -> dict:
    return {"Authorization": API_KEY}


def get_stats(epic_name: str) -> dict:
    """
    Fetch full stats breakdown for a player.
    Returns the raw stats dict keyed by mode.
    """
    url = f"{API_BASE}/stats/br/v2"
    params = {"name": epic_name, "image": "none"}
    resp = httpx.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != 200:
        raise ValueError(f"API error: {data.get('error', 'Unknown error')}")

    stats = data["data"]["stats"]

    # Build a normalized snapshot dict per mode
    snapshot = {}
    mode_map = {
        "solo":   stats.get("all", {}).get("solo", {}),
        "duo":    stats.get("all", {}).get("duo", {}),
        "trio":   stats.get("all", {}).get("trio", {}),
        "squad":  stats.get("all", {}).get("squad", {}),
        "ltm":    stats.get("all", {}).get("ltm", {}),
        "overall": stats.get("all", {}).get("overall", {}),
    }

    for mode, raw in mode_map.items():
        snapshot[mode] = _normalize_mode(raw)

    return snapshot


def get_ranked_stats(epic_name: str) -> dict:
    """
    Fetch ranked stats for ZB Ranked BR and ZB Ranked Reload.
    Uses the habanero (ranked) endpoint.
    Returns dict with keys: ranked_br, ranked_reload
    """
    url = f"{API_BASE}/stats/br/v2"
    params = {"name": epic_name, "image": "none"}
    resp = httpx.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != 200:
        raise ValueError(f"API error: {data.get('error', 'Unknown error')}")

    stats = data["data"]["stats"]

    ranked = {}

    # ZB Ranked BR — keyName: "ranked" on the nobuildranked key
    ranked_raw = stats.get("all", {})
    # Try common ranked keys the API exposes
    ranked["ranked_br"] = _normalize_mode(
        ranked_raw.get("nobuildranked", ranked_raw.get("ranked", {}))
    )
    # ZB Ranked Reload — reloadranked
    ranked["ranked_reload"] = _normalize_mode(
        ranked_raw.get("reloadranked", {})
    )

    return ranked


def _normalize_mode(raw: dict) -> dict:
    """Normalize a raw mode stats dict to our standard keys."""
    if not raw:
        return {
            "matches": 0, "wins": 0, "kills": 0, "deaths": 0,
            "top3": 0, "top5": 0, "top10": 0, "top25": 0,
            "minutes_played": 0, "players_outlasted": 0,
            "kd": 0.0, "win_rate": 0.0, "kills_per_match": 0.0,
            "score": 0,
        }
    return {
        "matches":          raw.get("matches", 0),
        "wins":             raw.get("wins", 0),
        "kills":            raw.get("kills", 0),
        "deaths":           raw.get("deaths", 0),
        "top3":             raw.get("top3", 0),
        "top5":             raw.get("top5", 0),
        "top10":            raw.get("top10", 0),
        "top25":            raw.get("top25", 0),
        "minutes_played":   raw.get("minutesPlayed", 0),
        "players_outlasted": raw.get("playersOutlasted", 0),
        "kd":               raw.get("kd", 0.0),
        "win_rate":         raw.get("winRate", 0.0),
        "kills_per_match":  raw.get("killsPerMatch", 0.0),
        "score":            raw.get("score", 0),
    }


def compute_delta(snap_start: dict, snap_end: dict) -> dict:
    """
    Compute per-mode deltas between two snapshots.
    Returns a dict of mode -> delta stats.
    """
    delta = {}
    all_modes = set(snap_start.keys()) | set(snap_end.keys())

    for mode in all_modes:
        s = snap_start.get(mode, {})
        e = snap_end.get(mode, {})
        if not s or not e:
            continue

        d_matches = e.get("matches", 0) - s.get("matches", 0)
        d_wins    = e.get("wins", 0)    - s.get("wins", 0)
        d_kills   = e.get("kills", 0)   - s.get("kills", 0)
        d_deaths  = e.get("deaths", 0)  - s.get("deaths", 0)
        d_top10   = e.get("top10", 0)   - s.get("top10", 0)
        d_minutes = e.get("minutes_played", 0) - s.get("minutes_played", 0)

        # Skip modes with no activity
        if d_matches <= 0:
            continue

        kd = round(d_kills / d_deaths, 2) if d_deaths > 0 else float(d_kills)
        win_rate = round((d_wins / d_matches) * 100, 1) if d_matches > 0 else 0.0
        kpm = round(d_kills / d_matches, 2) if d_matches > 0 else 0.0

        delta[mode] = {
            "matches":        d_matches,
            "wins":           d_wins,
            "kills":          d_kills,
            "deaths":         d_deaths,
            "top10":          d_top10,
            "minutes_played": d_minutes,
            "kd":             kd,
            "win_rate":       win_rate,
            "kills_per_match": kpm,
        }

    return delta
