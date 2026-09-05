"""Build a deterministic plugin ZIP with no test logs or bytecode."""
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
plugin = root / "token-saver"
files = [".codex-plugin/plugin.json", "skills/token-saver/SKILL.md", "scripts/token_saver.py"]
target = root / "dist/token-saver-0.1.0.zip"
target.parent.mkdir(exist_ok=True)
with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
    for name in files:
        info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        archive.writestr(info, (plugin / name).read_bytes())
with ZipFile(target) as archive:
    assert archive.testzip() is None
    assert archive.namelist() == files
    for name in files:
        assert archive.read(name) == (plugin / name).read_bytes()
print(f"Created {target}\nSHA256: {hashlib.sha256(target.read_bytes()).hexdigest()}")
