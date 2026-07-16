#!/usr/bin/env bash
set -euo pipefail

if (($# < 1)); then
  echo "usage: run-script.sh <script-path> [args...]" >&2
  exit 64
fi

script_path="$1"
shift

if [[ "$script_path" != /* ]]; then
  script_path="$(pwd -P)/$script_path"
fi

search_dir="$(cd "$(dirname "$script_path")" && pwd -P)"
repo_root=""
while [[ "$search_dir" != "/" ]]; do
  if [[ -f "$search_dir/.codex-plugin/plugin.json" && -d "$search_dir/scripts" ]]; then
    repo_root="$search_dir"
    break
  fi
  search_dir="$(dirname "$search_dir")"
done

if [[ -z "$repo_root" ]]; then
  echo "Could not locate Project Truss plugin root for $script_path" >&2
  exit 127
fi

exec python3 "$repo_root/scripts/lib/project_truss_cli.py" "$script_path" "$@"
