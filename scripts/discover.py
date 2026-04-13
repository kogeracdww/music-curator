"""
STEP B-1: discover.py
ラジオ局API/RSSから曲を収集して朝・夜のプレイリストを作る

ソース：
  KEXP API        → 欧米インディー全般
  Korean Indie RSS → K-Indie
  A-indie RSS      → 日本・アジア全般
  ParaPOP RSS      → 東南アジア
  FIP RSS          → ジャズ・ワールド・欧州
"""

import os
import json
import datetime
import time
import re
import requests
import xml.etree.ElementTree as ET
import anthropic
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import WEEKDAY_CONFIG, SLOT_CONFIG

JST = datetime.timezone(datetime.timedelta(hours=9))


def get_today_config():
    weekday = datetime.datetime.now(JST).weekday()
    return weekday, WEEKDAY_CONFIG[weekday]


def get_youtube_client():
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
    return build("youtube", "v3", credentials=creds)


def get_spotify_token() -> str:
    """Spotify APIのアクセストークンを取得"""
    import base64
    client_id     = os.environ["SPOTIFY_CLIENT_ID"]
    client_secret = os.environ["SPOTIFY_CLIENT_SECRET"]

    credentials = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode()

    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
        timeout=10
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise ValueError(f"Spotifyトークン取得失敗: {resp.text}")
    print(f"  ✅ Spotify認証成功")
    return token


def search_spotify(token: str, artist: str, title: str) -> dict:
    """Spotifyで曲を検索してTrack情報を取得"""
    try:
        query = f"artist:{artist} track:{title}"
        resp = requests.get(
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query, "type": "track", "limit": 1},
            timeout=10
        )
        items = resp.json().get("tracks", {}).get("items", [])
        if not items:
            # シンプルなクエリで再検索
            resp2 = requests.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": f"{artist} {title}", "type": "track", "limit": 1},
                timeout=10
            )
            items = resp2.json().get("tracks", {}).get("items", [])

        if not items:
            return {}

        track = items[0]
        return {
            "spotify_id":      track["id"],
            "spotify_url":     track["external_urls"]["spotify"],
            "popularity":      track["popularity"],
            "artist_verified": track["artists"][0]["name"],
            "title_verified":  track["name"],
        }
    except Exception as e:
        print(f"    ⚠️ Spotify検索失敗: {artist} - {e}")
        return {}


