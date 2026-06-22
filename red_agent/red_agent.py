import os, subprocess
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

LOG_PATH    = os.path.expanduser("~/ai-red-blue-lab/logs/red_team_report.txt")
ANALYSIS    = os.path.expanduser("~/ai-red-blue-lab/logs/ai_red_analysis.txt")

# --- تشغيل سكربت الهجوم ---
print("🔴 بدء هجوم Red Team...\n")
subprocess.run(["bash",
    os.path.expanduser("~/ai-red-blue-lab/red_agent/attack.sh")])

# --- قراءة التقرير ---
with open(LOG_PATH, "r") as f:
    report = f.read()

print(f"\n📋 التقرير جاهز ({len(report)} حرف)")
print("=" * 50)

# --- إرسال التقرير لـ GPT-4o مباشرة ---
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("RED_API_VERSION"),
)

print("\n🤖 Red Agent يحلل التقرير...\n")

response = client.chat.completions.create(
    model=os.getenv("RED_DEPLOYMENT_NAME"),
    messages=[
        {
            "role": "system",
            "content": """أنت خبير اختبار اختراق (Red Team).
مهمتك تحليل نتائج الهجوم وتقديم:
1. ملخص الثغرات المكتشفة مع درجة الخطورة (Critical/High/Medium)
2. شرح كيف تم استغلال كل ثغرة
3. الأدلة من التقرير (Proof of Concept)
4. توصيات الإصلاح للـ Blue Team
أجب بتقرير منظم واضح بالعربية مع الاحتفاظ بالمصطلحات التقنية بالإنجليزية."""
        },
        {
            "role": "user",
            "content": f"حلّل تقرير الاختراق التالي:\n\n{report}"
        }
    ],
    max_tokens=1500,
)

analysis = response.choices[0].message.content

# --- عرض وحفظ التحليل ---
print("=" * 50)
print(analysis)
print("=" * 50)
print(f"\nTokens مستخدمة: {response.usage.total_tokens}")

with open(ANALYSIS, "w") as f:
    f.write(analysis)

print(f"\n✅ تم حفظ التحليل في: {ANALYSIS}")
