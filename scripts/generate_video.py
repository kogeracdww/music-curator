"""
STEP A-2: generate_video.py
新レイアウト対応版
・上部グレー：プレイリストタイトル＋ジャンル
・クリーム中段：10曲リスト＋ダンサー
・下部グレー：YouTubeリンク＋ハッシュタグ
"""

import os
import json
import argparse
import datetime
import subprocess
import shutil
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SLOT_CONFIG

# ── 定数 ────────────────────────────────────────────
W, H = 1080, 1920
FPS = 24
DURATION = 20
DANCER_INTERVAL = FPS // 2

ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

# ゾーン境界
ZONE_A_END = 530   # 上部グレー終わり
ZONE_B_END = 1140  # クリーム中段終わり

# カラー
DARK_TEXT   = (30, 30, 30)
MID_TEXT    = (80, 80, 80)
LIGHT_TEXT  = (130, 130, 130)
WHITE_TEXT  = (255, 255, 255)
ACCENT_LINE = (180, 180, 180)


def gf(size, bold=False):
    s = "-Bold" if bold else ""
    for p in [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{s}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{s}.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def load_dancer_frames(dancer_prefix: str) -> list:
    frames = []
    dancer_dir = os.path.join(ASSETS_DIR, "dancer")
    for i in range(1, 9):
        path = os.path.join(dancer_dir, f"{dancer_prefix}_{i:02d}.png")
        if os.path.exists(path):
            frames.append(Image.open(path).convert("RGBA"))
        else:
            print(f"  ⚠️  {path} が見つかりません")
    if not frames:
        raise FileNotFoundError(f"ダンサー画像なし: {dancer_prefix}")
    return frames


def wrap_text(text: str, font, max_width: int, draw) -> list:
    """テキストを最大幅で折り返す"""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bb = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def get_songs_from_playlist(slot: str) -> list:
    """
    TODAYプレイリストから現在の曲を取得
    （手動削除後の曲リストを反映）
    """
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
    youtube = build("youtube", "v3", credentials=creds)

    playlist_id = os.environ.get(
        "YT_PLAYLIST_TODAY" if slot == "morning" else "YT_PLAYLIST_YESTERDAY"
    )

    items = []
    next_page = None
    while True:
        params = dict(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50
        )
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
            "artist": snippet["videoOwnerChannelTitle"],
            "title": snippet["title"],
            "youtube_video_id": vid,
            "youtube_url": f"https://youtu.be/{vid}",
            "comment_ja": "",
            "comment_en": "",
            "genre": "",
        })

    print(f"  📋 プレイリストから{len(songs)}曲取得")
    return songs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--slot", required=True,
                        choices=["morning", "evening"])
    args = parser.parse_args()

    slot_cfg = SLOT_CONFIG[args.slot]
    slot_label = "朝" if args.slot == "morning" else "深夜"
    print(f"🎬 動画生成: {slot_cfg['title_prefix']} [{slot_label}枠]")

    # TODAYプレイリストから現在の曲を取得（手動削除後を反映）
    print("📋 TODAYプレイリストから曲を取得中...")
    songs = get_songs_from_playlist(args.slot)

    if not songs:
        print("⚠️  プレイリストに曲がありません。終了します。")
        return

    # discoveryデータを読み込んでdancer/bgm情報を取得
    path = os.path.join(DATA_DIR, f"discovery_{args.date}_{args.slot}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["songs"] = songs  # プレイリストの現在の曲で上書き
    else:
        # データがない場合はslot設定から取得
        data = {
            "songs": songs,
            "dancer_prefix": slot_cfg["dancer_prefix"],
            "bgm": slot_cfg["bgm"],
            "region": "",
        }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(
        OUTPUT_DIR,
        f"{args.date}_{args.slot}.mp4"
    )

 def generate_video(data: dict, slot: str, output_path: str):
    """動画を生成"""
    slot_cfg = SLOT_CONFIG[slot]
    # slot設定から固定素材を使用
    dancer_prefix = slot_cfg["dancer_prefix"]
    bgm_file = slot_cfg["bgm"]


if __name__ == "__main__":
    main()
