"""Build a deterministic plugin ZIP with no test logs or bytecode."""
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
plugin = root / "token-saver"
files = [".codex-plugin/plugin.json", "skills/token-saver/SKILL.md", "scripts/token_saver.py"]
manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
version = manifest.get("version")
if not isinstance(version, str) or re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+-]*", version) is None:
    raise ValueError("plugin.json must contain a safe, non-empty version string")
target = root / f"dist/token-saver-{version}.zip"
target.parent.mkdir(exist_ok=True)
with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
    for name in files:
        info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        archive.writestr(info, (plugin / name).read_bytes())
with ZipFile(target) as archive:
    corrupt_member = archive.testzip()
    if corrupt_member is not None:
        raise RuntimeError(f"Corrupt ZIP member: {corrupt_member}")
    if archive.namelist() != files:
        raise RuntimeError("ZIP contents do not match the expected plugin files")
    for name in files:
        if archive.read(name) != (plugin / name).read_bytes():
            raise RuntimeError(f"ZIP member differs from source: {name}")
print(f"Created {target}\nSHA256: {hashlib.sha256(target.read_bytes()).hexdigest()}")
