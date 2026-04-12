"""
STEP C-1: send_email.py
YouTube発掘リスト（朝・夜）＋X候補リストを1通のメールで送信
"""

import os
import json
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# 曜日別楽器グループ
INSTRUMENT_GROUPS = {
    0: {  # 月
        "label": "Group A",
        "instruments": [
            "Vibraphone", "Contrabass", "Balalaika", "Clarinet",
            "Bassoon", "Didgeridoo", "Taiko", "OP-1 synthesizer",
            "Cymbals", "Musical Saw"
        ]
    },
    1: {  # 火
        "label": "Group B",
        "instruments": [
            "Tambourine", "Handpan", "Snare Drum", "Viola",
            "Sitar", "Sarod", "Harmonica", "French Horn",
            "Harmonium", "Angklung"
        ]
    },
    2: {  # 水
        "label": "Group C",
        "instruments": [
            "Marimba", "Piano", "Harp", "Ocarina",
            "Pipe Organ", "Kalimba", "Celesta", "Mridangam",
            "Tongue Drum", "Roland TB-303"
        ]
    },
    3: {  # 木
        "label": "Group D",
        "instruments": [
            "Guitar", "Mandolin", "Flute", "Trombone",
            "Shakuhachi", "Tabla", "Balafon", "Timpani",
            "Xylophone", "Djembe"
        ]
    },
    4: {  # 金
        "label": "Group E",
        "instruments": [
            "Violin", "Koto", "Gayageum", "Charango",
            "Recorder", "Alphorn", "Kalimba", "Conga",
            "Akai MPC", "Theremin"
        ]
    },
    5: {  # 土
        "label": "Group F",
        "instruments": [
            "Cello", "Shamisen", "Saxophone", "Oboe",
            "Steelpan", "Bongo drum", "Bodhran", "Guitarron",
            "Roland TR-808", "Theremin"
        ]
    },
    6: {  # 日
        "label": "Group G",
        "instruments": [
            "Handpan", "Ukulele", "Erhu", "Oud",
            "Trumpet", "Tuba", "Djembe", "Glockenspiel",
            "Mellotron", "Biwa"
        ]
    },
}

# X投稿用絵文字パターン
X_EMOJIS = {
    "beginner": ["🌱✨", "🎹💫", "🎸🌟", "🎻🌱", "🥁✨"],
    "advanced": ["🔥✨", "🎵👏", "🎶💎", "🎼🌟", "✨🎵"],
    "unique":   ["🎼🔮", "✨🎵", "🎶🌀", "🎸💫", "🎹🔮"],
}


def load_discovery(date: str, slot: str) -> dict:
    path = f"data/discovery_{date}_{slot}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_x_candidates(date: str) -> dict:
    path = f"data/x_candidates_{date}.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def build_youtube_section(data: dict, slot: str) -> str:
    """YouTube発掘リストのHTMLセクションを生成"""
    songs = data["songs"]
    slot_emoji = "☕️✨" if slot == "morning" else "🌙"
    title = "Today's Morning Playlist" if slot == "morning" \
        else "Midnight playlist for tonight"

    rows = ""
    for i, s in enumerate(songs):
        rows += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:10px 8px; font-size:13px; color:#333;">
            <strong>{i+1:02d}.</strong>
            <strong>{s['artist']}</strong><br>
            <span style="color:#555;">「{s['title']}」</span><br>
            <span style="font-size:11px; color:#999;">{s.get('genre', '')}</span><br>
            <span style="font-size:12px; color:#444; margin-top:4px; display:block;">
              🇯🇵 {s.get('comment_ja', '')}<br>
              🇺🇸 {s.get('comment_en', '')}
            </span>
            <span style="font-size:11px; margin-top:4px; display:block;">
              ▶ <a href="{s.get('youtube_url', '')}" style="color:#4a90d9;">YouTube</a>
            </span>
          </td>
        </tr>
        """

    return f"""
    <div style="margin-bottom:24px;">
      <div style="background:#1a1a2e; color:#fff; padding:16px 20px;
                  border-radius:10px 10px 0 0;">
        <h2 style="margin:0; font-size:17px;">{slot_emoji} {title}</h2>
        <p style="margin:4px 0 0; color:#aaa; font-size:12px;">
          {data['region']} · {len(songs)}曲
        </p>
      </div>
      <table style="width:100%; border-collapse:collapse;
                    border:1px solid #ddd; border-top:none;">
        {rows}
      </table>
    </div>
    """


def build_x_section(x_data: dict) -> str:
    """X候補リストのHTMLセクションを生成（検索リンク方式）"""
    if not x_data:
        return ""

    group = x_data.get("group", "")
    weekday = x_data.get("weekday", 0)
    instruments = INSTRUMENT_GROUPS[weekday]["instruments"]

    rows = ""
    emoji_pool = (
        X_EMOJIS["beginner"] +
        X_EMOJIS["advanced"] +
        X_EMOJIS["unique"]
    )

    for i, instrument in enumerate(instruments):
        emoji = emoji_pool[i % len(emoji_pool)]

        # X検索URL（動画・新着・6日以内に絞る）
        query = instrument.replace(" ", "%20")
        search_url = (
            f"https://twitter.com/search?"
            f"q={query}%20filter%3Avideos"
            f"&f=live&src=typed_query"
        )

        rows += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:10px 8px; font-size:13px; color:#333;">
            <strong>{i+1:02d}.</strong>
            【{instrument}】<br>
            <span style="font-size:12px; margin-top:4px; display:block;">
              🔍 <a href="{search_url}" style="color:#1da1f2;">
                Xで「{instrument}」の演奏動画を検索
              </a>
            </span>
            <span style="font-size:11px; color:#999;">
              ※ 新着順・動画のみで表示されます
            </span>
          </td>
          <td style="padding:10px 8px; text-align:center;
                     font-size:22px; white-space:nowrap; width:80px;">
            {emoji}
          </td>
        </tr>
        """

    return f"""
    <div style="margin-bottom:24px;">
      <div style="background:#1da1f2; color:#fff; padding:16px 20px;
                  border-radius:10px 10px 0 0;">
        <h2 style="margin:0; font-size:17px;">
          𝕏 リポスト候補 · {group}
        </h2>
        <p style="margin:4px 0 0; color:#e0f0ff; font-size:12px;">
          リンクをクリック → 気に入った演奏動画を絵文字付きでリポスト
        </p>
      </div>
      <table style="width:100%; border-collapse:collapse;
                    border:1px solid #ddd; border-top:none;">
        <thead>
          <tr style="background:#f0f8ff;">
            <th style="padding:8px; text-align:left;
                       font-size:12px; color:#666;">楽器・検索リンク</th>
            <th style="padding:8px; text-align:center;
                       font-size:12px; color:#666;">絵文字</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
      <div style="padding:10px 12px; background:#f0f8ff;
                  border:1px solid #ddd; border-top:none;
                  font-size:12px; color:#666;">
        ※ 絵文字はそのままリポストのコメントにお使いください<br>
        ※ 新着順で表示されるので6日以内の投稿が上に来ます
      </div>
    </div>
    """

