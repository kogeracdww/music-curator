"""
STEP D-2: youtube_upload.py
生成した動画をYouTubeに予約投稿し、プレイリストを更新する
・Todayプレイリスト：毎日10曲入れ替え
・Selected/Midnightプレイリスト：4日分40曲をキープ（古い曲を削除）
"""

import os
import sys
import json
import datetime
import argparse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SLOT_CONFIG, PLAYLIST_RULES


def get_youtube_client():
    client_secret = json.loads(os.environ["YOUTUBE_CLIENT_SECRET"])
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


def build_caption(songs: list, slot: str, config: dict) -> dict:
    """タイトルと説明文を生成"""
    slot_cfg = SLOT_CONFIG[slot]
    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%Y.%m.%d")

    emoji = "🌅" if slot == "morning" else "🌙"
    title = f"{emoji} {slot_cfg['title_prefix']} | {today}"

    # 曲リスト
    song_list = "\n".join([
        f"{i+1:02d}. {s['artist']} - {s['title']}"
        for i, s in enumerate(songs)
    ])

    # プレイリストURL
    playlist_id = os.environ.get(
        "YT_PLAYLIST_TODAY" if slot == "morning" else "YT_PLAYLIST_YESTERDAY",
        ""
    )
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

    # ジャンルタグ（スペース・括弧を除去・小文字化）
    genre_tags = " ".join([
        "#" + g.lower().replace(" ", "").replace("(", "").replace(")", "").replace("-", "")
        for g in slot_cfg["genres"]
    ])

    app_url = "https://play.google.com/store/apps/dev?id=5374692864597792516"

    description = f"""{emoji} {slot_cfg['title_prefix']}
{today}

🎵 Tracklist
{song_list}

▶ YouTube Playlist
{playlist_url}

#musicdiscovery {genre_tags}

━━━━━━━━━━━━
🔗 {app_url}

We'll offer simple products that give you a little boost every day.
"""

    tags = ["musicdiscovery"] + [
        g.lower().replace(" ", "").replace("(", "").replace(")", "").replace("-", "")
        for g in slot_cfg["genres"]
    ]

    return {
        "title": title,
        "description": description,
        "tags": tags,
    }


def get_scheduled_time(slot: str) -> str:
    """予約投稿時刻を取得"""
    now_jst = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    )
    today = now_jst.date()

    hour = 8 if slot == "morning" else 19
    post_time = datetime.datetime(
        today.year, today.month, today.day, hour, 0, 0,
        tzinfo=datetime.timezone(datetime.timedelta(hours=9))
    )

    if post_time <= now_jst:
        post_time += datetime.timedelta(days=1)

    return post_time.isoformat()


def upload_video(youtube, video_path: str, caption: dict,
                 scheduled_time: str) -> str:
    """動画をアップロード"""
    body = {
        "snippet": {
            "title": caption["title"],
            "description": caption["description"],
            "tags": caption["tags"],
            "categoryId": "10",
        },
        "status": {
            "privacyStatus": "private",
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


def update_selected_playlist(youtube, songs: list, slot: str):
    """
    Selected/Midnightプレイリストを更新
    ・今日の10曲を先頭に追加
    ・4日前（40曲以降）の曲を削除
    """
    if slot == "morning":
        playlist_id = os.environ["YT_PLAYLIST_SELECTED_A"]
    else:
        playlist_id = os.environ["YT_PLAYLIST_SELECTED_B"]

    keep_days = PLAYLIST_RULES["keep_days"]
    songs_per_day = PLAYLIST_RULES["songs_per_day"]
    max_songs = keep_days * songs_per_day  # 40曲

    # 既存アイテムを取得
    existing_items = []
    next_page = None
    while True:
        params = dict(part="id,snippet", playlistId=playlist_id, maxResults=50)
        if next_page:
            params["pageToken"] = next_page
        resp = youtube.playlistItems().list(**params).execute()
        existing_items.extend(resp.get("items", []))
        next_page = resp.get("nextPageToken")
        if not next_page:
            break

    # 今日の曲を先頭に追加
    added = 0
    for song in reversed(songs):  # 逆順で追加して先頭に
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
                    },
                    "position": 0
                }}
            ).execute()
            added += 1
        except Exception as e:
            print(f"  ⚠️  追加失敗: {song['title']} - {e}")

    print(f"  ✅ {added}曲追加")

    # 40曲を超えた分を削除（古い順）
    total = len(existing_items) + added
    if total > max_songs:
        delete_count = total - max_songs
        # 既存アイテムの末尾から削除
        to_delete = existing_items[-(delete_count):]
        for item in to_delete:
            try:
                youtube.playlistItems().delete(id=item["id"]).execute()
            except Exception as e:
                print(f"  ⚠️  削除失敗: {e}")
        print(f"  🗑  {delete_count}曲削除（4日前分）")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",  required=True)
    parser.add_argument("--slot",  required=True, choices=["morning", "evening"])
    parser.add_argument("--video", required=True)
    args = parser.parse_args()

    slot_cfg = SLOT_CONFIG[args.slot]
    slot_label = "朝" if args.slot == "morning" else "深夜"
    print(f"📤 YouTube投稿開始: {slot_cfg['title_prefix']} [{slot_label}枠]")

    youtube = get_youtube_client()

    # プレイリストから現在の曲を取得（discoveryデータ不要）
    playlist_id = os.environ.get(
        "YT_PLAYLIST_TODAY" if args.slot == "morning" else "YT_PLAYLIST_YESTERDAY",
        ""
    )
    items = []
    next_page = None
    while True:
        params = dict(part="snippet", playlistId=playlist_id, maxResults=50)
        if next_page:
            params["pageToken"] = next_page
        resp = youtube.playlistItems().list(**params).execute()
        items.extend(resp.get("items", []))
        next_page = resp.get("nextPageToken")
        if not next_page:
            break

    songs = []
    for item in items:
        snippet = item["snippet"]
        vid = snippet["resourceId"]["videoId"]
        songs.append({
            "artist": snippet.get("videoOwnerChannelTitle", "Unknown"),
            "title": snippet["title"],
            "youtube_video_id": vid,
            "youtube_url": f"https://youtu.be/{vid}",
        })

    print(f"  📋 {len(songs)}曲取得")

    # キャプション生成・動画アップロード
    caption = build_caption(songs, args.slot, {})
    scheduled_time = get_scheduled_time(args.slot)
    print(f"📅 予約投稿時刻: {scheduled_time}")

    video_id = upload_video(youtube, args.video, caption, scheduled_time)

    # Selectedプレイリスト更新
    print("📋 Selectedプレイリスト更新中...")
    update_selected_playlist(youtube, songs, args.slot)

    # 結果保存
    os.makedirs("data", exist_ok=True)
    result = {
        "date": args.date,
        "slot": args.slot,
        "video_id": video_id,
        "scheduled_time": scheduled_time,
        "song_count": len(songs),
    }
    with open(f"data/upload_{args.date}_{args.slot}.json", "w",
              encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 完了: https://youtu.be/{video_id}")


if __name__ == "__main__":
    main()
