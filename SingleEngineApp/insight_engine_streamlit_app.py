"""
Streamlit Web-Oberfläche
Benutzerfreundliche Web-Oberfläche für den Insight Agent
"""

import os
import sys
import streamlit as st
from datetime import datetime
import json
import locale
from loguru import logger

# UTF-8-Kodierungsumgebung einrichten
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# Systemkodierung festlegen
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except locale.Error:
        pass

# src-Verzeichnis zum Python-Pfad hinzufügen
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from InsightEngine import DeepSearchAgent, Settings
from config import settings
from utils.github_issues import error_with_issue_link


def main():
    """Hauptfunktion"""
    st.set_page_config(
        page_title="Insight Agent",
        page_icon="",
        layout="wide"
    )

    st.title("Insight Agent")
    st.markdown("KI-Agent für Tiefenanalyse privater Meinungsdatenbanken")
    st.markdown("Vollautomatische 24/7-Erfassung von Meinungsdaten aus 13 Social-Media-Plattformen und Technikforen")

    # URL-Parameter prüfen
    try:
        # Neue Version von query_params verwenden
        query_params = st.query_params
        auto_query = query_params.get('query', '')
        auto_search = query_params.get('auto_search', 'false').lower() == 'true'
    except AttributeError:
        # Kompatibilität mit älterer Version
        query_params = st.experimental_get_query_params()
        auto_query = query_params.get('query', [''])[0]
        auto_search = query_params.get('auto_search', ['false'])[0].lower() == 'true'

    # ----- Konfiguration fest kodiert -----
    # Erzwinge Kimi
    model_name = settings.INSIGHT_ENGINE_MODEL_NAME or "kimi-k2-0711-preview"
    # Standard-Erweiterkonfiguration
    max_reflections = 2
    max_content_length = 500000  # Kimi unterstützt Langtexte

    # Vereinfachter Bereich zur Anzeige der Suchanfrage

    # Automatische Anfrage als Standardwert oder Platzhaltermeldung
    display_query = auto_query if auto_query else "Warte auf Analysedaten von der Hauptseite..."

    # Schreibgeschützter Anzeigebereich für die Anfrage
    st.text_area(
        "Aktuelle Anfrage",
        value=display_query,
        height=100,
        disabled=True,
        help="Die Anfrage wird über das Suchfeld der Hauptseite gesteuert",
        label_visibility="hidden"
    )

    # Automatische Suchlogik
    start_research = False
    query = auto_query

    if auto_search and auto_query and 'auto_search_executed' not in st.session_state:
        st.session_state.auto_search_executed = True
        start_research = True
    elif auto_query and not auto_search:
        st.warning("Warte auf Startsignal für die Suche...")

    # Konfiguration validieren
    if start_research:
        if not query.strip():
            st.error("Bitte eine Suchanfrage eingeben")
            logger.error("Bitte eine Suchanfrage eingeben")
            return

        # LLM-Schlüssel in der Konfiguration prüfen
        if not settings.INSIGHT_ENGINE_API_KEY:
            st.error("Bitte INSIGHT_ENGINE_API_KEY in den Umgebungsvariablen setzen")
            logger.error("Bitte INSIGHT_ENGINE_API_KEY in den Umgebungsvariablen setzen")
            return

        # API-Schlüssel und Datenbankkonfiguration aus der Konfiguration verwenden
        db_host = settings.DB_HOST
        db_user = settings.DB_USER
        db_password = settings.DB_PASSWORD
        db_name = settings.DB_NAME
        db_port = settings.DB_PORT
        db_charset = settings.DB_CHARSET

        # Settings-Konfiguration erstellen (Felder müssen Großbuchstaben sein für die Settings-Klasse)
        config = Settings(
            INSIGHT_ENGINE_API_KEY=settings.INSIGHT_ENGINE_API_KEY,
            INSIGHT_ENGINE_BASE_URL=settings.INSIGHT_ENGINE_BASE_URL,
            INSIGHT_ENGINE_MODEL_NAME=model_name,
            DB_HOST=db_host,
            DB_USER=db_user,
            DB_PASSWORD=db_password,
            DB_NAME=db_name,
            DB_PORT=db_port,
            DB_CHARSET=db_charset,
            DB_DIALECT=settings.DB_DIALECT,
            MAX_REFLECTIONS=max_reflections,
            MAX_CONTENT_LENGTH=max_content_length,
            OUTPUT_DIR="insight_engine_streamlit_reports"
        )

        # Recherche ausführen
        execute_research(query, config)


