"""Reproducible synthetic output-volume benchmark, not a billing benchmark."""
import json
from pathlib import Path
import tempfile
from test_token_saver import module, ROOT


def main():
    fixtures = {
        "repeated-build": "Compiling module...\n" * 10000 + "ERROR src/app.ts:42 missing export\n",
        "unique-test-log": "\n".join(f"PASS suite_{i}: 12 assertions completed" for i in range(5000)) + "\nFAIL suite_final: expected 2 received 1\n",
        "korean-log": "작업을 처리하고 있습니다.\n" * 5000 + "오류: 데이터 연결 실패\n",
        "short-output": "All 3 tests passed.\n",
    }
    results = []
    with tempfile.TemporaryDirectory() as temp:
        for name, text in fixtures.items():
            path = Path(temp) / f"{name}.log"
            path.write_text(text, encoding="utf-8")
            output = module.excerpt(module.load_source(path))
            results.append({"case": name, "input_chars": len(text), "output_chars": len(output),
                            "character_reduction_percent": round((1-len(output)/len(text))*100, 2)})
    report = {"method": "Synthetic fixtures; 6000-character cap including metadata. Excludes skill/prompt overhead and subsequent reads; does not measure actual tokens or billing.", "results": results}
    target = ROOT / "BENCHMARK.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
