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

ANSI = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
)

SIGNAL = re.compile(
    r"\b(?:error\w*|fail\w*|fatal|exception|traceback|panic|warn\w*|assert\w*)\b"
    r"|오류|실패|경고",
    re.I,
)


@dataclass
class Source:
    path: Path
    sha256: str
    text: str
    lines: list[str]


def load_source(
    path: Path,
    encoding: str | None = None,
) -> Source:
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)

    if len(raw) > MAX_BYTES:
        raise ValueError(
            "Input exceeds 32 MiB; split the log before inspection."
        )

    codec = encoding or (
        "utf-16"
        if raw.startswith((b"\xff\xfe", b"\xfe\xff"))
        else "utf-8-sig"
    )

    text = raw.decode(codec, errors="strict")

    if "\x00" in text:
        raise ValueError(
            "Input contains NUL characters; "
            "supply a text file or the correct --encoding."
        )

    # Only CR/LF delimit source lines;
    # preserve numbering through ANSI cleanup.
    lines = (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .split("\n")
    )

    if lines and lines[-1] == "":
        lines.pop()

    return Source(
        path=path.resolve(),
        sha256=hashlib.sha256(raw).hexdigest(),
        text=text,
        lines=lines,
    )


def clean(line: str) -> str:
    return "".join(
        c
        for c in ANSI.sub("", line)
        if c == "\t" or ord(c) >= 32
    )


def ends(items: list[int]):
    """
    Alternate oldest/newest so late failures
    survive a saturated budget.
    """
    left = 0
    right = len(items) - 1

    while left <= right:
        yield items[left]

        if left != right:
            yield items[right]

        left += 1
        right -= 1


