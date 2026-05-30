package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"hash/crc32"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"unicode"
)

type UStat struct {
	Words      int `json:"words"`
	Joins      int `json:"joins"`
	Lol        int `json:"lol"`
	Degeneracy int `json:"degeneracy"`
	Links      int `json:"links"`
}
type Chan struct {
	Messages int            `json:"messages"`
	Actions  int            `json:"actions"`
	Words    int            `json:"words"`
	Links    int            `json:"links"`
	Joins    int            `json:"joins"`
	Users    map[string]int `json:"-"`
	TopWords map[string]int `json:"-"`
	Domains  map[string]int `json:"-"`
}
type Quote struct {
	T string `json:"t"`
	C string `json:"c"`
	U string `json:"u"`
	M string `json:"m"`
}
type Pair struct {
	K string
	V int
}
type Edge struct {
	From  string `json:"from"`
	To    string `json:"to"`
	Count int    `json:"count"`
}

var urlRe = regexp.MustCompile(`https?://[^\s<>()"']+`)
var lolWords = map[string]bool{"lol": true, "lmao": true, "lmfao": true, "rofl": true, "haha": true, "hehe": true, "kek": true}
var degen = map[string]bool{"fuck": true, "shit": true, "bitch": true, "cunt": true, "faggot": true, "retard": true, "whore": true, "slut": true, "degenerate": true, "degen": true, "idiot": true, "moron": true, "dumb": true, "stupid": true, "kys": true, "rape": true, "pedo": true, "nazi": true}
var bots = map[string]bool{"duckhunt": true, "murasa": true, "urlinfo": true, "agnes": true, "trivia": true, "internets": true, "nickserv": true, "chanserv": true, "botserv": true, "hostserv": true, "memoserv": true}
var stop = map[string]bool{}

