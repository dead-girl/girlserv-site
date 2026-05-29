#!/usr/bin/env python3
"""
GirlServ unified menu builder.

Run this from the root of the GitHub repo.

What it does:
- Reads the REAL menu from index.html
- Copies that exact top-bar into every HTML page
- Copies the index.html style block that contains the real menu CSS
- Removes the older custom menus:
  - .top-menu
  - .gs-restored-menu
  - previous injected menu attempts
- Does NOT touch index.html
"""

from __future__ import print_function

import re
from pathlib import Path


ROOT = Path(".").resolve()
INDEX = ROOT / "index.html"

START_MARK = "<!-- GIRLSERV_SHARED_INDEX_MENU_START -->"
END_MARK = "<!-- GIRLSERV_SHARED_INDEX_MENU_END -->"

STYLE_START = "<!-- GIRLSERV_SHARED_INDEX_MENU_STYLE_START -->"
STYLE_END = "<!-- GIRLSERV_SHARED_INDEX_MENU_STYLE_END -->"

SCRIPT_START = "<!-- GIRLSERV_SHARED_INDEX_MENU_SCRIPT_START -->"
SCRIPT_END = "<!-- GIRLSERV_SHARED_INDEX_MENU_SCRIPT_END -->"


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path, text):
    path.write_text(text, encoding="utf-8")


def extract_balanced_div(html, start_index):
    """
    Extract one full <div>...</div> block, including nested divs.
    This avoids the broken regex problem where only the first inner </div> is copied.
    """
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

    raise RuntimeError("Could not find the full closing </div> for the top-bar menu.")


def extract_exact_index_menu(index_html):
    start = index_html.find('<div class="top-bar" aria-label="GirlServ top navigation">')
    if start == -1:
        start = index_html.find('<div class="top-bar"')
    if start == -1:
        raise RuntimeError("Could not find .top-bar in index.html")

    return extract_balanced_div(index_html, start)


def extract_index_menu_styles(index_html):
    """
    Copy the actual index style block that contains the menu CSS.
    This is intentionally not a recreated menu style.
    """
    styles = re.findall(r"<style[^>]*>.*?</style>", index_html, flags=re.I | re.S)
    chosen = []

    for block in styles:
        if (
            ".top-bar" in block
            or ".top-nav" in block
            or ".mini-logo" in block
            or ".nav-preview" in block
        ):
            chosen.append(block)

    if not chosen:
        raise RuntimeError("Could not find the menu CSS style block in index.html")

    return "\n".join(chosen)


def relative_prefix_for(path):
    rel = path.relative_to(ROOT)
    depth = len(rel.parts) - 1
    if depth <= 0:
        return ""
    return "../" * depth


def make_menu_work_from_this_file(menu_html, target_path):
    """
    Keep the exact copied menu structure/classes, but fix paths so it works from pages in folders.
    This only changes href/src URLs, not the design.
    """
    prefix = relative_prefix_for(target_path)

    menu = menu_html

    menu = menu.replace('src="assets/', 'src="' + prefix + 'assets/')
    menu = menu.replace("src='assets/", "src='" + prefix + "assets/")

    link_map = {
        'href="/"': 'href="' + prefix + 'index.html"',
        'href="/index.html"': 'href="' + prefix + 'index.html"',
        'href="/loudmouths"': 'href="' + prefix + 'doors/loudmouths.html"',
        'href="/channel-trolls"': 'href="' + prefix + 'doors/channel-trolls.html"',
        'href="/lol-lords"': 'href="' + prefix + 'doors/lol-lords.html"',
        'href="/clickbait-crew"': 'href="' + prefix + 'doors/clickbait-crew.html"',
        'href="/frequent-flyers"': 'href="' + prefix + 'doors/frequent-flyers.html"',
        'href="/stat-dump"': 'href="' + prefix + 'doors/stat-dump.html"',
        'href="/girls-notes"': 'href="' + prefix + 'doors/girls-notes.html"',
        'href="/room-reports"': 'href="' + prefix + 'doors/room-reports.html"',
        'href="/girlbook"': 'href="' + prefix + 'doors/the-girlbook.html"',
    }

    for old, new in link_map.items():
        menu = menu.replace(old, new)

    return menu


