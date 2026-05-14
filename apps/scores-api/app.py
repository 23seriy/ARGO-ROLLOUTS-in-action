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
# Team colors for NBA-style scorecards
# ---------------------------------------------------------------------------
TEAM_COLORS = {
    "LAL": {"primary": "#552583", "secondary": "#FDB927"},
    "BOS": {"primary": "#007A33", "secondary": "#BA9653"},
    "GSW": {"primary": "#1D428A", "secondary": "#FFC72C"},
    "DEN": {"primary": "#0E2240", "secondary": "#FEC524"},
    "MIL": {"primary": "#00471B", "secondary": "#EEE1C6"},
    "PHI": {"primary": "#006BB6", "secondary": "#ED174C"},
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """NBA Game-Night Dashboard with live scorecards and traffic testing."""
    v_color = "#3b82f6" if VERSION == "v1" else "#22c55e"
    v_glow = "rgba(59,130,246,0.3)" if VERSION == "v1" else "rgba(34,197,94,0.3)"
    v_label = "STABLE" if VERSION == "v1" else "CANARY"
    features = "Basic box scores" if VERSION == "v1" else "Box scores + live play-by-play"

    # Build game cards HTML
    game_cards = ""
    for game in LIVE_GAMES:
        h = game["home"]
        a = game["away"]
        hc = TEAM_COLORS.get(h["abbreviation"], {"primary": "#333", "secondary": "#888"})
        ac = TEAM_COLORS.get(a["abbreviation"], {"primary": "#333", "secondary": "#888"})
        pbp_html = ""
        if VERSION == "v2":
            plays = PLAY_BY_PLAY.get(game["game_id"], [])
            if plays:
                rows = "".join(
                    f'<div class="pbp-row">'
                    f'<span class="pbp-time">{p["time"]}</span>'
                    f'<span class="pbp-team" style="color:{TEAM_COLORS.get(p["team"],{"secondary":"#ccc"})["secondary"]}">{p["team"]}</span>'
                    f'<span class="pbp-action"><strong>{p["player"]}</strong> — {p["action"]}</span>'
                    f'<span class="pbp-score">{p["score"]}</span>'
                    f'</div>'
                    for p in plays
                )
                pbp_html = f'<div class="pbp-section"><div class="pbp-label">PLAY-BY-PLAY <span class="v2-badge">v2</span></div>{rows}</div>'

        game_cards += f"""
        <div class="game-card">
          <div class="game-header">
            <span class="quarter-badge">Q{game["quarter"]} · {game["time_remaining"]}</span>
            <span class="arena-label">{game["arena"]}</span>
          </div>
          <div class="matchup">
            <div class="team-block">
              <div class="team-abbr" style="color:{ac["secondary"]}">{a["abbreviation"]}</div>
              <div class="team-name">{a["team"]}</div>
              <div class="team-score" style="border-color:{ac["primary"]}">{a["score"]}</div>
            </div>
            <div class="vs-divider">VS</div>
            <div class="team-block">
              <div class="team-abbr" style="color:{hc["secondary"]}">{h["abbreviation"]}</div>
              <div class="team-name">{h["team"]}</div>
              <div class="team-score" style="border-color:{hc["primary"]}">{h["score"]}</div>
            </div>
          </div>
          {pbp_html}
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>NBA Scores API {VERSION} — Argo Rollouts in Action</title>
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
          background:
            radial-gradient(ellipse at top left, {v_glow}, transparent 40%),
            linear-gradient(180deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
          color: #f8fafc;
          min-height: 100vh;
          padding: 32px 16px;
        }}
        .container {{ max-width: 960px; margin: 0 auto; }}

        /* ── Hero ────────────────────────────── */
        .hero {{
          position: relative;
          overflow: hidden;
          background: linear-gradient(135deg, rgba(30,41,59,0.92), rgba(15,23,42,0.95));
          border: 1px solid rgba(148,163,184,0.15);
          border-radius: 24px;
          padding: 28px 32px;
          box-shadow: 0 24px 60px rgba(0,0,0,0.4);
          margin-bottom: 20px;
        }}
        .hero::before {{
          content: "";
          position: absolute;
          inset: auto -100px -100px auto;
          width: 280px; height: 280px;
          border-radius: 50%;
          background: radial-gradient(circle, {v_glow}, transparent 70%);
        }}
        .hero-top {{
          display: flex; align-items: center; gap: 14px;
          flex-wrap: wrap; margin-bottom: 12px; position: relative;
        }}
        .version-pill {{
          display: inline-flex; align-items: center; gap: 8px;
          padding: 6px 16px; border-radius: 999px;
          background: {v_color}22; border: 1px solid {v_color}55;
          font-weight: 800; font-size: 0.9rem; letter-spacing: 0.06em;
          color: {v_color}; text-transform: uppercase;
        }}
        .version-dot {{
          width: 8px; height: 8px; border-radius: 50%;
          background: {v_color};
          box-shadow: 0 0 8px {v_color};
          animation: pulse 2s ease-in-out infinite;
        }}
        @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.4; }} }}
        h1 {{
          position: relative;
          font-size: 2.4rem;
          background: linear-gradient(135deg, #f97316, #facc15 45%, #38bdf8 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          margin-bottom: 6px;
        }}
        .subtitle {{
          position: relative; color: #94a3b8; line-height: 1.6; max-width: 720px;
        }}
        .hero-grid {{
          position: relative;
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
          gap: 12px; margin-top: 18px;
        }}
        .hero-stat {{
          background: rgba(15,23,42,0.7);
          border: 1px solid rgba(148,163,184,0.15);
          border-radius: 14px; padding: 12px 14px;
        }}
        .hero-stat-label {{
          color: #64748b; font-size: 0.78rem; text-transform: uppercase;
          letter-spacing: 0.06em; font-weight: 700;
        }}
        .hero-stat-value {{
          margin-top: 4px; font-size: 1.05rem; font-weight: 800; color: #e2e8f0;
        }}

        /* ── Game Cards ─────────────────────── */
        .games-label {{
          color: #94a3b8; font-size: 0.82rem; font-weight: 700;
          text-transform: uppercase; letter-spacing: 0.08em;
          margin-bottom: 10px;
        }}
        .games-grid {{
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 14px; margin-bottom: 20px;
        }}
        .game-card {{
          background: linear-gradient(180deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95));
          border: 1px solid rgba(148,163,184,0.12);
          border-radius: 18px; padding: 18px;
          box-shadow: 0 12px 32px rgba(0,0,0,0.25);
        }}
        .game-header {{
          display: flex; justify-content: space-between; align-items: center;
          margin-bottom: 14px;
        }}
        .quarter-badge {{
          background: #ef444422; color: #fca5a5; padding: 3px 10px;
          border-radius: 999px; font-size: 0.78rem; font-weight: 700;
          border: 1px solid #ef444433;
        }}
        .arena-label {{ color: #64748b; font-size: 0.75rem; }}
        .matchup {{
          display: flex; align-items: center; justify-content: space-around; gap: 8px;
        }}
        .team-block {{ text-align: center; }}
        .team-abbr {{ font-size: 1.4rem; font-weight: 900; letter-spacing: 0.04em; }}
        .team-name {{ color: #94a3b8; font-size: 0.78rem; margin-top: 2px; }}
        .team-score {{
          font-size: 2rem; font-weight: 900; margin-top: 6px;
          padding: 4px 14px; border-radius: 10px;
          background: rgba(15,23,42,0.6); border-bottom: 3px solid;
        }}
        .vs-divider {{
          color: #475569; font-size: 0.8rem; font-weight: 700;
        }}

        /* ── Play-by-Play (v2 only) ─────────── */
        .pbp-section {{
          margin-top: 14px; padding-top: 12px;
          border-top: 1px solid rgba(148,163,184,0.1);
        }}
        .pbp-label {{
          color: #64748b; font-size: 0.72rem; font-weight: 700;
          text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;
        }}
        .v2-badge {{
          display: inline-block; background: #22c55e22; color: #22c55e;
          padding: 1px 6px; border-radius: 4px; font-size: 0.68rem;
          border: 1px solid #22c55e44; margin-left: 6px;
        }}
        .pbp-row {{
          display: grid;
          grid-template-columns: 70px 40px 1fr 70px;
          gap: 8px; padding: 5px 0; font-size: 0.8rem;
          border-bottom: 1px solid rgba(148,163,184,0.06);
          align-items: center;
        }}
        .pbp-time {{ color: #64748b; font-family: monospace; font-size: 0.75rem; }}
        .pbp-team {{ font-weight: 800; font-size: 0.78rem; }}
        .pbp-action {{ color: #cbd5e1; }}
        .pbp-score {{ color: #94a3b8; text-align: right; font-family: monospace; }}

        /* ── Traffic Tester ──────────────────── */
        .tester {{
          background: linear-gradient(180deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95));
          border: 1px solid rgba(148,163,184,0.12);
          border-radius: 18px; padding: 22px; margin-bottom: 20px;
          box-shadow: 0 12px 32px rgba(0,0,0,0.25);
        }}
        .tester-title {{
          color: #f8fafc; font-size: 1.1rem; font-weight: 700; margin-bottom: 14px;
        }}
        .controls {{
          display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px;
        }}
        button {{
          border: none; border-radius: 12px; padding: 11px 18px;
          cursor: pointer; color: white; font-weight: 700; font-size: 0.9rem;
          box-shadow: 0 8px 20px rgba(0,0,0,0.25);
          transition: transform 0.15s, box-shadow 0.15s;
        }}
        button:hover {{
          transform: translateY(-1px);
          box-shadow: 0 12px 28px rgba(0,0,0,0.35);
        }}
        .btn-single {{ background: linear-gradient(135deg, #3b82f6, #6366f1); }}
        .btn-burst {{ background: linear-gradient(135deg, #f97316, #ea580c); }}
        .btn-mega {{ background: linear-gradient(135deg, #ef4444, #dc2626); }}
        .btn-secondary {{ background: linear-gradient(135deg, #475569, #334155); }}

        .stats-bar {{
          display: flex; justify-content: space-between; flex-wrap: wrap;
          gap: 8px; margin-bottom: 10px;
        }}
        .stat-item {{
          background: rgba(15,23,42,0.7);
          border: 1px solid rgba(148,163,184,0.1);
          border-radius: 10px; padding: 8px 14px; flex: 1; min-width: 100px;
          text-align: center;
        }}
        .stat-label {{ color: #64748b; font-size: 0.72rem; text-transform: uppercase; font-weight: 700; }}
        .stat-value {{ font-size: 1.3rem; font-weight: 800; margin-top: 2px; }}
        .stat-v1 {{ color: #3b82f6; }}
        .stat-v2 {{ color: #22c55e; }}
        .stat-err {{ color: #ef4444; }}
        .stat-total {{ color: #e2e8f0; }}

        .dist-bar {{
          display: flex; height: 10px; border-radius: 6px; overflow: hidden;
          background: #1e293b; margin-bottom: 14px;
        }}
        .dist-v1 {{ background: #3b82f6; transition: width 0.3s; }}
        .dist-v2 {{ background: #22c55e; transition: width 0.3s; }}
        .dist-err {{ background: #ef4444; transition: width 0.3s; }}

        .history {{
          max-height: 200px; overflow-y: auto; font-size: 0.82rem;
        }}
        .history-row {{
          display: flex; align-items: center; gap: 8px; padding: 4px 0;
          border-bottom: 1px solid rgba(148,163,184,0.06);
        }}
        .h-dot {{
          width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
        }}
        .h-dot-v1 {{ background: #3b82f6; }}
        .h-dot-v2 {{ background: #22c55e; }}
        .h-dot-err {{ background: #ef4444; }}
        .h-text {{ color: #94a3b8; }}
        .h-latency {{ color: #64748b; margin-left: auto; font-family: monospace; }}

        /* ── Footer ─────────────────────────── */
        .footer {{
          color: #475569; font-size: 0.82rem; text-align: center; margin-top: 8px;
        }}
        .footer a {{ color: #64748b; text-decoration: none; }}
        .footer a:hover {{ color: #94a3b8; }}
      </style>
    </head>
    <body>
      <div class="container">
        <!-- Hero -->
        <div class="hero">
          <div class="hero-top">
            <div class="version-pill"><div class="version-dot"></div> {VERSION} · {v_label}</div>
          </div>
          <h1>🏀 NBA Live Scores API</h1>
          <p class="subtitle">
            {features} — served by <strong>Argo Rollouts</strong>.
            Hit the traffic tester below to see which version responds during a canary rollout.
          </p>
          <div class="hero-grid">
            <div class="hero-stat">
              <div class="hero-stat-label">Version</div>
              <div class="hero-stat-value" style="color:{v_color}">{VERSION}</div>
            </div>
            <div class="hero-stat">
              <div class="hero-stat-label">Strategy</div>
              <div class="hero-stat-value">{v_label}</div>
            </div>
            <div class="hero-stat">
              <div class="hero-stat-label">Live Games</div>
              <div class="hero-stat-value">{len(LIVE_GAMES)}</div>
            </div>
            <div class="hero-stat">
              <div class="hero-stat-label">Features</div>
              <div class="hero-stat-value">{"PBP + Scores" if VERSION == "v2" else "Scores Only"}</div>
            </div>
          </div>
        </div>

        <!-- Live Games -->
        <div class="games-label">Live Scoreboard</div>
        <div class="games-grid">{game_cards}</div>

        <!-- Traffic Tester -->
        <div class="tester">
          <div class="tester-title">🔬 Canary Traffic Tester</div>
          <div class="controls">
            <button class="btn-single" onclick="callScores()">🏀 Single Request</button>
            <button class="btn-burst" onclick="runBurst(20)">🔥 20-Request Burst</button>
            <button class="btn-mega" onclick="runBurst(50)">🚨 50-Request Surge</button>
            <button class="btn-secondary" onclick="resetStats()">Reset Stats</button>
          </div>
          <div class="stats-bar">
            <div class="stat-item"><div class="stat-label">Total</div><div class="stat-value stat-total" id="s-total">0</div></div>
            <div class="stat-item"><div class="stat-label">v1 (stable)</div><div class="stat-value stat-v1" id="s-v1">0</div></div>
            <div class="stat-item"><div class="stat-label">v2 (canary)</div><div class="stat-value stat-v2" id="s-v2">0</div></div>
            <div class="stat-item"><div class="stat-label">Errors</div><div class="stat-value stat-err" id="s-err">0</div></div>
          </div>
          <div class="dist-bar" id="dist-bar">
            <div class="dist-v1" id="bar-v1" style="width:0%"></div>
            <div class="dist-v2" id="bar-v2" style="width:0%"></div>
            <div class="dist-err" id="bar-err" style="width:0%"></div>
          </div>
          <div class="history" id="history"></div>
        </div>

        <div class="footer">
          <a href="/scores">/scores</a> · <a href="/health">/health</a> · <a href="/metrics">/metrics</a>
          &nbsp;|&nbsp; Argo Rollouts in Action
        </div>
      </div>

      <script>
        let counts = {{ v1: 0, v2: 0, err: 0 }};
        let history = [];

        async function callScores() {{
          const start = performance.now();
          try {{
            const res = await fetch('/scores');
            const ms = (performance.now() - start).toFixed(0);
            if (!res.ok) {{
              counts.err++;
              history.unshift({{ version: 'error', status: res.status, latency: ms }});
            }} else {{
              const data = await res.json();
              const v = data.version || '?';
              if (v === 'v1') counts.v1++;
              else if (v === 'v2') counts.v2++;
              else counts.err++;
              history.unshift({{ version: v, status: res.status, latency: ms, games: data.game_count }});
            }}
          }} catch (e) {{
            counts.err++;
            history.unshift({{ version: 'error', status: 0, latency: '—' }});
          }}
          if (history.length > 40) history.pop();
          renderStats();
        }}

        async function runBurst(n) {{
          for (let i = 0; i < n; i++) {{
            await callScores();
            await new Promise(r => setTimeout(r, 150));
          }}
        }}

        function resetStats() {{
          counts = {{ v1: 0, v2: 0, err: 0 }};
          history = [];
          renderStats();
        }}

        function renderStats() {{
          const total = counts.v1 + counts.v2 + counts.err;
          document.getElementById('s-total').textContent = total;
          document.getElementById('s-v1').textContent = counts.v1 + (total ? ' (' + pct(counts.v1, total) + ')' : '');
          document.getElementById('s-v2').textContent = counts.v2 + (total ? ' (' + pct(counts.v2, total) + ')' : '');
          document.getElementById('s-err').textContent = counts.err;

          document.getElementById('bar-v1').style.width = pct(counts.v1, total);
          document.getElementById('bar-v2').style.width = pct(counts.v2, total);
          document.getElementById('bar-err').style.width = pct(counts.err, total);

          const hEl = document.getElementById('history');
          hEl.innerHTML = history.slice(0, 30).map(h => {{
            const dotClass = h.version === 'v1' ? 'h-dot-v1' : h.version === 'v2' ? 'h-dot-v2' : 'h-dot-err';
            const label = h.version === 'error' ? `ERROR ${{h.status}}` : `${{h.version}} — ${{h.status}} — ${{h.games || '?'}} games`;
            return `<div class="history-row"><div class="h-dot ${{dotClass}}"></div><span class="h-text">${{label}}</span><span class="h-latency">${{h.latency}}ms</span></div>`;
          }}).join('');
        }}

        function pct(n, total) {{ return total ? Math.round(n / total * 100) + '%' : '0%'; }}
      </script>
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
