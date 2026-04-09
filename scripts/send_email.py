"""
STEP C-1: send_email.py
発掘した10曲をメールで送信する
メール内に [✅ A-朝] [✅ A-夕] ボタン（リンク）を含む
"""

import os
import json
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def load_today_discovery():
    """今日の発掘結果を読み込む"""
    today = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))
    ).strftime("%Y-%m-%d")
    path = f"data/discovery_{today}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_html(data: dict) -> str:
    """メールHTMLを構築"""
    songs = data["songs"]
    date = data["date"]
    region = data["region"]

    # GitHub Actions webhook URL (後で設定)
    base_url = os.environ.get("WEBHOOK_BASE_URL", "https://your-webhook-url.com")

    rows = ""
    for i, s in enumerate(songs):
        idx = i + 1
        # ボタンリンク（クリックでGitHub Actionsをトリガー）
        btn_morning = f"{base_url}/trigger?slot=morning&idx={i}&date={date}"
        btn_evening = f"{base_url}/trigger?slot=evening&idx={i}&date={date}"

        rows += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:12px 8px; font-size:13px; color:#333;">
            <strong>{idx}.</strong> {s['artist']}<br>
            <span style="color:#666;">「{s['title']}」</span><br>
            <span style="font-size:11px; color:#999;">
              {s['country']} · {s['genre']} · 
              フォロワー約{s['followers']}人
            </span><br>
            <span style="font-size:12px; color:#444; margin-top:4px; display:block;">
              🇯🇵 {s['comment_ja']}<br>
              🇺🇸 {s['comment_en']}
            </span>
            <span style="font-size:11px; color:#888; margin-top:4px; display:block;">
              🔍 YouTube: {s['youtube_search']}
            </span>
          </td>
          <td style="padding:12px 8px; text-align:center; white-space:nowrap;">
            <a href="{btn_morning}" 
               style="display:inline-block; margin:4px; padding:8px 16px;
                      background:#1a1a2e; color:#d4af37; 
                      text-decoration:none; border-radius:6px;
                      font-size:13px; font-weight:bold;">
              ✅ A-朝
            </a><br>
            <a href="{btn_evening}"
               style="display:inline-block; margin:4px; padding:8px 16px;
                      background:#1a1a2e; color:#d4af37;
                      text-decoration:none; border-radius:6px;
                      font-size:13px; font-weight:bold;">
              ✅ A-夕
            </a>
          </td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, sans-serif; max-width:700px; margin:0 auto; padding:20px;">

      <div style="background:#1a1a2e; color:#d4af37; padding:20px; border-radius:12px; margin-bottom:20px;">
        <h1 style="margin:0; font-size:22px;">🎵 Underground Radar</h1>
        <p style="margin:8px 0 0; color:#aaa; font-size:14px;">
          {date} · {region} · {len(songs)}曲
        </p>
      </div>

      <p style="color:#555; font-size:14px;">
        今日の発掘リストです。Spotifyで流し聴きしてから、<br>
        朝枠・夕枠に使いたい曲の横のボタンを押してください。
      </p>

      <table style="width:100%; border-collapse:collapse;">
        <thead>
          <tr style="background:#f5f5f5;">
            <th style="padding:10px 8px; text-align:left; font-size:13px; color:#666;">曲情報</th>
            <th style="padding:10px 8px; text-align:center; font-size:13px; color:#666;">選択</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>

      <div style="margin-top:24px; padding:16px; background:#f9f9f9; border-radius:8px;">
        <p style="margin:0; font-size:13px; color:#666;">
          📋 YouTube TODAY プレイリストも自動更新済みです<br>
          ボタンを押すと動画生成・予約投稿が自動で始まります
        </p>
      </div>

    </body>
    </html>
    """
    return html


def send_email(html: str, date: str, region: str):
    """Gmailでメール送信"""
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎵 [{date}] Underground Radar 発掘リスト · {region}"
    msg["From"] = gmail_user
    msg["To"] = gmail_user  # 自分自身に送信

    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, gmail_user, msg.as_string())

    print(f"✅ メール送信完了 → {gmail_user}")


def main():
    data = load_today_discovery()
    print(f"📧 メール生成中... {data['date']} / {data['region']}")
    html = build_html(data)
    send_email(html, data["date"], data["region"])


if __name__ == "__main__":
    main()
