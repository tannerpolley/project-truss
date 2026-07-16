#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from package_provenance import load_runtime_package, runtime_manifest, validate_runtime_reads


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    package = load_runtime_package(root)
    entries = runtime_manifest(root)
    findings = validate_runtime_reads(root, package)
    print(json.dumps({"ok": not findings, "phase": "runtime-package", "files": len(entries), "bytes": sum(entry.length for entry in entries), "findings": findings}, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