def get_audio_features(token: str, spotify_id: str) -> dict:
    """
    Spotify Audio Featuresを取得
    valence（多幸感）・energy・tempo で朝・夜判定に使用
    """
    try:
        resp = requests.get(
            f"https://api.spotify.com/v1/audio-features/{spotify_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        data = resp.json()
        return {
            "valence":      data.get("valence", 0.5),
            "energy":       data.get("energy", 0.5),
            "tempo":        data.get("tempo", 100),
            "acousticness": data.get("acousticness", 0.5),
        }
    except Exception as e:
        print(f"    ⚠️ Audio Features取得失敗: {e}")
        return {}


# ── ソース別収集 ──────────────────────────────────────

def fetch_kexp(hours: int = 24) -> list:
    """KEXP APIから過去N時間の曲を取得"""
    since = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(hours=hours)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    songs = []
    url = (
        f"https://api.kexp.org/v2/plays/"
        f"?play_type=trackplay&airdate_after={since}&limit=200"
    )
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        for item in resp.json().get("results", []):
            artist = item.get("artist", "").strip()
            song   = item.get("song", "").strip()
            if artist and song:
                songs.append({
                    "artist": artist,
                    "title":  song,
                    "album":  item.get("album", ""),
                    "source": "KEXP",
                })
        print(f"  KEXP: {len(songs)}曲")
    except Exception as e:
        print(f"  ⚠️ KEXP失敗: {e}")
    return songs


def fetch_rss(url: str, source_name: str) -> list:
    """
    汎用RSSパーサー
    タイトルから「Artist - Song」または「Song / Artist」を抽出
    """
    songs = []
    try:
        resp = requests.get(url, timeout=15,
                            headers={"User-Agent": "MusicCuratorBot/1.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for item in root.findall(".//item"):
            raw_title = item.findtext("title", "").strip()
            if not raw_title:
                continue

            # 「Artist - Song」形式
            if " - " in raw_title:
                parts = raw_title.split(" - ", 1)
                artist = parts[0].strip()
                title  = parts[1].strip()
            # 「Song / Artist」形式
            elif " / " in raw_title:
                parts = raw_title.split(" / ", 1)
                title  = parts[0].strip()
                artist = parts[1].strip()
            else:
                # タイトルのみ判別できない場合はskip
                continue

            if artist and title:
                songs.append({
                    "artist": artist,
                    "title":  title,
                    "album":  "",
                    "source": source_name,
                })

        print(f"  {source_name}: {len(songs)}曲")
    except Exception as e:
        print(f"  ⚠️ {source_name}失敗: {e}")
    return songs


def fetch_all_sources(hours: int = 24) -> list:
    """全ソースから収集・重複除去"""
    all_songs = []

    # KEXP API
    all_songs.extend(fetch_kexp(hours=hours))

    # RSS ソース
    rss_sources = [
        ("https://www.koreanindie.com/feed/",               "Korean Indie"),
        ("https://a-indie.com/feed",                         "A-indie"),
        ("https://parapop.net/feed",                         "ParaPOP"),
        ("https://www.radiofrance.fr/fip/rss",               "FIP"),
    ]
    for url, name in rss_sources:
        all_songs.extend(fetch_rss(url, name))

    # 重複除去（artist+titleで判定）
    seen = set()
    unique = []
    for s in all_songs:
        key = f"{s['artist'].lower()}_{s['title'].lower()}"
        if key not in seen:
            seen.add(key)
            unique.append(s)

    print(f"  統合後: {len(unique)}曲（重複除去済み）")
    return unique


# ── Claude APIで振り分け＋コメント生成 ────────────────

def classify_and_comment(songs: list) -> dict:
    """朝・夜に振り分けてコメント生成"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    morning_genres = " / ".join(SLOT_CONFIG["morning"]["genres"])
    evening_genres = " / ".join(SLOT_CONFIG["evening"]["genres"])

    songs_text = "\n".join([
        f"{i+1}. {s['artist']} - {s['title']} [{s['source']}]"
        f"{' [valence:{:.2f} energy:{:.2f}]'.format(s['valence'], s['energy']) if 'valence' in s else ''}"
        for i, s in enumerate(songs)
    ])

    prompt = f"""
あなたは音楽キュレーターです。
世界の厳選ラジオ局（KEXP・Korean Indie・A-indie・ParaPOP・FIP）が
紹介した曲を朝用・深夜用に振り分けてください。

【朝用の雰囲気・ジャンル】
{morning_genres}
少しポジティブ・上質・爽やか・母国語以外の歌詞が望ましい

【深夜用の雰囲気・ジャンル】
{evening_genres}
チルアウト・深い・落ち着いた・作業に合う

【曲リスト】
{songs_text}

【出力形式】
必ずJSON形式のみで返してください。前後に余計なテキスト不要。

{{
  "morning": [
    {{
      "index": 1,
      "comment_en": "One-line comment under 60 chars"
    }}
  ],
  "evening": [
    {{
      "index": 2,
      "comment_en": "One-line comment under 60 chars"
    }}
  ]
}}

朝・夜それぞれ必ず15曲以上を選んでください。
どちらにも当てはまらない曲はより近い方に入れてください。
曲が少ない場合は全曲をどちらかに振り分けてください。
"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)

    classified = {"morning": [], "evening": []}
    for slot in ["morning", "evening"]:
        for item in result.get(slot, []):
            idx = item["index"] - 1
            if 0 <= idx < len(songs):
                song = songs[idx].copy()
                song["comment_en"] = item.get("comment_en", "")
                classified[slot].append(song)

    return classified


# ── YouTube検索・長さフィルタリング ──────────────────

def parse_duration(duration: str) -> int:
    """ISO 8601 (PT3M45S) → 秒"""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return 0
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    return h * 3600 + m * 60 + s


def search_youtube_video(youtube, artist: str, title: str) -> dict:
    """
    YouTube検索 → 長さフィルタ
    1曲につき1回のみ検索（クォータ節約）
    ショート(60秒未満)・長尺(600秒以上)を除外
    """
    try:
        query = f"{artist} {title}"
        resp = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=5,
            videoCategoryId="10",
        ).execute()

        video_ids = [
            item["id"]["videoId"]
            for item in resp.get("items", [])
        ]
        if not video_ids:
            return {}

        details = youtube.videos().list(
            part="contentDetails",
            id=",".join(video_ids)
        ).execute()

        for item in details.get("items", []):
            sec = parse_duration(
                item["contentDetails"]["duration"]
            )
            if 60 <= sec < 600:
                vid = item["id"]
                return {
                    "youtube_video_id": vid,
                    "youtube_url":      f"https://youtu.be/{vid}",
                    "duration_seconds": sec,
                }

    except Exception as e:
        print(f"    ⚠️ YouTube検索失敗: {artist} - {e}")

    return {}
  
  
def enrich_with_spotify(songs: list) -> list:
    """
    SpotifyでTrack情報・Audio Featuresを付加
    valence・energyで朝・夜の事前振り分けに使用
    """
    try:
        token = get_spotify_token()
    except Exception as e:
        print(f"  ⚠️ Spotify認証失敗: {e}")
        return songs

    enriched = []
    for song in songs:
        sp = search_spotify(token, song["artist"], song["title"])
        if sp:
            song.update(sp)
            # Audio Features取得
            af = get_audio_features(token, sp["spotify_id"])
            song.update(af)
            # Spotifyで確認できたアーティスト名・曲名で上書き（精度向上）
            song["artist"] = sp["artist_verified"]
            song["title"]  = sp["title_verified"]

        enriched.append(song)
        time.sleep(0.1)

    found = sum(1 for s in enriched if "spotify_id" in s)
    print(f"  Spotify: {found}/{len(enriched)}曲マッチ")
    return enriched

def enrich_with_youtube(youtube, songs: list,
                        n: int = 10, max_attempts: int = 20) -> list:
    """各曲にYouTube情報を付加・フィルタリング"""
    enriched = []
    for song in songs[:max_attempts]:
        if len(enriched) >= n:
            break
        yt = search_youtube_video(youtube, song["artist"], song["title"])
        if not yt:
            print(f"    スキップ: {song['artist']} - {song['title']}")
            continue
        song.update(yt)
        enriched.append(song)
        time.sleep(0.3)
    return enriched


# ── プレイリスト更新 ──────────────────────────────────

def update_today_playlist(youtube, songs: list, slot: str):
    playlist_id = os.environ.get(
        "YT_PLAYLIST_TODAY" if slot == "morning"
        else "YT_PLAYLIST_YESTERDAY", ""
    )
    if not playlist_id:
        print("  ⚠️ プレイリストIDなし")
        return

    # クリア
    try:
        existing = youtube.playlistItems().list(
            part="id", playlistId=playlist_id, maxResults=50
        ).execute()
        for item in existing.get("items", []):
            youtube.playlistItems().delete(id=item["id"]).execute()
        print("  🗑 クリア完了")
    except Exception as e:
        print(f"  ⚠️ クリア失敗: {e}")

    # 追加
    added = 0
    for song in songs:
        vid = song.get("youtube_video_id", "")
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
                    }
                }}
            ).execute()
            added += 1
        except Exception as e:
            print(f"  ⚠️ 追加失敗: {song['title']} - {e}")
    print(f"  ✅ {added}曲追加")


