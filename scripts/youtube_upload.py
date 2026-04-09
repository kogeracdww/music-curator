"""
STEP D-2: youtube_upload.py
生成した動画をYouTubeに予約投稿し、プレイリストを更新する
"""

import os
import json
import datetime
import argparse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def get_youtube_client():
    """YouTube APIクライアントを取得"""
    client_secret = json.loads(os.environ["YOUTUBE_CLIENT_SECRET"])
    refresh_token = os.environ["YOUTUBE_REFRESH_TOKEN"]

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_secret["installed"]["client_id"],
        client_secret=client_secret["installed"]["client_secret"],
    )

    # トークンをリフレッシュ
    creds.refresh(Request())

    return build("youtube", "v3", credentials=creds)


def build_caption(song: dict, slot: str) -> dict:
    """タイトルと説明文を生成"""
    slot_label = "朝" if slot == "morning" else "夕"
    country_tag = song.get("country", "").replace(" ", "")
    genre_tag = song.get("genre", "").replace(" ", "")
    app_url = os.environ.get("APP_URL", "yourapp.com")

    title = f"{song['artist']} - {song['title']} | {song['country']} · {song['genre']}"
    # YouTubeタイトルは100文字以内
    if len(title) > 95:
        title = title[:92] + "..."

    description = f"""🌍 今日の発掘 / Today's Discovery

{song['artist']} - {song['title']}
{song['country']} · {song['genre']} · フォロワー約{song['followers']}人

{song['comment_ja']}
{song['comment_en']}

🎧 Listen to this song:
▶ YouTube → (概要欄参照)
♪ Spotify → (概要欄参照)
🍎 Apple Music → (概要欄参照)
🛒 Tower Records → (概要欄参照)

━━━━━━━━━━━━
🔗 発掘した音楽をもっと深く楽しむ → {app_url}
━━━━━━━━━━━━

#musicdiscovery #unknownartist #{country_tag} #{genre_tag}
#undergroundmusic #indiemusic #newmusic
"""

    tags = [
        "musicdiscovery", "unknownartist", "undergroundmusic",
        "indiemusic", "newmusic",
        song["country"], song["genre"],
        song["artist"], song["title"],
    ]

    return {
        "title": title,
        "description": description,
        "tags": tags,
    }


def get_scheduled_time(slot: str) -> str:
    """予約投稿時刻を取得 (RFC3339形式)"""
    now_jst = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    )
    today = now_jst.date()

    if slot == "morning":
        post_time = datetime.datetime(
            today.year, today.month, today.day, 8, 0, 0,
            tzinfo=datetime.timezone(datetime.timedelta(hours=9))
        )
    else:
        post_time = datetime.datetime(
            today.year, today.month, today.day, 19, 0, 0,
            tzinfo=datetime.timezone(datetime.timedelta(hours=9))
        )

    # 過去の時刻なら翌日に
    if post_time <= now_jst:
        post_time += datetime.timedelta(days=1)

    return post_time.isoformat()


def upload_video(youtube, video_path: str, caption: dict, scheduled_time: str) -> str:
    """動画をアップロード"""
    body = {
        "snippet": {
            "title": caption["title"],
            "description": caption["description"],
            "tags": caption["tags"],
            "categoryId": "10",  # Music
        },
        "status": {
            "privacyStatus": "private",  # 予約投稿はprivateで作成後publishAtを設定
            "publishAt": scheduled_time,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  アップロード: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"✅ アップロード完了: https://youtu.be/{video_id}")
    return video_id


def add_to_playlist(youtube, video_id: str, playlist_id: str):
    """動画をプレイリストに追加"""
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id,
                },
                "position": 0,  # 先頭に追加
            }
        }
    ).execute()
    print(f"✅ プレイリストに追加: {playlist_id}")


def update_today_playlist(youtube, video_id: str):
    """TODAYプレイリストを更新（既存を削除して追加）"""
    playlist_id = os.environ["YT_PLAYLIST_TODAY"]

    # 既存のアイテムを取得
    existing = youtube.playlistItems().list(
        part="id",
        playlistId=playlist_id,
        maxResults=50
    ).execute()

    # 全削除
    for item in existing.get("items", []):
        youtube.playlistItems().delete(id=item["id"]).execute()

    # 新しい動画を追加
    add_to_playlist(youtube, video_id, playlist_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",     required=True, help="対象日 (YYYY-MM-DD)")
    parser.add_argument("--idx",      required=True, type=int)
    parser.add_argument("--slot",     required=True, choices=["morning", "evening"])
    parser.add_argument("--video",    required=True, help="動画ファイルパス")
    args = parser.parse_args()

    # 発掘データ読み込み
    data_path = f"data/discovery_{args.date}.json"
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    song = data["songs"][args.idx]
    slot_label = "朝" if args.slot == "morning" else "夕"
    print(f"📤 YouTube投稿開始: {song['artist']} - {song['title']} [{slot_label}枠]")

    youtube = get_youtube_client()

    caption = build_caption(song, args.slot)
    scheduled_time = get_scheduled_time(args.slot)
    print(f"📅 予約投稿時刻: {scheduled_time}")

    video_id = upload_video(youtube, args.video, caption, scheduled_time)

    # SELECTEDプレイリストに追加
    if args.slot == "morning":
        playlist_id = os.environ["YT_PLAYLIST_SELECTED_A"]
    else:
        playlist_id = os.environ["YT_PLAYLIST_SELECTED_B"]

    add_to_playlist(youtube, video_id, playlist_id)

    # 結果を保存
    result = {
        "date": args.date,
        "slot": args.slot,
        "song": song,
        "video_id": video_id,
        "scheduled_time": scheduled_time,
        "playlist_id": playlist_id,
    }

    os.makedirs("data", exist_ok=True)
    with open(f"data/upload_{args.date}_{args.slot}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 完了: https://youtu.be/{video_id}")


if __name__ == "__main__":
    main()
