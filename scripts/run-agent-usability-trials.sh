#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ "${1:-}" == "-DispatchProbe" || "${1:-}" == "--dispatch-probe" ]]; then
  exec "$root/scripts/lib/run-script.sh" "${BASH_SOURCE[0]}" "$@"
fi
exec python3 "$root/scripts/run-agent-usability-trials.py" "$@"
