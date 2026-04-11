"""
STEP B-1: discover.py
YouTube Data APIで36時間以内にアップされた実在の曲を検索・発掘する
→ Claude APIは一言コメント生成のみに使用
→ 発掘後にTodayプレイリストを更新する
"""

import os
import json
import datetime
import anthropic
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import WEEKDAY_CONFIG, DISCOVERY_RULES, SLOT_CONFIG


def get_today_config():
    weekday = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).weekday()
    return weekday, WEEKDAY_CONFIG[weekday]


def get_youtube_client():
    """YouTube APIクライアントを取得"""
    import json as json_mod
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    client_secret = json_mod.loads(os.environ["YOUTUBE_CLIENT_SECRET"])
    refresh_token = os.environ["YOUTUBE_REFRESH_TOKEN"]

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_secret["installed"]["client_id"],
        client_secret=client_secret["installed"]["client_secret"],
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def search_new_songs(youtube, slot: str, region_countries: list) -> list:
    """
    YouTube Data APIで36時間以内にアップされた曲を検索
    """
    slot_cfg = SLOT_CONFIG[slot]
    genres = slot_cfg["genres"]
    hours = DISCOVERY_RULES["release_hours"]
    n = DISCOVERY_RULES["songs_per_day"]

    published_after = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(hours=hours)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    found = []
    seen_ids = set()

    # ジャンルごとに検索
    for genre in genres:
        if len(found) >= n:
            break

        query = f"{genre} music original"
        try:
            response = youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                publishedAfter=published_after,
                videoCategoryId="10",  # Music
                maxResults=5,
                order="date",
            ).execute()

            for item in response.get("items", []):
                if len(found) >= n:
                    break

                vid = item["id"]["videoId"]
                if vid in seen_ids:
                    continue
                seen_ids.add(vid)

                snippet = item["snippet"]
                found.append({
                    "artist": snippet["channelTitle"],
                    "title": snippet["title"],
                    "youtube_video_id": vid,
                    "youtube_url": f"https://youtu.be/{vid}",
                    "genre": genre,
                    "country": "Unknown",
                    "followers": "0",
                    "comment_ja": "",
                    "comment_en": "",
                    "published_at": snippet["publishedAt"],
                })

        except Exception as e:
            print(f"  ⚠️  検索失敗 ({genre}): {e}")

    return found[:n]


def generate_comments(songs: list, slot: str, weekday_config: dict) -> list:
    """Claude APIで一言コメントを生成"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    slot_cfg = SLOT_CONFIG[slot]

    songs_text = "\n".join([
        f"{i+1}. {s['artist']} - {s['title']} (Genre: {s['genre']})"
        for i, s in enumerate(songs)
    ])

    prompt = f"""
以下の楽曲リストに対して、それぞれ一言コメントを生成してください。

プレイリストの雰囲気: {slot_cfg['description']}

楽曲リスト:
{songs_text}

【出力形式】
必ずJSON配列のみを返してください。他のテキストは一切不要です。

[
  {{
    "comment_ja": "この曲の魅力を伝える一言（日本語・30文字以内）",
    "comment_en": "One-line comment in English (under 50 chars)"
  }}
]
"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    comments = json.loads(raw.strip())

    for i, song in enumerate(songs):
        if i < len(comments):
            song["comment_ja"] = comments[i].get("comment_ja", "")
            song["comment_en"] = comments[i].get("comment_en", "")

    return songs


def save_results(songs: list, slot: str, weekday: int, config: dict) -> str:
    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%Y-%m-%d")

    result = {
        "date": today,
        "slot": slot,
        "weekday": weekday,
        "region": config["region"],
        "bgm": config["bgm"],
        "dancer_prefix": config["dancer_prefix"],
        "songs": songs,
    }

    os.makedirs("data", exist_ok=True)
    path = f"data/discovery_{today}_{slot}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 保存完了: {len(songs)}曲 → {path}")
    return path


def update_today_playlist(youtube, songs: list, slot: str):
    """Todayプレイリストを更新（既存削除→新規追加）"""
    if slot == "morning":
        playlist_id = os.environ["YT_PLAYLIST_TODAY"]
    else:
        playlist_id = os.environ["YT_PLAYLIST_YESTERDAY"]

    # 既存アイテムを全削除
    try:
        existing = youtube.playlistItems().list(
            part="id", playlistId=playlist_id, maxResults=50
        ).execute()
        for item in existing.get("items", []):
            youtube.playlistItems().delete(id=item["id"]).execute()
        print(f"🗑  プレイリストをクリア")
    except Exception as e:
        print(f"  ⚠️  クリア失敗: {e}")

    # 新しい曲を追加
    added = 0
    for song in songs:
        vid = song.get("youtube_video_id", "").strip()
        if not vid:
            continue
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={"snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": vid
                    }
                }}
            ).execute()
            added += 1
        except Exception as e:
            print(f"  ⚠️  追加失敗: {song['title']} - {e}")

    print(f"✅ プレイリスト更新完了: {added}曲追加")


def main():
    weekday, config = get_today_config()
    print(f"📅 今日: {config['label']} / {config['region']}")

    youtube = get_youtube_client()

    for slot in ["morning", "evening"]:
        slot_cfg = SLOT_CONFIG[slot]
        print(f"\n{'🌅' if slot == 'morning' else '🌙'} {slot_cfg['title_prefix']}")
        print(f"  ジャンル: {' / '.join(slot_cfg['genres'])}")

        # YouTube APIで実在する曲を検索
        print("  🔍 YouTube APIで曲を検索中...")
        songs = search_new_songs(youtube, slot, config["countries"])
        print(f"  📋 {len(songs)}曲取得")

        for i, s in enumerate(songs, 1):
            print(f"    {i:2d}. {s['artist']} - {s['title']}")

        # Claude APIでコメント生成
        print("  💬 コメント生成中...")
        songs = generate_comments(songs, slot, config)

        # 保存
        save_results(songs, slot, weekday, config)

        # Todayプレイリスト更新
        print("  📋 プレイリスト更新中...")
        update_today_playlist(youtube, songs, slot)

    print("\n✅ 全処理完了")


if __name__ == "__main__":
    main()
