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


def render_frame(frame_idx: int, dancer_frames: list,
                 data: dict, slot: str) -> Image.Image:
    """1フレームをレンダリング"""
    slot_cfg = SLOT_CONFIG[slot]
    songs = data["songs"]

    # ベース画像（ダンサーコマ送り）
    d_idx = (frame_idx // DANCER_INTERVAL) % len(dancer_frames)
    frame = dancer_frames[d_idx].copy().convert("RGBA")

    # テキストレイヤー
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    def fa(start, dur=20):
        return int(255 * min(1.0, max(0.0, (frame_idx - start) / dur)))

    # ── ゾーンA: プレイリストタイトル＋ジャンル（上部グレー）──
    a = fa(0)
    if a:
        # タイトル（大）
        title = slot_cfg["title_prefix"]
        font_title = gf(88, bold=True)

        # 2行に分割
        words = title.split()
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])

        y = 60
        for line in [line1, line2]:
            bb = draw.textbbox((0, 0), line, font=font_title)
            tw = bb[2] - bb[0]
            x = max(50, (W - tw) // 2)
            draw.text((x, y), line, font=font_title,
                      fill=(*WHITE_TEXT, a))
            y += 105

        # ジャンル表示
        a2 = fa(10)
        if a2:
            genre_text = " / ".join(slot_cfg["genres"])
            font_genre = gf(34)
            # 長い場合は折り返し
            bb = draw.textbbox((0, 0), genre_text, font=font_genre)
            tw = bb[2] - bb[0]
            if tw > W - 100:
                # 2行に分割
                genres = slot_cfg["genres"]
                half = len(genres) // 2
                g1 = " / ".join(genres[:half])
                g2 = " / ".join(genres[half:])
                for gi, gl in enumerate([g1, g2]):
                    bb2 = draw.textbbox((0, 0), gl, font=font_genre)
                    tw2 = bb2[2] - bb2[0]
                    x2 = max(50, (W - tw2) // 2)
                    draw.text((x2, y + gi * 48), gl,
                              font=font_genre,
                              fill=(*WHITE_TEXT, int(a2 * 0.85)))
            else:
                x2 = max(50, (W - tw) // 2)
                draw.text((x2, y + 10), genre_text,
                          font=font_genre,
                          fill=(*WHITE_TEXT, int(a2 * 0.85)))

    # ── ゾーンB: 10曲リスト（クリーム中段・左側）──
    a = fa(15)
    if a:
        font_song = gf(36, bold=False)
        font_num  = gf(36, bold=True)

        list_x = 55
        list_y = ZONE_A_END + 50
        line_h = 68  # 1曲あたりの高さ

        for i, song in enumerate(songs[:10]):
            y_pos = list_y + i * line_h
            num_text = f"{i+1:02d}."

            # 番号
            draw.text((list_x, y_pos), num_text,
                      font=font_num, fill=(*DARK_TEXT, a))

            # アーティスト - 曲名（長い場合は省略）
            song_text = f"{song['artist']} - {song['title']}"
            max_w = 560  # ダンサーと重ならない幅
            bb = draw.textbbox((0, 0), song_text, font=font_song)
            while bb[2] - bb[0] > max_w and len(song_text) > 10:
                song_text = song_text[:-4] + "..."
                bb = draw.textbbox((0, 0), song_text, font=font_song)

            draw.text((list_x + 75, y_pos), song_text,
                      font=font_song, fill=(*DARK_TEXT, a))

    # ── ゾーンC: リンク＋タグ（下部グレー）──
    a = fa(25)
    if a:
        ix = 55
        y = ZONE_B_END + 55

        # YouTubeリンク
        font_link = gf(36)
        playlist_id = os.environ.get(
            "YT_PLAYLIST_TODAY" if slot == "morning" else "YT_PLAYLIST_YESTERDAY",
            ""
        )
        link_text = f"▶ YouTube → youtu.be/playlist"
        draw.text((ix, y), link_text, font=font_link,
                  fill=(*DARK_TEXT, a))
        y += 65

        # ハッシュタグ
        a2 = fa(32)
        if a2:
            font_tag = gf(30)
            base_tags = "#musicdiscovery"
            genre_tags = " ".join([
                f"#{g.replace(' ', '').replace('(', '').replace(')', '')}"
                for g in slot_cfg["genres"]
            ])

            for tag_line in [base_tags, genre_tags]:
                draw.text((ix, y), tag_line, font=font_tag,
                          fill=(*MID_TEXT, int(a2 * 0.9)))
                y += 48

    frame.alpha_composite(layer)
    return frame.convert("RGB")


def generate_video(data: dict, slot: str, output_path: str):
    """動画を生成"""
    dancer_prefix = data["dancer_prefix"]
    bgm_file = data["bgm"]

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
        frame = render_frame(i, dancer_frames, data, slot)
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

    path = os.path.join(DATA_DIR, f"discovery_{args.date}_{args.slot}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    slot_cfg = SLOT_CONFIG[args.slot]
    slot_label = "朝" if args.slot == "morning" else "深夜"
    print(f"🎬 動画生成: {slot_cfg['title_prefix']} [{slot_label}枠]")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(
        OUTPUT_DIR,
        f"{args.date}_{args.slot}.mp4"
    )

    generate_video(data, args.slot, output_path)


if __name__ == "__main__":
    main()
