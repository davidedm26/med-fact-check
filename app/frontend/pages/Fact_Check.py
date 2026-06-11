import streamlit as st
import requests
import json
from bs4 import BeautifulSoup
import time

# 1. Importa dai nostri nuovi moduli separati nelle rispettive cartelle
from utils.text_processing import split_into_sentences
from components.ui_components import (
    load_global_css, 
    render_navbar, 
    render_footer, 
    render_claim_checklist, 
    update_interactive_loading,
    inject_floating_buttons_css
)

# 2. Configurazione della Pagina
st.set_page_config(
    page_title="Fact Check | Med Fact Check",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Carica il CSS globale e la Navbar in alto
load_global_css()
render_navbar()

# Inizializzazione Stati per ricordare i dati tra i vari refresh
if 'last_input_method' not in st.session_state: st.session_state.last_input_method = None
if "real_results" not in st.session_state: st.session_state.real_results = None
if "current_subclaims" not in st.session_state: st.session_state.current_subclaims = []
if "current_evaluations" not in st.session_state: st.session_state.current_evaluations = []

# Placeholder vuoto per l'animazione a tutto schermo che inietteremo dopo
overlay_placeholder = st.empty()

# Layout Principale
_, col_main, _ = st.columns([1, 14, 1])

with col_main:
    # Il tasto per tornare alla tua VERA homepage
    if st.button("← Back to Home", type="secondary"):
        st.switch_page("app.py")

    st.markdown('<div class="panel-title">Medical Fact Check Panel</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-subtitle">Submit a medical claim and rigorously verify it against trusted scientific literature.</div>', unsafe_allow_html=True)

    input_method = st.radio("Choose Input Method:", ["✍️ Text Input", "📄 Upload TXT", "🔗 Provide URL"], horizontal=True)
    
    # Reset selezione claim quando cambia metodo
    if st.session_state.last_input_method != input_method:
        st.session_state.selected_claims = {}
        st.session_state.last_input_method = input_method
    
    claim = ""

    with st.container():
        # METODO 1: Testo
        if input_method == "✍️ Text Input":
            claim = st.text_area("Medical Claim:", height=130, placeholder="E.g., Taking a daily vitamin D supplement helps prevent osteoporosis...")
            
        # METODO 2: Upload TXT
        elif input_method == "📄 Upload TXT":
            uploaded_file = st.file_uploader("Choose a .txt file", type="txt")
            if uploaded_file is not None:
                file_content = uploaded_file.getvalue().decode("utf-8")
                
                with st.expander("📄 File Content", expanded=True):
                    st.text_area("File Content:", value=file_content[:1000] + ("..." if len(file_content) > 1000 else ""), height=150, disabled=True)
                
                sentences = split_into_sentences(file_content)
                if sentences:
                    st.markdown(f"**📊 Found {len(sentences)} sentences in the document**")
                    selected_claims = render_claim_checklist(sentences, context=f"File: {uploaded_file.name}")
                    if selected_claims: claim = selected_claims[0]
                    else: st.warning("⚠️ Please select a claim to verify")
                else: st.warning("⚠️ No valid sentences found in the document")
                    
        # METODO 3: URL
        elif input_method == "🔗 Provide URL":
            url_input = st.text_input("Enter Article URL:", placeholder="https://example.com/article")
            fetch_clicked = st.button("🌐 Fetch URL Content", type="secondary")
            
            if "fetched_url_data" not in st.session_state:
                st.session_state.fetched_url_data = {"url": None, "sentences": [], "page_content": ""}

            if url_input and fetch_clicked:
                if not url_input.startswith(("http://", "https://")): st.warning("Please enter a valid URL starting with http:// or https://")
                else:
                    try:
                        with st.spinner("Fetching content from URL..."):
                            headers = {"User-Agent": "Mozilla/5.0"}
                            res = requests.get(url_input, headers=headers, timeout=10)
                            if res.status_code == 200:
                                soup = BeautifulSoup(res.text, "html.parser")
                                for script in soup(["script", "style"]): script.extract()
                                page_content = soup.get_text(separator=' ', strip=True)
                                sentences = split_into_sentences(page_content)
                                st.session_state.fetched_url_data = {"url": url_input, "sentences": sentences, "page_content": page_content}
                            else: st.error(f"Failed to fetch URL. Status code: {res.status_code}")
                    except Exception as e: st.error(f"Error fetching URL: {str(e)}")
            
            if st.session_state.fetched_url_data.get("url") == url_input and url_input != "":
                st.success("✅ Content fetched successfully!")
                page_content = st.session_state.fetched_url_data.get("page_content", "")
                with st.expander("🌐 Page Content", expanded=True):
                    preview = page_content[:1000] + ("..." if len(page_content) > 1000 else "")
                    st.text_area("Page Content:", value=preview, height=150, disabled=True)
                
                sentences = st.session_state.fetched_url_data.get("sentences", [])
                if sentences:
                    st.markdown(f"**📊 Found {len(sentences)} sentences on the page**")
                    selected_claims = render_claim_checklist(sentences, context=f"URL: {url_input}")
                    if selected_claims: claim = selected_claims[0]
                    else: st.warning("⚠️ Please select a claim to verify")
                else: st.warning("⚠️ No valid sentences found on the page")

    st.markdown("<br>", unsafe_allow_html=True)
    error_placeholder = st.empty()
    
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        verify_clicked = st.button("Verify Claim", type="primary", use_container_width=True)

    # ==========================================
    # LOGICA BACKEND E CHIAMATA API FASTAPI
    # ==========================================
    if verify_clicked:
        if not claim.strip(): st.warning("Please provide a valid claim or document before verifying.")
        else:
            # Pulisci i dati vecchi prima di una nuova analisi
            st.session_state.fact_check_claim = claim
            st.session_state.current_subclaims = []
            st.session_state.current_evaluations = []
            st.session_state.source_selections = {}
            st.session_state.downloader_status = {}
            st.session_state.retriever_status = {}
            st.session_state.queries_by_source = {}
            st.session_state.download_stats = {}
            if "current_final" in st.session_state: del st.session_state["current_final"]
                
            st.session_state.start_time = time.time()
            st.session_state.execution_time = 0.0
            error_placeholder.empty() 
            
            # Mostra la schermata di caricamento iniziale
            update_interactive_loading(placeholder=overlay_placeholder, claim=claim, step=1)
                
            try:
                response = requests.post("http://backend:8000/api/v1/fact-check-stream", json={"claim": claim}, stream=True, timeout=900)
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: "):
                                data_str = decoded_line[6:]
                                try:
                                    step_data = json.loads(data_str)
                                    
                                    if "error" in step_data:
                                        overlay_placeholder.empty()
                                        error_placeholder.error(f"❌ Pipeline Error: {step_data['error']}")
                                        break
                                    
                                    # FASE 1: Decomposizione
                                    if "decompose" in step_data:
                                        scs = step_data["decompose"].get("verifiable_subclaims", [])
                                        for sc in scs:
                                            sc_text = sc if isinstance(sc, str) else sc.get("claim", str(sc))
                                            st.session_state.current_subclaims.append(sc_text)
                                        st.session_state.max_step = max(st.session_state.get("max_step", 1), 2)
                                        update_interactive_loading(placeholder=overlay_placeholder, claim=claim, step=st.session_state.max_step, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=0, total_to_verify=len(st.session_state.current_subclaims))
                                        
                                    # FASE 2: Selezione Fonti e Download
                                    elif "source_selector" in step_data:
                                        info = step_data["source_selector"]
                                        sub_id = info.get("subclaim_id")
                                        if sub_id: st.session_state.source_selections[sub_id] = [k for k, v in (info.get("retrieval_source") or {}).items() if v > 0]
                                        st.session_state.max_step = max(st.session_state.get("max_step", 1), 2)
                                        update_interactive_loading(placeholder=overlay_placeholder, claim=claim, step=st.session_state.max_step, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=0, total_to_verify=len(st.session_state.current_subclaims))
                                        
                                    elif "downloader_agent" in step_data:
                                        info = step_data["downloader_agent"]
                                        sub_id = info.get("subclaim_id")
                                        if sub_id: 
                                            st.session_state.downloader_status[sub_id] = len(info.get("downloaded_chunks", []))
                                            if "queries_by_source" not in st.session_state: st.session_state.queries_by_source = {}
                                            if "download_stats" not in st.session_state: st.session_state.download_stats = {}
                                            st.session_state.queries_by_source[sub_id] = info.get("queries_by_source", {})
                                            st.session_state.download_stats[sub_id] = info.get("download_stats", {})
                                        st.session_state.max_step = max(st.session_state.get("max_step", 1), 2)
                                        update_interactive_loading(placeholder=overlay_placeholder, claim=claim, step=st.session_state.max_step, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=0, total_to_verify=len(st.session_state.current_subclaims))
                                        
                                    # FASE 3: Retrieval e Valutazione
                                    elif "hybrid_retriever" in step_data:
                                        info = step_data["hybrid_retriever"]
                                        sub_id = info.get("subclaim_id")
                                        if sub_id: st.session_state.retriever_status[sub_id] = len(info.get("retrieved_chunks", []))
                                        st.session_state.max_step = max(st.session_state.get("max_step", 1), 2)
                                        update_interactive_loading(placeholder=overlay_placeholder, claim=claim, step=st.session_state.max_step, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=len(st.session_state.current_evaluations), total_to_verify=len(st.session_state.current_subclaims))
                                        
                                    elif any(k in step_data for k in ["verify_subclaim", "evaluate_subclaim", "reasoning", "veracity"]):
                                        inner_data = step_data.get("verify_subclaim", step_data.get("evaluate_subclaim", step_data.get("veracity", step_data.get("reasoning", {}))))
                                        eval_results = inner_data.get("evaluation_results", []) if isinstance(inner_data, dict) else []
                                        for er in eval_results:
                                            if er not in st.session_state.current_evaluations:
                                                st.session_state.current_evaluations.append(er)
                                        if len(st.session_state.current_evaluations) == len(st.session_state.current_subclaims) and len(st.session_state.current_subclaims) > 0:
                                            st.session_state.max_step = max(st.session_state.get("max_step", 1), 4)
                                        else:
                                            st.session_state.max_step = max(st.session_state.get("max_step", 1), 3)
                                        update_interactive_loading(placeholder=overlay_placeholder, claim=claim, step=st.session_state.max_step, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=len(st.session_state.current_evaluations), total_to_verify=len(st.session_state.current_subclaims))
                                        
                                    # FASE 4: Aggregazione
                                    elif "aggregate" in step_data:
                                        if "start_time" in st.session_state: st.session_state.execution_time = time.time() - st.session_state.start_time
                                        current_final = step_data["aggregate"].get("final_verdict", {})
                                        st.session_state.current_final = current_final
                                        update_interactive_loading(
                                            placeholder=overlay_placeholder,
                                            claim=claim, 
                                            step=4, 
                                            subclaims=st.session_state.current_subclaims, 
                                            evaluations=st.session_state.current_evaluations, 
                                            verified_count=len(st.session_state.current_evaluations), 
                                            total_to_verify=len(st.session_state.current_subclaims),
                                            final_verdict=current_final
                                        )
                                except json.JSONDecodeError: pass
                else:
                    overlay_placeholder.empty()
                    error_placeholder.error(f"❌ Backend Connection Error (Status Code: {response.status_code})")
            except Exception as e:
                overlay_placeholder.empty()
                error_placeholder.error(f"❌ Failed to connect to the backend API: {str(e)}")

# ==========================================
# FINAL BUTTONS (Renderizzati quando l'analisi è finita)
# ==========================================
render_footer()

if getattr(st.session_state, "current_final", None):
    # Ricarica l'overlay Fase 4 in caso l'utente navighi in altre pagine e poi torni qui
    update_interactive_loading(
        placeholder=overlay_placeholder,
        claim=st.session_state.get("fact_check_claim", claim),
        step=4,
        subclaims=st.session_state.get("current_subclaims", []),
        evaluations=st.session_state.get("current_evaluations", []),
        verified_count=len(st.session_state.get("current_evaluations", [])),
        total_to_verify=len(st.session_state.get("current_subclaims", [])),
        final_verdict=st.session_state.current_final
    )

    try:
        import utils.pdf_generator
        import importlib
        importlib.reload(utils.pdf_generator)
        from utils.pdf_generator import generate_fact_check_pdf
        pdf_bytes = generate_fact_check_pdf(
            claim=st.session_state.get("fact_check_claim", claim),
            final_verdict=st.session_state.current_final,
            subclaims=st.session_state.get("current_evaluations", []),
            exec_time=getattr(st.session_state, "execution_time", 0.0)
        )
    except Exception as e:
        import traceback
        st.error(f"PDF Generation Error: {e}\n\n{traceback.format_exc()}")
        pdf_bytes = b""

    inject_floating_buttons_css()

    st.markdown('<span class="marker-dl-btn" style="display:none;"></span>', unsafe_allow_html=True)
    st.download_button("📄 Download PDF Report", data=pdf_bytes, file_name="FactCheck_Report.pdf", mime="application/pdf", key="pdf_dl")

    st.markdown('<span class="marker-new-btn" style="display:none;"></span>', unsafe_allow_html=True)
    if st.button("🔄 New Analysis", key="new_analysis"):
        for state_key in ["current_final", "fact_check_claim", "current_subclaims", "current_evaluations", "source_selections", "downloader_status", "retriever_status"]:
            if state_key in st.session_state: del st.session_state[state_key]
        st.rerun()