#!/usr/bin/env bash
# =====================================================================
# JABBERWOCKY APPS — UNIFIED SYSTEM ENVIRONMENT ENTRY OPERATOR
# VERSION: 5.9.0 [Absolute Entry Anchor]
# Location: install.sh (Absolute Repository Root Anchor)
# =====================================================================
set -e

SRCDIR="$(cd "$(dirname "${BASH_SOURCE}")" && pwd)"

clear
echo "====================================================================="
echo "🐉 JABBERWOCKY APPS: INITIALIZING ECOSYSTEM INTEGRATION"
echo "   CORE ENGINE RUNTIME: v5.9.0"
echo "====================================================================="

if [ -d "${SRCDIR}/software" ]; then
    echo "🔐 Synchronizing execution clearances across script tracks..."
    chmod -R 755 "${SRCDIR}/software"
fi

echo "🚀 Chain-loading full-screen interactive onboarding dashboard console..."
sleep 2
exec python3 "${SRCDIR}/software/curses_ui.py"