# ── 保存 ──────────────────────────────────────────────

def save_results(songs: list, slot: str, weekday: int, config: dict):
    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    result = {
        "date":          today,
        "slot":          slot,
        "weekday":       weekday,
        "region":        config["region"],
        "bgm":           config["bgm"],
        "dancer_prefix": config["dancer_prefix"],
        "songs":         songs,
    }
    os.makedirs("data", exist_ok=True)
    path = f"data/discovery_{today}_{slot}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  ✅ 保存: {len(songs)}曲 → {path}")


# ── X候補データ生成 ───────────────────────────────────

INSTRUMENT_GROUPS = {
    0: {"label": "Group A", "instruments": ["Vibraphone","Contrabass","Balalaika","Clarinet","Bassoon","Didgeridoo","Taiko","OP-1 synthesizer","Cymbals","Musical Saw"]},
    1: {"label": "Group B", "instruments": ["Tambourine","Handpan","Snare Drum","Viola","Sitar","Sarod","Harmonica","French Horn","Harmonium","Angklung"]},
    2: {"label": "Group C", "instruments": ["Marimba","Piano","Harp","Ocarina","Pipe Organ","Kalimba","Celesta","Mridangam","Tongue Drum","Roland TB-303"]},
    3: {"label": "Group D", "instruments": ["Guitar","Mandolin","Flute","Trombone","Shakuhachi","Tabla","Balafon","Timpani","Xylophone","Djembe"]},
    4: {"label": "Group E", "instruments": ["Violin","Koto","Gayageum","Charango","Recorder","Alphorn","Kalimba","Conga","Akai MPC","Theremin"]},
    5: {"label": "Group F", "instruments": ["Cello","Shamisen","Saxophone","Oboe","Steelpan","Bongo drum","Bodhran","Guitarron","Roland TR-808","Theremin"]},
    6: {"label": "Group G", "instruments": ["Handpan","Ukulele","Erhu","Oud","Trumpet","Tuba","Djembe","Glockenspiel","Mellotron","Biwa"]},
}


