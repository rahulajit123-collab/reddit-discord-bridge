

import os
import json
import time
import requests
import xml.etree.ElementTree as ET

from pathlib import Path
from html import unescape

FEED_URL = os.environ["REDDIT_RSS_URL"]
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

STATE_FILE = Path("seen_posts.json")

HEADERS = {
    "User-Agent": "HalfBaked-RedditDiscordBridge/1.0"
}


def local_name(tag):
    return tag.split("}")[-1].lower()


def get_child_text(element, names):
    for child in element:
        if local_name(child.tag) in names:
            if child.text:
                return child.text.strip()

            # Atom links usually store the URL in href.
            href = child.attrib.get("href")
            if href:
                return href

    return None


def fetch_posts():
    response = requests.get(
        FEED_URL,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    posts = []

    for element in root.iter():
        if local_name(element.tag) not in ("item", "entry"):
            continue

        title = get_child_text(element, {"title"})
        link = get_child_text(element, {"link"})
        post_id = get_child_text(element, {"guid", "id"})
        author = get_child_text(
            element,
            {"creator", "author", "name"}
        )

        if not title or not link:
            continue

        post_id = post_id or link

        posts.append({
            "id": post_id,
            "title": unescape(title),
            "link": link,
            "author": author or "Unknown"
        })

    return posts


def save_seen(ids):
    STATE_FILE.write_text(
        json.dumps(ids[-1000:], indent=2),
        encoding="utf-8"
    )


def send_to_discord(post):
    embed = {
        "title": post["title"][:256],
        "url": post["link"],
        "description": f"Posted by {post['author']}",
        "color": 0x8A63D2,
        "footer": {
            "text": "Clash of Clans Leaks"
        }
    }

    while True:
        response = requests.post(
            WEBHOOK_URL,
            json={
                "embeds": [embed],
                "allowed_mentions": {"parse": []}
            },
            timeout=30
        )

        if response.status_code == 429:
            retry = response.json().get("retry_after", 3)
            time.sleep(float(retry) + 1)
            continue

        response.raise_for_status()
        break


def main():
    posts = fetch_posts()

    seen = (
        json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if STATE_FILE.exists()
        else []
    )

    # First run: remember existing posts without sending them.
    if not seen:
        save_seen([post["id"] for post in posts])
        print(f"Initial setup complete. Saved {len(posts)} existing posts.")
        return

    seen_set = set(seen)

    new_posts = [
        post for post in reversed(posts)
        if post["id"] not in seen_set
    ]

    for post in new_posts:
        send_to_discord(post)

        seen.append(post["id"])
        seen_set.add(post["id"])
        save_seen(seen)

        print(f"Sent to Discord: {post['title']}")

    if not new_posts:
        print("No new posts found.")

    save_seen(seen)


if __name__ == "__main__":
    main()




