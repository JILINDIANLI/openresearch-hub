#!/usr/bin/env bash
set -Eeuo pipefail
if [[ $# -ne 1 || ! -f "$1" ]]; then echo "Usage: $0 gitea-dump.zip" >&2; exit 2; fi
echo "Gitea restore replaces application data. Stop service and snapshot gitea_data first; follow deploy/README.md."
echo "Automated restore is intentionally not run against a live persistent volume."
exit 3
