#!/usr/bin/env python3
from pathlib import Path
import re, json
from collections import Counter, defaultdict

log_path = Path("#truth-seekers.txt")
out_path = Path("channel_fun_stats.json")
text = log_path.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()

msg_re = re.compile(r'^\[(?P<ts>[^\]]+)\]\s+<(?P<nick>[^>]+)>\s(?P<msg>.*)$')
action_re = re.compile(r'^\[(?P<ts>[^\]]+)\]\s+—\s(?P<nick>\S+)\s(?P<action>.*)$')
join_re = re.compile(r'^\[(?P<ts>[^\]]+)\]\s+→\s(?P<nick>\S+)\sjoined\b')
quit_re = re.compile(r'^\[(?P<ts>[^\]]+)\]\s+⇐\s(?P<nick>\S+)\squit\b')
left_re = re.compile(r'^\[(?P<ts>[^\]]+)\]\s+←\s(?P<nick>\S+)\sleft\b')
kick_re = re.compile(r'^\[(?P<ts>[^\]]+)\]\s+\*\s(?P<op>\S+)\skicked\s(?P<target>\S+)\b(?::\s(?P<reason>.*))?', re.I)
mode_re = re.compile(r'^\[(?P<ts>[^\]]+)\]\s+\*\s(?P<op>\S+)\sset\s(?P<mode>[+-][ovhqa])\s(?P<target>\S+)', re.I)
nick_re = re.compile(r'^\[(?P<ts>[^\]]+)\]\s+\*\s(?P<old>\S+)\s→\s(?P<new>\S+)')

stopwords = set("a an the and or but if then else for from of to in on with at by as is are was were be been being it its this that these those i me my mine we us our you your yours he she they them his her their do does did done not no yes yeah yep nah just so very really actually like lol lmao rofl haha hehe hi hey hello sup thanks thank ty ok okay what who where when why how can could would should will shall may might im i'm ive i've dont don't didnt didn't doesnt doesn't cant can't wont won't".split())
swears = ["fuck","fucking","fucked","fucker","shit","shitty","bullshit","ass","asshole","bitch","bitches","damn","cunt","dick","piss","retard","retarded","fag","faggot","nigger","nigga","whore","slut"]

messages, actions, nick_changes = [], [], []
joins, quits, kicks_by_op, kicks_received, mode_ops, mode_given = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()

for line in lines:
    if m := msg_re.match(line):
        d = m.groupdict()
        messages.append({"ts": d["ts"], "nick": d["nick"].strip(), "text": d["msg"].strip()})
    elif m := action_re.match(line):
        d = m.groupdict()
        actions.append({"ts": d["ts"], "nick": d["nick"], "text": d["action"].strip()})
    elif m := join_re.match(line):
        joins[m.group("nick")] += 1
    elif m := (quit_re.match(line) or left_re.match(line)):
        quits[m.group("nick")] += 1
    elif m := kick_re.match(line):
        kicks_by_op[m.group("op")] += 1
        kicks_received[m.group("target")] += 1
    elif m := mode_re.match(line):
        mode_ops[m.group("op")] += 1
        mode_given[m.group("target")] += 1
    elif m := nick_re.match(line):
        nick_changes.append(m.groupdict())

word_counts, words_by_user, swears_by_user = Counter(), defaultdict(Counter), defaultdict(Counter)
talk_edges, popular = Counter(), Counter()
quotes = []
last_speaker = None

for msg in messages:
    nick, body = msg["nick"], msg["text"]
    low = body.lower()
    for tok in re.findall(r"[a-zA-Z][a-zA-Z']{2,}", low):
        tok = tok.strip("'").lower()
        if tok and tok not in stopwords and not tok.startswith("http"):
            word_counts[tok] += 1
            words_by_user[nick][tok] += 1
    for sw in swears:
        count = len(re.findall(rf"\b{re.escape(sw)}\w*\b", low))
        if count:
            swears_by_user[nick][sw] += count
    for target in set(re.findall(r'\b([A-Za-z_`\-\[\]{}][A-Za-z0-9_`\-\[\]{}-]{1,30})[:,]', body)):
        if target.lower() != nick.lower():
            talk_edges[(nick, target)] += 2
    if last_speaker and last_speaker.lower() != nick.lower():
        talk_edges[(last_speaker, nick)] += 1
    last_speaker = nick
    if 25 <= len(body) <= 140 and not body.startswith(("http://", "https://")):
        quotes.append({"nick": nick, "quote": body, "ts": msg["ts"]})

for (a, b), c in talk_edges.items():
    popular[b] += c

user_swear_totals = Counter({u: sum(c.values()) for u, c in swears_by_user.items()})

fun_stats = {
    "meta": {"source": str(log_path), "lines": len(lines), "messages": len(messages), "actions": len(actions), "usersWithMessages": len(set(m["nick"] for m in messages))},
    "topWords": [{"word": w, "count": c} for w, c in word_counts.most_common(100)],
    "topWordsByUser": {u: [{"word": w, "count": c} for w, c in ctr.most_common(20)] for u, ctr in sorted(words_by_user.items(), key=lambda kv: sum(kv[1].values()), reverse=True)[:50]},
    "swearLords": [{"nick": u, "count": c, "top": swears_by_user[u].most_common(5)} for u, c in user_swear_totals.most_common(30)],
    "conversationMagnets": [{"nick": u, "score": c} for u, c in popular.most_common(30)],
    "talkEdges": [{"from": a, "to": b, "weight": c} for (a, b), c in talk_edges.most_common(150)],
    "randomQuotes": quotes[:300],
    "joins": [{"nick": u, "count": c} for u, c in joins.most_common(30)],
    "quits": [{"nick": u, "count": c} for u, c in quits.most_common(30)],
    "kicks": {"byOp": [{"nick": u, "count": c} for u, c in kicks_by_op.most_common(30)], "received": [{"nick": u, "count": c} for u, c in kicks_received.most_common(30)]},
    "modeChanges": {"byOp": [{"nick": u, "count": c} for u, c in mode_ops.most_common(30)], "givenTo": [{"nick": u, "count": c} for u, c in mode_given.most_common(30)]},
    "nickChanges": nick_changes[:300],
}

out_path.write_text(json.dumps(fun_stats, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {out_path}")
