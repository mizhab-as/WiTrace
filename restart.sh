#!/bin/bash
# WiFi CSI Dashboard Restart Script

echo "🛑 Stopping any existing server on port 8080..."
lsof -tiTCP:8080 -sTCP:LISTEN 2>/dev/null | xargs kill -9 2>/dev/null || true

echo "⏳ Waiting..."
sleep 1

echo "🚀 Starting dashboard..."
cd /Users/mizhabas/wifi_csi_imaging
/Users/mizhabas/wifi_csi_imaging/.venv/bin/python python/app.py
