# Betriebshandbuch (Runbook) -- BettaFish

**Letzte Aktualisierung:** 2026-03-20

## Deployment

### Docker-Deployment (empfohlen)

```bash
# 1. Umgebungsvariablen vorbereiten
cp .env.example .env
# .env-Datei mit allen API-Schluesseln und DB-Konfiguration befuellen

# 2. Dienste starten
docker compose up -d

# 3. Logs pruefen
docker compose logs -f bettafish
```

**Ports:**
- `5000` -- Flask-Hauptanwendung
- `8501` -- InsightEngine Streamlit
- `8502` -- MediaEngine Streamlit
- `8503` -- QueryEngine Streamlit
- `5444` -- PostgreSQL (extern)

**Docker-Images:**
- `ghcr.io/666ghj/bettafish:latest` (Haupt-Image)
- `ghcr.nju.edu.cn/666ghj/bettafish:latest` (Spiegel fuer schnelleren Download)
- `postgres:15` (Datenbank)

### Manuelles Deployment

```bash
conda activate bettafish
python app.py
```

Die Datenbank wird beim ersten Start von `app.py` automatisch initialisiert.

## Ueberwachung und Logs

### Log-Verzeichnisse

| Verzeichnis | Inhalt |
|-------------|--------|
| `logs/` | Laufzeit-Logs aller Agents |
| `final_reports/` | Generierte HTML-Berichte |
| `final_reports/ir/` | IR-JSON-Zwischendarstellungen |
| `final_reports/pdf/` | PDF-Berichte |
| `final_reports/md/` | Markdown-Berichte |
| `*_streamlit_reports/` | Einzelne Agent-Berichte |

### Health-Check

```bash
# Flask-Anwendung erreichbar?
curl -s http://localhost:5000 | head -5

# Datenbank-Verbindung (Docker)
docker exec bettafish-db pg_isready -U bettafish

# Container-Status
docker compose ps
```

## Haeufige Probleme und Loesungen

### Port bereits belegt

**Symptom:** `Address already in use` beim Start von `app.py` oder Streamlit.

**Loesung:**
```bash
# Prozess auf Port finden und beenden
lsof -i :5000     # oder :8501, :8502, :8503
kill <PID>
```

Hinweis: Streamlit-Prozesse koennen nach einem Abbruch den Port weiter belegen.

### Datenbank-Verbindung fehlgeschlagen

**Symptom:** `OperationalError` oder `Connection refused` beim Start.

**Pruefschritte:**
1. `.env`-Datei: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` korrekt?
2. `DB_DIALECT` auf `postgresql` oder `mysql` gesetzt?
3. Datenbank erreichbar? `pg_isready -h <host> -p <port>`
4. Bei Docker: `docker compose ps` -- laeuft der `db`-Container?

### LLM-API-Fehler

**Symptom:** Timeouts, `401 Unauthorized`, leere Antworten.

**Pruefschritte:**
1. API-Schluessel in `.env` korrekt und gueltig?
2. `BASE_URL` erreichbar? `curl <BASE_URL>/models`
3. Modellname korrekt geschrieben?
4. Fuer Report Agent: Staerkeres Modell verwenden, wenn Diagramme leer oder Absaetze fehlerhaft

### Playwright / Crawler-Fehler

**Symptom:** `Browser closed unexpectedly` oder `Executable not found`.

**Loesung:**
```bash
playwright install chromium
```

In Docker wird der Browser automatisch installiert.

### WeasyPrint / PDF-Export fehlgeschlagen

**Symptom:** ImportError oder fehlende System-Bibliotheken.

**Loesung:** Siehe `static/Partial README for PDF Exporting/README.md` fuer plattformspezifische Anweisungen. PDF-Generierung ist optional -- `--skip-pdf` verwenden, um sie zu umgehen.

### Berichte mit leeren Diagrammen

**Ursache:** Report Agent verwendet ein zu schwaches LLM-Modell.

**Loesung:** In `.env` ein staerkeres Modell fuer `REPORT_ENGINE_MODEL_NAME` konfigurieren (empfohlen: gemini-2.5-pro oder vergleichbar).

## Rollback-Verfahren

### Docker-Rollback

```bash
# 1. Aktuelle Container stoppen
docker compose down

# 2. Aelteres Image verwenden
# In docker-compose.yml das Image-Tag aendern, z.B.:
#   image: ghcr.io/666ghj/bettafish:<aeltere-version>

# 3. Neu starten
docker compose up -d
```

### Berichte erneut generieren

Falls ein Bericht fehlerhaft ist, koennen die Kapitel-Daten wiederverwendet werden:

```bash
python regenerate_latest_html.py    # HTML aus letztem Lauf
python regenerate_latest_md.py      # Markdown aus letztem Lauf
python regenerate_latest_pdf.py     # PDF aus IR-JSON
```

### Datenbank

- PostgreSQL-Daten liegen unter `./db_data/` (Docker-Volume)
- Vor groesseren Aenderungen: `pg_dump` ausfuehren
- Rollback: Container stoppen, `db_data/` aus Backup wiederherstellen, Container starten

## Sicherheitshinweise

- API-Schluessel niemals in den Code committen -- immer `.env` verwenden
- `.env` ist in `.gitignore` eingetragen
- Datenbank-Abfragen nutzen SQLAlchemy ORM (parameterisiert, kein SQL-Injection-Risiko)
- Crawler respektiert `robots.txt` -- nur fuer Forschungszwecke verwenden
- Lizenz: GPL-2.0
