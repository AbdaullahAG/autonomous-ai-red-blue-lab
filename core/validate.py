import subprocess

def check_legit_login(target_url="http://localhost:5000", username="admin", password="secret123"):
    """
    يتحقق أن الترقيع لم يكسر وظيفة شرعية أساسية (تسجيل دخول بمعرّف صحيح).
    يرجع True إذا نجح تسجيل الدخول الشرعي، False إذا انكسر.
    """
    result = subprocess.run(
        [
            "curl", "-s",
            "-X", "POST", f"{target_url}/login",
            "--data-urlencode", f"username={username}",
            "--data-urlencode", f"password={password}",
        ],
        capture_output=True, text=True, timeout=15,
    )
    return "Welcome" in result.stdout or result.returncode == 0 and "welcome" in result.stdout.lower()