def execute_research(query: str, config: Settings):
    """Recherche ausführen"""
    try:
        # Fortschrittsanzeige erstellen
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Agent initialisieren
        status_text.text("Agent wird initialisiert...")
        agent = DeepSearchAgent(config)
        st.session_state.agent = agent

        progress_bar.progress(10)

        # Berichtsstruktur generieren
        status_text.text("Berichtsstruktur wird generiert...")
        agent._generate_report_structure(query)
        progress_bar.progress(20)

        # Absätze verarbeiten
        total_paragraphs = len(agent.state.paragraphs)
        for i in range(total_paragraphs):
            status_text.text(f"Verarbeite Abschnitt {i + 1}/{total_paragraphs}: {agent.state.paragraphs[i].title}")

            # Erste Suche und Zusammenfassung
            agent._initial_search_and_summary(i)
            progress_value = 20 + (i + 0.5) / total_paragraphs * 60
            progress_bar.progress(int(progress_value))

            # Reflexionsschleife
            agent._reflection_loop(i)
            agent.state.paragraphs[i].research.mark_completed()

            progress_value = 20 + (i + 1) / total_paragraphs * 60
            progress_bar.progress(int(progress_value))

        # Abschlussbericht generieren
        status_text.text("Abschlussbericht wird generiert...")
        final_report = agent._generate_final_report()
        progress_bar.progress(90)

        # Bericht speichern
        status_text.text("Bericht wird gespeichert...")
        agent._save_report(final_report)
        progress_bar.progress(100)

        status_text.text("Recherche abgeschlossen!")

        # Ergebnisse anzeigen
        display_results(agent, final_report)

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_display = error_with_issue_link(
            f"Fehler während der Recherche: {str(e)}",
            error_traceback,
            app_name="Insight Engine Streamlit App"
        )
        st.error(error_display)
        logger.exception(f"Fehler während der Recherche: {str(e)}")


def display_results(agent: DeepSearchAgent, final_report: str):
    """Rechercheergebnisse anzeigen"""
    st.header("Analyse abgeschlossen")

    # Ergebnis-Tabs
    tab1, tab2 = st.tabs(["Zusammenfassung", "Quellenangaben"])

    with tab1:
        st.markdown(final_report)

    with tab2:
        # Abschnittsdetails
        st.subheader("Abschnittsdetails")
        for i, paragraph in enumerate(agent.state.paragraphs):
            with st.expander(f"Abschnitt {i + 1}: {paragraph.title}"):
                st.write("**Erwarteter Inhalt:**", paragraph.content)
                st.write("**Finaler Inhalt:**", paragraph.research.latest_summary[:300] + "..."
                if len(paragraph.research.latest_summary) > 300
                else paragraph.research.latest_summary)
                st.write("**Anzahl Suchen:**", paragraph.research.get_search_count())
                st.write("**Reflexionszyklen:**", paragraph.research.reflection_iteration)

        # Suchverlauf
        st.subheader("Suchverlauf")
        all_searches = []
        for paragraph in agent.state.paragraphs:
            all_searches.extend(paragraph.research.search_history)

        if all_searches:
            for i, search in enumerate(all_searches):
                with st.expander(f"Suche {i + 1}: {search.query}"):
                    st.write("**URL:**", search.url)
                    st.write("**Titel:**", search.title)
                    st.write("**Inhaltsvorschau:**",
                             search.content[:200] + "..." if len(search.content) > 200 else search.content)
                    if search.score:
                        st.write("**Relevanzbewertung:**", search.score)


if __name__ == "__main__":
    main()
