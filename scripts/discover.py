"""
STEP B-1: discover.py
Claude APIを使って今日のリージョンから10曲を発掘する
"""

import os
import json
import datetime
import anthropic
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import WEEKDAY_CONFIG, DISCOVERY_RULES

def get_today_config():
    """今日の曜日設定を取得"""
    weekday = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).weekday()
    return weekday, WEEKDAY_CONFIG[weekday]

def discover_songs(weekday: int, config: dict) -> list:
    """Claude APIで曲を発掘"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    countries_str = "、".join(config["countries"])
    region = config["region"]
    n = DISCOVERY_RULES["songs_per_day"]
    max_followers = DISCOVERY_RULES["max_followers"]
    months = DISCOVERY_RULES["release_months"]

    prompt = f"""
あなたは世界の無名音楽を発掘するキュレーターです。

今日のリージョン: {region}
対象国: {countries_str}

以下の条件を満たすアーティストと楽曲を{n}件発掘してください。

【発掘条件】
- リリースから{months}ヶ月以内の新曲
- フォロワー{max_followers}人未満（理想は100人以下）
- メジャーレーベル非所属
- インスト多め・歌あり・音楽性重視
- YouTubeまたはSpotifyに存在する曲

【出力形式】
必ずJSON配列のみを返してください。他のテキストは一切不要です。

[
  {{
    "artist": "アーティスト名",
    "title": "曲名",
    "country": "国名（英語）",
    "genre": "ジャンル（英語・簡潔に）",
    "followers": "フォロワー数の概算（数字のみ）",
    "youtube_search": "YouTubeで検索するためのキーワード",
    "spotify_search": "Spotifyで検索するためのキーワード",
    "comment_ja": "この曲の魅力を伝える一言（日本語・40文字以内）",
    "comment_en": "One-line comment in English (under 60 chars)",
    "release_year": 2024,
    "release_month": 11
  }}
]

実在する可能性が高いアーティストを選んでください。
架空のアーティストは避けてください。
"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    # JSONの抽出（```json ... ``` などが含まれる場合に対応）
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    songs = json.loads(raw.strip())
    return songs


def save_results(songs: list, weekday: int, config: dict):
    """発掘結果をJSONファイルに保存"""
    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%Y-%m-%d")

    result = {
        "date": today,
        "weekday": weekday,
        "region": config["region"],
        "bgm": config["bgm"],
        "dancer_prefix": config["dancer_prefix"],
        "songs": songs
    }

    os.makedirs("data", exist_ok=True)
    path = f"data/discovery_{today}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 発掘完了: {len(songs)}曲 → {path}")
    return path


def main():
    weekday, config = get_today_config()
    print(f"📅 今日: {config['label']} / {config['region']}")
    print(f"🎵 BGM: {config['bgm']}")
    print(f"💃 ダンサー: {config['dancer_prefix']}_01〜08.png")
    print("🔍 Claude APIで曲を発掘中...")

    songs = discover_songs(weekday, config)

    for i, s in enumerate(songs, 1):
        print(f"  {i:2d}. {s['artist']} - {s['title']} ({s['country']})")

    path = save_results(songs, weekday, config)
    return path


if __name__ == "__main__":
    main()