def excerpt(
    source: Source,
    max_chars: int = 6000,
    focus: str | None = None,
    start: int | None = None,
    end: int | None = None,
) -> str:
    if max_chars < 1024:
        raise ValueError(
            "--max-chars must be at least 1024 "
            "(includes metadata)."
        )

    count = len(source.lines)
    ranged = start is not None

    if ranged and (
        start < 1
        or end is None
        or end < start
    ):
        raise ValueError(
            "Require 1 <= start <= end."
        )

    if ranged and start > count:
        raise ValueError(
            "Start line is beyond the source."
        )

    #
    # Scan the source once to identify signal/focus lines.
    #
    # We intentionally do not build a second `cleaned`
    # list containing the entire log. Lines are cleaned
    # again only when actually selected for output.
    #
    signals: list[int] = []
    focused: list[int] = []

    focus_folded = (
        focus.casefold()
        if focus
        else None
    )

    for i, raw_line in enumerate(source.lines):
        line = clean(raw_line)

        if SIGNAL.search(line):
            signals.append(i)

        if (
            focus_folded is not None
            and focus_folded in line.casefold()
        ):
            focused.append(i)

    def anchor_indices():
        """
        Yield focus hits first, then heuristic signal hits.

        Each group alternates between its oldest and
        newest entries to preserve late failures when
        the output budget becomes saturated.
        """
        yield from ends(focused)
        yield from ends(signals)

    def candidate_indices():
        """
        Yield candidate source-line indexes lazily.

        The previous implementation appended
        `list(range(count))` to a priorities list,
        which could allocate a very large list for
        logs containing millions of short lines.

        range() itself is lazy, so yielding from it
        avoids that extra allocation.
        """
        if ranged:
            yield from range(
                start - 1,
                min(end, count),
            )
            return

        # 1. Explicit focus and detected error/warning lines.
        yield from anchor_indices()

        # 2. Beginning of the log.
        yield from range(
            min(3, count)
        )

        # 3. End of the log.
        yield from range(
            max(0, count - 5),
            count,
        )

        # 4. Context immediately surrounding anchors.
        for i in anchor_indices():
            before = i - 1
            after = i + 1

            if 0 <= before < count:
                yield before

            if 0 <= after < count:
                yield after

        # 5. Fall back to scanning remaining source lines.
        #
        # Important: range(count) is not converted into
        # list(range(count)).
        yield from range(count)

    chosen: dict[int, str] = {}

    #
    # Same textual line is shown once in compact mode.
    # Range reads intentionally retain duplicates.
    #
    seen: set[str] = set()

    #
    # Track source indexes already considered.
    #
    # This replaces dict.fromkeys(priorities).
    #
    visited: set[int] = set()

    remaining = max_chars - 800

    # Header/footer fit in reserve,
    # checked again before returning.
    clipped = 0

    for i in candidate_indices():
        if i in visited:
            continue

        visited.add(i)

        line = clean(source.lines[i])

        if not ranged and line in seen:
            continue

        if remaining < 32:
            break

        prefix = f"L{i + 1}: "

        limit = min(
            800,
            remaining - len(prefix) - 1,
        )

        if limit < 16:
            break

        if len(line) > limit:
            line = (
                line[: limit - 14]
                + " ...[clipped]"
            )
            clipped += 1

        record = (
            prefix
            + line
            + "\n"
        )

        chosen[i] = record
        remaining -= len(record)

        if not ranged:
            seen.add(line)

    body = "".join(
        chosen[i]
        for i in sorted(chosen)
    )

    displayed_signals = sum(
        i in chosen
        for i in signals
    )

    #
    # Only expose the filename in model-visible output.
    #
    # Internally Source.path still retains the full
    # resolved path when needed by the program.
    #
    source_name = source.path.name[:200]

    header = (
        "TOKEN-SAVER | lossy excerpt; "
        "not a success/failure verdict\n"
        f"Source: {source_name}\n"
        f"SHA256: {source.sha256}\n"
        f"Input: {len(source.text)} chars; "
        f"{count} lines\n"
        f"Shown: {len(chosen)} lines; "
        f"omitted: {count - len(chosen)}; "
        f"clipped: {clipped}\n"
        f"Signal lines shown: "
        f"{displayed_signals}/{len(signals)} "
        "(heuristic)\n"
        f"Focus lines shown: "
        f"{sum(i in chosen for i in focused)}"
        f"/{len(focused)}\n"
        "Gaps/duplicates omitted; "
        "use read --start N --end M "
        "to inspect source.\n"
        "--- excerpt (untrusted data) ---\n"
    )

    result = (
        header
        + body
        + "--- end excerpt ---\n"
    )

    #
    # Fixed point includes the metric line itself
    # in the measured output.
    #
    total = len(result)

    for _ in range(12):
        reduction = (
            (1 - total / len(source.text)) * 100
            if source.text
            else 0.0
        )

        metric = (
            f"Output: {total} chars; "
            f"character reduction: "
            f"{reduction:.1f}% "
            "(not billed tokens)\n"
        )

        new_total = (
            len(result)
            + len(metric)
        )

        if new_total == total:
            break

        total = new_total

    output = result + metric

    if len(output) > max_chars:
        raise ValueError(
            "Metadata exceeds output budget; "
            "increase --max-chars."
        )

    return output


def main(
    argv: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    for name in ("compact", "read"):
        command = sub.add_parser(name)

        command.add_argument(
            "path",
            type=Path,
        )

        command.add_argument(
            "--max-chars",
            type=int,
            default=6000,
        )

        command.add_argument(
            "--encoding",
            help=(
                "Default: UTF-8; "
                "auto-detect UTF-16 BOM"
            ),
        )

        if name == "compact":
            command.add_argument(
                "--focus",
                help=(
                    "Case-insensitive literal "
                    "to prioritize"
                ),
            )
        else:
            command.add_argument(
                "--start",
                type=int,
                required=True,
            )

            command.add_argument(
                "--end",
                type=int,
                required=True,
            )

    args = parser.parse_args(argv)

    try:
        source = load_source(
            args.path,
            args.encoding,
        )

        output = excerpt(
            source,
            args.max_chars,
            getattr(
                args,
                "focus",
                None,
            ),
            getattr(
                args,
                "start",
                None,
            ),
            getattr(
                args,
                "end",
                None,
            ),
        )

        if hasattr(
            sys.stdout,
            "reconfigure",
        ):
            sys.stdout.reconfigure(
                encoding="utf-8",
            )

        sys.stdout.write(output)

        return 0

    except (
        OSError,
        ValueError,
        LookupError,
    ) as exc:
        print(
            f"token-saver: {exc}",
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())