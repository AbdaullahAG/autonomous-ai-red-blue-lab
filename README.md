<div align="center">

# 🤖⚔️ AI Red Team vs Blue Team Lab

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Azure_OpenAI-GPT--4o_&_gpt--5.2-412991?logo=openai&logoColor=white"/>
  <img src="https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker&logoColor=white"/>
  <img src="https://img.shields.io/badge/Kali_Linux-Ready-557C94?logo=kalilinux&logoColor=white"/>
  <img src="https://img.shields.io/badge/Pipeline-Closed--Loop_Autonomous-orange"/>
  <img src="https://img.shields.io/badge/License-MIT-green"/>
</p>

<p align="center">
  <b>Two autonomous AI agents. One attacks. One defends. Complete self-healing loop in under 2 minutes.</b>
</p>

</div>

---

## ⚡ The Numbers That Matter

| Metric | Value |
|--------|-------|
| 🏗️ App built & deployed | ~15 seconds |
| 💥 Full attack cycle (nmap → SQLi → XSS) | **70 seconds** |
| 🛡️ Patch generated & redeployed | ~30 seconds |
| ✅ Autonomous Re-test & Verification | ~15 seconds |
| ⏱️ **Total End-to-End Cycle** | **< 2 minutes** |
| 💰 **Total API Token Cost** | **~$0.08** |
| 👤 Human Intervention | **Zero (100% Autonomous)** |

---

## 🎯 What This Is

A fully automated **AI Security Research Lab & Self-Healing Pipeline** where:

- 🔵 **Blue Agent** (`gpt-5.2`) builds a deliberately vulnerable Flask/SQLite web app and deploys it via Docker.
- 🔴 **Red Agent** (`GPT-4o`) attacks it using automated tools (`nmap`, `sqlmap`, `curl`) and builds an attack intelligence report.
- 🔄 **Orchestrator Loop** feeds the logs directly into the Blue Agent, which safely rewrites the target's source code, triggers a Docker environment rebuild, and updates defenses.
- 🏁 **Verification Loop** summons the Red Agent once more to audit the secure code and attempt bypasses, achieving a fully resilient **closed-loop feedback system**.

---

## 🏗️ Architecture & Core Pipeline

┌───────────────────────────────────────────────────────────────────────────┐
│                              Kali Linux VM                                │
│                                                                           │
│        ┌─────────────────── 📄 orchestrator.py ───────────────────┐       │
│        │                                                          │       │
│        ▼                                                          ▼       │
│  🔴 Red Agent (GPT-4o)                                      🔵 Blue Agent │
│   └─► nmap recon & scanning                                  (gpt-5.2)    │
│   └─► sqlmap payload generation & exploit                    └─► App Build│
│   └─► Automated Stored XSS injections                        └─► Patching │
│   └─► Re-verification & bypass testing                       └─► Docker Up│
│        ▲                                                          │       │
│        └─────────────────── [Feedback Loop] ──────────────────────┘       │
│                                                                           │
│  🎯 Target: vulnerable-webapp [Isolated Docker Containers]                │
└───────────────────────────────────────────────────────────────────────────┘


---

## 🚀 Quick Start

### Prerequisites
- Kali Linux (or any Linux distribution with `nmap` + `sqlmap`)
- Docker & Docker Compose
- Azure OpenAI account with GPT-4o & gpt-5.2 deployments
- Python 3.11+

### 1. Clone & Setup
```bash
git clone [https://github.com/YOUR_USERNAME/autonomous-ai-red-blue-lab.git](https://github.com/YOUR_USERNAME/autonomous-ai-red-blue-lab.git)
cd autonomous-ai-red-blue-lab

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
