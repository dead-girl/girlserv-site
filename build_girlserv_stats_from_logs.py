#!/usr/bin/env python3
from pathlib import Path
import zipfile, json, re, sys
from collections import Counter, defaultdict

DEFAULT_INPUT = "irccloud-logs"
MAIN_STATS_OUTPUT = "truth_seekers_user_stats.json"
LORE_STATS_OUTPUT = "channel_fun_stats.json"

STOPWORDS = set("""
a an the and or but if then else for from of to in on with at by as is are was were be been being it its this that these those i me my mine we us our you your yours he she they them his her their
do does did done not no yes yeah yep nah just so very really actually like lol lmao rofl haha hehe hi hey hello sup thanks thank ty ok okay what who where when why how can could would should will shall may might im i'm ive i've dont don't didnt didn't doesnt doesn't cant can't wont won't
have has had all about out up down over under into than then here there because also get got make made say said see saw look good bad going come came much many more most some any one two three
""".split())

SWEARS = [
    "fuck", "fucking", "fucked", "fucker", "shit", "shitty", "bullshit", "ass", "asshole", "bitch", "bitches",
    "damn", "cunt", "dick", "piss", "retard", "retarded", "fag", "faggot", "nigger", "nigga", "whore", "slut"
]

BOT_NAMES = {
    "redrose", "nil", "girl", "billgates", "chanserv", "nickserv", "botserv", "hostserv", "memoserv",
    "global", "irc.shells.org", "status", "*status", "irccloud"
}

word_re = re.compile(r"[a-zA-Z][a-zA-Z']{2,}")
mention_re = re.compile(r'\b([A-Za-z_`\-\[\]{}][A-Za-z0-9_`\-\[\]{}-]{1,30})[:,]')
url_re = re.compile(r'https?://\S+|www\.\S+', re.I)
lol_re = re.compile(r'\b(lol+|lmao+|lmfao+|rofl+|haha+|hehe+)\b', re.I)
swear_res = [(sw, re.compile(rf"\b{re.escape(sw)}\w*\b", re.I)) for sw in SWEARS]


def is_public_channel_log(path_string):
    name = Path(path_string).name
    return name.startswith("#") and name.lower().endswith(".txt")


def iter_inputs(input_path):
    input_path = Path(input_path)

    if input_path.is_file():
        yield input_path
        return

    if input_path.is_dir():
        for file_path in sorted(input_path.rglob("*")):
            if file_path.is_file() and (
                file_path.suffix.lower() == ".zip" or is_public_channel_log(str(file_path))
            ):
                yield file_path
        return

    raise SystemExit(f"Input not found: {input_path}")


def iter_public_logs(input_path):
    for file_path in iter_inputs(input_path):
        if file_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(file_path) as zf:
                for name in zf.namelist():
                    if is_public_channel_log(name):
                        with zf.open(name) as fh:
                            yield f"{file_path.name}:{name}", fh
        elif is_public_channel_log(str(file_path)):
            yield str(file_path), open(file_path, "rb")


def parse_timestamp_and_body(line):
    if not line.startswith("["):
        return None, None
    close = line.find("]")
    if close == -1:
        return None, None
    return line[1:close], line[close + 1:].strip()


def parse_message(body):
    if not body.startswith("<"):
        return None
    end = body.find(">")
    if end == -1:
        return None
    nick = body[1:end].strip()
    msg = body[end + 1:].strip()
    if not nick or not msg:
        return None
    return nick, msg


def parse_action(body):
    if not body.startswith("— "):
        return None
    rest = body[2:].strip()
    if " " not in rest:
        return None
    nick, action = rest.split(" ", 1)
    return nick.strip(), action.strip()


def clean_word(tok):
    return tok.strip("'").lower()


def is_bot(nick):
    return str(nick or "").lower() in BOT_NAMES


def user_record():
    return {"words": 0, "joins": 0, "lol": 0, "degeneracy": 0, "links": 0}


