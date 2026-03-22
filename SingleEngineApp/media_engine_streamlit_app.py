"""
Streamlit Web-Oberfläche
Benutzerfreundliche Web-Oberfläche für den Media Agent
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

from MediaEngine import DeepSearchAgent, AnspireSearchAgent, Settings
from config import settings
from utils.github_issues import error_with_issue_link


def main():
    """Hauptfunktion"""
    st.set_page_config(
        page_title="Media Agent",
        page_icon="",
        layout="wide"
    )

    st.title("Media Agent")
    st.markdown("KI-Agent mit starken multimodalen Fähigkeiten")
    st.markdown("Überwindet reine Textgrenzen – analysiert Videos, Bilder und Livestreams")
    st.markdown("Nutzt strukturierte Multimodal-Daten moderner Suchmaschinen (Kalender, Wetter, Aktien u.v.m.) für erweiterte Analyse")

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
    # Erzwinge Gemini
    model_name = settings.MEDIA_ENGINE_MODEL_NAME or "gemini-2.5-pro"
    # Standard-Erweiterkonfiguration
    max_reflections = 2
    max_content_length = 20000

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

        # API-Schlüssel für Gemini prüfen
        if not settings.MEDIA_ENGINE_API_KEY:
            st.error("Bitte MEDIA_ENGINE_API_KEY in den Umgebungsvariablen setzen")
            logger.error("Bitte MEDIA_ENGINE_API_KEY in den Umgebungsvariablen setzen")
            return

        # API-Schlüssel aus der Konfiguration verwenden
        engine_key = settings.MEDIA_ENGINE_API_KEY
        bocha_key = settings.BOCHA_WEB_SEARCH_API_KEY
        ansire_key = settings.ANSPIRE_API_KEY

        # Settings erstellen (Pydantic-Settings-Stil, Großbuchstaben-Variablen bevorzugt)
        if settings.SEARCH_TOOL_TYPE == "BochaAPI":
            if not bocha_key:
                st.error("Bitte BOCHA_WEB_SEARCH_API_KEY in den Umgebungsvariablen setzen")
                logger.error("Bitte BOCHA_WEB_SEARCH_API_KEY in den Umgebungsvariablen setzen")
                return
            logger.info("Verwende Bocha-Such-API")
            config = Settings(
                MEDIA_ENGINE_API_KEY=engine_key,
                MEDIA_ENGINE_BASE_URL=settings.MEDIA_ENGINE_BASE_URL,
                MEDIA_ENGINE_MODEL_NAME=model_name,
                SEARCH_TOOL_TYPE="BochaAPI",
                BOCHA_WEB_SEARCH_API_KEY=bocha_key,
                MAX_REFLECTIONS=max_reflections,
                SEARCH_CONTENT_MAX_LENGTH=max_content_length,
                OUTPUT_DIR="media_engine_streamlit_reports",
            )
        elif settings.SEARCH_TOOL_TYPE == "AnspireAPI":
            if not ansire_key:
                st.error("Bitte ANSPIRE_API_KEY in den Umgebungsvariablen setzen")
                logger.error("Bitte ANSPIRE_API_KEY in den Umgebungsvariablen setzen")
                return
            logger.info("Verwende Anspire-Such-API")
            config = Settings(
                MEDIA_ENGINE_API_KEY=engine_key,
                MEDIA_ENGINE_BASE_URL=settings.MEDIA_ENGINE_BASE_URL,
                MEDIA_ENGINE_MODEL_NAME=model_name,
                SEARCH_TOOL_TYPE="AnspireAPI",
                ANSPIRE_API_KEY=ansire_key,
                MAX_REFLECTIONS=max_reflections,
                SEARCH_CONTENT_MAX_LENGTH=max_content_length,
                OUTPUT_DIR="media_engine_streamlit_reports",
            )
        else:
            st.error(f"Unbekannter Suchwerkzeugtyp: {settings.SEARCH_TOOL_TYPE}")
            logger.error(f"Unbekannter Suchwerkzeugtyp: {settings.SEARCH_TOOL_TYPE}")
            return

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
        if config.SEARCH_TOOL_TYPE == "BochaAPI":
            agent = DeepSearchAgent(config)
        elif config.SEARCH_TOOL_TYPE == "AnspireAPI":
            agent = AnspireSearchAgent(config)
        else:
            raise ValueError(f"Unbekannter Suchwerkzeugtyp: {config.SEARCH_TOOL_TYPE}")
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
        logger.info("Abschlussbericht wird generiert...")
        final_report = agent._generate_final_report()
        progress_bar.progress(90)

        # Bericht speichern
        status_text.text("Bericht wird gespeichert...")
        logger.info("Bericht wird gespeichert...")
        agent._save_report(final_report)
        progress_bar.progress(100)

        status_text.text("Recherche abgeschlossen!")
        logger.info("Recherche abgeschlossen!")
        # Ergebnisse anzeigen
        display_results(agent, final_report)

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        error_display = error_with_issue_link(
            f"Fehler während der Recherche: {str(e)}",
            error_traceback,
            app_name="Media Engine Streamlit App"
        )
        st.error(error_display)
        logger.exception(f"Fehler während der Recherche: {str(e)}")


def display_results(agent: DeepSearchAgent, final_report: str):
    """Rechercheergebnisse anzeigen"""
    st.header("Rechercheergebnisse")

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
                query_label = search.query if search.query else "Anfrage nicht erfasst"
                with st.expander(f"Suche {i + 1}: {query_label}"):
                    paragraph_title = getattr(search, "paragraph_title", "") or "Abschnitt nicht gekennzeichnet"
                    search_tool = getattr(search, "search_tool", "") or "Werkzeug nicht gekennzeichnet"
                    has_result = getattr(search, "has_result", True)
                    st.write("**Abschnitt:**", paragraph_title)
                    st.write("**Verwendetes Werkzeug:**", search_tool)
                    preview = search.content or ""
                    if not isinstance(preview, str):
                        preview = str(preview)
                    if len(preview) > 200:
                        preview = preview[:200] + "..."
                    st.write("**URL:**", search.url or "Keine")
                    st.write("**Titel:**", search.title or "Keine")
                    st.write("**Inhaltsvorschau:**", preview if preview else "Kein Inhalt verfügbar")
                    if not has_result:
                        st.info("Diese Suche hat keine Ergebnisse zurückgegeben")
                    if search.score:
                        st.write("**Relevanzbewertung:**", search.score)


if __name__ == "__main__":
    main()
