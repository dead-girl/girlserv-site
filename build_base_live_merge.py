#!/usr/bin/env python3
from pathlib import Path
import argparse, json, re, collections, urllib.parse

ts_re = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.*)$')
msg_re = re.compile(r'^<([^>]+)> ?(.*)$')
action_re = re.compile(r'^— ([^ ]+) (.*)$')
join_re = re.compile(r'^→ ([^ ]+) joined ')
url_re = re.compile(r'https?://\S+', re.I)
word_re = re.compile(r"[A-Za-z0-9_']+")
lol_re = re.compile(r'\b(?:lol|lmao|rofl|haha|hehe|bahaha|bwahaha)\b', re.I)
deg_re = re.compile(r'\b(?:fuck|fucking|fucked|shit|shitty|bitch|bastard|cunt|asshole|motherfucker|wtf|cock|dick|piss)\b', re.I)

def parse_log(path: Path):
    stats = collections.defaultdict(lambda: {"words":0,"joins":0,"lol":0,"degeneracy":0,"links":0})
    overall_words = collections.Counter()
    per_user_words = collections.defaultdict(collections.Counter)
    domain_counts = collections.Counter()
    domains_by_user = collections.defaultdict(collections.Counter)
    first_seen = {}
    last_seen = {}
    messages_per_user = collections.Counter()
    actions_per_user = collections.Counter()
    mentioned_pairs = collections.Counter()
    reply_pairs = collections.Counter()
    stopwords = {
        "the","and","for","that","with","you","this","have","just","your","but","are","not","was","its","it's",
        "from","they","them","what","when","where","will","then","than","into","about","would","there","their",
        "been","were","she","him","her","his","our","out","all","too","can","cant","can't","did","didnt","didn't",
        "has","had","who","why","how","one","only","like","dont","don't","get","got","let","lets","let's","im","i'm",
        "ive","i've","ill","i'll","u","ur","http","https","www","com","co","za","amp"
    }
    prev_speaker = None

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            m = ts_re.match(raw.lstrip("\ufeff"))
            if not m:
                continue
            ts, payload = m.groups()
            mm = msg_re.match(payload)
            if mm:
                nick, msg = mm.groups()
                first_seen.setdefault(nick, ts)
                last_seen[nick] = ts
                words = word_re.findall(msg)
                stats[nick]["words"] += len(words)
                stats[nick]["lol"] += len(lol_re.findall(msg))
                stats[nick]["degeneracy"] += len(deg_re.findall(msg))
                links = url_re.findall(msg)
                stats[nick]["links"] += len(links)
                messages_per_user[nick] += 1

                if prev_speaker and prev_speaker != nick:
                    reply_pairs[(prev_speaker, nick)] += 1
                prev_speaker = nick

                lowered = msg.lower()
                for w in words:
                    wl = w.lower()
                    if len(wl) >= 3 and wl not in stopwords and not wl.isdigit():
                        overall_words[wl] += 1
                        per_user_words[nick][wl] += 1

                for other in list(first_seen.keys()) + [nick]:
                    if other != nick and other.lower() in lowered:
                        mentioned_pairs[(nick, other)] += 1

                for url in links:
                    try:
                        domain = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
                        if domain:
                            domain_counts[domain] += 1
                            domains_by_user[nick][domain] += 1
                    except Exception:
                        pass
                continue

            ma = action_re.match(payload)
            if ma:
                nick, msg = ma.groups()
                first_seen.setdefault(nick, ts)
                last_seen[nick] = ts
                words = word_re.findall(msg)
                stats[nick]["words"] += len(words)
                stats[nick]["lol"] += len(lol_re.findall(msg))
                stats[nick]["degeneracy"] += len(deg_re.findall(msg))
                stats[nick]["links"] += len(url_re.findall(msg))
                actions_per_user[nick] += 1
                continue

            mj = join_re.match(payload)
            if mj:
                nick = mj.group(1)
                first_seen.setdefault(nick, ts)
                last_seen[nick] = ts
                stats[nick]["joins"] += 1
                continue

    return {
        "user_stats": stats,
        "top_words_overall": overall_words,
        "top_words_by_user": per_user_words,
        "top_domains": domain_counts,
        "domains_by_user": domains_by_user,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "messages_per_user": messages_per_user,
        "actions_per_user": actions_per_user,
        "mentions": mentioned_pairs,
        "reply_flow": reply_pairs,
    }

def merge_user_stats(base, live):
    merged = {}
    keys = set(base) | set(live)
    for k in keys:
        merged[k] = {
            "words": int(base.get(k, {}).get("words", 0)) + int(live.get(k, {}).get("words", 0)),
            "joins": int(base.get(k, {}).get("joins", 0)) + int(live.get(k, {}).get("joins", 0)),
            "lol": int(base.get(k, {}).get("lol", 0)) + int(live.get(k, {}).get("lol", 0)),
            "degeneracy": int(base.get(k, {}).get("degeneracy", 0)) + int(live.get(k, {}).get("degeneracy", 0)),
            "links": int(base.get(k, {}).get("links", 0)) + int(live.get(k, {}).get("links", 0)),
        }
    return dict(sorted(merged.items(), key=lambda kv: kv[0].lower()))

def as_counter_pairs(counter, limit=200):
    return counter.most_common(limit)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-user-stats", required=True)
    ap.add_argument("--live-delta-log", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base = json.loads(Path(args.base_user_stats).read_text(encoding="utf-8"))
    live = parse_log(Path(args.live_delta_log))
    merged = merge_user_stats(base, live["user_stats"])

    (outdir / "live_delta_user_stats.json").write_text(json.dumps(live["user_stats"], indent=2), encoding="utf-8")
    (outdir / "merged_user_stats.json").write_text(json.dumps(merged, indent=2), encoding="utf-8")

    summary = {
        "totals": {
            "users": len(merged),
            "words": sum(v["words"] for v in merged.values()),
            "joins": sum(v["joins"] for v in merged.values()),
            "lol": sum(v["lol"] for v in merged.values()),
            "degeneracy": sum(v["degeneracy"] for v in merged.values()),
            "links": sum(v["links"] for v in merged.values()),
        }
    }
    (outdir / "merged_summary_stats.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    word_stats = {
        "top_words_overall": as_counter_pairs(live["top_words_overall"], 200),
        "top_words_by_user": {u: c.most_common(25) for u, c in sorted(live["top_words_by_user"].items())}
    }
    (outdir / "live_word_stats.json").write_text(json.dumps(word_stats, indent=2), encoding="utf-8")

    interaction_map = {
        "mentions": [{"from": a, "to": b, "count": c} for (a,b), c in live["mentions"].most_common(300)],
        "reply_flow": [{"from": a, "to": b, "count": c} for (a,b), c in live["reply_flow"].most_common(300)],
    }
    (outdir / "live_interaction_map.json").write_text(json.dumps(interaction_map, indent=2), encoding="utf-8")

    link_stats = {
        "top_domains": live["top_domains"].most_common(200),
        "domains_by_user": {u: c.most_common(25) for u, c in sorted(live["domains_by_user"].items())}
    }
    (outdir / "live_link_stats.json").write_text(json.dumps(link_stats, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
