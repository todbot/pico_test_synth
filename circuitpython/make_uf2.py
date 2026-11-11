#!/usr/bin/env python3
"""make_uf2.py -- build one UF2: CircuitPython firmware plus a prebuilt
CIRCUITPY drive holding an app and its libraries.

  python3 make_uf2.py adafruit-circuitpython-...uf2 wavesynth
  python3 make_uf2.py ...uf2 synthtools_polysynth -o polysynth.uf2

Needs picotool, circup, and folder2uf2
If using homebrew:  brew install picotool && pip3 install circup folder2uf2
"""

import argparse
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLASH_SIZES = {"rp2040": 2 * 1024 * 1024, "rp2350": 4 * 1024 * 1024}
# picotool's family names, as UF2 family ids
FAMILY_IDS = {"rp2040": 0xE48BFF56, "rp2350-arm-s": 0xE48BFF59,
              "rp2350-riscv": 0xE48BFF5A}
SKIP_NAMES = {"__pycache__", "README.md"}
UF2_MAGICS = (0x0A324655, 0x9E5D5157)
UF2_MAGIC_END = 0x0AB16F30
PAGE, SECTOR = 256, 4096


def pad_sectors(uf2_path):
    """Rewrite a UF2 so every 4K flash sector it touches is whole.

    The RP2040 bootrom re-erases a sector whose blocks straddle two of the
    host's 8K writes, losing its first pages. Unpadded, a firmware not
    ending on 4K puts every drive sector there, and CP reformats.
    """
    data = uf2_path.read_bytes()
    pages = {}
    for i in range(0, len(data), 512):
        _, _, flags, addr, size, _, _, family = struct.unpack_from(
            "<8I", data, i)
        if size != PAGE:
            sys.exit(f"{uf2_path}: block at {addr:#x} isn't {PAGE} bytes")
        pages[addr] = data[i + 32 : i + 32 + PAGE]
    blank = b"\xff" * PAGE
    sectors = sorted({a - a % SECTOR for a in pages})
    addrs = [s + p for s in sectors for p in range(0, SECTOR, PAGE)]
    out = bytearray()
    for n, addr in enumerate(addrs):
        out += struct.pack("<8I", *UF2_MAGICS, flags, addr, PAGE, n,
                           len(addrs), family)
        out += pages.get(addr, blank).ljust(476, b"\0")
        out += struct.pack("<I", UF2_MAGIC_END)
    uf2_path.write_bytes(out)


def fw_info(uf2_path):
    """Pull family, board, version, and CIRCUITPY start from picotool."""
    out = subprocess.run(["picotool", "info", "-a", str(uf2_path)],
                         check=True, capture_output=True, text=True).stdout
    def find(pat):
        m = re.search(pat, out, re.M)
        if not m:
            sys.exit(f"couldn't find {pat!r} in 'picotool info' output")
        return m.group(1)
    return {
        # picotool wraps long lines, so "family ID" can split
        "family": find(r"family\s+ID\s+'([\w-]+)'"),
        "board": find(r"BOARD=(\S+)"),
        "version": find(r"^\s*version:\s+(\S+)"),
        # only the start is trustworthy: the size CP reports is a fixed
        # 1MB, the real drive runs to the end of flash
        "drive_start": int(find(r"embedded drive:\s+(0x[0-9a-fA-F]+)"), 16),
    }


def stage_app(app_dir, req_path, stage, info, extras=()):
    """Lay out the CIRCUITPY contents in stage/."""
    ignore = lambda d, names: [n for n in names
                               if n.startswith(".") or n in SKIP_NAMES
                               or n.endswith(".uf2")]
    shutil.copytree(app_dir, stage, dirs_exist_ok=True, ignore=ignore)
    for extra in extras:
        if extra.is_dir():
            shutil.copytree(extra, stage / extra.name, dirs_exist_ok=True,
                            ignore=ignore)
        else:
            shutil.copy2(extra, stage / extra.name)
    (stage / "lib").mkdir(exist_ok=True)
    packages = []
    for line in req_path.read_text().splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        local = req_path.parent / line
        if local.is_dir():
            # a local package, imported from /lib
            shutil.copytree(local, stage / "lib" / local.name,
                            dirs_exist_ok=True, ignore=ignore)
        elif local.is_file():
            # an app's own copy of a module shadows ours
            if not (stage / local.name).exists():
                shutil.copy2(local, stage / local.name)
        else:
            packages.append(line)
    if packages:
        reqs = stage.parent / "circup_requirements.txt"
        reqs.write_text("\n".join(packages) + "\n")
        subprocess.run(["circup", "--path", str(stage),
                        "--board-id", info["board"],
                        "--cpy-version", info["version"],
                        "install", "-r", str(reqs)], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("firmware", type=Path, help="CircuitPython .uf2")
    ap.add_argument("app", type=Path, help="app dir, e.g. polysynth")
    ap.add_argument("-o", "--output", type=Path,
                    help="output .uf2 (default: <app>-<board>.uf2)")
    ap.add_argument("-r", "--requirements", type=Path,
                    default=HERE / "requirements.txt")
    ap.add_argument("-a", "--add", type=Path, action="append", default=[],
                    help="file or dir to also put in /, e.g. "
                         "wavesynth/wavetables (repeatable)")
    ap.add_argument("--flash-size", type=lambda s: int(s, 0),
                    help="flash bytes (default: 2MB rp2040, 4MB rp2350)")
    ap.add_argument("--full", action="store_true",
                    help="write the whole drive, wiping what was on it, "
                         "not just its used part")
    ap.add_argument("--keep", action="store_true",
                    help="keep the staging dir and print its path")
    args = ap.parse_args()

    info = fw_info(args.firmware)
    if info["family"] not in FAMILY_IDS:
        sys.exit(f"unknown family {info['family']!r}")
    chip = info["family"].split("-")[0]
    flash_size = args.flash_size or FLASH_SIZES[chip]
    out = args.output or Path(f"{args.app.resolve().name}-{info['board']}.uf2")

    tmp = Path(tempfile.mkdtemp(prefix="make_uf2_"))
    try:
        stage = tmp / "CIRCUITPY"
        stage_app(args.app, args.requirements, stage, info, args.add)
        # layout from the firmware itself, not folder2uf2's board table
        subprocess.run(["folder2uf2", "--combine", str(args.firmware),
                        "--flash-offset", hex(info["drive_start"]),
                        "--flash-size", hex(flash_size),
                        "--family-id", hex(FAMILY_IDS[info["family"]]),
                        *(["--full"] if args.full else []),
                        "-o", str(out), str(stage)], check=True)
        pad_sectors(out)
        print(f"{out}: CircuitPython {info['version']} for {info['board']}")
    finally:
        if args.keep:
            print(f"staging dir: {tmp}")
        else:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
