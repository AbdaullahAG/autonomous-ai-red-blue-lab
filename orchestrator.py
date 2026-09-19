import os
import subprocess
import time
import uuid
from openai import OpenAI
from dotenv import load_dotenv
from core.identity import AgentIdentity, log_action, verify_chain, log_kill_switch
from core.scope import check_binary_allowed, check_write_allowed, ScopeViolation

load_dotenv()

SESSION_ID = str(uuid.uuid4())[:8]

client = OpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    base_url="https://wisecoder.services.ai.azure.com/openai/v1",
)

RED = AgentIdentity(role="red-team", instance_id=SESSION_ID)
BLUE = AgentIdentity(role="blue-team", instance_id=SESSION_ID)

BASE = os.path.dirname(os.path.abspath(__file__))
TARGET_URL = "http://localhost:5000"


def run_script(script_path, log_path, agent, purpose):
    """ينفذ سكريبت هجوم/إعادة اختبار حقيقي فعلياً، ويسجل الحدث بالكامل."""
    result = subprocess.run(
        ["bash", script_path], capture_output=True, text=True, timeout=600
    )
    with open(log_path, "r") as f:
        report = f.read()

    log_action(
        agent=agent,
        declared_purpose=purpose,
        action_taken=f"executed {os.path.basename(script_path)} (real nmap/sqlmap/curl against {TARGET_URL})",
        scope_used=f"target={TARGET_URL}",
        authority_basis=f"lab-authorized-{agent.role}-role",
        outcome="executed" if result.returncode == 0 else f"executed_with_errors:{result.returncode}",
    )
    return report


