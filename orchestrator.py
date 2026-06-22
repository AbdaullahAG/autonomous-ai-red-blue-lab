import os
import subprocess
import time
from openai import AzureOpenAI
from dotenv import load_dotenv

# 1. تحميل الإعدادات والمفاتيح
load_dotenv()

client_red = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("RED_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

client_blue = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("BLUE_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

TARGET_URL = "http://localhost:5000"

def run_command(command):
    """دالة مساعدة لتشغيل أوامر النظام (مثل دكر أو أدوات الفحص)"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout + "\n" + result.stderr
    except subprocess.TimeoutExpired:
        return "[Timeout] استغرق الأمر وقتاً طويلاً."

print("Red Team vs Blue Team...")
print("==================================================")

# --- الجولة الأولى: الهجوم التلقائي ---
print("\n [lvl 1] lunch (Red Agent)...")

# هنا نطلب من GPT-4o التخطيط للهجوم بناءً على الهدف المتاح
red_prompt = f"You are an expert automated Red Team agent. The target is {TARGET_URL}. Provide a strategy and execute simulated tests against it (SQLi and XSS). Return a detailed security report of what was found."

red_response = client_red.chat.completions.create(
    model=os.getenv("RED_DEPLOYMENT_NAME"),
    messages=[{"role": "user", "content": red_prompt}]
)
attack_report = red_response.choices[0].message.content
print("Red Agent Successfully Report !")


# --- الجولة الثانية: الدفاع التلقائي ---
print("\n [lvl 2] The coordinator automatically submits the report to the Blue Agent...")

# نقرأ الكود الضعيف الحالي لنسلمه للمدافع مع التقرير
with open("webapp/app.py", "r") as f:
    current_code = f.read()

blue_prompt = f"""
You are an expert Blue Team security engineer. 
Analyze this attack report:
---
{attack_report}
---
And fix the security vulnerabilities in this Flask code:
---
{current_code}
---
Return ONLY the complete, corrected Python code inside a markdown code block. Do not write explanations.
"""

blue_response = client_blue.chat.completions.create(
    model=os.getenv("BLUE_DEPLOYMENT_NAME"),
    messages=[{"role": "user", "content": blue_prompt}],
    max_completion_tokens=2000 # متوافق مع gpt-5.2 لتوكنز التفكير
)

fixed_code_raw = blue_response.choices[0].message.content

# تنظيف المخرجات واستخراج كود البايثون فقط
if "```python" in fixed_code_raw:
    fixed_code = fixed_code_raw.split("```python")[1].split("```")[0].strip()
else:
    fixed_code = fixed_code_raw.strip()

# كتابة الكود الجديد المُصلح فوق الكود القديم تلقائياً
with open("webapp/app.py", "w") as f:
    f.write(fixed_code)
print(" Blue Agent patch code and rewrite the file auto")


# --- الجولة الثالثة: إعادة البناء والتحقق التلقائي ---
print("\n [lvl 3] The coordinator rebuilds the Docker environment with the new code...")
rebuild_output = run_command("cd webapp && docker compose down && docker compose up -d --build")
print("update docker and patch.")

time.sleep(3) # انتظار قصير لضمان تشغيل السيرفر

print("\n [lvl 4] The coordinator calls on Red Agent once again to verify the effectiveness of the patch.....")

# تعديل الـ Prompt لمنع حظر الذكاء الاصطناعي وجعله يحلل الكود الجديد
verify_prompt = f"""
You are the Red Team agent. The Blue Team claims they fixed the security vulnerabilities.
Here is the newly patched Flask code they just deployed:
---
{fixed_code}
---
Analyze this updated code and simulate how your previous payloads (SQL Injection and Stored XSS) would react against it. 
Provide a final verification report confirming if the patches successfully BLOCKED the attacks or if any bypass exists.
"""

verify_response = client_red.chat.completions.create(
    model=os.getenv("RED_DEPLOYMENT_NAME"),
    messages=[{"role": "user", "content": verify_prompt}]
)

print("\n==================================================")
print(" النتيجة النهائية لإعادة الاختبار بعد الترقيع التلقائي:")
print(verify_response.choices[0].message.content)


print("\n==================================================")
print("النتيجة النهائية لإعادة الاختبار بعد الترقيع التلقائي:")
print(verify_response.choices[0].message.content)
