"""
STEP B-1: discover.py
Claude APIを使って今日のリージョンから10曲を発掘する
→ 発掘後にYouTube TODAYプレイリストを更新する
"""

import os
import json
import datetime
import anthropic
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import WEEKDAY_CONFIG, DISCOVERY_RULES


def get_today_config():
    weekday = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).weekday()
    return weekday, WEEKDAY_CONFIG[weekday]


def discover_songs(weekday: int, config: dict) -> list:
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
    "youtube_video_id": "YouTubeのVideo ID（わかれば）。不明な場合は空文字",
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
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    songs = json.loads(raw.strip())
    return songs


def save_results(songs: list, weekday: int, config: dict) -> str:
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


def update_today_playlist(songs: list):
    client_secret_str = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

    if not client_secret_str or not refresh_token:
        print("⚠️  YouTube認証情報がありません。スキップします。")
        return

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        client_secret = json.loads(client_secret_str)
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_secret["installed"]["client_id"],
            client_secret=client_secret["installed"]["client_secret"],
        )
        creds.refresh(Request())
        youtube = build("youtube", "v3", credentials=creds)

        playlist_id = os.environ["YT_PLAYLIST_TODAY"]

        existing = youtube.playlistItems().list(
            part="id", playlistId=playlist_id, maxResults=50
        ).execute()
        for item in existing.get("items", []):
            youtube.playlistItems().delete(id=item["id"]).execute()
        print("🗑  TODAYプレイリストをクリア")

        added = 0
        for song in songs:
            vid = song.get("youtube_video_id", "").strip()
            if not vid:
                print(f"  スキップ（Video IDなし）: {song['artist']} - {song['title']}")
                continue
            try:
                youtube.playlistItems().insert(
                    part="snippet",
                    body={"snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": vid}
                    }}
                ).execute()
                print(f"  ✅ 追加: {song['artist']} - {song['title']} ({vid})")
                added += 1
            except Exception as e:
                print(f"  ⚠️  追加失敗: {song['artist']} - {e}")

        print(f"✅ TODAYプレイリスト更新完了: {added}曲追加")

    except Exception as e:
        print(f"⚠️  TODAYプレイリスト更新エラー: {e}")
        print("   ※ 発掘・メール送信は続行します")


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

    print("📋 YouTube TODAYプレイリストを更新中...")
    update_today_playlist(songs)

    return path


if __name__ == "__main__":
    main()
