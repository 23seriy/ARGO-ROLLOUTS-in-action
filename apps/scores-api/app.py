"""
NBA Live Scores API — the service we progressively deliver with Argo Rollouts.

VERSION is toggled at build time via Docker build-arg so the same source
produces v1 (basic box scores) and v2 (box scores + play-by-play).
"""

import os
import time
import random
from flask import Flask, jsonify, request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

VERSION = os.getenv("APP_VERSION", "v1")
ERROR_RATE = float(os.getenv("ERROR_RATE", "0"))  # 0-1, inject failures for analysis demos

# ---------------------------------------------------------------------------
# Prometheus metrics — used by AnalysisRun to decide promote vs rollback
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "scores_api_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status", "version"],
)
REQUEST_LATENCY = Histogram(
    "scores_api_request_duration_seconds",
    "Request latency in seconds",
    ["endpoint", "version"],
)

# ---------------------------------------------------------------------------
# Sample NBA data
# ---------------------------------------------------------------------------
LIVE_GAMES = [
    {
        "game_id": "2025-nba-001",
        "home": {"team": "Lakers", "abbreviation": "LAL", "score": 108},
        "away": {"team": "Celtics", "abbreviation": "BOS", "score": 112},
        "quarter": 4,
        "time_remaining": "2:34",
        "arena": "Crypto.com Arena",
    },
    {
        "game_id": "2025-nba-002",
        "home": {"team": "Warriors", "abbreviation": "GSW", "score": 96},
        "away": {"team": "Nuggets", "abbreviation": "DEN", "score": 101},
        "quarter": 3,
        "time_remaining": "5:12",
        "arena": "Chase Center",
    },
    {
        "game_id": "2025-nba-003",
        "home": {"team": "Bucks", "abbreviation": "MIL", "score": 115},
        "away": {"team": "76ers", "abbreviation": "PHI", "score": 110},
        "quarter": 4,
        "time_remaining": "0:45",
        "arena": "Fiserv Forum",
    },
]

PLAY_BY_PLAY = {
    "2025-nba-001": [
        {"time": "2:34 Q4", "team": "BOS", "player": "Jayson Tatum", "action": "3-point jumper", "score": "112-108"},
        {"time": "2:58 Q4", "team": "LAL", "player": "LeBron James", "action": "driving layup", "score": "108-109"},
        {"time": "3:15 Q4", "team": "BOS", "player": "Jaylen Brown", "action": "steal and fast-break dunk", "score": "109-106"},
        {"time": "3:40 Q4", "team": "LAL", "player": "Anthony Davis", "action": "block on Tatum", "score": "106-106"},
    ],
    "2025-nba-002": [
        {"time": "5:12 Q3", "team": "DEN", "player": "Nikola Jokić", "action": "no-look pass to Murray for three", "score": "101-96"},
        {"time": "5:30 Q3", "team": "GSW", "player": "Stephen Curry", "action": "deep three from the logo", "score": "96-98"},
        {"time": "5:55 Q3", "team": "DEN", "player": "Jamal Murray", "action": "mid-range pullup", "score": "98-93"},
    ],
    "2025-nba-003": [
        {"time": "0:45 Q4", "team": "MIL", "player": "Giannis Antetokounmpo", "action": "euro-step and-one", "score": "115-110"},
        {"time": "1:10 Q4", "team": "PHI", "player": "Joel Embiid", "action": "fadeaway jumper", "score": "112-110"},
        {"time": "1:30 Q4", "team": "MIL", "player": "Damian Lillard", "action": "step-back three", "score": "112-108"},
    ],
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Landing page with version badge."""
    color = "#1E90FF" if VERSION == "v1" else "#32CD32"
    features = "Basic box scores" if VERSION == "v1" else "Box scores + live play-by-play"
    return f"""
    <html>
    <head><title>NBA Scores API {VERSION}</title></head>
    <body style="font-family:Arial,sans-serif;background:#1a1a2e;color:#eee;padding:40px;text-align:center;">
        <h1>🏀 NBA Live Scores API</h1>
        <div style="display:inline-block;background:{color};padding:8px 24px;border-radius:20px;font-size:24px;font-weight:bold;margin:16px 0;">
            {VERSION}
        </div>
        <p style="font-size:18px;">{features}</p>
        <p style="margin-top:32px;font-size:14px;color:#888;">
            <a href="/scores" style="color:{color};">/scores</a> ·
            <a href="/health" style="color:{color};">/health</a> ·
            <a href="/metrics" style="color:{color};">/metrics</a>
        </p>
    </body>
    </html>
    """


@app.route("/scores")
def scores():
    """Return live game scores. v2 adds play-by-play data."""
    with REQUEST_LATENCY.labels(endpoint="/scores", version=VERSION).time():
        # Simulate occasional errors for analysis demos
        if ERROR_RATE > 0 and random.random() < ERROR_RATE:
            REQUEST_COUNT.labels(method="GET", endpoint="/scores", status="500", version=VERSION).inc()
            return jsonify({"error": "Scoreboard service temporarily unavailable"}), 500

        games = []
        for game in LIVE_GAMES:
            entry = dict(game)
            # v2 enhancement: include play-by-play
            if VERSION == "v2":
                entry["play_by_play"] = PLAY_BY_PLAY.get(game["game_id"], [])
            games.append(entry)

        REQUEST_COUNT.labels(method="GET", endpoint="/scores", status="200", version=VERSION).inc()
        return jsonify({
            "version": VERSION,
            "game_count": len(games),
            "games": games,
        })


@app.route("/health")
def health():
    """Liveness / readiness probe."""
    REQUEST_COUNT.labels(method="GET", endpoint="/health", status="200", version=VERSION).inc()
    return jsonify({"status": "healthy", "version": VERSION})


@app.route("/metrics")
def metrics():
    """Prometheus scrape endpoint."""
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
