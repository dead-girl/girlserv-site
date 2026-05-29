#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(".").resolve()
INDEX = ROOT / "index.html"

START_MARK = "<!-- GIRLSERV_SHARED_INDEX_MENU_START -->"
END_MARK = "<!-- GIRLSERV_SHARED_INDEX_MENU_END -->"
STYLE_START = "<!-- GIRLSERV_SHARED_INDEX_MENU_STYLE_START -->"
STYLE_END = "<!-- GIRLSERV_SHARED_INDEX_MENU_STYLE_END -->"
SCRIPT_START = "<!-- GIRLSERV_SHARED_INDEX_MENU_SCRIPT_START -->"
SCRIPT_END = "<!-- GIRLSERV_SHARED_INDEX_MENU_SCRIPT_END -->"

PAGES = [
    "loudmouths.html",
    "channel-trolls.html",
    "lol-lords.html",
    "clickbait-crew.html",
    "frequent-flyers.html",
    "stat-dump.html",
    "girls-notes.html",
    "room-reports.html",
    "girlbook.html",
]

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")

def extract_balanced_div(html: str, start_index: int) -> str:
    tag_re = re.compile(r"</?div\b[^>]*>", re.I)
    depth = 0
    for match in tag_re.finditer(html, start_index):
        tag = match.group(0).lower()
        if tag.startswith("<div"):
            depth += 1
        elif tag.startswith("</div"):
            depth -= 1
            if depth == 0:
                return html[start_index:match.end()]
    raise RuntimeError("Could not extract full .top-bar block from index.html")

def extract_menu(index_html: str) -> str:
    start = index_html.find('<div class="top-bar" aria-label="GirlServ top navigation">')
    if start == -1:
        start = index_html.find('<div class="top-bar"')
    if start == -1:
        raise RuntimeError("Could not find .top-bar in index.html")
    return extract_balanced_div(index_html, start)

def extract_style_blocks(index_html: str) -> str:
    styles = re.findall(r"<style[^>]*>.*?</style>", index_html, flags=re.I | re.S)
    chosen = []
    for block in styles:
        if any(token in block for token in [".top-bar", ".top-nav", ".mini-logo", ".nav-preview", ".nav-text"]):
            chosen.append(block)
    if not chosen:
        raise RuntimeError("Could not find menu style block in index.html")
    return "\n".join(chosen)

def strip_old_injected_blocks(text: str) -> str:
    markers = [
        (STYLE_START, STYLE_END),
        (START_MARK, END_MARK),
        (SCRIPT_START, SCRIPT_END),
    ]
    for start, end in markers:
        text = re.sub(re.escape(start) + r".*?" + re.escape(end) + r"\s*", "", text, flags=re.S)

    old_patterns = [
        r'\n?<style id="girlserv-one-menu-style">.*?</style>\s*',
        r'\n?<script id="girlserv-one-menu-active-script">.*?</script>\s*',
        r'\n?<style id="girlserv-exact-index-menu-style">.*?</style>\s*',
        r'\n?<script id="girlserv-exact-index-menu-active-script">.*?</script>\s*',
        r'\n?<style id="gs-restored-menu-style">.*?</style>\s*',
        r'\n?<nav class="gs-restored-menu">.*?</nav>\s*',
        r'\n?<nav class="top-menu">.*?</nav>\s*',
    ]
    for pat in old_patterns:
        text = re.sub(pat, "\n", text, flags=re.S)

    start = text.find('<div class="top-bar" aria-label="GirlServ top navigation">')
    if start == -1:
        start = text.find('<div class="top-bar"')
    if start != -1:
        try:
            block = extract_balanced_div(text, start)
            text = text[:start] + "\n" + text[start + len(block):]
        except Exception:
            pass

    return text

def make_menu_work_for_root_pages(menu_html: str) -> str:
    menu = menu_html

    replacements = {
        'href="/"': 'href="index.html"',
        'href="/index.html"': 'href="index.html"',
        'href="/loudmouths"': 'href="loudmouths.html"',
        'href="/channel-trolls"': 'href="channel-trolls.html"',
        'href="/lol-lords"': 'href="lol-lords.html"',
        'href="/clickbait-crew"': 'href="clickbait-crew.html"',
        'href="/frequent-flyers"': 'href="frequent-flyers.html"',
        'href="/stat-dump"': 'href="stat-dump.html"',
        'href="/girls-notes"': 'href="girls-notes.html"',
        'href="/room-reports"': 'href="room-reports.html"',
        'href="/girlbook"': 'href="girlbook.html"',
    }

    for old, new in replacements.items():
        menu = menu.replace(old, new)

    return menu

def active_script() -> str:
    return """<script>
(function () {
  var path = window.location.pathname.split("/").pop() || "index.html";
  var map = {
    "": "index.html",
    "index": "index.html",
    "index.html": "index.html",
    "loudmouths": "loudmouths.html",
    "loudmouths.html": "loudmouths.html",
    "channel-trolls": "channel-trolls.html",
    "channel-trolls.html": "channel-trolls.html",
    "lol-lords": "lol-lords.html",
    "lol-lords.html": "lol-lords.html",
    "clickbait-crew": "clickbait-crew.html",
    "clickbait-crew.html": "clickbait-crew.html",
    "frequent-flyers": "frequent-flyers.html",
    "frequent-flyers.html": "frequent-flyers.html",
    "stat-dump": "stat-dump.html",
    "stat-dump.html": "stat-dump.html",
    "girls-notes": "girls-notes.html",
    "girls-notes.html": "girls-notes.html",
    "room-reports": "room-reports.html",
    "room-reports.html": "room-reports.html",
    "girlbook": "girlbook.html",
    "girlbook.html": "girlbook.html"
  };
  var current = map[path] || path;
  document.querySelectorAll(".top-nav-item[data-page]").forEach(function (item) {
    item.classList.toggle("is-current", item.getAttribute("data-page") === current);
  });
})();
</script>"""

def patch_page(path: Path, menu_html: str, styles_html: str) -> None:
    text = read(path)
    text = strip_old_injected_blocks(text)

    if "</head>" not in text or "</body>" not in text or re.search(r"<body[^>]*>", text, flags=re.I) is None:
        raise RuntimeError(f"{path.name} is missing head/body structure")

    style_block = STYLE_START + "\n" + styles_html + "\n" + STYLE_END + "\n"
    menu_block = START_MARK + "\n" + menu_html + "\n" + END_MARK + "\n"
    script_block = SCRIPT_START + "\n" + active_script() + "\n" + SCRIPT_END + "\n"

    text = text.replace("</head>", style_block + "\n</head>", 1)
    text = re.sub(r"(<body[^>]*>)", r"\1\n" + menu_block, text, count=1, flags=re.I)
    text = text.replace("</body>", script_block + "\n</body>", 1)
    write(path, text)

def main():
    if not INDEX.exists():
        raise SystemExit("index.html not found. Put this file in the repo root.")
    index_html = read(INDEX)
    menu_html = make_menu_work_for_root_pages(extract_menu(index_html))
    styles_html = extract_style_blocks(index_html)

    for name in PAGES:
        path = ROOT / name
        if path.exists():
            patch_page(path, menu_html, styles_html)
            print("patched", name)
        else:
            print("skipped", name, "(file not found)")

    print("done")

if __name__ == "__main__":
    main()
