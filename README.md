# mse_ai_g — Gemini AI Automation Helper

<div align="center">

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

**A lightweight, open-source proxy server that exposes a Gemini-compatible API interface powered by browser automation — no paid API keys required.**

<br>

<div align="center">
  <h3>Watch the Full Tutorial on YouTube</h3>
  <a href="https://www.youtube.com/watch?v=e_9tMLRXeKY">
    <img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube Tutorial" />
  </a>
  <br>
  <em>Learn how to install, set up, and build AI workflows with mse_ai_g</em>
</div>

</div>

---

## ❤️ Sponsors

- [Kareem Adel](https://www.facebook.com/Kareemadel.official.account) — Owner & CEO at Wzila

---

## 🌟 Overview

**mse_ai_g** is a high-performance proxy server built with **FastAPI** and **Playwright**. It automates a real browser session in the background and exposes a clean, Gemini-compatible REST API — making it a seamless drop-in replacement for AI nodes in tools like **n8n**.

This project targets **Google Gemini**, exposing a Gemini-compatible endpoint (`/v1beta/models/...`) with full support for system instructions, tool calling, and multi-turn conversations.

---

## ✨ Key Features

- 💸 **Zero API Costs** — Powered by browser automation, no paid credentials needed
- 🔌 **Gemini-Compatible Interface** — Drop-in replacement for Gemini API clients
- 🤖 **Tool Calling Support** — Full function/tool calling with JSON parsing for AI agent workflows
- 🔗 **n8n Ready** — Works directly with n8n HTTP and AI Agent nodes
- 🔒 **Secure** — Protected by a configurable API secret key
- 🐳 **Dockerized** — One-command deployment

---

## ⚙️ How It Works

```
Your App / n8n  ──►  mse_ai_g (FastAPI)  ──►  Browser (Playwright)  ──►  Gemini Web UI
                ◄──  Standard JSON Response  ◄──  Parsed Response       ◄──
```

1. **Browser Engine** — A single Chromium instance launches at startup and stays alive. All requests share it through an async lock, eliminating per-request overhead.
2. **Prompt Builder** — Incoming API payloads (system instructions, conversation history, tool definitions) are assembled into a clean prompt injected into the browser.
3. **Tool Call Parsing** — When tools are defined, the model is instructed to respond in structured JSON. The server parses the response and maps it back to the standard `functionCall` schema.
4. **Response Formatting** — The final output is wrapped in a Gemini-compatible response envelope, ready for your client or n8n to consume.

---

## 🛠️ Quick Start

### Option 1 — Docker (Recommended)

```bash
git clone https://github.com/MohamedElsayed-debug/mse_ai_g.git
cd mse_ai_g
docker-compose up --build -d
```

Server starts on `http://localhost:9999`

### Option 2 — Manual

```bash
# Python 3.10+ required
pip install -r requirements.txt
playwright install chromium
python main.py
```

---

## 🔧 Configuration

| Variable | Default | Description |
|---|---|---|
| `API_SECRET_KEY` | `change-secret-key-2026` | Your server's API key |

---

## 📡 API Reference

**Base URL:** `http://localhost:9999`

**Endpoint:** `POST /v1beta/models/gemini-3:generateContent`

**Header:** `x-goog-api-key: <your-secret-key>`

### Example — cURL

```bash
curl -X POST "http://localhost:9999/v1beta/models/gemini-3:generateContent" \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: change-secret-key-2026" \
  -d '{
    "contents": [
      { "role": "user", "parts": [{ "text": "Hello, how are you?" }] }
    ]
  }'
```

---

## 🔌 Connecting to n8n

### Via HTTP Node

1. Add an **HTTP Request** node
2. Method: `POST`
3. URL: `http://localhost:9999/v1beta/models/gemini-3:generateContent`
4. Header: `x-goog-api-key: change-secret-key-2026`
5. Body: Gemini-format JSON (see example above)

### Via AI Agent Node

Use the HTTP node as a custom LLM provider — pass tool definitions in the `tools` field and the server handles the full tool-calling cycle automatically.

---

## 💎 PRO Version

The open-source version is great for personal workflows. The **PRO Version** is built for teams and production environments.

| Feature | This Repo | PRO Version |
|---|:---:|:---:|
| Tool calling / function calling | ✅ | ✅ |
| **Gemini backend** | ✅ | ✅ |
| **ChatGPT backend** | ❌ | ✅ |
| **Image analysis (URL & Base64)** | ❌ | ✅ |
| **Admin dashboard (GUI)** | ❌ | ✅ |
| **Multi-user management** | ❌ | ✅ |
| **Usage statistics & logging** | ❌ | ✅ |
| **Per-key token quotas** | ❌ | ✅ |
| **Priority support** | ❌ | ✅ |

---

## 📬 Contact

Interested in the PRO version or a custom integration?

- **Telegram:** [@MohMsE](https://t.me/MohMsE)
- **LinkedIn:** [Mohamed Elsayed](https://linkedin.com/in/mohamed-elsayed-3a319939a)
- **Facebook:** [Melsayed2001](https://www.facebook.com/Melsayed2001)
- **GitHub:** [@MohamedElsayed-debug](https://github.com/MohamedElsayed-debug)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

> **Disclaimer:** This project automates a web browser for personal and educational use. Usage must comply with the terms of service of the underlying platforms. The authors are not responsible for misuse.
