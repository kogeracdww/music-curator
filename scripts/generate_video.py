"""
STEP A-2: generate_video.py
選ばれた曲の情報から縦動画(1080x1920)を生成する

使い方:
  python generate_video.py --date 2024-11-25 --idx 3 --slot morning
"""

import os
import json
import argparse
import datetime
import subprocess
import shutil
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# ── 定数 ────────────────────────────────────────────
W, H = 1080, 1920
FPS = 24
DURATION = 20  # 秒
DANCER_INTERVAL = FPS // 2  # 0.5秒ごとにコマ送り

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
DATA_DIR   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")

# カラー (shortM系の配色に合わせる)
GRAY_TOP    = (204, 204, 204)  # 上部グレー
CREAM_MID   = (248, 243, 239)  # クリーム中段
GRAY_BOT    = (204, 204, 204)  # 下部グレー
DARK_TEXT   = (30, 30, 30)
MID_TEXT    = (80, 80, 80)
LIGHT_TEXT  = (130, 130, 130)
WHITE_TEXT  = (255, 255, 255)
ACCENT_LINE = (160, 160, 160)

# ゾーン境界 (ピクセル)
ZONE_A_END = 530   # 上部グレー終わり
ZONE_B_END = 1140  # クリーム中段終わり


def gf(size, bold=False):
    """フォント取得"""
    s = "-Bold" if bold else ""
    for p in [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{s}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{s}.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def load_dancer_frames(dancer_prefix: str) -> list:
    """ダンサー画像を8枚読み込む"""
    frames = []
    dancer_dir = os.path.join(ASSETS_DIR, "dancer")
    for i in range(1, 9):
        path = os.path.join(dancer_dir, f"{dancer_prefix}_{i:02d}.png")
        if os.path.exists(path):
            frames.append(Image.open(path).convert("RGBA"))
        else:
            print(f"  ⚠️  {path} が見つかりません。スキップします。")
    if not frames:
        raise FileNotFoundError(f"ダンサー画像が見つかりません: {dancer_prefix}")
    return frames


def render_frame(frame_idx: int, dancer_frames: list, base_img: Image.Image, song: dict) -> Image.Image:
    """1フレームをレンダリング"""
    frame = base_img.copy().convert("RGBA")

    # ── ダンサー（コマ送り）──
    d_idx = (frame_idx // DANCER_INTERVAL) % len(dancer_frames)
    dancer = dancer_frames[d_idx]
    # ダンサーはそのままのサイズで配置（元画像に既に配置済み）
    # base_imgがshortMシリーズなのでダンサーは既に含まれている
    # → ダンサーフレームをそのままbase_imgに差し込む

    # shortM系はダンサーが右寄りに配置された状態の画像なので
    # フレームをそのままbase画像として使う
    dancer_resized = dancer.resize((W, H), Image.LANCZOS)
    frame = dancer_resized.copy()

    # ── テキストレイヤー ──
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # フェードイン
    def fa(start, dur=20):
        return int(255 * min(1.0, max(0.0, (frame_idx - start) / dur)))

    # ── ゾーンA: コメント (上部グレー・英語のみ) ──
    a = fa(5)
    if a:
        comment_en = song.get("comment_en", "")
        font_en = gf(76, bold=True)

        words = comment_en.split()
        mid = len(words) // 2
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])

        for idx_line, line in enumerate([line1, line2]):
            if not line:
                continue
            bb = draw.textbbox((0, 0), line, font=font_en)
            tw = bb[2] - bb[0]
            x = max(60, (W - tw) // 2)
            y_pos = 100 + idx_line * 110
            draw.text((x, y_pos), line, font=font_en,
                      fill=(*WHITE_TEXT, a))

    # ── ゾーンB: ジャケット画像エリア (クリーム) ──
    # ジャケットはプレースホルダー（将来はURL取得）
    a = fa(10)
    if a:
        jx, jy, js = 55, ZONE_A_END + 75, 340
        draw.rectangle([(jx, jy), (jx + js, jy + js)],
                       fill=(20, 20, 20, int(a * 0.9)))
        # ジャケット内に曲名略記
        jfont = gf(24)
        draw.text((jx + js // 2, jy + js // 2),
                  song.get("title", "")[:16],
                  font=jfont, fill=(*WHITE_TEXT, int(a * 0.6)), anchor="mm")

    # ── ゾーンC: 曲情報 (下部グレー) ──
    ix = 65
    y = ZONE_B_END + 55

    a = fa(15)
    if a:
        draw.text((ix, y),
                  f"♪  {song['artist']}  -  {song['title']}",
                  font=gf(40, bold=True), fill=(*DARK_TEXT, a))
        y += 58

        draw.text((ix, y),
                  f"📍 {song['country']}  ·  {song['genre']}",
                  font=gf(34), fill=(*MID_TEXT, a))
        y += 62

    a = fa(22)
    if a:
        draw.line([(ix, y), (W - ix, y)], fill=(*ACCENT_LINE, int(a * 0.7)), width=2)
        y += 28

        draw.text((ix, y), "🎧 Listen to this song:",
                  font=gf(32), fill=(*MID_TEXT, a))
        y += 50

        # 配信サービス（絵文字＋テキスト）
        services = [
            ("▶", "YouTube"),
            ("♪", "Spotify"),
            ("🍎", "Apple Music"),
            ("🛒", "Tower Records"),
        ]
        for icon, name in services:
            draw.text((ix + 8, y), f"{icon}  {name}",
                      font=gf(30), fill=(*DARK_TEXT, a))
            y += 46

    a = fa(35)
    if a:
        y += 12
        handle = song.get("handle", "")
        if handle:
            draw.text((ix, y), handle, font=gf(32),
                      fill=(60, 100, 180, a))
            y += 52

        draw.line([(ix, y), (W - ix, y)],
                  fill=(*ACCENT_LINE, int(a * 0.6)), width=2)
        y += 26

        app_url = os.environ.get("APP_URL", "yourapp.com")
        draw.text((ix, y), f"🔗  {app_url}",
                  font=gf(30), fill=(*DARK_TEXT, a))
        y += 50

        # ハッシュタグ
        country_tag = song.get("country", "").replace(" ", "")
        genre_tag = song.get("genre", "").replace(" ", "")
        hashtags = f"#musicdiscovery #unknownartist #{country_tag} #{genre_tag}"
        draw.text((ix, y), hashtags, font=gf(26),
                  fill=(*LIGHT_TEXT, int(a * 0.85)))

    frame.alpha_composite(layer)
    return frame.convert("RGB")


def generate_video(song: dict, dancer_prefix: str, bgm_file: str, output_path: str):
    """動画を生成"""
    frames_dir = output_path.replace(".mp4", "_frames")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"💃 ダンサー読み込み: {dancer_prefix}")
    dancer_frames = load_dancer_frames(dancer_prefix)

    # ベース画像（1枚目を使用）
    dancer_dir = os.path.join(ASSETS_DIR, "dancer")
    base_path = os.path.join(dancer_dir, f"{dancer_prefix}_01.png")
    base_img = Image.open(base_path).convert("RGBA")

    total = FPS * DURATION
    print(f"🎬 フレーム生成: {total}枚")

    for i in range(total):
        if i % (FPS * 5) == 0:
            print(f"  {i}/{total} ({i * 100 // total}%)")
        frame = render_frame(i, dancer_frames, base_img, song)
        frame.save(os.path.join(frames_dir, f"f_{i:05d}.png"))

    # BGM合成
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
        print(f"  ⚠️  BGMファイルが見つかりません。無音で生成します。")
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
    parser.add_argument("--date", required=True, help="対象日 (YYYY-MM-DD)")
    parser.add_argument("--idx",  required=True, type=int, help="曲のインデックス (0始まり)")
    parser.add_argument("--slot", required=True, choices=["morning", "evening"], help="投稿枠")
    args = parser.parse_args()

    # 発掘データ読み込み
    path = os.path.join(DATA_DIR, f"discovery_{args.date}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    song = data["songs"][args.idx]
    dancer_prefix = data["dancer_prefix"]
    bgm_file = data["bgm"]

    slot_label = "朝" if args.slot == "morning" else "夕"
    print(f"🎬 動画生成開始: {song['artist']} - {song['title']} [{slot_label}枠]")

    output_path = os.path.join(
        OUTPUT_DIR,
        f"{args.date}_{args.slot}_{song['artist'].replace(' ', '_')}.mp4"
    )

    generate_video(song, dancer_prefix, bgm_file, output_path)


if __name__ == "__main__":
    main()
