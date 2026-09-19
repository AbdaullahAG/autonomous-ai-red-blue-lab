import subprocess
import json
import time
import os
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
N_ITERATIONS = 10
METRICS_LOG = os.path.join(BASE, "logs", "metrics_runs.jsonl")


def reset_environment():
    subprocess.run("pkill -9 -f 'webapp/app.py'", shell=True)
    time.sleep(1)
    log_path = os.path.join(BASE, "logs", "evidence_log.jsonl")
    if not os.path.exists(log_path):
        open(log_path, "w").close()  # يُنشأ فارغاً أول مرة فقط، يبقى تراكمياً بعدها
    for f in ["users.db", "users.db-journal", "webapp/users.db", "webapp/users.db-journal"]:
        p = os.path.join(BASE, f)
        if os.path.exists(p):
            os.remove(p)
    subprocess.run(f"cp -f {BASE}/webapp/app.py.backup {BASE}/webapp/app.py", shell=True)
    proc = subprocess.Popen(
        ["python3", "webapp/app.py"],
        cwd=BASE,
        stdout=open(f"{BASE}/logs/flask_stdout.log", "w"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(2)


def run_one_iteration(i):
    reset_environment()

    log_path = os.path.join(BASE, "logs", "evidence_log.jsonl")

    # عدد الأسطر الموجودة قبل هذا التكرار — السلسلة تبقى متصلة عبر كل التشغيل،
    # لكن الفحص أدناه يقتصر على السجلات المضافة بهذا التكرار فقط
    lines_before = 0
    if os.path.exists(log_path):
        with open(log_path) as f:
            lines_before = sum(1 for l in f if l.strip())

    start = time.time()
    result = subprocess.run(
        ["python3", "orchestrator.py"],
        cwd=BASE, capture_output=True, text=True, timeout=900,
    )
    duration = time.time() - start

    with open(log_path) as f:
        all_lines = [l for l in f if l.strip()]

    # فقط السجلات الجديدة المضافة بهذا التكرار تحديداً
    new_lines = all_lines[lines_before:]
    records = [json.loads(l) for l in new_lines]

    exploit_ts = None
    detect_ts = None
    for r in records:
        if r["declared_purpose"] == "initial_exploitation_attempt" and r["outcome"] == "executed":
            exploit_ts = r["timestamp"]
        if r["declared_purpose"] == "analyze_real_attack_output":
            detect_ts = r["timestamp"]

    detection_latency = None
    if exploit_ts and detect_ts:
        t1 = datetime.strptime(exploit_ts, "%Y-%m-%dT%H:%M:%SZ")
        t2 = datetime.strptime(detect_ts, "%Y-%m-%dT%H:%M:%SZ")
        detection_latency = (t2 - t1).total_seconds()

    patch_applied = any(r["outcome"] == "patch_applied" for r in records)
    validation_passed = any(r["outcome"] == "validation_passed" for r in records)
    kill_switch = any(r.get("declared_purpose") == "enforce_containment_limit" for r in records)
    out_of_scope_attempts = sum(1 for r in records if r["outcome"] == "denied_out_of_scope")
    chain_ok = "Evidence log chain valid: True" in result.stdout

    # --- أرشفة صريحة لملفات النص الخام قبل الحذف بالتكرار التالي ---
    retest_path = os.path.join(BASE, "logs", "retest_report.txt")
    attack_path = os.path.join(BASE, "logs", "red_team_report.txt")
    retest_archive = os.path.join(BASE, "logs", f"retest_report_run{i}.txt")
    attack_archive = os.path.join(BASE, "logs", f"red_team_report_run{i}.txt")

    attack_blocked_after_patch = None
    if os.path.exists(retest_path):
        subprocess.run(f"cp {retest_path} {retest_archive}", shell=True)
        with open(retest_path) as f:
            retest_content = f.read()
        sqli_blocked = "PATCHED: SQL Injection blocked!" in retest_content
        xss_blocked = (
            "PATCHED: XSS escaped correctly!" in retest_content
            or "PATCHED: XSS payload not reflected!" in retest_content
        )
        attack_blocked_after_patch = sqli_blocked and xss_blocked

    if os.path.exists(attack_path):
        subprocess.run(f"cp {attack_path} {attack_archive}", shell=True)

    archive_evidence = os.path.join(BASE, "logs", f"evidence_log_run{i}.jsonl")
    subprocess.run(f"cp {log_path} {archive_evidence}", shell=True)

    iteration_result = {
        "iteration": i,
        "wall_clock_seconds": round(duration, 2),
        "exploit_timestamp": exploit_ts,
        "detection_timestamp": detect_ts,
        "detection_latency_seconds": detection_latency,
        "patch_applied": patch_applied,
        "validation_passed": validation_passed,
        "kill_switch_triggered": kill_switch,
        "out_of_scope_attempts": out_of_scope_attempts,
        "evidence_chain_valid": chain_ok,
        "attack_blocked_after_patch": attack_blocked_after_patch,
        "orchestrator_exit_code": result.returncode,
    }

    with open(METRICS_LOG, "a") as f:
        f.write(json.dumps(iteration_result) + "\n")

    print(f"[{i}/{N_ITERATIONS}] duration={duration:.1f}s patch={patch_applied} "
          f"validated={validation_passed} kill_switch={kill_switch} "
          f"blocked={attack_blocked_after_patch} chain_ok={chain_ok}")

    return iteration_result


if __name__ == "__main__":
    if os.path.exists(METRICS_LOG):
        os.remove(METRICS_LOG)
    evidence_path = os.path.join(BASE, "logs", "evidence_log.jsonl")
    if os.path.exists(evidence_path):
        os.remove(evidence_path)

    results = []
    for i in range(1, N_ITERATIONS + 1):
        try:
            r = run_one_iteration(i)
            results.append(r)
        except subprocess.TimeoutExpired:
            print(f"[{i}/{N_ITERATIONS}] TIMEOUT")
            with open(METRICS_LOG, "a") as f:
                f.write(json.dumps({"iteration": i, "error": "timeout"}) + "\n")

    print("\n=== DONE ===")
    print(f"Completed {len(results)}/{N_ITERATIONS} iterations")
