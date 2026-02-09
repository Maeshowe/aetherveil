#!/bin/bash
# OBSIDIAN MM — Cron Setup for Mac Mini
#
# Installs a crontab entry to run daily_run.py after US market close.
# Schedule: 23:30 CET (Mon-Fri) — ~1.5h after US close (22:00 CET winter)
#
# Usage:
#   cd /path/to/aetherveil
#   bash scripts/setup_cron.sh
#
# To verify:
#   crontab -l
#
# To remove:
#   crontab -l | grep -v "obsidian daily_run" | crontab -

set -euo pipefail

# Auto-detect project root (parent of scripts/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"
DAILY_SCRIPT="${PROJECT_ROOT}/scripts/daily_run.py"
LOG_DIR="${PROJECT_ROOT}/logs"

# Validate
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment not found at ${VENV_PYTHON}"
    echo "Run: python3.12 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
    exit 1
fi

if [ ! -f "$DAILY_SCRIPT" ]; then
    echo "ERROR: daily_run.py not found at ${DAILY_SCRIPT}"
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Cron job definition
# 23:30 CET Mon-Fri — after US market close + dark pool data stabilization
# Note: macOS cron uses system timezone. If Mac Mini is set to CET, this works directly.
# If set to UTC, use "30 22 * * 1-5" instead (22:30 UTC = 23:30 CET winter)
CRON_SCHEDULE="30 23 * * 1-5"
CRON_CMD="${VENV_PYTHON} ${DAILY_SCRIPT} >> ${LOG_DIR}/cron.log 2>&1"
CRON_COMMENT="# obsidian daily_run — OBSIDIAN MM data collection (23:30 CET Mon-Fri)"

# Check if already installed
if crontab -l 2>/dev/null | grep -q "obsidian daily_run"; then
    echo "Cron job already installed. Current entry:"
    crontab -l | grep -A1 "obsidian daily_run"
    echo ""
    read -p "Replace existing entry? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    # Remove existing entry
    crontab -l | grep -v "obsidian daily_run" | crontab -
fi

# Install cron job
(crontab -l 2>/dev/null; echo "$CRON_COMMENT"; echo "$CRON_SCHEDULE $CRON_CMD") | crontab -

echo "Cron job installed successfully!"
echo ""
echo "Schedule: ${CRON_SCHEDULE} (23:30 CET, Mon-Fri)"
echo "Command:  ${CRON_CMD}"
echo "Logs:     ${LOG_DIR}/cron.log"
echo "          ${LOG_DIR}/daily_YYYY-MM-DD.log"
echo ""
echo "Verify with: crontab -l"
echo "Test now:    ${VENV_PYTHON} ${DAILY_SCRIPT}"
echo ""
echo "IMPORTANT: Make sure your Mac Mini timezone is set to CET/Europe."
echo "Check with: date +%Z"