func init() {
	for _, w := range strings.Fields("the a an and or but if then else for from with without into onto over under this that these those there here have has had was were are is am be been being not no yes you your youre me my mine we our ours they them their he him his she her hers it its of to in on at as by do does did done just like lol lmao rofl haha hehe im ive id ill dont cant wont isnt wasnt didnt should could would really very more most much many some any all one two three get got go goes going say says said think thought know knew make made take took see saw come came because cause about when where who what why how") {
		stop[w] = true
	}
}
func words(s string) []string {
	out := []string{}
	var b strings.Builder
	for _, r := range s {
		if unicode.IsLetter(r) || unicode.IsDigit(r) || r == '_' || r == '\'' {
			b.WriteRune(unicode.ToLower(r))
		} else {
			if b.Len() > 1 {
				out = append(out, strings.Trim(b.String(), "_'"))
			}
			b.Reset()
		}
	}
	if b.Len() > 1 {
		out = append(out, strings.Trim(b.String(), "_'"))
	}
	return out
}
func topMap(m map[string]int, n int) [][]interface{} {
	arr := make([]Pair, 0, len(m))
	for k, v := range m {
		arr = append(arr, Pair{k, v})
	}
	sort.Slice(arr, func(i, j int) bool { return arr[i].V > arr[j].V })
	if len(arr) > n {
		arr = arr[:n]
	}
	out := make([][]interface{}, len(arr))
	for i, p := range arr {
		out[i] = []interface{}{p.K, p.V}
	}
	return out
}
func topObj(m map[string]int, n int, key string) []map[string]interface{} {
	arr := make([]Pair, 0, len(m))
	for k, v := range m {
		arr = append(arr, Pair{k, v})
	}
	sort.Slice(arr, func(i, j int) bool { return arr[i].V > arr[j].V })
	if len(arr) > n {
		arr = arr[:n]
	}
	out := []map[string]interface{}{}
	for _, p := range arr {
		out = append(out, map[string]interface{}{key: p.K, "count": p.V})
	}
	return out
}
func host(u string) string {
	x, err := url.Parse(u)
	if err != nil {
		return ""
	}
	h := strings.ToLower(x.Hostname())
	h = strings.TrimPrefix(h, "www.")
	return h
}
func dump(path string, v interface{}) {
	f, _ := os.Create(path)
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetEscapeHTML(false)
	enc.Encode(v)
}
func main() {
	if len(os.Args) < 3 {
		panic("args")
	}
	root, out := os.Args[1], os.Args[2]
	quoteLimit := 120000
	os.MkdirAll(filepath.Join(out, "base_stats"), 0755)
	user := map[string]*UStat{}
	msgUser := map[string]int{}
	actUser := map[string]int{}
	topWords := map[string]int{}
	topPhrases := map[string]int{}
	domains := map[string]int{}
	domainsByUser := map[string]map[string]int{}
	wordsByUser := map[string]map[string]int{}
	phrasesByUser := map[string]map[string]int{}
	channels := map[string]*Chan{}
	first := map[string]string{}
	last := map[string]string{}
	quoteCount := map[string]int{}
	quoteWords := map[string]int{}
	quotes := []Quote{}
	reply := map[string]int{}
	lastMsg := map[string]string{}
	seen := map[uint64]bool{}
	raw, messages, actions, joins, quits, kicks, modes, dupes := 0, 0, 0, 0, 0, 0, 0, 0
	minTs, maxTs := "", ""
	files := []string{}
	filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() {
			n := filepath.Base(path)
			if strings.HasPrefix(n, "#") && strings.HasSuffix(n, ".txt") && !strings.HasPrefix(n, "._") {
				files = append(files, path)
			}
		}
		return nil
	})
	for idx, path := range files {
		chname := strings.ToLower(strings.TrimSuffix(filepath.Base(path), filepath.Ext(path)))
		ch := channels[chname]
		if ch == nil {
			ch = &Chan{Users: map[string]int{}, TopWords: map[string]int{}, Domains: map[string]int{}}
			channels[chname] = ch
		}
		f, err := os.Open(path)
		if err != nil {
			continue
		}
		sc := bufio.NewScanner(f)
		sc.Buffer(make([]byte, 1024), 1024*1024)
		firstLine := true
		for sc.Scan() {
			b := sc.Bytes()
			raw++
			if firstLine {
				firstLine = false
				if len(b) > 0 && (b[0] == '#' || strings.HasPrefix(string(b), "\ufeff#")) {
					continue
				}
			}
			if len(b) < 24 || b[0] != '[' {
				continue
			}
			crc := uint64(crc32.ChecksumIEEE(b)) ^ (uint64(crc32.ChecksumIEEE([]byte(chname))) << 32)
			if seen[crc] {
				dupes++
				continue
			}
			seen[crc] = true
			line := strings.TrimPrefix(sc.Text(), "\ufeff")
			if len(line) < 23 {
				continue
			}
			ts := line[1:20]
			rest := line[22:]
			nick, msg := "", ""
			isAction := false
			if strings.HasPrefix(rest, "<") {
				j := strings.Index(rest, "> ")
				if j > 1 {
					nick = rest[1:j]
					msg = rest[j+2:]
				}
			} else if strings.HasPrefix(rest, "— ") {
				tmp := rest[2:]
				sp := strings.Index(tmp, " ")
				if sp > 0 {
					nick = tmp[:sp]
					msg = tmp[sp+1:]
					isAction = true
				}
			} else if strings.Contains(rest, " joined ") || strings.HasSuffix(rest, " joined") {
				fields := strings.Fields(rest)
				if len(fields) >= 2 && fields[0] == "→" {
					nick = fields[1]
				} else if len(fields) >= 1 {
					nick = strings.TrimLeft(fields[0], "→")
				}
				if nick != "" && !bots[strings.ToLower(nick)] {
					if user[nick] == nil {
						user[nick] = &UStat{}
					}
					user[nick].Joins++
					ch.Joins++
					joins++
					if first[nick] == "" {
						first[nick] = ts
					}
					last[nick] = ts
				}
				continue
			} else {
				if strings.Contains(rest, " kicked ") {
					kicks++
				} else if strings.HasPrefix(rest, "* ") && strings.Contains(rest, " set ") {
					modes++
				} else if strings.HasPrefix(rest, "← ") {
					quits++
				}
				continue
			}
			if nick == "" || bots[strings.ToLower(nick)] {
				continue
			}
			wds := words(msg)
			wc := len(wds)
			if user[nick] == nil {
				user[nick] = &UStat{}
			}
			u := user[nick]
			u.Words += wc
			ch.Words += wc
			ch.Users[nick]++
			if first[nick] == "" {
				first[nick] = ts
			}
			last[nick] = ts
			if minTs == "" || ts < minTs {
				minTs = ts
			}
			if maxTs == "" || ts > maxTs {
				maxTs = ts
			}
			if isAction {
				actions++
				actUser[nick]++
				ch.Actions++
			} else {
				messages++
				msgUser[nick]++
				ch.Messages++
			}
			for _, w := range wds {
				if lolWords[w] {
					u.Lol++
				}
				if degen[w] {
					u.Degeneracy++
				}
				if len(w) > 2 && !stop[w] {
					topWords[w]++
					if wordsByUser[nick] == nil {
						wordsByUser[nick] = map[string]int{}
					}
					wordsByUser[nick][w]++
					ch.TopWords[w]++
				}
			}
			for i := 0; i+1 < len(wds); i++ {
				a, bb := wds[i], wds[i+1]
				if len(a) > 2 && len(bb) > 2 && !stop[a] && !stop[bb] {
					ph := a + " " + bb
					topPhrases[ph]++
					if phrasesByUser[nick] == nil {
						phrasesByUser[nick] = map[string]int{}
					}
					phrasesByUser[nick][ph]++
				}
			}
			for _, uu := range urlRe.FindAllString(msg, -1) {
				d := host(uu)
				if d != "" {
					domains[d]++
					if domainsByUser[nick] == nil {
						domainsByUser[nick] = map[string]int{}
					}
					domainsByUser[nick][d]++
					ch.Domains[d]++
					ch.Links++
					u.Links++
				}
			}
			if prev := lastMsg[chname]; prev != "" && strings.ToLower(prev) != strings.ToLower(nick) {
				reply[nick+"\x00"+prev]++
			}
			lastMsg[chname] = nick
			if len(msg) >= 18 && len(msg) <= 260 && len(wds) >= 4 && !strings.Contains(strings.ToLower(msg), "http") && !strings.Contains(".!$/?", msg[:1]) {
				if len(quotes) < quoteLimit {
					quotes = append(quotes, Quote{ts, chname, nick, msg})
				}
				quoteCount[nick]++
				for _, w := range wds {
					if len(w) > 2 && !stop[w] {
						quoteWords[w]++
					}
				}
			}
		}
		f.Close()
		if (idx+1)%25 == 0 {
			fmt.Fprintln(os.Stderr, "processed", idx+1, "/", len(files))
		}
	}
	base := map[string]UStat{}
	for n, u := range user {
		if u.Words+u.Joins+u.Lol+u.Degeneracy+u.Links > 0 {
			base[n] = *u
		}
	}
	totalWords, totalJoins, totalLol, totalDegen, totalLinks := 0, 0, 0, 0, 0
	for _, u := range base {
		totalWords += u.Words
		totalJoins += u.Joins
		totalLol += u.Lol
		totalDegen += u.Degeneracy
		totalLinks += u.Links
	}
	topUsers := map[string][][]interface{}{}
	for _, field := range []string{"words", "joins", "lol", "links", "degeneracy"} {
		m := map[string]int{}
		for n, u := range base {
			switch field {
			case "words":
				m[n] = u.Words
			case "joins":
				m[n] = u.Joins
			case "lol":
				m[n] = u.Lol
			case "links":
				m[n] = u.Links
			case "degeneracy":
				m[n] = u.Degeneracy
			}
		}
		topUsers[field] = topMap(m, 100)
	}
	summary := map[string]interface{}{"archive_source": "irccloud-export-292117-2026-05-30-13-51-40.zip", "cutoff": maxTs, "range": map[string]string{"first": minTs, "last": maxTs}, "dedupe": map[string]interface{}{"method": "channel + exact exported line", "duplicates_removed": dupes}, "totals": map[string]int{"users": len(base), "words": totalWords, "joins": totalJoins, "lol": totalLol, "degeneracy": totalDegen, "links": totalLinks, "messages": messages, "actions": actions, "channels": len(channels), "raw_lines_seen": raw}, "top_users": topUsers}
	channelStats := map[string]interface{}{}
	for c, ch := range channels {
		channelStats[c] = map[string]interface{}{"messages": ch.Messages, "actions": ch.Actions, "words": ch.Words, "links": ch.Links, "joins": ch.Joins, "users": len(ch.Users), "top_users": topMap(ch.Users, 30), "top_words": topMap(ch.TopWords, 30), "top_domains": topMap(ch.Domains, 20)}
	}
	edges := []Edge{}
	for k, v := range reply {
		parts := strings.SplitN(k, "\x00", 2)
		if len(parts) == 2 {
			edges = append(edges, Edge{parts[0], parts[1], v})
		}
	}
	sort.Slice(edges, func(i, j int) bool { return edges[i].Count > edges[j].Count })
	if len(edges) > 500 {
		edges = edges[:500]
	}
	twByUser := map[string]interface{}{}
	for n, m := range wordsByUser {
		twByUser[n] = topObj(m, 50, "word")
	}
	tpByUser := map[string]interface{}{}
	for n, m := range phrasesByUser {
		tpByUser[n] = topObj(m, 30, "phrase")
	}
	fun := map[string]interface{}{"meta": map[string]interface{}{"source": "irccloud-export-292117-2026-05-30-13-51-40.zip", "lines": raw, "messages": messages, "actions": actions, "usersWithMessages": len(msgUser), "channels": len(channels), "cutoff": maxTs, "duplicatesRemoved": dupes}, "topWords": topObj(topWords, 200, "word"), "topPhrases": topObj(topPhrases, 200, "phrase"), "topWordsByUser": twByUser, "topPhrasesByUser": tpByUser, "conversationMagnets": topObj(msgUser, 100, "nick"), "talkEdges": edges, "mentionEdges": []Edge{}, "randomQuotes": quotes[:min(len(quotes), 1000)], "quoteMeta": map[string]interface{}{"totalStored": len(quotes), "byUser": topMap(quoteCount, 1000), "searchWords": topMap(quoteWords, 1000)}, "linkDomains": topObj(domains, 200, "domain"), "channels": channelStats, "joins": topUsers["joins"], "quits": quits, "kicks": kicks, "modeChanges": modes}
	dump(filepath.Join(out, "base_user_stats.json"), base)
	dump(filepath.Join(out, "base_stats", "summary_stats.json"), summary)
	dump(filepath.Join(out, "channel_fun_stats.json"), fun)
	dump(filepath.Join(out, "base_stats", "channel_stats.json"), channelStats)
	dump(filepath.Join(out, "base_stats", "word_stats.json"), map[string]interface{}{"top_words_overall": topMap(topWords, 5000), "top_words_by_user": wordsByUser, "top_phrases_overall": topMap(topPhrases, 2000), "top_phrases_by_user": phrasesByUser})
	dump(filepath.Join(out, "base_stats", "link_stats.json"), map[string]interface{}{"top_domains": topMap(domains, 1000), "domains_by_user": domainsByUser})
	dump(filepath.Join(out, "base_stats", "interaction_map.json"), map[string]interface{}{"mentions": []Edge{}, "reply_flow": edges})
	dump(filepath.Join(out, "base_stats", "event_stats.json"), map[string]interface{}{"messages_per_user": topMap(msgUser, 1000), "actions_per_user": topMap(actUser, 1000), "first_seen": first, "last_seen": last, "kick_events": kicks, "mode_events": modes, "quit_events": quits})
	dump(filepath.Join(out, "base_stats", "chat_quote_index.json"), map[string]interface{}{"meta": map[string]interface{}{"stored": len(quotes), "cutoff": maxTs}, "byUser": topMap(quoteCount, 2000), "searchWords": topMap(quoteWords, 2000)})
	qf, _ := os.Create(filepath.Join(out, "base_stats", "chat_quotes.jsonl"))
	for _, q := range quotes {
		b, _ := json.Marshal(q)
		qf.Write(b)
		qf.Write([]byte("\n"))
	}
	qf.Close()
	bs, _ := json.MarshalIndent(summary, "", "  ")
	fmt.Println(string(bs))
}
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