def main():
    input_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT
    main_output = sys.argv[2] if len(sys.argv) > 2 else MAIN_STATS_OUTPUT
    lore_output = sys.argv[3] if len(sys.argv) > 3 else LORE_STATS_OUTPUT

    public_log_count = 0
    total_lines = 0
    message_count = 0
    users_seen = set()

    user_stats = defaultdict(user_record)
    word_counts = Counter()
    words_by_user = defaultdict(Counter)
    swears_by_user = defaultdict(Counter)
    joins = Counter()
    quits = Counter()
    kicks_by_op = Counter()
    kicks_received = Counter()
    mode_ops = Counter()
    mode_given = Counter()
    nick_changes = []
    talk_edges = Counter()
    popular = Counter()
    quotes = []

    for source_name, fh in iter_public_logs(input_arg):
        public_log_count += 1
        last_speaker = None

        with fh:
            for raw in fh:
                total_lines += 1
                line = raw.decode("utf-8", errors="replace").rstrip("\n\r")
                ts, body = parse_timestamp_and_body(line)
                if not body:
                    continue

                parsed_msg = parse_message(body)
                if parsed_msg:
                    nick, msg = parsed_msg
                    message_count += 1
                    low_nick = nick.lower()
                    bot = is_bot(nick)

                    low = msg.lower()
                    words = [clean_word(tok) for tok in word_re.findall(low)]
                    useful_words = [w for w in words if w and not w.startswith("http")]

                    if not bot:
                        users_seen.add(nick)
                        user_stats[nick]["words"] += len(useful_words)
                        user_stats[nick]["links"] += len(url_re.findall(msg))
                        user_stats[nick]["lol"] += len(lol_re.findall(msg))

                    for tok in useful_words:
                        if tok not in STOPWORDS:
                            word_counts[tok] += 1
                            if not bot:
                                words_by_user[nick][tok] += 1

                    if not bot:
                        swear_count = 0
                        for sw, sw_re in swear_res:
                            count = len(sw_re.findall(low))
                            if count:
                                swears_by_user[nick][sw] += count
                                swear_count += count

                        user_stats[nick]["degeneracy"] += swear_count

                        for target in set(mention_re.findall(msg)):
                            if target.lower() != low_nick:
                                talk_edges[(nick, target)] += 2

                        if last_speaker and last_speaker.lower() != low_nick:
                            talk_edges[(last_speaker, nick)] += 1

                        last_speaker = nick

                        if (
                            25 <= len(msg) <= 140
                            and not msg.startswith(("http://", "https://"))
                            and "://" not in msg
                            and len(quotes) < 700
                        ):
                            quotes.append({"nick": nick, "quote": msg, "ts": ts})

                    continue

                parsed_action = parse_action(body)
                if parsed_action:
                    nick, action = parsed_action
                    if not is_bot(nick):
                        action_words = [clean_word(tok) for tok in word_re.findall(action.lower())]
                        user_stats[nick]["words"] += len(action_words)
                        if 20 <= len(action) <= 140 and len(quotes) < 700:
                            quotes.append({"nick": nick, "quote": "* " + action, "ts": ts})
                    continue

                if body.startswith("→ "):
                    parts = body.split()
                    if len(parts) >= 2 and parts[1] != "Joined":
                        nick = parts[1]
                        joins[nick] += 1
                        if not is_bot(nick):
                            user_stats[nick]["joins"] += 1
                    continue

                if body.startswith("⇐ ") or body.startswith("← "):
                    parts = body.split()
                    if len(parts) >= 2 and parts[1] != "You":
                        quits[parts[1]] += 1
                    continue

                if body.startswith("* "):
                    pieces = body[2:].strip().split()

                    if len(pieces) >= 4 and pieces[1].lower() == "set":
                        op, mode, target = pieces[0], pieces[2], pieces[3]
                        if mode.startswith(("+", "-")):
                            if not is_bot(op):
                                mode_ops[op] += 1
                            if not is_bot(target):
                                mode_given[target] += 1
                        continue

                    if len(pieces) >= 3 and pieces[1].lower() == "kicked":
                        op, target = pieces[0], pieces[2]
                        if not is_bot(op):
                            kicks_by_op[op] += 1
                        if not is_bot(target):
                            kicks_received[target] += 1
                        continue

                    if "→" in pieces and len(pieces) >= 3:
                        try:
                            arrow = pieces.index("→")
                            nick_changes.append({"old": pieces[0], "new": pieces[arrow + 1], "ts": ts})
                        except Exception:
                            pass

    for (a, b), c in talk_edges.items():
        if not is_bot(b):
            popular[b] += c

    user_swear_totals = Counter({u: sum(c.values()) for u, c in swears_by_user.items()})

    main_stats = {
        nick: stats
        for nick, stats in sorted(user_stats.items(), key=lambda kv: kv[1]["words"], reverse=True)
        if not is_bot(nick) and sum(stats.values()) > 0
    }

    lore_stats = {
        "meta": {
            "source": "combined public IRC channel logs",
            "privacy": "Only #channel log files were parsed. Private/query logs were ignored. Other channel names are intentionally not displayed.",
            "publicChannelLogsParsed": public_log_count,
            "lines": total_lines,
            "messages": message_count,
            "usersWithMessages": len(users_seen),
        },
        "topWords": [{"word": w, "count": c} for w, c in word_counts.most_common(100)],
        "topWordsByUser": {
            u: [{"word": w, "count": c} for w, c in ctr.most_common(20)]
            for u, ctr in sorted(words_by_user.items(), key=lambda kv: sum(kv[1].values()), reverse=True)[:50]
        },
        "swearLords": [{"nick": u, "count": c, "top": swears_by_user[u].most_common(5)} for u, c in user_swear_totals.most_common(30)],
        "conversationMagnets": [{"nick": u, "score": c} for u, c in popular.most_common(30)],
        "talkEdges": [{"from": a, "to": b, "weight": c} for (a, b), c in talk_edges.most_common(150)],
        "randomQuotes": quotes,
        "joins": [{"nick": u, "count": c} for u, c in joins.most_common(30) if not is_bot(u)],
        "quits": [{"nick": u, "count": c} for u, c in quits.most_common(30) if not is_bot(u)],
        "kicks": {
            "byOp": [{"nick": u, "count": c} for u, c in kicks_by_op.most_common(30) if not is_bot(u)],
            "received": [{"nick": u, "count": c} for u, c in kicks_received.most_common(30) if not is_bot(u)],
        },
        "modeChanges": {
            "byOp": [{"nick": u, "count": c} for u, c in mode_ops.most_common(30) if not is_bot(u)],
            "givenTo": [{"nick": u, "count": c} for u, c in mode_given.most_common(30) if not is_bot(u)],
        },
        "nickChanges": nick_changes[:500],
    }

    Path(main_output).write_text(json.dumps(main_stats, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(lore_output).write_text(json.dumps(lore_stats, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {main_output}")
    print(f"Wrote {lore_output}")
    print(f"Parsed {public_log_count} public #channel logs")
    print(f"Parsed {message_count} messages")
    print("Ignored private/query logs")


if __name__ == "__main__":
    main()
