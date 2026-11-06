"""Check local paths and heading anchors in the reviewed source documentation."""
from __future__ import annotations

from collections import Counter
import html
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.package_source import source_files


def prose(text):
    """Ignore fenced examples without treating shell comments as headings."""
    marker = None
    for number, line in enumerate(text.splitlines(), 1):
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            token = fence[1]
            if marker is None:
                marker = token
            elif token[0] == marker[0] and len(token) >= len(marker):
                marker = None
            continue
        if marker is None:
            yield number, line


def anchors(text):
    result, counts = set(), Counter()
    for _, line in prose(text):
        for match in re.finditer(r'<(?:a|h[1-6])\b[^>]*\b(?:id|name)=["\']([^"\']+)["\']', line):
            result.add(match[1])
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        title = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", match[1])
        title = html.unescape(re.sub(r"<[^>]*>", "", title)).lower()
        slug = re.sub(r"[^\w\-\s]", "", title, flags=re.UNICODE).replace(" ", "-")
        count = counts[slug]
        counts[slug] += 1
        result.add(slug + ("-" + str(count) if count else ""))
    return result


def check_documents(root, files):
    """Return actionable failures; a file existing outside the archive is insufficient."""
    root = Path(root).resolve()
    included = {Path(path).resolve() for path in files}
    documents = {path: path.read_text(encoding="utf-8-sig") for path in included if path.suffix == ".md"}
    headings = {path: anchors(text) for path, text in documents.items()}
    errors, links = [], 0
    for path, text in sorted(documents.items()):
        for number, line in prose(text):
            for match in re.finditer(r"\]\(([^)\n]+)\)", line):
                destination = match[1].strip().split(' "', 1)[0].strip("<>")
                url = urlsplit(destination)
                if url.scheme or url.netloc:
                    continue
                links += 1
                target = (path.parent / unquote(url.path)).resolve() if url.path else path
                label = f"{path.relative_to(root).as_posix()}:{number}"
                if not target.is_relative_to(root) or target not in included:
                    errors.append(f"{label}: local target is not in the reviewed source: {destination}")
                elif url.fragment and target.suffix == ".md" and unquote(url.fragment) not in headings[target]:
                    errors.append(f"{label}: missing heading anchor: {destination}")
    return len(documents), links, errors


def main():
    try:
        documents, links, errors = check_documents(ROOT, source_files(ROOT))
    except (OSError, ValueError, UnicodeError) as error:
        print(f"Documentation check failed: {error}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"Validated {documents} Markdown documents and {links} local links/anchors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
