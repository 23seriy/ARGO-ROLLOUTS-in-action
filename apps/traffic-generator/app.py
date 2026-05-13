"""
Game-Night Traffic Generator — simulates NBA fan traffic hitting the Scores API.

Runs as a Kubernetes Job or Deployment.  Sends a steady stream of requests so
Prometheus has data for AnalysisRuns to evaluate during canary rollouts.
"""

import os
import time
import random
import requests
import sys

TARGET_URL = os.getenv("TARGET_URL", "http://scores-api-stable:8080")
RPS = int(os.getenv("REQUESTS_PER_SECOND", "5"))
DURATION = int(os.getenv("DURATION_SECONDS", "300"))  # 0 = infinite
BURST_CHANCE = float(os.getenv("BURST_CHANCE", "0.1"))  # chance of a 3x burst
HEADERS = {}

# Optional: send preview header for header-based routing demos
PREVIEW_HEADER = os.getenv("PREVIEW_HEADER", "")
if PREVIEW_HEADER:
    HEADERS["X-Canary"] = PREVIEW_HEADER


def send_request(session: requests.Session):
    """Fire a single GET /scores and print the result."""
    try:
        resp = session.get(f"{TARGET_URL}/scores", headers=HEADERS, timeout=5)
        version = "?"
        try:
            version = resp.json().get("version", "?")
        except Exception:
            pass
        status_icon = "✅" if resp.status_code == 200 else "❌"
        print(f"{status_icon}  {resp.status_code}  version={version}  latency={resp.elapsed.total_seconds():.3f}s")
    except requests.exceptions.RequestException as exc:
        print(f"❌  ERROR  {exc}")


def main():
    print(f"🏀 Game-Night Traffic Generator")
    print(f"   Target:   {TARGET_URL}")
    print(f"   RPS:      {RPS}")
    print(f"   Duration: {'infinite' if DURATION == 0 else f'{DURATION}s'}")
    print(f"   Headers:  {HEADERS or '(none)'}")
    print()

    session = requests.Session()
    start = time.time()
    count = 0

    while True:
        if DURATION > 0 and (time.time() - start) >= DURATION:
            break

        # Occasional burst to simulate buzzer-beater traffic spikes
        burst = random.random() < BURST_CHANCE
        batch = RPS * 3 if burst else RPS
        if burst:
            print("🔥 BURST — buzzer-beater traffic spike!")

        for _ in range(batch):
            send_request(session)
            count += 1

        time.sleep(1)

    elapsed = time.time() - start
    print(f"\n📊 Done — {count} requests in {elapsed:.1f}s ({count / max(elapsed, 1):.1f} req/s)")


if __name__ == "__main__":
    main()