def build_full_email(date: str, morning_data: dict,
                     evening_data: dict, x_data: dict) -> str:
    """メール全体のHTMLを生成"""

    youtube_morning = build_youtube_section(morning_data, "morning") \
        if morning_data else ""
    youtube_evening = build_youtube_section(evening_data, "evening") \
        if evening_data else ""
    x_section = build_x_section(x_data)

    github_url = "https://github.com/kogeracdww/music-curator/actions"

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system,sans-serif;
                 max-width:640px; margin:0 auto; padding:20px;">

      <!-- ヘッダー -->
      <div style="background:#111; color:#fff; padding:20px;
                  border-radius:12px; margin-bottom:24px;">
        <h1 style="margin:0; font-size:20px;">🎵 Daily Music Report</h1>
        <p style="margin:6px 0 0; color:#aaa; font-size:13px;">{date}</p>
      </div>

      <!-- 操作ガイド -->
      <div style="background:#f9f9f9; border:1px solid #ddd;
                  border-radius:8px; padding:14px; margin-bottom:24px;
                  font-size:13px; color:#555;">
        <strong>📋 今日のタスク</strong><br>
        1️⃣ YouTube：プレイリストで流し聴き → 不要な曲を削除<br>
        2️⃣ YouTube：
        <a href="{github_url}" style="color:#4a90d9;">GitHub Actions</a>
        で朝・夜それぞれ動画生成を実行<br>
        3️⃣ X：気に入った演奏動画を絵文字付きでリポスト
      </div>

      <!-- YouTube朝枠 -->
      {youtube_morning}

      <!-- YouTube夜枠 -->
      {youtube_evening}

      <!-- X候補 -->
      {x_section}

      <!-- フッター -->
      <div style="margin-top:24px; padding:14px;
                  border-top:1px solid #eee;
                  font-size:11px; color:#999; text-align:center;">
        Underground Radar · Daily Music Discovery
      </div>

    </body>
    </html>
    """


def send_email(html: str, subject: str):
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = gmail_user

    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, gmail_user, msg.as_string())

    print(f"✅ メール送信完了: {subject}")


def main():
    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%Y-%m-%d")

    # データ読み込み
    morning_data = None
    evening_data = None

    try:
        morning_data = load_discovery(today, "morning")
    except FileNotFoundError:
        print("⚠️  朝枠データなし")

    try:
        evening_data = load_discovery(today, "evening")
    except FileNotFoundError:
        print("⚠️  夜枠データなし")

    x_data = load_x_candidates(today)
    if not x_data:
        print("⚠️  X候補データなし")

    # メール生成・送信
    html = build_full_email(today, morning_data, evening_data, x_data)
    subject = f"🎵 [{today}] Daily Music Report · YouTube + 𝕏"
    send_email(html, subject)


if __name__ == "__main__":
    main()