def remove_marked_blocks(text):
    patterns = [
        (STYLE_START, STYLE_END),
        (START_MARK, END_MARK),
        (SCRIPT_START, SCRIPT_END),
    ]

    for start, end in patterns:
        text = re.sub(
            re.escape(start) + r".*?" + re.escape(end) + r"\s*",
            "",
            text,
            flags=re.S,
        )

    return text


def remove_old_custom_menus(text):
    text = re.sub(r"\n?<style id=\"girlserv-one-menu-style\">.*?</style>\s*", "\n", text, flags=re.S)
    text = re.sub(r"\n?<script id=\"girlserv-one-menu-active-script\">.*?</script>\s*", "\n", text, flags=re.S)
    text = re.sub(r"\n?<style id=\"girlserv-exact-index-menu-style\">.*?</style>\s*", "\n", text, flags=re.S)
    text = re.sub(r"\n?<script id=\"girlserv-exact-index-menu-active-script\">.*?</script>\s*", "\n", text, flags=re.S)

    text = re.sub(r"\n?<style id=\"gs-restored-menu-style\">.*?</style>\s*", "\n", text, flags=re.S)
    text = re.sub(r"\n?<nav class=\"gs-restored-menu\">.*?</nav>\s*", "\n", text, flags=re.S)
    text = re.sub(r"\n?<nav class=\"top-menu\">.*?</nav>\s*", "\n", text, flags=re.S)

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


def active_script():
    return """<script>
(function () {
  var path = window.location.pathname.replace(/^\\/+|\\/+$/g, "");
  var file = path.split("/").pop() || "index.html";

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
    "girlbook": "the-girlbook.html",
    "the-girlbook": "the-girlbook.html",
    "the-girlbook.html": "the-girlbook.html"
  };

  var current = map[file] || map[path] || file;

  document.querySelectorAll(".top-nav-item[data-page]").forEach(function (item) {
    item.classList.toggle("is-current", item.getAttribute("data-page") === current);
  });
})();
</script>"""


def patch_page(path, exact_menu, exact_styles):
    text = read_text(path)

    text = remove_marked_blocks(text)
    text = remove_old_custom_menus(text)

    menu_for_page = make_menu_work_from_this_file(exact_menu, path)

    style_block = STYLE_START + "\n" + exact_styles + "\n" + STYLE_END + "\n"
    menu_block = START_MARK + "\n" + menu_for_page + "\n" + END_MARK + "\n"
    script_block = SCRIPT_START + "\n" + active_script() + "\n" + SCRIPT_END + "\n"

    if "</head>" not in text:
        raise RuntimeError(str(path) + " has no </head>")
    if re.search(r"<body[^>]*>", text, flags=re.I) is None:
        raise RuntimeError(str(path) + " has no <body>")
    if "</body>" not in text:
        raise RuntimeError(str(path) + " has no </body>")

    text = text.replace("</head>", style_block + "\n</head>", 1)
    text = re.sub(r"(<body[^>]*>)", r"\1\n" + menu_block, text, count=1, flags=re.I)
    text = text.replace("</body>", script_block + "\n</body>", 1)

    write_text(path, text)


def main():
    if not INDEX.exists():
        raise SystemExit("Run this from the GitHub repo root. index.html was not found.")

    index_html = read_text(INDEX)
    exact_menu = extract_exact_index_menu(index_html)
    exact_styles = extract_index_menu_styles(index_html)

    pages = []
    for path in ROOT.rglob("*.html"):
        rel = path.relative_to(ROOT)

        if ".git" in rel.parts:
            continue
        if path.name == "index.html":
            continue
        if ".backup" in path.name or path.name.endswith(".old"):
            continue

        pages.append(path)

    for page in sorted(pages):
        patch_page(page, exact_menu, exact_styles)
        print("patched", page.relative_to(ROOT))

    print("")
    print("DONE.")
    print("index.html was left untouched.")
    print("All other HTML pages now use the exact .top-bar menu copied from index.html.")


if __name__ == "__main__":
    main()
