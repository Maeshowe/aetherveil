#!/bin/bash
# OBSIDIAN MM — Sync production data from Mac Mini to local dev environment.
#
# Pulls the Parquet cache, logs, and output from the Mac Mini deployment
# to the local MacBook for dashboard development and analysis.
#
# Usage:
#   bash scripts/sync_from_mini.sh                    # sync data/ only
#   bash scripts/sync_from_mini.sh --all              # sync data/ + logs/ + output/
#   bash scripts/sync_from_mini.sh --dry-run           # preview what would transfer
#   MINI_HOST=user@host bash scripts/sync_from_mini.sh # custom host
#
# Prerequisites:
#   - SSH key auth configured to Mac Mini
#   - rsync installed (macOS default)

set -euo pipefail

# --- Configuration ---
# Override with environment variables if needed
MINI_HOST="${MINI_HOST:-safrtam@Tamass-Mac-mini.local}"
MINI_PROJECT="${MINI_PROJECT:-~/SSH-Services/aetherveil}"

# Auto-detect local project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_PROJECT="$(dirname "$SCRIPT_DIR")"

# --- Parse arguments ---
SYNC_ALL=false
DRY_RUN=false
CLEAN_LOCAL=false

for arg in "$@"; do
    case $arg in
        --all)
            SYNC_ALL=true
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        --clean)
            CLEAN_LOCAL=true
            ;;
        --help|-h)
            echo "Usage: bash scripts/sync_from_mini.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --all       Sync data/, logs/, and output/ (default: data/ only)"
            echo "  --dry-run   Preview transfer without copying"
            echo "  --clean     Delete local files not on Mini (careful!)"
            echo "  -h, --help  Show this help"
            echo ""
            echo "Environment:"
            echo "  MINI_HOST     SSH host (default: safrtam@Tamass-Mac-mini.local)"
            echo "  MINI_PROJECT  Remote project path (default: ~/SSH-Services/aetherveil)"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg"
            exit 1
            ;;
    esac
done

# --- Build rsync flags ---
RSYNC_FLAGS="-avz --progress --compress"

if [ "$DRY_RUN" = true ]; then
    RSYNC_FLAGS="$RSYNC_FLAGS --dry-run"
    echo "[DRY RUN] No files will be transferred"
    echo ""
fi

if [ "$CLEAN_LOCAL" = true ]; then
    RSYNC_FLAGS="$RSYNC_FLAGS --delete"
fi

# Exclude common non-data files
RSYNC_FLAGS="$RSYNC_FLAGS --exclude='.DS_Store'"

# --- Sync data/ ---
echo "========================================"
echo "  OBSIDIAN MM — Sync from Mac Mini"
echo "========================================"
echo ""
echo "  Source: ${MINI_HOST}:${MINI_PROJECT}/"
echo "  Target: ${LOCAL_PROJECT}/"
echo ""

echo "--- Syncing data/ (Parquet cache) ---"
rsync $RSYNC_FLAGS \
    "${MINI_HOST}:${MINI_PROJECT}/data/" \
    "${LOCAL_PROJECT}/data/"

if [ "$SYNC_ALL" = true ]; then
    echo ""
    echo "--- Syncing logs/ ---"
    rsync $RSYNC_FLAGS \
        "${MINI_HOST}:${MINI_PROJECT}/logs/" \
        "${LOCAL_PROJECT}/logs/"

    echo ""
    echo "--- Syncing output/ ---"
    rsync $RSYNC_FLAGS \
        "${MINI_HOST}:${MINI_PROJECT}/output/" \
        "${LOCAL_PROJECT}/output/"
fi

echo ""
echo "========================================"
echo "  Sync complete!"
echo "========================================"
echo ""
echo "  Run status check:   python scripts/check_status.py"
echo "  Launch dashboard:   streamlit run src/obsidian/dashboard/app.py"
