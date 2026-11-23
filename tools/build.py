#!/usr/bin/env python3
"""Build a `.cindy` theme package from this repository.

Self-contained: needs Python 3 only, no Cindy internals. It validates the
manifest, theme documents and assets, then writes `dist/<name>.cindy` as a ZIP
archive whose entries live at the archive root.

    python tools/build.py                # validate + build
    python tools/build.py --check        # validate only
    python tools/build.py --out /tmp/x.cindy

Checks are intentionally conservative and mirror the rules that make Cindy
reject or mis-render a theme:

* manifest: formatVersion 2, type "theme", unique portable paths
* theme docs: id/name/type/family, one variant per mode per family
* colour tokens: every value is a string; tokens Cindy reads as HSL parts
  (`hsl(var(--x))`) must carry HSL components, everything else a full colour
* appearance: allowed fields and value ranges, `asset:<id>` references resolve
  to a declared resource of the matching kind
* assets: portable relative paths, size and megapixel limits, brand images exist
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORMATS = json.loads((ROOT / "tools" / "token-formats.json").read_text(encoding="utf-8"))["tokens"]

LIMITS = {
    "font": 10 * 1024 * 1024,
    "image": 20 * 1024 * 1024,
    "video": 100 * 1024 * 1024,
}
TOTAL_LIMIT = 256 * 1024 * 1024

HSL_TRIPLET = re.compile(r"^\d+(?:\.\d+)?\s+\d+(?:\.\d+)?%\s+\d+(?:\.\d+)?%$")
HSL_ALIAS = re.compile(r"^var\(--[a-z0-9-]+-hsl\)$")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
BAD_PATH = re.compile(r'[\\:<>"|?*\x00-\x1f]')

APPEARANCE_FIELDS = {
    "uiFont", "codeFont", "bodyFont", "terminalFont",
    "wallpaper", "reading", "contentStyle", "density", "motion",
}


def is_portable(value: str) -> bool:
    if not isinstance(value, str) or not 0 < len(value) <= 4096 or BAD_PATH.search(value):
        return False
    return all(
        part not in ("", ".", "..") and not part.endswith((".", " "))
        and not re.match(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", part, re.I)
        for part in value.split("/")
    )


def image_megapixels(path: pathlib.Path) -> float | None:
    """Read PNG/JPEG/WebP dimensions without decoding pixels."""
    head = path.read_bytes()[:32]
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", head[16:24])
        return w * h / 1e6
    if head[:2] == b"\xff\xd8":
        data = path.read_bytes()
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w * h / 1e6
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seg
        return None
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return None
    return None


def validate(root: pathlib.Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    manifest_path = root / "cindy.json"
    if not manifest_path.is_file():
        return [f"missing {manifest_path}"], warnings
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("formatVersion") != 2 or manifest.get("type") != "theme":
        errors.append('cindy.json: expected formatVersion 2 and type "theme"')

    docs = manifest.get("themes") or []
    if not docs:
        errors.append("cindy.json: themes must list at least one document")
    if len(set(docs)) != len(docs):
        errors.append("cindy.json: themes contains duplicates")
    for name in docs:
        if not is_portable(name) or not (root / name).is_file():
            errors.append(f"cindy.json: theme document missing or not portable: {name}")

    resources: dict[str, dict] = {}
    for res in manifest.get("resources", []):
        rid, kind, path = res.get("id"), res.get("kind"), res.get("path")
        if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", rid):
            errors.append(f"cindy.json: bad resource id: {rid}")
            continue
        if rid in resources:
            errors.append(f"cindy.json: duplicate resource id: {rid}")
        if kind not in LIMITS:
            errors.append(f"cindy.json: resource {rid} has unknown kind: {kind}")
        if not is_portable(str(path)) or not (root / str(path)).is_file():
            errors.append(f"cindy.json: resource {rid} path missing or not portable: {path}")
            continue
        size = (root / path).stat().st_size
        if size > LIMITS[kind]:
            errors.append(f"assets: {path} exceeds the {kind} limit ({size} bytes)")
        if kind == "image":
            mp = image_megapixels(root / path)
            if mp and mp > 40:
                errors.append(f"assets: {path} is {mp:.1f} MP, over the 40 MP limit")
        resources[rid] = {"kind": kind, "path": path}

    variants: set[tuple[str, str]] = set()
    ids: set[str] = set()
    total = sum((root / r["path"]).stat().st_size for r in resources.values() if (root / r["path"]).is_file())

    for name in docs:
        if not (root / name).is_file():
            continue
        doc = json.loads((root / name).read_text(encoding="utf-8"))
        label = f"{name}"
        for field in ("id", "name"):
            if not isinstance(doc.get(field), str) or not doc[field].strip():
                errors.append(f"{label}: {field} must be a non-empty string")
        if doc.get("id") in ids:
            errors.append(f"{label}: duplicate theme id {doc.get('id')}")
        ids.add(doc.get("id"))
        mode = doc.get("type")
        if mode not in ("light", "dark"):
            errors.append(f"{label}: type must be light or dark")
        family = doc.get("family")
        if isinstance(family, str) and family.strip() and mode in ("light", "dark"):
            key = (family.strip(), mode)
            if key in variants:
                errors.append(f"{label}: duplicate {mode} variant in family {family}")
            variants.add(key)

        colors = doc.get("colors")
        if not isinstance(colors, dict):
            errors.append(f"{label}: colors must be an object")
            colors = {}
        for key, value in colors.items():
            if not isinstance(value, str):
                errors.append(f"{label}: colors.{key} must be a string")
                continue
            expected = FORMATS.get(key)
            if expected == "hsl":
                looks_hsl = HSL_TRIPLET.match(value) or HSL_ALIAS.match(value)
                if not looks_hsl:
                    hint = " (a hex colour here silently drops the declaration -> currentColor, e.g. a black hairline)" if HEX.match(value) else ""
                    warnings.append(f"{label}: colors.{key} is read as hsl(var(--{key})); write HSL parts like `45 40% 92%`{hint}")
            elif expected == "color" and HSL_TRIPLET.match(value):
                warnings.append(f"{label}: colors.{key} is read as a full colour; HSL parts will be ignored")

        brand = doc.get("brand") or {}
        for role in ("icon", "logo"):
            value = brand.get(role)
            if value is None:
                continue
            if not is_portable(str(value)) or not (root / str(value)).is_file():
                errors.append(f"{label}: brand.{role} missing or not portable: {value}")
            elif (root / value).stat().st_size > 20 * 1024 * 1024:
                errors.append(f"{label}: brand.{role} exceeds 20 MiB")
            else:
                total += (root / value).stat().st_size

        appearance = doc.get("appearance")
        if appearance is None:
            continue
        extra = set(appearance) - APPEARANCE_FIELDS
        if extra:
            errors.append(f"{label}: unknown appearance fields: {', '.join(sorted(extra))}")
        for slot in ("uiFont", "codeFont", "bodyFont", "terminalFont"):
            font = appearance.get(slot)
            if not isinstance(font, dict):
                continue
            ref = font.get("resource")
            if ref:
                if not str(ref).startswith("asset:"):
                    errors.append(f"{label}: {slot}.resource must be asset:<id>")
                else:
                    rid = str(ref).split(":", 1)[1]
                    if rid not in resources:
                        errors.append(f"{label}: {slot} references undeclared resource {rid}")
                    elif resources[rid]["kind"] != "font":
                        errors.append(f"{label}: {slot} references {rid}, which is not a font")
        wall = appearance.get("wallpaper")
        if isinstance(wall, dict):
            ref = wall.get("resource")
            if ref:
                rid = str(ref).split(":", 1)[1]
                if rid not in resources:
                    errors.append(f"{label}: wallpaper references undeclared resource {rid}")
                elif resources[rid]["kind"] not in ("image", "video"):
                    errors.append(f"{label}: wallpaper must reference an image or video")
            vis = wall.get("visibility")
            if vis is not None and not 0 <= float(vis) <= 1:
                errors.append(f"{label}: wallpaper.visibility must be 0..1")
            blur = wall.get("blur")
            if blur is not None and not 0 <= float(blur) <= 20:
                errors.append(f"{label}: wallpaper.blur must be 0..20px")
            if wall.get("motion") not in (None, "static", "dynamic"):
                errors.append(f'{label}: wallpaper.motion must be "static" or "dynamic"')

    if total > TOTAL_LIMIT:
        errors.append(f"package would exceed 256 MiB uncompressed ({total} bytes)")
    return errors, warnings


def build(root: pathlib.Path, out: pathlib.Path) -> None:
    manifest = json.loads((root / "cindy.json").read_text(encoding="utf-8"))
    entries: list[str] = ["cindy.json", *manifest["themes"]]
    for res in manifest.get("resources", []):
        entries.append(res["path"])
    for name in manifest["themes"]:
        brand = json.loads((root / name).read_text(encoding="utf-8")).get("brand") or {}
        entries += [v for v in brand.values() if isinstance(v, str)]

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(entries)):
            archive.write(root / path, path)
    print(f"built {out} ({out.stat().st_size} bytes, {len(set(entries))} entries)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "dist" / "wind-valley.cindy")
    parser.add_argument("--check", action="store_true", help="validate only, do not write an archive")
    args = parser.parse_args()

    errors, warnings = validate(ROOT)
    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    if errors:
        print(f"\n{len(errors)} error(s); nothing built.")
        return 1
    print(f"validation passed ({len(warnings)} warning(s))")
    if not args.check:
        build(ROOT, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
