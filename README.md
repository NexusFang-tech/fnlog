# FNLog — Fortnite Zero Build Session Tracker

> A personal stat tracking CLI and vaporwave web dashboard for Fortnite Zero Build players.

![Python](https://img.shields.io/badge/Python-3.10+-b44fff?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-00f5d4?style=flat-square&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-local-ff4fb8?style=flat-square&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-00d4ff?style=flat-square)

---

## What it does

FNLog tracks your Fortnite Zero Build sessions using **stat delta tracking** — it snapshots your career stats before and after each session, calculates exactly what happened, and stores it locally in SQLite.

- **CLI tool** (`fnlog`) — start/end sessions, view history, check bests, manage seasons
- **Vaporwave web dashboard** — charts, highlights, win streaks, shareable session cards
- **Multi-mode tracking** — ZB Solos, Duos, Trios, Squads, Reload, Ranked BR, Ranked Reload
- **Season support** — tag sessions to a season, filter stats by season
- **Shareable cards** — `/share/{id}` generates a screenshot-worthy stat card for posting

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| CLI | Python, Click, Rich |
| API | [Fortnite-API.com](https://fortnite-api.com) (free) |
| Storage | SQLite via `sqlite3` |
| Web server | FastAPI + Uvicorn |
| Templates | Jinja2 |
| Charts | Chart.js |
| Fonts | Orbitron + Share Tech Mono (Google Fonts) |

---

## Setup

### Prerequisites
- Python 3.10+
- A free API key from [fortnite-api.com](https://fortnite-api.com)
- Your Epic Games display name

### Install

```bash
git clone https://github.com/yourusername/fnlog.git
cd fnlog

python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate

pip install -e .
```

### Configure

```bash
copy .env.example .env   # Windows
cp .env.example .env     # macOS/Linux
```

Edit `.env`:

```env
FNLOG_API_KEY=your_api_key_here
FNLOG_EPIC_NAME=YourEpicName
```

---

## Usage

### Track a session

```bash
# Before you queue up
fnlog start

# After you're done playing
fnlog end
```

`fnlog end` prompts for optional session notes, then shows a full breakdown by mode.

### View your stats

```bash
fnlog stats                      # All-time bests + career summary
fnlog history                    # Session history table
fnlog history --season Ch6S2     # Filter by season
fnlog stats --season Ch6S2       # Season bests
```

### Web dashboard

```bash
fnlog web
# Automatically opens http://localhost:7420
```

Load any tracked player via the search bar, or filter by season with the dropdown.

### Other commands

```bash
fnlog status     # Check if a session is currently active
fnlog seasons    # List all seasons with recorded sessions
fnlog clean      # Delete zero-match test sessions
fnlog dashboard  # Textual terminal TUI dashboard
```

---

## Modes Tracked

| Key | Mode |
|-----|------|
| `solo` | Zero Build Solos |
| `duo` | Zero Build Duos |
| `trio` | Zero Build Trios |
| `squad` | Zero Build Squads |
| `ltm` | Zero Build Reload / LTM |
| `ranked_br` | Zero Build Ranked BR |
| `ranked_reload` | Zero Build Ranked Reload |

---

## How stat delta tracking works

Epic's API doesn't expose per-match history — only career totals. FNLog works around this:

1. `fnlog start` records your current career totals as a snapshot
2. You play as many matches as you want across any modes
3. `fnlog end` fetches totals again and subtracts
4. The difference is your session — kills, wins, K/D, win rate, per mode

FNLog can only track sessions going forward from installation.

---

## Project Structure

```
fnlog/
├── fnlog/
│   ├── cli.py          ← fnlog command (Click + Rich)
│   ├── config.py       ← .env loading, mode/color definitions
│   ├── api.py          ← Fortnite-API.com client + delta engine
│   ├── db.py           ← SQLite schema, queries, season/streak logic
│   ├── dashboard.py    ← Textual terminal TUI dashboard
│   ├── web.py          ← FastAPI web server
│   └── templates/
│       ├── dashboard.html   ← Vaporwave career dashboard
│       ├── session.html     ← Session detail page
│       └── share.html       ← Shareable session card
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## Roadmap

- [ ] Season summary comparison (side-by-side)
- [ ] Discord webhook on session end
- [ ] Export sessions to CSV
- [ ] Public hosted dashboard (friend group leaderboard)

---

## License

MIT

---

*Built by mskeith — Zero Build only, always.*