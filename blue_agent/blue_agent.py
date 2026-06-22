import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

ANALYSIS_PATH  = os.path.expanduser("~/ai-red-blue-lab/logs/ai_red_analysis.txt")
APP_PATH       = os.path.expanduser("~/ai-red-blue-lab/webapp/app.py")
PATCHED_LOG    = os.path.expanduser("~/ai-red-blue-lab/logs/blue_patch_report.txt")

# --- قراءة تقرير Red Team ---
with open(ANALYSIS_PATH, "r") as f:
    red_report = f.read()

# --- قراءة الكود الحالي ---
with open(APP_PATH, "r") as f:
    current_code = f.read()

print("🔵 Blue Agent يحلل التقرير ويُصلح الثغرات...\n")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("BLUE_API_VERSION"),
)

response = client.chat.completions.create(
    model=os.getenv("BLUE_DEPLOYMENT_NAME"),
    messages=[
        {
            "role": "system",
            "content": """أنت مطور أمني خبير (Blue Team).
مهمتك إصلاح ثغرات أمنية في كود Python/Flask.

قواعد صارمة:
1. أعد الكود الكامل لـ app.py بعد الإصلاح فقط، بدون أي شرح قبله أو بعده
2. الكود يجب أن يبدأ مباشرة بـ: from flask import
3. لا تضع ```python أو ``` حول الكود
4. أصلح SQL Injection باستخدام Parameterized Queries فقط
5. أصلح Stored XSS باستخدام html.escape() عند العرض
6. احتفظ بنفس منطق التطبيق وهيكله"""
        },
        {
            "role": "user",
            "content": f"""تقرير Red Team:
{red_report}

الكود الحالي المطلوب إصلاحه:
{current_code}

أعد الكود الكامل بعد الإصلاح."""
        }
    ],

)

patched_code = response.choices[0].message.content.strip()

# --- تنظيف الكود من أي markdown ---
if patched_code.startswith("```"):
    lines = patched_code.split("\n")
    patched_code = "\n".join(lines[1:-1])

# --- التحقق أن الكود سليم ---
if "from flask import" not in patched_code:
    print("❌ خطأ: الكود المُعاد لا يبدو صحيحاً!")
    print(patched_code[:200])
    exit(1)

# --- حفظ نسخة احتياطية ---
backup_path = APP_PATH + ".backup"
with open(backup_path, "w") as f:
    f.write(current_code)
print(f"💾 نسخة احتياطية محفوظة في: {backup_path}")

# --- كتابة الكود المُصلح ---
with open(APP_PATH, "w") as f:
    f.write(patched_code)
print(f"✅ تم حفظ الكود المُصلح في: {APP_PATH}")

# --- حفظ تقرير الترقيع ---
with open(PATCHED_LOG, "w") as f:
    f.write("=== Blue Team Patch Report ===\n\n")
    f.write(patched_code)

print(f"📋 تقرير الترقيع: {PATCHED_LOG}")
print(f"Tokens مستخدمة: {response.usage.total_tokens}")
print("\n🔄 الآن أعد بناء Docker...")
