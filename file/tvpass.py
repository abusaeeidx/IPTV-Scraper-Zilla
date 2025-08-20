import requests
import re
import os
from datetime import datetime, timedelta

UPSTREAM_URL = "http://tvpass.org/playlist/m3u"
LOCAL_FILE = "TVPass.m3u"

LOCKED_GROUPS = {
    "ppv": {
        "tvg-id": "PPV.EVENTS.Dummy.us",
        "tvg-logo": ""
    },
    "mlb": {
        "tvg-id": "MLB.Baseball.Dummy.us",
        "tvg-logo": ""
    },
    "wnba": {
        "tvg-id": "WNBA.dummy.us",
        "tvg-logo": ""
    }
}

def extract_event_date(title):
    patterns = [
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{1,2}/\d{1,2})",
        r"([A-Za-z]+ \d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            text = match.group(1)
            for fmt in ("%Y-%m-%d", "%m/%d", "%B %d", "%b %d"):
                try:
                    parsed = datetime.strptime(text, fmt)
                    if "%Y" not in fmt:
                        parsed = parsed.replace(year=datetime.now().year)
                    return parsed.date()
                except ValueError:
                    continue
    return None

def is_event_outdated(title):
    event_date = extract_event_date(title)
    if event_date:
        return event_date < datetime.now().date()
    return False

def fetch_upstream_pairs():
    res = requests.get(UPSTREAM_URL, timeout=15)
    res.raise_for_status()
    lines = res.text.splitlines()
    pairs = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            meta = lines[i].strip()
            i += 1
            if i < len(lines):
                url = lines[i].strip()
                title = extract_title(meta)
                if not is_event_outdated(title):
                    pairs.append((meta, url))
        i += 1
    return pairs

def parse_local_playlist():
    if not os.path.exists(LOCAL_FILE):
        print(f"⚠️ {LOCAL_FILE} not found. Starting fresh.")
        return "#EXTM3U", []

    with open(LOCAL_FILE, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    header = lines[0] if lines and lines[0].startswith("#EXTM3U") else "#EXTM3U"
    pairs = []
    i = 1
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            meta = lines[i].strip()
            i += 1
            if i < len(lines):
                url = lines[i].strip()
                title = extract_title(meta)
                if not is_event_outdated(title):
                    pairs.append((meta, url))
        i += 1
    return header, pairs

def extract_title(extinf_line):
    return extinf_line.split(",")[-1].strip().lower()

def extract_group(extinf_line):
    if 'group-title="' in extinf_line:
        return extinf_line.split('group-title="')[1].split('"')[0].strip()
    return ""

def lock_metadata(meta_line, title):
    original_group = extract_group(meta_line)
    group_key = original_group.lower()
    if group_key in LOCKED_GROUPS:
        locked = LOCKED_GROUPS[group_key]
        display_group = group_key.upper()
        title_cased = title.title()
        return f'#EXTINF:-1 tvg-id="{locked["tvg-id"]}" tvg-name="{title_cased}" tvg-logo="{locked["tvg-logo"]}" group-title="{display_group}",{title_cased}'
    return meta_line

def update_playlist(local_pairs, upstream_pairs):
    updated = []
    used_titles = set()
    upstream_map = {extract_title(meta): url for meta, url in upstream_pairs}

    for meta, url in local_pairs:
        title = extract_title(meta)
        if title in upstream_map:
            new_url = upstream_map[title]
            new_meta = lock_metadata(meta, title)
            updated.append((new_meta, new_url))
            used_titles.add(title)
        else:
            updated.append((lock_metadata(meta, title), url))

    for meta, url in upstream_pairs:
        title = extract_title(meta)
        if title not in used_titles:
            updated.append((lock_metadata(meta, title), url))

    return updated

def write_playlist(header, updated_pairs):
    with open(LOCAL_FILE, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for meta, url in updated_pairs:
            f.write(meta + "\n")
            f.write(url + "\n")
    print(f"✅ Updated {LOCAL_FILE} with {len(updated_pairs)} total streams.")

def main():
    header, local_pairs = parse_local_playlist()
    upstream_pairs = fetch_upstream_pairs()
    updated_pairs = update_playlist(local_pairs, upstream_pairs)
    write_playlist(header, updated_pairs)

if __name__ == "__main__":
    main()