def save_x_candidates(weekday: int):
    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    x_data = {
        "date":       today,
        "weekday":    weekday,
        "group":      INSTRUMENT_GROUPS[weekday]["label"],
        "candidates": [],
    }
    os.makedirs("data", exist_ok=True)
    with open(f"data/x_candidates_{today}.json", "w", encoding="utf-8") as f:
        json.dump(x_data, f, ensure_ascii=False, indent=2)


# ── メイン ────────────────────────────────────────────

def main():
    weekday, config = get_today_config()
    print(f"📅 今日: {config['label']} / {config['region']}")

    youtube = get_youtube_client()

    # 全ソースから収集
    print("\n📻 ラジオ局・メディアから収集中...")
    raw_songs = fetch_all_sources(hours=72)

    if not raw_songs:
        print("⚠️ 曲が取得できませんでした")
        return

    # 30曲に絞ってからClaudeに渡す（クォータ節約）
    import random
    if len(raw_songs) > 30:
        raw_songs = random.sample(raw_songs, 30)
        print(f"  → 30曲にランダム絞り込み")

    # Spotifyで曲情報・Audio Featuresを付加
    print("\n🎵 Spotifyで曲情報を取得中...")
    raw_songs = enrich_with_spotify(raw_songs)

    # Claude APIで振り分け（Audio Features情報も渡す）
    print("\n🤖 朝・夜に振り分け中...")
    classified = classify_and_comment(raw_songs)

    # YouTube検索・保存・プレイリスト更新
    for slot in ["morning", "evening"]:
        label = "🌅 朝枠" if slot == "morning" else "🌙 深夜枠"
        print(f"\n{label} YouTube検索中...")

        songs_yt = enrich_with_youtube(
            youtube, classified[slot], n=10,
            max_attempts=20
        )

        for i, s in enumerate(songs_yt, 1):
            dur = s.get("duration_seconds", 0)
            print(f"  {i:2d}. {s['artist']} - {s['title']} "
                  f"({dur//60}:{dur%60:02d}) [{s['source']}]")

        save_results(songs_yt, slot, weekday, config)

        print(f"  📋 プレイリスト更新中...")
        update_today_playlist(youtube, songs_yt, slot)

    # X候補保存
    save_x_candidates(weekday)

    print("\n✅ 全処理完了")


if __name__ == "__main__":
    main()
