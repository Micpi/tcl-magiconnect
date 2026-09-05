"""Build a HACS integration ZIP and verify version alignment."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def build():
    component = ROOT / "custom_components/tcl_magiconnect"
    manifest = json.loads((component / "manifest.json").read_text(encoding="utf-8"))
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    # HACS explicitly rejects arbitrary fields, including a 'version' key.
    allowed = {"name", "homeassistant", "render_readme", "zip_release", "filename"}
    if set(hacs) - allowed:
        raise ValueError("Unexpected HACS metadata keys")
    filename = f"tcl_magiconnect-{manifest['version']}.zip"
    if hacs.get("filename") != filename or hacs.get("zip_release") is not True:
        raise ValueError("manifest.json version and hacs.json filename must agree")
    output = ROOT / "dist" / filename
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        paths = sorted(p for p in component.rglob("*") if p.suffix in {".py", ".json", ".yaml"})
        for path in paths + [ROOT / "LICENSE"]:
            name = path.relative_to(component).as_posix() if path != ROOT / "LICENSE" else "LICENSE"
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert json.loads(archive.read("manifest.json"))["version"] == manifest["version"]
        assert "__init__.py" in archive.namelist()
        assert "translations/fr.json" in archive.namelist()
    print(output)
    return output


if __name__ == "__main__":
    build()
