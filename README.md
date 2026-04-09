# music-curator

Underground Radar (チャンネルA) の自動化パイプライン

## ディレクトリ構成

```
music-curator/
├── .github/
│   └── workflows/
│       ├── daily.yml           # 毎朝7時: 発掘→メール送信
│       └── generate_video.yml  # ボタン押下: 動画生成→YouTube投稿
├── scripts/
│   ├── discover.py             # Claude APIで10曲発掘
│   ├── send_email.py           # 候補リストをメール送信
│   ├── generate_video.py       # 縦動画(1080x1920)生成
│   └── youtube_upload.py       # YouTube予約投稿・プレイリスト更新
├── assets/
│   ├── bgm/                    # BGM音源 (bgm_01.mp3〜bgm_07.mp3)
│   └── dancer/                 # 線画PNG (shortM_01_01.png〜shortM_07_08.png)
├── data/                       # 発掘結果JSON (自動生成)
├── output/                     # 生成動画 (自動生成)
├── config.py                   # 曜日別設定
└── requirements.txt
```

## 1日の流れ

```
毎朝7時 (GitHub Actions自動実行)
  ↓
discover.py: Claude APIで10曲発掘
  ↓
send_email.py: 候補リストをメールで送信
  ↓
[あなたの作業: 5〜10分]
メールを確認 → 流し聴き → A-朝/A-夕ボタンを2回押す
  ↓
generate_video.py: 動画生成 (1080x1920・20秒)
  ↓
youtube_upload.py: YouTube予約投稿 (朝8時・夜19時)
                   SELECTEDプレイリストに追加
```

## GitHub Secrets 一覧

| Secret名 | 内容 |
|---------|------|
| ANTHROPIC_API_KEY | Anthropic APIキー |
| GMAIL_USER | Gmailアドレス |
| GMAIL_APP_PASSWORD | Gmailアプリパスワード |
| YOUTUBE_CLIENT_SECRET | Google OAuth JSONの中身 |
| YOUTUBE_REFRESH_TOKEN | YouTubeリフレッシュトークン |
| YT_PLAYLIST_TODAY | TODAYプレイリストID |
| YT_PLAYLIST_YESTERDAY | YESTERDAYプレイリストID |
| YT_PLAYLIST_SELECTED_A | SELECTED Aプレイリストvrhvrhvrhvrhvrhcvrhc |
| YT_PLAYLIST_SELECTED_B | SELECTED Bプレイリストvrhcvrhcvrhcvrhc |
| APP_URL | アプリ・サービスURL |
| WEBHOOK_BASE_URL | メールボタントリガー用URL |

## 曜日別設定

| 曜日 | リージョン | BGM | 線画 |
|-----|---------|-----|-----|
| 月 | 英語圏 | bgm_01.mp3 | shortM_01 |
| 火 | 東南アジア | bgm_02.mp3 | shortM_02 |
| 水 | 日本 | bgm_03.mp3 | shortM_03 |
| 木 | 東欧/南米/中米/アフリカ | bgm_04.mp3 | shortM_04 |
| 金 | 西欧・北米 | bgm_05.mp3 | shortM_05 |
| 土 | 韓国 | bgm_06.mp3 | shortM_06 |
| 日 | 西欧/北米/東南アジア | bgm_07.mp3 | shortM_07 |

## assets のアップロード方法

BGMと線画はGitHubにpushしてください:

```bash
git clone https://github.com/kogeracdww/music-curator.git
cd music-curator
# assets/bgm/ にbgm_01.mp3〜bgm_07.mp3を配置
# assets/dancer/ にshortM_01_01.png〜shortM_07_08.pngを配置
git add assets/
git commit -m "Add assets"
git push
```
