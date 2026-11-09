
import json
import os
import time
from pathlib import Path

import requests

SUBREDDIT_URL = (
    "https://www.reddit.com/r/ClashOfClansLeaks/new.json?limit=100"
)

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
STATE_FILE = Path("seen_posts.json")

HEADERS = {
    "User-Agent": "RedditDiscordBridge/1.0 (personal subreddit feed)"
}


def save_seen(ids):
    STATE_FILE.write_text(
        json.dumps(ids[-1000:], indent=2),
        encoding="utf-8"
    )


def send_to_discord(post):
    title = post.get("title", "Untitled Reddit post")
    author = post.get("author", "Unknown")
    permalink = "https://www.reddit.com" + post["permalink"]

    embed = {
        "title": title[:256],
        "url": permalink,
        "description": f"Posted by u/{author}",
        "color": 0x8A63D2,
        "footer": {
            "text": "r/ClashOfClansLeaks"
        }
    }

    while True:
        response = requests.post(
            WEBHOOK_URL,
            json={"embeds": [embed]},
            timeout=30
        )

        if response.status_code == 429:
            retry = response.json().get("retry_after", 3)
            time.sleep(float(retry) + 1)
            continue

        response.raise_for_status()
        break



def main():
    response = requests.get(
        SUBREDDIT_URL,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()

    posts = response.json()["data"]["children"]
    posts = [item["data"] for item in posts]

    seen = (
        json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if STATE_FILE.exists()
        else []
    )

    # First run: save existing posts without sending them.
    if not seen:
        save_seen([post["id"] for post in posts])
        print("Initial setup complete. Existing posts saved.")
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
        print(f"Sent: {post['title']}")

    if not new_posts:
        print("No new Reddit posts.")

    save_seen(seen)


if __name__ == "__main__":
    main()
