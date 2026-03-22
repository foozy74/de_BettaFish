# Entwickler-Handbuch -- BettaFish

**Letzte Aktualisierung:** 2026-03-20

## Voraussetzungen

| Werkzeug | Version | Zweck |
|----------|---------|-------|
| Python | 3.9+ (empfohlen 3.11) | Laufzeitumgebung |
| Conda oder uv | aktuell | Paketverwaltung |
| PostgreSQL | 15+ | Datenbank (alternativ MySQL) |
| Playwright | 1.45+ | Browser-Automatisierung fuer Crawler |
| Docker (optional) | aktuell | Container-Deployment |

## Umgebung einrichten

### 1. Repository klonen und Verzeichnis wechseln

```bash
git clone <repository-url>
cd de_BettaFish
```

### 2. Python-Umgebung erstellen

**Mit Conda:**
```bash
conda create -n bettafish python=3.11
conda activate bettafish
```

**Mit uv:**
```bash
uv venv --python 3.11
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
```

### 3. Abhaengigkeiten installieren

```bash
pip install -r requirements.txt
# oder schneller mit uv:
uv pip install -r requirements.txt
```

### 4. Playwright-Browser installieren

```bash
playwright install chromium
```

### 5. Umgebungsvariablen konfigurieren

```bash
cp .env.example .env
```

Pflichtfelder in `.env`:

| Variable | Beschreibung |
|----------|-------------|
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | Datenbankverbindung |
| `DB_DIALECT` | `postgresql` (empfohlen) oder `mysql` |
| `INSIGHT_ENGINE_API_KEY/BASE_URL/MODEL_NAME` | LLM fuer Insight Agent (empfohlen: kimi-k2) |
| `MEDIA_ENGINE_API_KEY/BASE_URL/MODEL_NAME` | LLM fuer Media Agent (empfohlen: gemini-2.5-pro) |
| `QUERY_ENGINE_API_KEY/BASE_URL/MODEL_NAME` | LLM fuer Query Agent (empfohlen: deepseek-chat) |
| `REPORT_ENGINE_API_KEY/BASE_URL/MODEL_NAME` | LLM fuer Report Agent (empfohlen: gemini-2.5-pro) |
| `MINDSPIDER_API_KEY/BASE_URL/MODEL_NAME` | LLM fuer MindSpider (empfohlen: deepseek-chat) |
| `FORUM_HOST_API_KEY/BASE_URL/MODEL_NAME` | LLM fuer Forum-Moderator (empfohlen: qwen-plus) |
| `KEYWORD_OPTIMIZER_API_KEY/BASE_URL/MODEL_NAME` | LLM fuer SQL-Keyword-Optimierung (empfohlen: qwen-plus) |
| `TAVILY_API_KEY` | Tavily Web-Suche |
| `SEARCH_TOOL_TYPE` | `AnspireAPI` (Standard) oder `BochaAPI` |

Alle LLM-Konfigurationen muessen das OpenAI-API-Format unterstuetzen.

## Entwicklungs-Workflow

### System starten

```bash
# Gesamtes System (Flask + Streamlit-Agents)
python app.py
# Erreichbar unter http://localhost:5000
```

### Einzelne Agents starten (Streamlit)

```bash
streamlit run SingleEngineApp/query_engine_streamlit_app.py --server.port 8503
streamlit run SingleEngineApp/media_engine_streamlit_app.py --server.port 8502
streamlit run SingleEngineApp/insight_engine_streamlit_app.py --server.port 8501
```

### Berichte ohne Agent-Lauf generieren

```bash
python report_engine_only.py                          # Standardausfuehrung
python report_engine_only.py --query "Thema"          # Mit bestimmtem Thema
python report_engine_only.py --skip-pdf --skip-markdown
```

### Berichte neu rendern

```bash
python regenerate_latest_html.py    # HTML aus gespeicherten Kapiteln
python regenerate_latest_md.py      # Markdown aus gespeicherten Kapiteln
python regenerate_latest_pdf.py     # PDF aus IR-JSON
```

### Crawler (MindSpider)

```bash
cd MindSpider
python main.py --setup                                  # Erstinitialisierung
python main.py --broad-topic --date 2024-01-20          # Nur Themenextraktion
python main.py --deep-sentiment --platforms xhs dy wb   # Nur Tiefenanalyse
python main.py --complete --date 2024-01-20             # Kompletter Durchlauf
```

## Tests ausfuehren

```bash
# Mit pytest (empfohlen)
pytest tests/ -v

# Einzelne Testdateien
pytest tests/test_monitor.py -v
pytest tests/test_report_engine_sanitization.py -v

# Alternativ: eigener Test-Runner
python tests/run_tests.py
```

Verfuegbare Tests:
- `test_monitor.py` -- ForumEngine Log-Monitoring und -Parsing
- `test_report_engine_sanitization.py` -- ReportEngine Sicherheitspruefungen

## Projektstruktur (Kurzuebersicht)

```
de_BettaFish/
  app.py                  # Flask-Hauptanwendung (Einstiegspunkt)
  config.py               # Globale Konfiguration (Pydantic Settings)
  QueryEngine/            # Web-Suche Agent
  MediaEngine/            # Multimodale Analyse Agent
  InsightEngine/          # Datenbank-Mining Agent
  ReportEngine/           # Berichtgenerierung Agent
  ForumEngine/            # Agent-Koordination (Forum-Mechanismus)
  MindSpider/             # Social-Media Crawler
  SentimentAnalysisModel/ # Sentiment-Analyse-Modelle (BERT, GPT-2, Qwen, ML)
  SingleEngineApp/        # Streamlit-Apps fuer einzelne Agents
  tests/                  # Testverzeichnis
  templates/              # Flask-Templates
  static/                 # Statische Dateien
  final_reports/          # Generierte Berichte (HTML, PDF, IR-JSON)
  logs/                   # Laufzeit-Logs
```

Jeder Agent folgt derselben Struktur: `agent.py`, `nodes/`, `tools/`, `llms/`, `prompts/`, `state/`, `utils/`.

## Branch- und Commit-Konventionen

- Branch-Benennung: `feature/xxx`, `fix/xxx`, `docs/xxx`
- Commit-Format: [Conventional Commits](https://www.conventionalcommits.org/)
- Ziel-Branch fuer PRs: `main`
- Bestehende CONTRIBUTING.md im Root beachten

## Docker-Entwicklung

```bash
cp .env.example .env
docker compose up -d
```

Dienste:
- `bettafish` -- Hauptanwendung (Ports 5000, 8501-8503)
- `db` -- PostgreSQL 15 (Port 5444 extern, 5432 intern)

Volumes: `logs/`, `final_reports/`, `.env`, `*_streamlit_reports/`
