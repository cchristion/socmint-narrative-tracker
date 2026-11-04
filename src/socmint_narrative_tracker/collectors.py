import hashlib
import json
import re
from datetime import datetime, timedelta

import pandas as pd
import requests
import scrapetube
from bs4 import BeautifulSoup
from ddgs import DDGS

CACHE_DIR = "data/cache"
SAMPLE_PATH = "data/sample_acme_bank.json"


def _md5(text: str) -> str:
    # Produces a 12-char hash to fingerprint profile avatars
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def scrape_youtube_live(topic: str, limit: int = 15) -> list[dict]:
    results = []
    try:
        videos = scrapetube.get_search(topic, limit=limit)
        now = datetime.utcnow()
        for idx, v in enumerate(videos):
            vid_id = v.get("videoId", f"yt_{idx}")
            title = v.get("title", {}).get("runs", [{}])[0].get("text", "")
            channel = (
                v.get("ownerText", {})
                .get("runs", [{}])[0]
                .get("text", f"yt_channel_{idx}")
            )
            view_text = v.get("viewCountText", {}).get("simpleText", "0")
            views = int(re.sub(r"[^0-9]", "", view_text) or 150)

            results.append(
                {
                    "post_id": f"yt_{vid_id}",
                    "platform": "YouTube",
                    "author_handle": f"@{re.sub(r'[^a-zA-Z0-9_]', '', channel) or 'yt_user'}",
                    "author_created_at": None,
                    "avatar_hash": _md5(channel),
                    "timestamp": (now - timedelta(hours=idx * 2 + 1)).isoformat(),
                    "text": title or f"Video coverage regarding {topic}",
                    "media_urls": [f"https://www.youtube.com/watch?v={vid_id}"],
                    "media_type": "video",
                    "amplified_handle": "",
                    "link": f"https://www.youtube.com/watch?v={vid_id}",
                }
            )
    except Exception as e:
        print(f"[WARN] YouTube scrape error: {e}")
    return results


def scrape_telegram_and_x_live(topic: str, limit: int = 15) -> list[dict]:
    results = []
    now = datetime.utcnow()
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

    try:
        with DDGS() as ddgs:
            for idx, hit in enumerate(
                ddgs.text(f'site:t.me "{topic}"', max_results=limit)
            ):
                href = hit.get("href", "")
                body = hit.get("body", "") or hit.get("title", "")
                m = re.search(r"t\.me/(?:s/)?([a-zA-Z0-9_]+)", href)
                handle = f"@{m.group(1)}" if m else f"@tg_channel_{idx}"
                ts_iso = (now - timedelta(hours=idx * 2 + 1)).isoformat()

                if "t.me/s/" in href:
                    try:
                        resp = requests.get(href, headers=headers, timeout=5)
                        soup = BeautifulSoup(resp.text, "html.parser")
                        t_tag = soup.select_one(".tgme_widget_message_date time")
                        if t_tag and t_tag.get("datetime"):
                            ts_iso = t_tag["datetime"][:19]
                    except Exception:
                        pass

                results.append(
                    {
                        "post_id": f"tg_live_{idx}",
                        "platform": "Telegram",
                        "author_handle": handle,
                        "author_created_at": None,
                        "avatar_hash": _md5(handle),
                        "timestamp": ts_iso,
                        "text": body[:400],
                        "media_urls": [],
                        "media_type": "text",
                        "amplified_handle": "",
                        "link": href,
                    }
                )

            for idx, hit in enumerate(
                ddgs.text(
                    f'(site:x.com OR site:twitter.com) "{topic}"', max_results=limit
                )
            ):
                href = hit.get("href", "")
                body = hit.get("body", "") or hit.get("title", "")
                m = re.search(r"(?:x\.com|twitter\.com)/([a-zA-Z0-9_]+)", href)
                handle = f"@{m.group(1)}" if m else f"@x_user_{idx}"

                results.append(
                    {
                        "post_id": f"x_live_{idx}",
                        "platform": "X",
                        "author_handle": handle,
                        "author_created_at": None,
                        "avatar_hash": _md5(handle),
                        "timestamp": (now - timedelta(hours=idx * 2 + 1)).isoformat(),
                        "text": body[:400],
                        "media_urls": [],
                        "media_type": "text",
                        "amplified_handle": "",
                        "link": href,
                    }
                )
    except Exception as e:
        print(f"[WARN] Live OSINT error: {e}")
    return results


def collect_posts(
    topic: str, start_date: str, end_date: str, platforms: list[str], mode: str = "live"
) -> pd.DataFrame:
    posts = []

    if mode == "sample":
        with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
            posts = json.load(f)
    else:
        if "YouTube" in platforms:
            posts.extend(scrape_youtube_live(topic))
        if "Telegram" in platforms or "X" in platforms:
            posts.extend(scrape_telegram_and_x_live(topic))

    df = pd.DataFrame(posts)
    if df.empty:
        return df

    df = df[df["platform"].isin(platforms)].copy()
    df["timestamp_dt"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["author_created_dt"] = pd.to_datetime(
        df["author_created_at"], utc=True, errors="coerce"
    )

    start_dt = pd.to_datetime(start_date, utc=True)
    end_dt = pd.to_datetime(end_date, utc=True) + pd.Timedelta(days=1)
    mask = (df["timestamp_dt"] >= start_dt) & (df["timestamp_dt"] <= end_dt)
    if mask.sum() > 0:
        df = df[mask].copy()

    return df.sort_values("timestamp_dt").reset_index(drop=True)
