# Research Assistant Agent

A simple **AI research agent** that:

1. Takes a research topic  
2. Searches the web + Wikipedia  
3. Browses promising pages  
4. Summarizes multiple sources  
5. Writes a structured report with references  

Built with a pure **ReAct** loop (no LangChain / CrewAI).

```
frontend/     ← web UI
backend/      ← FastAPI + agent + tools
```

---

## Project structure (GitHub-ready)

```
simple_ai_agent/
├── backend/
│   ├── main.py              # FastAPI → POST /api/research + serves frontend
│   ├── agent.py             # ReAct agent
│   ├── tools.py             # web_search, browse_url, wikipedia, current_time
│   ├── run_example.py       # CLI demo
│   ├── requirements.txt
│   └── .env.example         # ← copy to .env and add your API key
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── .gitignore
└── README.md
```

---

## Where to get your API key

You only need **one** key from any of these providers:

| Provider       | Get key here                                   | Env variable         | Notes              |
|----------------|------------------------------------------------|----------------------|--------------------|
| **OpenAI**     | https://platform.openai.com/api-keys           | `OPENAI_API_KEY`     | Default, paid      |
| **xAI (Grok)** | https://console.x.ai                           | `XAI_API_KEY`        | Grok models        |
| **Groq**       | https://console.groq.com/keys                  | `GROQ_API_KEY`       | Very fast & cheap  |
| **Together**   | https://api.together.xyz/settings/api-keys     | `TOGETHER_API_KEY`   | Open-source models |
| **OpenRouter** | https://openrouter.ai/keys                     | `OPENROUTER_API_KEY` | Many models, 1 key |

### Setup (do this once)

```bash
cd backend
cp .env.example .env
```

Open `backend/.env` and put your key, for example:

```env
OPENAI_API_KEY=sk-your-key-here
```

or for Grok:

```env
XAI_API_KEY=xai-your-key-here
```

**Never commit `.env`** — it is already listed in `.gitignore`.

---

## Run locally

### Backend (also serves the frontend)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Make sure backend/.env has your API key
uvicorn main:app --reload --port 8000
```

Then open:

| URL | What |
|-----|------|
| **http://localhost:8000** | Frontend UI |
| http://localhost:8000/docs | Swagger API docs |
| http://localhost:8000/api/health | Health check |

### CLI only (no browser)

```bash
cd backend
python run_example.py --topic "Your research topic here"
```

---

## API usage

```bash
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Recent advances in solid-state batteries for EVs",
    "provider": "openai",
    "max_turns": 12
  }'
```

---

## Push to GitHub

```bash
cd simple_ai_agent
git init
git add .
git commit -m "Initial commit: Research Assistant Agent (frontend + backend)"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/research-assistant-agent.git
git push -u origin main
```

**Before pushing**
- [ ] `backend/.env` is **not** tracked (covered by `.gitignore`)
- [ ] Only `backend/.env.example` is committed
- [ ] No API keys appear in any file

---

## How the agent works

```
User topic
    ↓
Thought → Action (web_search / browse_url / wikipedia)
    ↓
Observation
    ↓
… (repeat until enough info)
    ↓
Answer = structured research report with Sources & References
```

| Tool           | Purpose                                   |
|----------------|-------------------------------------------|
| `web_search`   | Search the public web (DuckDuckGo)        |
| `browse_url`   | Fetch & extract text from a specific page |
| `wikipedia`    | Wikipedia summary + URL                   |
| `current_time` | UTC timestamp                             |

---

## License

MIT
