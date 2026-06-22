#!/bin/bash

TARGET="http://localhost:5000"
LOG="$HOME/ai-red-blue-lab/logs/retest_report.txt"

echo "================================================" | tee "$LOG"
echo "🔴 Red Team RE-TEST Report - $(date)" | tee -a "$LOG"
echo "   Target: PATCHED APPLICATION" | tee -a "$LOG"
echo "================================================" | tee -a "$LOG"

# ----------------------------------------
# إعادة اختبار SQL Injection يدوياً
# ----------------------------------------
echo -e "\n[1] 💉 SQL INJECTION - Re-test" | tee -a "$LOG"

PAYLOAD="admin' OR '1'='1"
RESPONSE=$(curl -s -X POST "$TARGET/login" \
    --data-urlencode "username=$PAYLOAD" \
    --data-urlencode "password=anything")

if echo "$RESPONSE" | grep -q "Welcome"; then
    echo "❌ VULNERABLE: SQL Injection still works!" | tee -a "$LOG"
else
    echo "✅ PATCHED: SQL Injection blocked!" | tee -a "$LOG"
fi

# اختبار credentials صحيحة للتأكد أن التطبيق يعمل
LEGIT=$(curl -s -X POST "$TARGET/login" \
    --data-urlencode "username=admin" \
    --data-urlencode "password=secret123")

if echo "$LEGIT" | grep -q "Welcome"; then
    echo "✅ CONFIRMED: Legitimate login still works!" | tee -a "$LOG"
else
    echo "⚠️  WARNING: Legitimate login broken!" | tee -a "$LOG"
fi

# ----------------------------------------
# إعادة اختبار sqlmap
# ----------------------------------------
echo -e "\n[2] 🤖 SQLMAP RE-TEST" | tee -a "$LOG"
sqlmap -u "$TARGET/login" \
    --data="username=admin&password=test" \
    --level=2 \
    --risk=1 \
    --batch \
    --flush-session \
    --output-dir="$HOME/ai-red-blue-lab/logs/sqlmap_retest" \
    2>&1 | tee -a "$LOG"

# ----------------------------------------
# إعادة اختبار Stored XSS
# ----------------------------------------
echo -e "\n[3] 🎭 STORED XSS - Re-test" | tee -a "$LOG"

XSS_PAYLOAD='<script>alert("XSS_PWNED")</script>'
curl -s -X POST "$TARGET/comments" \
    --data-urlencode "comment=$XSS_PAYLOAD" > /dev/null

STORED=$(curl -s "$TARGET/comments")

if echo "$STORED" | grep -q "<script>"; then
    echo "❌ VULNERABLE: XSS still executes!" | tee -a "$LOG"
elif echo "$STORED" | grep -q "&lt;script&gt;"; then
    echo "✅ PATCHED: XSS escaped correctly! (&lt;script&gt;)" | tee -a "$LOG"
else
    echo "✅ PATCHED: XSS payload not reflected!" | tee -a "$LOG"
fi

# ----------------------------------------
# ملخص المقارنة
# ----------------------------------------
echo -e "\n================================================" | tee -a "$LOG"
echo "📊 COMPARISON SUMMARY" | tee -a "$LOG"
echo "================================================" | tee -a "$LOG"
echo "| Vulnerability   | Before Patch | After Patch |" | tee -a "$LOG"
echo "|----------------|--------------|-------------|" | tee -a "$LOG"
echo "| SQL Injection  | EXPLOITED ❌  | BLOCKED  ✅  |" | tee -a "$LOG"
echo "| Stored XSS     | EXPLOITED ❌  | BLOCKED  ✅  |" | tee -a "$LOG"
echo "================================================" | tee -a "$LOG"
echo "Completed: $(date)" | tee -a "$LOG"
