<div align="center">

# 🤖⚔️ AI Red Team vs Blue Team Lab

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Azure_OpenAI-GPT--4o-412991?logo=openai&logoColor=white"/>
  <img src="https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker&logoColor=white"/>
  <img src="https://img.shields.io/badge/Kali_Linux-Ready-557C94?logo=kalilinux&logoColor=white"/>
  <img src="https://img.shields.io/badge/License-MIT-green"/>
</p>

<p align="center">
  <b>Two AI agents. One attacks. One defends. Full cycle in under 2 minutes.</b><br/>
  <b>in less 2 minute 2 agent ; first one attack and the other defend.</b>
</p>

</div>

---

## ⚡ The Numbers That Matter

| Metric | Value |
|--------|-------|
| 🏗️ App built & deployed | ~15 seconds |
| 💥 Full attack cycle (nmap → SQLi → XSS) | **70 seconds** |
| 🛡️ Patch generated & redeployed | ~30 seconds |
| ✅ Re-test confirming fix | 3 seconds |
| ⏱️ **Total end-to-end** | **< 2 minutes** |
| 💰 **Total API cost** | **~$0.08** |
| 👤 Human intervention | **Zero** |

---

## 🎯 What This Is

A fully automated **AI security research lab** where:

- 🔵 **Blue Agent** (`gpt-5.2`) builds a deliberately vulnerable Flask/SQLite web app and deploys it via Docker
- 🔴 **Red Agent** (`GPT-4o`) attacks it using `nmap`, `sqlmap`, and `curl` — then analyzes findings
- 🔵 **Blue Agent** reads the attack report, patches the vulnerabilities, and rebuilds the container
- 🔴 **Red Agent** re-tests to confirm the patch works

No human writes code. No human runs tools. No human analyzes results.

---

## 🔍 Vulnerabilities Demonstrated

### Before Patch ❌
```
SQL Injection:  admin' OR '1'='1  →  Welcome admin!
                sqlmap dumped entire users table in 10 seconds

Stored XSS:     <script>alert("XSS_PWNED")</script>  →  Executed in browser
```

### After Patch ✅
```
SQL Injection:  admin' OR '1'='1  →  Invalid credentials
                sqlmap: "all tested parameters do not appear to be injectable"

Stored XSS:     <script>alert("XSS_PWNED")</script>
                →  &lt;script&gt;alert(&quot;XSS_PWNED&quot;)&lt;/script&gt;
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                 Kali Linux VM                   │
│                                                 │
│  🔵 Blue Agent (gpt-5.2)                       │
│     └─► Builds Flask/SQLite App                │
│     └─► Deploys via Docker                     │
│     └─► Reads attack report → Patches code     │
│     └─► Rebuilds container                     │
│                                                 │
│  🔴 Red Agent (GPT-4o)                         │
│     └─► nmap reconnaissance                    │
│     └─► Manual SQLi test                       │
│     └─► sqlmap automated scan + data dump      │
│     └─► Stored XSS injection                   │
│     └─► AI analysis of findings                │
│     └─► Re-test after patch                    │
│                                                 │
│  🎯 Target: vulnerable-webapp (Docker)         │
│     └─► localhost:5000                         │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Kali Linux (or any Linux with nmap + sqlmap)
- Docker + Docker Compose
- Azure OpenAI account with GPT-4o deployment
- Python 3.11+

### 1. Clone & Setup
```bash
git clone https://github.com/YOUR_USERNAME/ai-red-blue-lab.git
cd ai-red-blue-lab

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Azure OpenAI
```bash
cp .env.example .env
# Edit .env with your Azure credentials
nano .env
```

### 3. Test Connection
```bash
python3 test_connection.py
```

### 4. Run Blue Agent (Build Target)
```bash
cd webapp && docker compose up -d --build && cd ..
```

### 5. Run Red Agent (Attack)
```bash
python3 red_agent/red_agent.py
```

### 6. Run Blue Agent (Patch)
```bash
python3 blue_agent/blue_agent.py
cd webapp && docker compose down && docker compose up -d --build && cd ..
```

### 7. Re-test
```bash
bash red_agent/retest.sh
```

---

## 📁 Project Structure

```
ai-red-blue-lab/
├── 📄 README.md
├── 📄 requirements.txt
├── 📄 .env.example
├── 📄 test_connection.py
├── 📄 writeup.md              ← Full Arabic write-up
│
├── 🌐 webapp/
│   ├── app.py                 ← Vulnerable Flask app
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── 🔴 red_agent/
│   ├── red_agent.py           ← AI-powered attack agent
│   └── attack.sh              ← nmap + sqlmap + curl
│
├── 🔵 blue_agent/
│   └── blue_agent.py          ← AI-powered defense agent
│
└── 📊 logs/                   ← Generated during run
    ├── red_team_report.txt
    ├── ai_red_analysis.txt
    ├── blue_patch_report.txt
    └── retest_report.txt
```

---

## 💡 Key Technical Findings

**The Fix: 2 lines of code**

```python
# SQL Injection fix — Parameterized Query
cur.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pwd))

# XSS fix — Escape output
import html
f"<p>{html.escape(r[0])}</p>"
```

The vulnerabilities that took AI 70 seconds to find and exploit took AI 10 seconds to fix. The patch was 100% effective against sqlmap's full arsenal.

---

## ⚠️ Disclaimer

> This project is for **educational and research purposes only**.  
> All tests were conducted in a completely isolated VM environment.  
> Never use these techniques on systems without explicit written permission.

---

## 📖 Full Write-up

Read the complete Arabic write-up: [writeup.md](./writeup.md)

---

## 🤝 Contributing

Ideas for future experiments:
- [ ] Add CSRF and IDOR vulnerabilities
- [ ] Test agent performance across different models
- [ ] Add autonomous patch verification loop
- [ ] Multi-turn agent conversation logging

PRs welcome!

---

<div align="center">
  <sub>Built with Azure OpenAI · Tested on Kali Linux · Automated with Python</sub>
</div>
