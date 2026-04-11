"""
STEP A-2: generate_video.py
TODAYプレイリストの現在の曲（手動削除後）で動画生成
朝：shortM_01 + bgm_01.mp3
夜：shortM_02 + bgm_02.mp3
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

ZONE_A_END = 530
ZONE_B_END = 1140

DARK_TEXT  = (30, 30, 30)
MID_TEXT   = (80, 80, 80)
WHITE_TEXT = (255, 255, 255)


def gf(size, bold=False):
    s = "-Bold" if bold else ""
    for p in [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{s}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{s}.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def get_songs_from_playlist(slot: str) -> list:
    """TODAYプレイリストから現在の曲を取得（手動削除後を反映）"""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

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
    youtube = build("youtube", "v3", credentials=creds)

    playlist_id = os.environ.get(
        "YT_PLAYLIST_TODAY" if slot == "morning" else "YT_PLAYLIST_YESTERDAY",
        ""
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
            "artist": snippet.get("videoOwnerChannelTitle", "Unknown"),
            "title": snippet["title"],
            "youtube_video_id": vid,
            "youtube_url": f"https://youtu.be/{vid}",
            "comment_ja": "",
            "comment_en": "",
            "genre": "",
        })

    print(f"  📋 プレイリストから{len(songs)}曲取得")
    return songs


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


def render_frame(frame_idx: int, dancer_frames: list,
                 songs: list, slot: str) -> Image.Image:
    slot_cfg = SLOT_CONFIG[slot]

    d_idx = (frame_idx // DANCER_INTERVAL) % len(dancer_frames)
    frame = dancer_frames[d_idx].copy().convert("RGBA")

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    def fa(start, dur=20):
        return int(255 * min(1.0, max(0.0, (frame_idx - start) / dur)))

    # ゾーンA: タイトル＋ジャンル
    a = fa(0)
    if a:
        title = slot_cfg["title_prefix"]
        font_title = gf(88, bold=True)
        words = title.split()
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]
        y = 160
        for line in lines:
            bb = draw.textbbox((0, 0), line, font=font_title)
            tw = bb[2] - bb[0]
            x = max(50, (W - tw) // 2)
            draw.text((x, y), line, font=font_title,
                      fill=(*WHITE_TEXT, a))
            y += 105

        a2 = fa(10)
        if a2:
            genres = slot_cfg["genres"]
            half = len(genres) // 2
            genre_lines = [
                " / ".join(genres[:half]),
                " / ".join(genres[half:]),
            ]
            font_genre = gf(34)
            for gl in genre_lines:
                bb = draw.textbbox((0, 0), gl, font=font_genre)
                tw = bb[2] - bb[0]
                x = max(50, (W - tw) // 2)
                draw.text((x, y), gl, font=font_genre,
                          fill=(*WHITE_TEXT, int(a2 * 0.85)))
                y += 48

    # ゾーンB: 10曲リスト
    a = fa(15)
    if a:
        font_num  = gf(36, bold=True)
        font_song = gf(36)
        list_x = 55
        list_y = ZONE_A_END + 50
        line_h = 68

        for i, song in enumerate(songs[:10]):
            y_pos = list_y + i * line_h
            draw.text((list_x, y_pos), f"{i+1:02d}.",
                      font=font_num, fill=(*DARK_TEXT, a))

            song_text = f"{song['artist']} - {song['title']}"
            max_w = 560
            bb = draw.textbbox((0, 0), song_text, font=font_song)
            while bb[2] - bb[0] > max_w and len(song_text) > 10:
                song_text = song_text[:-4] + "..."
                bb = draw.textbbox((0, 0), song_text, font=font_song)

            draw.text((list_x + 75, y_pos), song_text,
                      font=font_song, fill=(*DARK_TEXT, a))

    # ゾーンC: リンク＋タグ
    a = fa(25)
    if a:
        ix = 55
        y = ZONE_B_END + 55

        draw.text((ix, y), "▶ YouTube → youtu.be/playlist",
                  font=gf(36), fill=(*DARK_TEXT, a))
        y += 65

        a2 = fa(32)
        if a2:
            font_tag = gf(30)
            draw.text((ix, y), "#musicdiscovery",
                      font=font_tag, fill=(*MID_TEXT, int(a2 * 0.9)))
            y += 48

            for genre in slot_cfg["genres"]:
                tag = "#" + genre.replace(" ", "").replace("(", "").replace(")", "").replace("-", "").lower()
                draw.text((ix, y), tag,
                          font=font_tag, fill=(*MID_TEXT, int(a2 * 0.9)))
                y += 44

    frame.alpha_composite(layer)
    return frame.convert("RGB")


def generate_video(songs: list, slot: str, output_path: str):
    slot_cfg = SLOT_CONFIG[slot]
    dancer_prefix = slot_cfg["dancer_prefix"]
    bgm_file = slot_cfg["bgm"]

    frames_dir = output_path.replace(".mp4", "_frames")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"💃 ダンサー読み込み: {dancer_prefix}")
    dancer_frames = load_dancer_frames(dancer_prefix)

    total = FPS * DURATION
    print(f"🎬 フレーム生成: {total}枚")

    for i in range(total):
        if i % (FPS * 5) == 0:
            print(f"  {i}/{total} ({i * 100 // total}%)")
        frame = render_frame(i, dancer_frames, songs, slot)
        frame.save(os.path.join(frames_dir, f"f_{i:05d}.png"))

    bgm_path = os.path.join(ASSETS_DIR, "bgm", bgm_file)
    print(f"🎵 BGM合成: {bgm_file}")

    if os.path.exists(bgm_path):
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", os.path.join(frames_dir, "f_%05d.png"),
            "-i", bgm_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-crf", "20",
            "-preset", "fast",
            "-shortest",
            output_path
        ]
    else:
        print("  ⚠️  BGMなし・無音で生成")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", os.path.join(frames_dir, "f_%05d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "20",
            "-preset", "fast",
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    shutil.rmtree(frames_dir)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpegエラー: {result.stderr[-500:]}")

    print(f"✅ 動画生成完了: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--slot", required=True,
                        choices=["morning", "evening"])
    args = parser.parse_args()

    slot_cfg = SLOT_CONFIG[args.slot]
    slot_label = "朝" if args.slot == "morning" else "深夜"
    print(f"🎬 動画生成: {slot_cfg['title_prefix']} [{slot_label}枠]")

    # TODAYプレイリストから現在の曲を取得
    print("📋 TODAYプレイリストから曲を取得中...")
    songs = get_songs_from_playlist(args.slot)

    if not songs:
        print("⚠️  プレイリストに曲がありません。終了します。")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(
        OUTPUT_DIR,
        f"{args.date}_{args.slot}.mp4"
    )

    generate_video(songs, args.slot, output_path)


if __name__ == "__main__":
    main()
