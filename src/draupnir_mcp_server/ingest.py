from __future__ import annotations
import argparse
import zipfile
from pathlib import Path

def unzip(zip_path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)

def main(argv=None):
    parser = argparse.ArgumentParser(description="Unzip Draupnir repo into data dir")
    parser.add_argument("--zip", required=True, help="Path to draupnir ZIP file")
    parser.add_argument("--dest", default="data", help="Destination directory")
    args = parser.parse_args(argv)

    zip_path = Path(args.zip).expanduser().resolve()
    dest = Path(args.dest).expanduser().resolve()

    if not zip_path.exists():
        raise SystemExit(f"ZIP not found: {zip_path}")

    unzip(zip_path, dest)
    print(f"Unzipped {zip_path} -> {dest}")

if __name__ == "__main__":
    main()
