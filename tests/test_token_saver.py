import hashlib
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "token-saver/scripts/token_saver.py"

spec = importlib.util.spec_from_file_location(
    "token_saver",
    SCRIPT,
)

module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class TokenSaverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "build.log"

    def source(self, text):
        self.path.write_text(
            text,
            encoding="utf-8",
        )
        return module.load_source(self.path)

    def test_source_header_hides_absolute_path(self):
        output = module.excerpt(
            self.source("error test\n")
        )

        self.assertIn(
            "Source: build.log",
            output,
        )

        self.assertNotIn(
            str(self.path.parent),
            output,
        )

    def test_middle_and_final_failure_survive(self):
        lines = [
            f"step {i}: processing module"
            for i in range(10000)
        ]

        lines[4500] = (
            "error TS2345: argument invalid"
        )

        lines[-1] = "FAIL final suite"

        output = module.excerpt(
            self.source("\n".join(lines)),
            2000,
        )

        self.assertIn(
            "L4501: error TS2345",
            output,
        )

        self.assertIn(
            "L10000: FAIL final suite",
            output,
        )

        self.assertLessEqual(
            len(output),
            2000,
        )

    def test_saturated_errors_keep_both_ends_and_disclose_omission(self):
        output = module.excerpt(
            self.source(
                "\n".join(
                    f"error {i}"
                    for i in range(1000)
                )
            ),
            1400,
        )

        self.assertIn(
            "L1: error 0",
            output,
        )

        self.assertIn(
            "L1000: error 999",
            output,
        )

        match = re.search(
            r"Signal lines shown: (\d+)/1000",
            output,
        )

        self.assertIsNotNone(match)

        self.assertLess(
            int(match[1]),
            1000,
        )

    def test_literal_focus_has_priority(self):
        output = module.excerpt(
            self.source(
                "noise\n" * 500
                + "needle [x] 한글\n"
            ),
            1024,
            "[x]",
        )

        self.assertIn(
            "L501: needle [x] 한글",
            output,
        )

    def test_ansi_and_utf16_preserve_source_numbering_and_hash(self):
        raw = (
            "시작\r\n"
            "\x1b[31m오류 발생\x1b[0m\r\n"
        ).encode("utf-16")

        self.path.write_bytes(raw)

        source = module.load_source(
            self.path
        )

        output = module.excerpt(source)

        self.assertIn(
            "L2: 오류 발생",
            output,
        )

        self.assertNotIn(
            "\x1b",
            output,
        )

        self.assertIn(
            hashlib.sha256(raw).hexdigest(),
            output,
        )

        self.assertEqual(
            raw,
            self.path.read_bytes(),
        )

    def test_exact_duplicates_collapsed_only_in_compact(self):
        source = self.source(
            "same\nsame\nsame\n"
        )

        self.assertEqual(
            module.excerpt(source).count(
                ": same\n"
            ),
            1,
        )

        self.assertEqual(
            module.excerpt(
                source,
                start=1,
                end=3,
            ).count(": same\n"),
            3,
        )

    def test_retrieve_omitted_range(self):
        source = self.source(
            "\n".join(
                f"content {i}"
                for i in range(1000)
            )
        )

        output = module.excerpt(
            source,
            start=450,
            end=452,
        )

        self.assertIn(
            "L450: content 449",
            output,
        )

        self.assertIn(
            "L452: content 451",
            output,
        )

        self.assertNotIn(
            "L453:",
            output,
        )

    def test_long_lines_bounded_and_disclosed(self):
        for size in (
            1024,
            1400,
            6000,
        ):
            output = module.excerpt(
                self.source(
                    "error "
                    + "가" * 100000
                ),
                size,
            )

            self.assertLessEqual(
                len(output),
                size,
            )

            self.assertIn(
                "[clipped]",
                output,
            )

            self.assertIn(
                "clipped: 1",
                output,
            )

    def test_metrics_include_all_output_characters(self):
        output = module.excerpt(
            self.source(
                "noise\n" * 10000
            )
        )

        match = re.search(
            r"Output: (\d+) chars",
            output,
        )

        self.assertIsNotNone(match)

        self.assertEqual(
            int(match[1]),
            len(output),
        )

        self.assertIn(
            "not billed tokens",
            output,
        )

    def test_empty_input_is_not_success_verdict(self):
        output = module.excerpt(
            self.source("")
        )

        self.assertIn(
            "0 lines",
            output,
        )

        self.assertIn(
            "not a success/failure verdict",
            output,
        )

    def test_invalid_range_and_budget(self):
        source = self.source(
            "one\n"
        )

        invalid_cases = (
            {
                "start": 0,
                "end": 1,
            },
            {
                "start": 2,
                "end": 3,
            },
            {
                "start": 1,
                "end": 0,
            },
            {
                "max_chars": 100,
            },
        )

        for kwargs in invalid_cases:
            with self.assertRaises(
                ValueError
            ):
                module.excerpt(
                    source,
                    **kwargs,
                )

    def test_binary_and_invalid_encoding_rejected(self):
        self.path.write_bytes(
            b"abc\x00def"
        )

        with self.assertRaises(
            ValueError
        ):
            module.load_source(
                self.path
            )

        self.path.write_bytes(
            b"\xffabc"
        )

        with self.assertRaises(
            UnicodeError
        ):
            module.load_source(
                self.path
            )

    def test_cli_error_and_success(self):
        missing = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "compact",
                str(self.path),
            ],
            capture_output=True,
        )

        self.assertEqual(
            missing.returncode,
            2,
        )

        self.source(
            "오류: test failure\n"
        )

        run = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "compact",
                str(self.path),
            ],
            capture_output=True,
        )

        self.assertEqual(
            run.returncode,
            0,
        )

        self.assertIn(
            "오류",
            run.stdout.decode("utf-8"),
        )

    def test_oversized_input_rejected(self):
        with self.path.open(
            "wb"
        ) as stream:
            stream.seek(
                module.MAX_BYTES
            )
            stream.write(b"x")

        with self.assertRaises(
            ValueError
        ):
            module.load_source(
                self.path
            )


if __name__ == "__main__":
    unittest.main()