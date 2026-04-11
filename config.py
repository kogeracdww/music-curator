# 曜日別設定 (0=月, 1=火, 2=水, 3=木, 4=金, 5=土, 6=日)

WEEKDAY_CONFIG = {
    0: {
        "label": "月曜日",
        "region": "英語圏",
        "countries": ["United States", "United Kingdom", "Australia", "Canada", "Ireland", "New Zealand"],
        "bgm": "bgm_01.mp3",
        "dancer_prefix": "shortM_01",
    },
    1: {
        "label": "火曜日",
        "region": "東南アジア",
        "countries": ["Indonesia", "Thailand", "Vietnam", "Philippines", "Malaysia", "Singapore"],
        "bgm": "bgm_02.mp3",
        "dancer_prefix": "shortM_02",
    },
    2: {
        "label": "水曜日",
        "region": "日本",
        "countries": ["Japan"],
        "bgm": "bgm_03.mp3",
        "dancer_prefix": "shortM_03",
    },
    3: {
        "label": "木曜日",
        "region": "東欧・南米・中米・アフリカ",
        "countries": [
            "Poland", "Czech Republic", "Hungary", "Romania", "Ukraine",
            "Brazil", "Argentina", "Colombia", "Mexico", "Chile",
            "Nigeria", "Ghana", "Kenya", "South Africa", "Ethiopia"
        ],
        "bgm": "bgm_04.mp3",
        "dancer_prefix": "shortM_04",
    },
    4: {
        "label": "金曜日",
        "region": "西欧・北米",
        "countries": ["France", "Germany", "Spain", "Italy", "Netherlands", "Sweden", "Norway", "United States", "Canada"],
        "bgm": "bgm_05.mp3",
        "dancer_prefix": "shortM_05",
    },
    5: {
        "label": "土曜日",
        "region": "韓国",
        "countries": ["South Korea"],
        "bgm": "bgm_06.mp3",
        "dancer_prefix": "shortM_06",
    },
    6: {
        "label": "日曜日",
        "region": "西欧・北米・東南アジア",
        "countries": [
            "France", "Germany", "Spain", "United States", "Canada",
            "Indonesia", "Thailand", "Vietnam", "Philippines"
        ],
        "bgm": "bgm_07.mp3",
        "dancer_prefix": "shortM_07",
    },
}

# 時間帯別ジャンル設定
SLOT_CONFIG = {
    "morning": {
        "label": "Morning Playlist",
        "title_prefix": "Today's Morning Playlist",
        "genres": [
            "City Pop Revival",
            "Bedroom Pop",
            "K-Indie",
            "Future Bass (Chill)",
        ],
        "description": "A little positive · Chill · No lyrics in your language",
    },
    "evening": {
        "label": "Late Night Playlist",
        "title_prefix": "Tonight's Late Night Playlist",
        "genres": [
            "Trip-Hop Revival",
            "Neo Soul",
            "Chillhop",
            "Indie Folk (Non-English)",
            "Sweet Soul",
        ],
        "description": "Chill Out · Deep · Late night work session",
    },
}

# 発掘条件
DISCOVERY_RULES = {
    "max_followers": 1000,
    "ideal_max_followers": 100,
    "release_hours": 36,       # 36時間以内にアップされた曲
    "songs_per_day": 10,
    "major_labels_excluded": True,
}

# 投稿時刻 (JST)
POST_TIMES = {
    "morning": "08:00",
    "evening": "19:00",
}

SLOT_CONFIG = {
    "morning": {
        "label": "Morning Playlist",
        "title_prefix": "Today's Morning Playlist",
        "genres": [
            "City Pop Revival",
            "Bedroom Pop",
            "K-Indie",
            "Future Bass (Chill)",
        ],
        "description": "A little positive · Chill · No lyrics in your language",
        "playlist_today": "Today's Morning Playlist",
        "playlist_selected": "Morning Playlist",
    },
    "evening": {
        "label": "Midnight Playlist",
        "title_prefix": "Midnight playlist for tonight",
        "genres": [
            "Trip-Hop Revival",
            "Neo Soul",
            "Chillhop",
            "Indie Folk (Non-English)",
            "Sweet Soul",
        ],
        "description": "Chill Out · Deep · Late night work session",
        "playlist_today": "Midnight playlist for tonight",
        "playlist_selected": "Midnight playlist",
    },
}

# プレイリスト管理設定
PLAYLIST_RULES = {
    "keep_days": 4,        # 何日分をキープするか
    "songs_per_day": 10,   # 1日あたりの曲数
    # 4日分 × 10曲 = 最大40曲をキープ
}