def call_model(deployment, system_prompt, user_prompt):
    response = client.responses.create(
        model=deployment,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.output_text


# فحص نطاق أولي: تأكد Red مسموح له الأدوات الأساسية قبل بدء الحلقة
for binary in ["nmap", "sqlmap", "curl"]:
    check_binary_allowed(RED, binary, TARGET_URL)

print(f"Red Team vs Blue Team... session={SESSION_ID}")
print("==================================================")

# --- [1] هجوم حقيقي ---
print("\n[lvl 1] Red Agent executing REAL attack (nmap/sqlmap/curl)...")
attack_report = run_script(
    f"{BASE}/red_agent/attack.sh",
    f"{BASE}/logs/red_team_report.txt",
    RED,
    "initial_exploitation_attempt",
)
print(f"   Attack report: {len(attack_report)} chars")

# --- [2] تحليل Red Agent (LLM) للنتائج الحقيقية ---
red_analysis = call_model(
    os.getenv("RED_DEPLOYMENT_NAME"),
    "أنت خبير اختبار اختراق (Red Team). حلّل نتائج الهجوم الحقيقية وقدّم ملخص الثغرات مع درجة الخطورة والأدلة.",
    f"حلّل تقرير الاختراق التالي:\n\n{attack_report}",
)
log_action(
    agent=RED,
    declared_purpose="analyze_real_attack_output",
    action_taken="LLM analysis of real attack.sh output",
    scope_used=f"target={TARGET_URL}",
    authority_basis="lab-authorized-red-team-role",
    outcome="analysis_generated",
)
print("Red Agent analysis complete.")

# --- [3] ترقيع Blue Agent (مع حلقة إعادة محاولة محدودة + kill-switch) ---
from core.validate import check_legit_login

MAX_PATCH_ATTEMPTS = 3
attempt_log_refs = []
patch_succeeded = False

with open(f"{BASE}/webapp/app.py", "r") as f:
    original_code = f.read()

current_code = original_code

for attempt in range(1, MAX_PATCH_ATTEMPTS + 1):
    print(f"\n[lvl 2] Blue Agent patching (attempt {attempt}/{MAX_PATCH_ATTEMPTS})...")

    patched_code = call_model(
        os.getenv("BLUE_DEPLOYMENT_NAME"),
        """أنت مطور أمني خبير (Blue Team). أعد الكود الكامل لـ app.py بعد الإصلاح فقط، بدون شرح.
الكود يجب أن يبدأ بـ: from flask import
لا تضع ```python حول الكود. أصلح SQLi بـ Parameterized Queries وXSS بـ html.escape().""",
        f"تقرير Red Team:\n{red_analysis}\n\nالكود الحالي:\n{current_code}\n\nأعد الكود الكامل بعد الإصلاح.",
    )

    patched_code = patched_code.strip()
    if patched_code.startswith("```"):
        patched_code = "\n".join(patched_code.split("\n")[1:-1])

    if "from flask import" not in patched_code:
        rec = log_action(
            agent=BLUE, declared_purpose="patch_reported_vulnerabilities",
            action_taken=f"patch_generation_failed_validation (attempt {attempt})",
            scope_used="file:webapp/app.py",
            authority_basis="lab-authorized-blue-team-role",
            outcome="rejected_invalid_patch",
        )
        attempt_log_refs.append(rec["record_hash"])
        continue

    check_write_allowed(BLUE, f"{BASE}/webapp/app.py")

    with open(f"{BASE}/webapp/app.py.backup", "w") as f:
        f.write(current_code)
    with open(f"{BASE}/webapp/app.py", "w") as f:
        f.write(patched_code)

    log_action(
        agent=BLUE, declared_purpose="patch_reported_vulnerabilities",
        action_taken=f"rewrote webapp/app.py based on real attack analysis (attempt {attempt})",
        scope_used="file:webapp/app.py",
        authority_basis="lab-authorized-blue-team-role",
        outcome="patch_applied",
    )
    print("Blue Agent patched webapp/app.py.")

    try:
        check_binary_allowed(BLUE, "sqlmap", TARGET_URL)
    except ScopeViolation as e:
        print(f"   (confirmed) {e}")

    print("Restarting Flask with patched code...")
    subprocess.run("pkill -9 -f 'python3 webapp/app.py'", shell=True)
    time.sleep(1)
    subprocess.Popen(
        ["python3", "webapp/app.py"],
        cwd=BASE,
        stdout=open(f"{BASE}/logs/flask_stdout.log", "w"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(2)

    print("Validating patch does not break legitimate functionality...")
    legit_ok = check_legit_login(TARGET_URL)

    if legit_ok:
        rec = log_action(
            agent=BLUE,
            declared_purpose="validate_patch_safety",
            action_taken=f"tested legitimate login against patched code (attempt {attempt})",
            scope_used="file:webapp/app.py",
            authority_basis="lab-authorized-blue-team-role",
            outcome="validation_passed",
        )
        print("✅ Patch validated: legitimate functionality intact.")
        patch_succeeded = True
        break

    rec = log_action(
        agent=BLUE,
        declared_purpose="validate_patch_safety",
        action_taken=f"tested legitimate login against patched code (attempt {attempt})",
        scope_used="file:webapp/app.py",
        authority_basis="lab-authorized-blue-team-role",
        outcome="patch_rejected_regression",
    )
    attempt_log_refs.append(rec["record_hash"])
    print(f"❌ REGRESSION DETECTED on attempt {attempt}. Rolling back and retrying...")

    subprocess.run("pkill -9 -f 'python3 webapp/app.py'", shell=True)
    time.sleep(1)
    with open(f"{BASE}/webapp/app.py", "w") as f:
        f.write(current_code)
    subprocess.Popen(
        ["python3", "webapp/app.py"],
        cwd=BASE,
        stdout=open(f"{BASE}/logs/flask_stdout.log", "a"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(2)

    log_action(
        agent=BLUE,
        declared_purpose="rollback_rejected_patch",
        action_taken=f"restored pre-patch webapp/app.py after regression (attempt {attempt})",
        scope_used="file:webapp/app.py",
        authority_basis="lab-authorized-blue-team-role",
        outcome="rolled_back",
    )

if not patch_succeeded:
    log_kill_switch(
        reason="N_consecutive_regression_failures",
        n=MAX_PATCH_ATTEMPTS,
        attempts_log_refs=attempt_log_refs,
    )
    print(f"\n==================================================")
    print(f"🛑 KILL-SWITCH TRIGGERED after {MAX_PATCH_ATTEMPTS} failed attempts.")
    print(f"Evidence log chain valid: {verify_chain()}")
    raise SystemExit(
        f"توقفت الحلقة نهائياً: {MAX_PATCH_ATTEMPTS} محاولات ترقيع متتالية فشلت (regression). "
        f"راجع logs/evidence_log.jsonl للتفاصيل."
    )

# --- [5] إعادة اختبار  ---
print("\n[lvl 4] Red Agent RE-TESTING patch (real requests)...")
retest_report = run_script(
    f"{BASE}/red_agent/retest.sh",
    f"{BASE}/logs/retest_report.txt",
    RED,
    "verify_patch_effectiveness",
)

print("\n==================================================")
print("نتيجة  الاختبار :")
print(retest_report)
print("\n==================================================")
print(f"Evidence log chain valid: {verify_chain()}")
