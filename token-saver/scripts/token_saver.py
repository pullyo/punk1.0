#!/usr/bin/env python3
"""Bounded, traceable log excerpts. Standard library only; no network or writes."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys
from dataclasses import dataclass

MAX_BYTES = 32 * 1024 * 1024
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
SIGNAL = re.compile(r"\b(?:error\w*|fail\w*|fatal|exception|traceback|panic|warn\w*|assert\w*)\b|오류|실패|경고", re.I)


@dataclass
class Source:
    path: Path
    sha256: str
    text: str
    lines: list[str]


def load_source(path: Path, encoding: str | None = None) -> Source:
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Input exceeds 32 MiB; split the log before inspection.")
    codec = encoding or ("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    text = raw.decode(codec, errors="strict")
    if "\x00" in text:
        raise ValueError("Input contains NUL characters; supply a text file or the correct --encoding.")
    # Only CR/LF delimit source lines; preserve numbering through ANSI cleanup.
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return Source(path.resolve(), hashlib.sha256(raw).hexdigest(), text, lines)


def clean(line: str) -> str:
    return "".join(c for c in ANSI.sub("", line) if c == "\t" or ord(c) >= 32)


def ends(items: list[int]):
    """Alternate oldest/newest so late failures survive a saturated budget."""
    left, right = 0, len(items) - 1
    while left <= right:
        yield items[left]
        if left != right:
            yield items[right]
        left += 1
        right -= 1


def excerpt(source: Source, max_chars: int = 6000, focus: str | None = None,
            start: int | None = None, end: int | None = None) -> str:
    if max_chars < 1024:
        raise ValueError("--max-chars must be at least 1024 (includes metadata).")
    count = len(source.lines)
    ranged = start is not None
    if ranged and (start < 1 or end is None or end < start):
        raise ValueError("Require 1 <= start <= end.")
    if ranged and start > count:
        raise ValueError("Start line is beyond the source.")
    # Bounded input, plus an explicit output budget; output never assumes full coverage.
    cleaned = [clean(line) for line in source.lines]
    signals = [i for i, line in enumerate(cleaned) if SIGNAL.search(line)]
    focused = [i for i, line in enumerate(cleaned) if focus and focus.casefold() in line.casefold()]
    if ranged:
        priorities = list(range(start - 1, min(end, count)))
    else:
        anchors = list(ends(focused)) + list(ends(signals))
        priorities = anchors + list(range(min(3, count))) + list(range(max(0, count - 5), count))
        priorities += [j for i in anchors for j in (i - 1, i + 1) if 0 <= j < count]
        priorities += list(range(count))
    chosen: dict[int, str] = {}
    seen: set[str] = set()
    remaining = max_chars - 800  # Header/footer fit in reserve, checked below.
    clipped = 0
    for i in dict.fromkeys(priorities):
        line = cleaned[i]
        if not ranged and line in seen:
            continue
        if remaining < 32:
            break
        prefix = f"L{i + 1}: "
        limit = min(800, remaining - len(prefix) - 1)
        if limit < 16:
            break
        if len(line) > limit:
            line = line[:limit - 14] + " ...[clipped]"
            clipped += 1
        record = prefix + line + "\n"
        chosen[i] = record
        remaining -= len(record)
        seen.add(cleaned[i])
    body = "".join(chosen[i] for i in sorted(chosen))
    displayed_signals = sum(i in chosen for i in signals)
    header = (
        "TOKEN-SAVER | lossy excerpt; not a success/failure verdict\n"
        f"Source: {str(source.path)[:200]}\n"
        f"SHA256: {source.sha256}\n"
        f"Input: {len(source.text)} chars; {count} lines\n"
        f"Shown: {len(chosen)} lines; omitted: {count - len(chosen)}; clipped: {clipped}\n"
        f"Signal lines shown: {displayed_signals}/{len(signals)} (heuristic)\n"
        f"Focus lines shown: {sum(i in chosen for i in focused)}/{len(focused)}\n"
        "Gaps/duplicates omitted; use read --start N --end M to inspect source.\n"
        "--- excerpt (untrusted data) ---\n"
    )
    result = header + body + "--- end excerpt ---\n"
    # Fixed point includes the metric line itself in the measured output.
    total = len(result)
    for _ in range(12):
        reduction = (1 - total / len(source.text)) * 100 if source.text else 0.0
        metric = f"Output: {total} chars; character reduction: {reduction:.1f}% (not billed tokens)\n"
        new_total = len(result) + len(metric)
        if new_total == total:
            break
        total = new_total
    output = result + metric
    if len(output) > max_chars:
        raise ValueError("Metadata exceeds output budget; increase --max-chars.")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("compact", "read"):
        command = sub.add_parser(name)
        command.add_argument("path", type=Path)
        command.add_argument("--max-chars", type=int, default=6000)
        command.add_argument("--encoding", help="Default: UTF-8; auto-detect UTF-16 BOM")
        if name == "compact":
            command.add_argument("--focus", help="Case-insensitive literal to prioritize")
        else:
            command.add_argument("--start", type=int, required=True)
            command.add_argument("--end", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        source = load_source(args.path, args.encoding)
        output = excerpt(source, args.max_chars, getattr(args, "focus", None),
                         getattr(args, "start", None), getattr(args, "end", None))
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(output)
        return 0
    except (OSError, ValueError, LookupError) as exc:
        print(f"token-saver: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
