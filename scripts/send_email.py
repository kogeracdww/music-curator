"""
STEP C-1: send_email.py
発掘した曲をメールで送信する（朝・夜の2通）
"""

import os
import json
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def load_discovery(date: str, slot: str) -> dict:
    """発掘結果を読み込む"""
    path = f"data/discovery_{date}_{slot}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_html(data: dict, slot: str) -> str:
    """メールHTMLを構築"""
    songs = data["songs"]
    date = data["date"]
    region = data["region"]
    slot_label = "🌅 朝枠" if slot == "morning" else "🌙 深夜枠"
    title = "Today's Morning Playlist" if slot == "morning" else "Midnight playlist for tonight"

    rows = ""
    for i, s in enumerate(songs):
        rows += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:10px 8px; font-size:13px; color:#333;">
            <strong>{i+1:02d}.</strong> {s['artist']}<br>
            <span style="color:#666;">「{s['title']}」</span><br>
            <span style="font-size:11px; color:#999;">
              {s.get('genre', '')}
            </span><br>
            <span style="font-size:12px; color:#444; margin-top:4px; display:block;">
              🇯🇵 {s.get('comment_ja', '')}<br>
              🇺🇸 {s.get('comment_en', '')}
            </span>
            <span style="font-size:11px; color:#4a90d9; margin-top:4px; display:block;">
              ▶ <a href="{s.get('youtube_url', '')}">YouTube</a>
            </span>
          </td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, sans-serif; max-width:600px; margin:0 auto; padding:20px;">

      <div style="background:#1a1a2e; color:#fff; padding:20px; border-radius:12px; margin-bottom:20px;">
        <h1 style="margin:0; font-size:20px;">{slot_label} {title}</h1>
        <p style="margin:8px 0 0; color:#aaa; font-size:13px;">
          {date} · {region} · {len(songs)}曲
        </p>
      </div>

      <p style="color:#555; font-size:13px;">
        TODAYプレイリストで流し聴きして、<br>
        GitHubのActionsから動画生成を実行してください。<br>
        <strong>Actions → Generate and Upload Video → Run workflow</strong><br>
        date: {date} / slot: {slot}
      </p>

      <table style="width:100%; border-collapse:collapse;">
        <thead>
          <tr style="background:#f5f5f5;">
            <th style="padding:10px 8px; text-align:left; font-size:12px; color:#666;">曲情報</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>

      <div style="margin-top:20px; padding:14px; background:#f9f9f9; border-radius:8px;">
        <p style="margin:0; font-size:12px; color:#666;">
          📋 TODAYプレイリストは自動更新済みです<br>
          ▶ <a href="https://github.com/kogeracdww/music-curator/actions">GitHub Actions を開く</a>
        </p>
      </div>

    </body>
    </html>
    """
    return html


def send_email(html: str, subject: str):
    """Gmailでメール送信"""
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

    for slot in ["morning", "evening"]:
        try:
            data = load_discovery(today, slot)
            slot_label = "朝枠" if slot == "morning" else "深夜枠"
            title = "Today's Morning Playlist" if slot == "morning" \
                else "Midnight playlist for tonight"

            html = build_html(data, slot)
            subject = f"🎵 [{today}] {slot_label} · {title}"
            send_email(html, subject)

        except FileNotFoundError:
            print(f"⚠️  {slot}のデータが見つかりません。スキップします。")
        except Exception as e:
            print(f"⚠️  {slot}のメール送信失敗: {e}")


if __name__ == "__main__":
    main()
