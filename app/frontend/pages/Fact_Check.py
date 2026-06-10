import streamlit as st
import streamlit.components.v1 as components
import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
import re

# 1. Configurazione della Pagina
st.set_page_config(
    page_title="Fact Check | Med Fact Check",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Funzione per evidenziare le citazioni
def highlight_quotes(text, supp, ref):
    hl = text
    if isinstance(supp, str): supp = [supp]
    if isinstance(ref, str): ref = [ref]
    for q in (supp or []):
        if q and len(q) > 5:
            q_pattern = r'\s+'.join(re.escape(word) for word in q.split())
            pattern = re.compile(q_pattern, re.IGNORECASE)
            hl = pattern.sub(r"<span style='background-color: rgba(16, 185, 129, 0.2); color: #34d399;'>\g<0></span>", hl)
    for q in (ref or []):
        if q and len(q) > 5:
            q_pattern = r'\s+'.join(re.escape(word) for word in q.split())
            pattern = re.compile(q_pattern, re.IGNORECASE)
            hl = pattern.sub(r"<span style='background-color: rgba(239, 68, 68, 0.2); color: #f87171;'>\g<0></span>", hl)
    return hl

# ==========================================
# 2. CSS GLOBALE (Input, Modali, Navigazione e Footer)
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
    
    [data-testid="stSidebar"], [data-testid="collapsedControl"], header { display: none !important; }
    [data-testid="stAppViewContainer"] { background-color: #0f172a !important; overflow-x: hidden; }
    .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; min-height: 100vh !important; display: flex; flex-direction: column; }
    html, body { font-family: 'Inter', sans-serif; background-color: #0f172a !important; color: #f8fafc; margin: 0; padding: 0; }

    .navbar { position: fixed; top: 0; width: 100%; background-color: #0b1120; border-bottom: 1px solid rgba(255,255,255,0.05); padding: 1.5rem 4rem; display: flex; justify-content: space-between; align-items: center; z-index: 9999; }
    .nav-logo { font-size: 1.5rem; font-weight: 800; color: #3b82f6; }
    .panel-title { font-size: 2.8rem; font-weight: 800; background: linear-gradient(to right, #00f2fe, #4facfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 5px; }
    .panel-subtitle { font-size: 1.1rem; color: #94a3b8; margin-bottom: 35px; }

    /* Input Box styling */
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 20px !important; border: 1px solid rgba(255, 255, 255, 0.05) !important; background: rgba(30, 41, 59, 0.4) !important; padding: 1.8rem !important; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.3) !important; }
    div.stButton > button, div.stDownloadButton > button { background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%) !important; border: none !important; color: #0f172a !important; font-weight: 800 !important; border-radius: 50px !important; padding: 0.9rem 2.5rem !important; transition: 0.3s !important; }
    div.stButton > button:hover { transform: scale(1.04) translateY(-2px) !important; box-shadow: 0 0 25px rgba(0, 242, 254, 0.6) !important; }
    div.stButton > button[kind="secondary"] { background: rgba(255,255,255,0.05) !important; color: #cbd5e1 !important; border: 1px solid rgba(255,255,255,0.1) !important; }

    /* Footer Fissato a Fondo Pagina */
    .footer { width: 100%; text-align: center; padding: 2rem 0; color: #64748b; font-size: 0.85rem; border-top: 1px solid rgba(255,255,255,0.05); background-color: #0b1120; margin-top: auto; }

    /* CSS per Finestre Modali Globali (Popup Cliccabili) */
    .modal-wrapper { position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(0,0,0,0.85); z-index:10000000; display:none; align-items:center; justify-content:center; backdrop-filter:blur(8px); }
    .modal-toggle:checked + .modal-wrapper { display:flex !important; }
    .modal-card { background:#0f172a; border:1px solid #38bdf8; border-radius:16px; padding:2rem; max-width:800px; width:90%; max-height:85vh; overflow-y:auto; box-shadow:0 0 40px rgba(56,189,248,0.4); position:relative; animation:zoomIn 0.3s cubic-bezier(0.175,0.885,0.32,1.275) forwards; text-align:left; }
    @keyframes zoomIn { 0% { transform:scale(0.8); opacity:0; } 100% { transform:scale(1); opacity:1; } }
    .close-btn { position:absolute; top:20px; right:20px; cursor:pointer; color:#f8fafc; background:#ef4444; width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:bold; transition:0.2s; font-size:14px; }
    .close-btn:hover { background:#dc2626; transform:scale(1.1); }
    .card-btn { display:block; cursor:pointer; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); padding:15px 20px; border-radius:12px; transition: 0.2s; position:relative; text-align:left; }
    .card-btn:hover { background:rgba(255,255,255,0.06); transform:translateY(-3px); box-shadow:0 5px 15px rgba(0,0,0,0.3); border-color:#38bdf8; }

    /* CSS per la Timeline Verticale del Menu (Fase DONE) */
    div[role="radiogroup"][aria-orientation="vertical"] { gap: 0; position: relative; padding-left: 10px; margin-top: 10px; }
    div[role="radiogroup"][aria-orientation="vertical"]::before { content: ''; position: absolute; left: 26px; top: 15px; bottom: 30px; width: 2px; background: rgba(255,255,255,0.15); z-index: 0; }
    div[role="radiogroup"][aria-orientation="vertical"] > label { padding: 15px 0 15px 50px; cursor: pointer; display: flex; align-items: center; background: transparent !important; border: none !important; margin: 0; position: relative; z-index: 1; }
    div[role="radiogroup"][aria-orientation="vertical"] > label > div:first-child { display: none !important; }
    div[role="radiogroup"][aria-orientation="vertical"] > label::before { content: ''; position: absolute; left: 10px; top: 50%; transform: translateY(-50%); width: 34px; height: 34px; border-radius: 50%; background: #0f172a; border: 2px solid #64748b; z-index: 2; transition: 0.3s; display:flex; align-items:center; justify-content:center; color:#64748b; font-weight:bold; font-size:14px; }
    
    div[role="radiogroup"][aria-orientation="vertical"] > label:nth-child(1)::before { content: '1'; }
    div[role="radiogroup"][aria-orientation="vertical"] > label:nth-child(2)::before { content: '2'; }
    div[role="radiogroup"][aria-orientation="vertical"] > label:nth-child(3)::before { content: '3'; }
    div[role="radiogroup"][aria-orientation="vertical"] > label:nth-child(4)::before { content: '4'; }

    div[role="radiogroup"][aria-orientation="vertical"] > label[data-checked="true"]:nth-child(1)::before { border-color: #38bdf8; background: #38bdf8; box-shadow: 0 0 15px rgba(56,189,248,0.6); color: #0f172a; }
    div[role="radiogroup"][aria-orientation="vertical"] > label[data-checked="true"]:nth-child(2)::before { border-color: #818cf8; background: #818cf8; box-shadow: 0 0 15px rgba(129,140,248,0.6); color: #0f172a; }
    div[role="radiogroup"][aria-orientation="vertical"] > label[data-checked="true"]:nth-child(3)::before { border-color: #a78bfa; background: #a78bfa; box-shadow: 0 0 15px rgba(167,139,250,0.6); color: #0f172a; }
    div[role="radiogroup"][aria-orientation="vertical"] > label[data-checked="true"]:nth-child(4)::before { border-color: #10b981; background: #10b981; box-shadow: 0 0 15px rgba(16,185,129,0.6); color: #0f172a; }

    div[role="radiogroup"][aria-orientation="vertical"] > label p { color: #94a3b8; font-weight: 600; font-size: 1.05rem; margin: 0; transition: 0.3s; }
    div[role="radiogroup"][aria-orientation="vertical"] > label[data-checked="true"] p { color: #f8fafc; font-weight: 800; }
    div[role="radiogroup"][aria-orientation="vertical"] > label:hover p { color: #e2e8f0; transform: translateX(3px); }
    </style>
""", unsafe_allow_html=True)

st.markdown("""<div class="navbar"><div class="nav-logo">⚕️ Med Fact Check</div><div style="font-size: 0.9rem; color: #94a3b8; font-weight:600;">MSc Unina • Big Data Engineering</div></div>""", unsafe_allow_html=True)
st.markdown('<div style="margin-top: 8rem;"></div>', unsafe_allow_html=True)

# 4. WRAPPER PRINCIPALE
_, col_main, _ = st.columns([1, 14, 1])

with col_main:
    overlay_placeholder = st.empty()
    if st.button("← Back to Home", type="secondary"): st.switch_page("app.py")

    st.markdown('<div class="panel-title">Medical Fact Check Panel</div><div class="panel-subtitle">Submit a medical claim and rigorously verify it against trusted scientific literature.</div>', unsafe_allow_html=True)

    input_method = st.radio("Choose Input Method:", ["✍️ Text Input", "📄 Upload TXT", "🔗 Provide URL"], horizontal=True)
    claim = ""

    with st.container():
        if input_method == "✍️ Text Input": claim = st.text_area("Medical Claim:", height=130, placeholder="E.g., Taking a daily vitamin D supplement helps prevent osteoporosis...")
        elif input_method == "📄 Upload TXT":
            uploaded_file = st.file_uploader("Choose a .txt file", type="txt")
            if uploaded_file: claim = uploaded_file.getvalue().decode("utf-8"); st.text_area("Preview:", value=claim, height=100, disabled=True)
        elif input_method == "🔗 Provide URL":
            url_input = st.text_input("Enter URL:")
            if url_input:
                try:
                    res = requests.get(url_input, timeout=10)
                    soup = BeautifulSoup(res.text, "html.parser")
                    for script in soup(["script", "style"]): script.extract()
                    claim = soup.get_text(separator=' ', strip=True)
                    st.text_area("Preview:", value=claim[:1000], height=100, disabled=True)
                except: st.error("Error fetching URL")

    st.markdown("<br>", unsafe_allow_html=True)
    error_placeholder = st.empty()
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col: verify_clicked = st.button("Verify Claim", type="primary", use_container_width=True)

    if "real_results" not in st.session_state: st.session_state.real_results = None
    if "current_subclaims" not in st.session_state: st.session_state.current_subclaims = []
    if "current_evaluations" not in st.session_state: st.session_state.current_evaluations = []

    # ==========================================
    # GESTIONE CARICAMENTO ANIMATO (STREAMING)
    # ==========================================
    def update_interactive_loading(claim, step=1, subclaims=None, evaluations=None, verified_count=0, total_to_verify=1):
        if subclaims is None: subclaims = []
        if evaluations is None: evaluations = []
        
        # VALORI DI DEFAULT BLINDATI PER EVITARE NAMEERROR
        central_title = "Processing..."
        central_subtitle = "Please wait..."
        anim_color = "#38bdf8"
        
        if step == 1:
            central_title, central_subtitle = "Initializing Medical AI Pipeline", "Warming up decomposition agents..."
            anim_color = "#38bdf8"
        elif step == 2:
            central_title = "RAG Database Ingestion"
            src_sel = getattr(st.session_state, "source_selections", {})
            if src_sel:
                all_s = set()
                for v in src_sel.values(): all_s.update(v)
                central_subtitle = f"Fonti selezionate: {', '.join(sorted(all_s))}"
            else: central_subtitle = "Selecting sources and preparing queries..."
            anim_color = "#818cf8"
        elif step == 3:
            central_title = "Clinical Reasoning Agent"
            central_subtitle = "Aggregating Subclaims verdicts..." if verified_count == total_to_verify else f"Validating {verified_count} of {total_to_verify} extracted claims..."
            anim_color = "#a78bfa"
        else:
            central_title, central_subtitle = "Generating Final Consensus", "Aggregating verdicts and calculating confidence score..."
            anim_color = "#10b981"

        def get_cards_html(target_phase):
            if not subclaims: return "<div style='color:#94a3b8; margin-top:20px; font-style:italic;'>⏳ Waiting for pipeline...</div>"
            html = "<div style='display:flex; flex-wrap:wrap; gap:15px; justify-content:center; align-items:center; margin-top:20px; width:100%; max-width:900px; margin-left:auto; margin-right:auto;'>"
            for i, sc in enumerate(subclaims):
                ev_data = next((e for e in evaluations if e.get("subclaim") == sc), None)
                if target_phase == 2:
                    if step < 2: status = "⏳ Pending..."
                    elif step == 2:
                        sub_id = f"sub_{i+1:02d}"
                        ret_stat = getattr(st.session_state, "retriever_status", {})
                        down_stat = getattr(st.session_state, "downloader_status", {})
                        if sub_id in ret_stat: status = f"✅ Selected {ret_stat[sub_id]} final chunks"
                        elif sub_id in down_stat: status = f"⏳ Ingesting {down_stat[sub_id]} chunks..."
                        else: status = "⏳ Querying Database..."
                    else: status = "✅ Documents Retrieved"
                elif target_phase == 3:
                    if step < 3: status = "⏳ Pending..."
                    elif step == 3 and ev_data: status = f"✅ Evaluated: {ev_data.get('label', 'NEI')}"
                    elif step == 3 and i == verified_count: status = "🔍 Evaluating..."
                    else: status = "⏳ Waiting in queue..."
                
                has_modal = bool(ev_data)
                if has_modal:
                    chunks = ev_data.get("retrieved_chunks", [])[:5]
                    reasoning = ev_data.get("justification", ev_data.get("selection_reasoning", "N/A"))
                    chunks_html = "".join([f"<div style='background:#1e293b; padding:10px; margin:8px 0; border-left:4px solid #38bdf8; border-radius:6px; font-size:0.85rem; text-align:left;'><strong style='color:#38bdf8;'>{c.get('metadata', {}).get('title', 'Ref')}</strong><br><em style='color:#cbd5e1;'>{highlight_quotes(c.get('text', ''), ev.get('supporting_quotes', []), ev.get('refuting_quotes', []))}</em></div>" for c in chunks])
                    modal_html = f"<input type='checkbox' id='modal-load-{target_phase}-{i}' class='modal-toggle' style='display:none;'><div class='modal-wrapper'><div class='modal-card'><label for='modal-load-{target_phase}-{i}' class='close-btn'>✖</label><h3 style='color:#38bdf8; margin-top:0;'>Analisi Subclaim {i+1}</h3><p style='color:#e2e8f0; font-style:italic;'>\"{sc}\"</p><hr style='border:none; border-top:1px solid rgba(255,255,255,0.1); margin:15px 0;'><strong style='color:#a78bfa;'>🧠 Ragionamento:</strong><p style='color:#f8fafc; font-size:0.95rem; line-height:1.6;'>{reasoning}</p><strong style='color:#a78bfa; margin-top:20px; display:block;'>📄 Top 5 Evidenze:</strong>{chunks_html}</div></div>"
                    card_html = f"<label for='modal-load-{target_phase}-{i}' class='card-btn' style='width:100%; max-width:400px; flex-grow:1;'><div style='position:absolute; right:10px; bottom:10px; font-size:3rem; opacity:0.04;'>🔍</div><div style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>SUBCLAIM {i+1}</div><div style='font-size:0.95rem; color:#f8fafc; margin-bottom:8px;'>\"{sc}\"</div><div style='font-size:0.8rem; font-weight:600; color:#38bdf8;'>{status}</div></label>{modal_html}"
                else:
                    card_html = f"<div style='background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); padding:15px 20px; border-radius:12px; width:100%; max-width:400px; flex-grow:1; text-align:left;'><div style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>SUBCLAIM {i+1}</div><div style='font-size:0.95rem; color:#f8fafc; margin-bottom:8px;'>\"{sc}\"</div><div style='font-size:0.8rem; font-weight:600; color:#38bdf8;'>{status}</div></div>"
                html += card_html
            html += "</div>"
            return html

        sc_html_p2 = get_cards_html(2)
        sc_html_p3 = get_cards_html(3)
        
        slide1_tree = f"<div style='display:flex; flex-direction:column; align-items:center; width:100%; max-width:800px; margin:20px auto; gap:10px;'>" + "".join([f"<div style='background:rgba(255,255,255,0.03); border:1px solid rgba(129,140,248,0.3); border-left:4px solid #818cf8; border-radius:12px; padding:15px; color:#e2e8f0; width:100%; text-align:left;'><div style='font-size:0.75rem; color:#818cf8; font-weight:bold; margin-bottom:5px;'>Subclaim {i+1}</div>{sc}</div>" for i, sc in enumerate(subclaims)]) + "</div>"
        safe_claim = claim.replace('"', '&quot;')
        slide1_content = f'<div style="color:rgba(248,250,252,0.6); font-size:1.2rem; text-transform:uppercase; letter-spacing:2px; margin-bottom:20px;">Original Claim Decomposition</div><div style="background:#0f172a; border:1px solid #38bdf8; border-radius:12px; padding:20px; color:#f8fafc; font-style:italic; max-width:800px; margin:0 auto; text-align:center;">"{safe_claim}"</div>{slide1_tree}'
        
        progress_percent = (step - 1) * 33.33
        stepper_html = f"""
        <div style="width: 100%; max-width: 500px; margin: 20px auto; position: relative;">
            <div style="position: absolute; top: 15px; left: 12.5%; width: 75%; height: 4px; background: rgba(255,255,255,0.1); z-index: 1;">
                <div style="height: 100%; background: {anim_color}; width: {progress_percent}%; transition: width 0.5s ease;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; position: relative; z-index: 2;">
                <div style="text-align: center; width: 25%; color: {anim_color if step>=1 else '#64748b'}; font-weight: bold;">●<br><span style="font-size: 0.75rem;">INPUT</span></div>
                <div style="text-align: center; width: 25%; color: {anim_color if step>=2 else '#64748b'}; font-weight: bold;">●<br><span style="font-size: 0.75rem;">RAG</span></div>
                <div style="text-align: center; width: 25%; color: {anim_color if step>=3 else '#64748b'}; font-weight: bold;">●<br><span style="font-size: 0.75rem;">EVAL</span></div>
                <div style="text-align: center; width: 25%; color: {anim_color if step>=4 else '#64748b'}; font-weight: bold;">●<br><span style="font-size: 0.75rem;">DONE</span></div>
            </div>
        </div>
        """

        html_content = f"""
        <style>
        .stApp {{ pointer-events: none !important; overflow: hidden !important; }}
        .cyber-overlay {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(15, 23, 42, 0.98); backdrop-filter: blur(20px); z-index: 9999999; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding-top:50px; pointer-events: auto !important; overflow-y: auto; }}
        @keyframes pulsate {{ 0% {{ transform: scale(0.6); opacity: 1; }} 100% {{ transform: scale(1.4); opacity: 0; }} }}
        </style>
        <div class="cyber-overlay">
          <div style="position: relative; width: 80px; height: 80px; display: flex; align-items: center; justify-content: center; margin-bottom: 1rem;">
              <div style="position: absolute; width: 100%; height: 100%; border-radius: 50%; border: 2px solid {anim_color}; animation: pulsate 2s infinite ease-out;"></div>
              <div style="width: 20px; height: 20px; background-color: {anim_color}; border-radius: 50%; box-shadow: 0 0 20px {anim_color};"></div>
          </div>
          <div style="font-size: 2rem; font-weight: 800; color: #f8fafc; text-align:center;">{central_title}</div>
          <div style="font-size: 1rem; color: #94a3b8; margin-bottom: 10px; text-align:center;">{central_subtitle}</div>
          {stepper_html}
          <div style="margin-top: 20px; width: 100%; text-align: center;">
              {sc_html_p2 if step == 2 else sc_html_p3 if step >= 3 else slide1_content}
          </div>
        </div>
        """
        overlay_placeholder.html(html_content)

    if verify_clicked:
        if claim.strip():
            st.session_state.fact_check_claim = claim
            st.session_state.current_subclaims = []
            st.session_state.current_evaluations = []
            st.session_state.source_selections = {}
            st.session_state.downloader_status = {}
            st.session_state.retriever_status = {}
            if "current_final" in st.session_state: del st.session_state["current_final"]
            error_placeholder.empty() 
            update_interactive_loading(claim=claim, step=1)
                
            try:
                response = requests.post("http://127.0.0.1:8000/api/v1/fact-check-stream", json={"claim": claim}, stream=True, timeout=900)
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: "):
                                data_str = decoded_line[6:]
                                try:
                                    step_data = json.loads(data_str)
                                    if "error" in step_data:
                                        error_placeholder.error(f"❌ Pipeline Error: {step_data['error']}")
                                        break
                                    if "decompose" in step_data:
                                        scs = step_data["decompose"].get("verifiable_subclaims", [])
                                        for sc in scs: st.session_state.current_subclaims.append(sc if isinstance(sc, str) else sc.get("claim", str(sc)))
                                        update_interactive_loading(claim=claim, step=2, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=0, total_to_verify=len(st.session_state.current_subclaims))
                                    elif "source_selector" in step_data:
                                        info = step_data["source_selector"]
                                        sub_id = info.get("subclaim_id")
                                        if sub_id: st.session_state.source_selections[sub_id] = [k for k, v in (info.get("retrieval_source") or {}).items() if v > 1]
                                        update_interactive_loading(claim=claim, step=2, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=0, total_to_verify=len(st.session_state.current_subclaims))
                                    elif "downloader_agent" in step_data:
                                        info = step_data["downloader_agent"]
                                        sub_id = info.get("subclaim_id")
                                        if sub_id: st.session_state.downloader_status[sub_id] = info.get("downloaded_chunks_count", 0)
                                        update_interactive_loading(claim=claim, step=2, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=0, total_to_verify=len(st.session_state.current_subclaims))
                                    elif "hybrid_retriever" in step_data:
                                        info = step_data["hybrid_retriever"]
                                        sub_id = info.get("subclaim_id")
                                        if sub_id: st.session_state.retriever_status[sub_id] = info.get("retrieved_chunks_count", 0)
                                        st.session_state.max_step = max(st.session_state.get("max_step", 1), 2)
                                        update_interactive_loading(claim=claim, step=st.session_state.max_step, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=len(st.session_state.current_evaluations), total_to_verify=len(st.session_state.current_subclaims))
                                    elif "verify_subclaim" in step_data or "evaluate_subclaim" in step_data or "reasoning" in step_data or "veracity" in step_data:
                                        inner_data = step_data.get("verify_subclaim", step_data.get("evaluate_subclaim", step_data.get("veracity", {})))
                                        for er in (inner_data.get("evaluation_results", []) if isinstance(inner_data, dict) else []):
                                            if er not in st.session_state.current_evaluations: st.session_state.current_evaluations.append(er)
                                        st.session_state.max_step = max(st.session_state.get("max_step", 1), 3)
                                        update_interactive_loading(claim=claim, step=st.session_state.max_step, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=len(st.session_state.current_evaluations), total_to_verify=len(st.session_state.current_subclaims))
                                    elif "aggregate" in step_data:
                                        st.session_state.current_final = step_data["aggregate"].get("final_verdict", {})
                                        st.session_state.final_evaluations = st.session_state.current_evaluations
                                        st.session_state.final_claim = claim
                                        st.session_state.final_subclaims = st.session_state.current_subclaims
                                        st.rerun()
                                except json.JSONDecodeError: pass
                else: error_placeholder.error(f"❌ Backend Connection Error (Status Code: {response.status_code})")
            except Exception as e: error_placeholder.error(f"❌ Failed to connect to the backend API: {str(e)}")

# ==========================================
# 6. DASHBOARD RISULTATI NAVIGABILE (FASE DONE)
# ==========================================
if "current_final" in st.session_state and "final_evaluations" in st.session_state:
    st.markdown("<div id='results-anchor'></div>", unsafe_allow_html=True)
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    col_menu, col_dettagli = st.columns([1, 2.8], gap="large")
    
    with col_menu:
        st.markdown("<h3 style='color:#38bdf8; margin-top:0; margin-bottom: 30px; font-weight:800; font-size:1.1rem; text-transform: uppercase; letter-spacing: 1px;'>Pipeline Nav</h3>", unsafe_allow_html=True)
        
        # Menu con Timeline Verticale (CSS specifico in testa al file gestisce lo stile)
        fase_selezionata = st.radio(
            "Seleziona la fase:",
            ["Fase 1: Decomposizione Claim", "Fase 2: Recupero Fonti (RAG)", "Fase 3: Valutazione Clinica", "Fase 4: Verdetto Finale"],
            index=3,
            label_visibility="collapsed"
        )
        
    with col_dettagli:
        # --- FASE 1: Decomposizione ---
        if "Fase 1" in fase_selezionata:
            st.markdown("<h2 style='color:#f8fafc; margin-top:0; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;'>1. Decomposizione del Claim Originale</h2>", unsafe_allow_html=True)
            st.info(f"**Claim Analizzato:**\n{st.session_state.final_claim}")
            st.markdown("<br><h4 style='color:#94a3b8; font-weight:600;'>Componenti Estratte (Subclaims):</h4>", unsafe_allow_html=True)
            
            st.markdown("<div style='display:flex; flex-direction:column; align-items:center; width:100%;'>", unsafe_allow_html=True)
            for i, sc in enumerate(st.session_state.final_subclaims):
                st.markdown(f"""
                <div style='background:rgba(255,255,255,0.03); padding:15px 25px; border-radius:12px; margin-bottom:15px; border-left: 4px solid #818cf8; box-shadow: 0 4px 10px rgba(0,0,0,0.15); width:100%; max-width:800px; text-align:left;'>
                    <div style='color:#818cf8; font-size:0.75rem; font-weight:800; text-transform:uppercase; margin-bottom:8px; letter-spacing:1px;'>Subclaim {i+1}</div>
                    <div style='color:#f8fafc; font-size:1.1rem; line-height:1.5;'>{sc}</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
                
        # --- FASE 2: RAG (Con Finestre Modali/Popup) ---
        elif "Fase 2" in fase_selezionata:
            st.markdown("<h2 style='color:#f8fafc; margin-top:0; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;'>2. Documenti Recuperati dalla Letteratura (RAG)</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color:#94a3b8; margin-bottom:25px;'>Documentazione scientifica estrapolata per ciascun subclaim. Clicca sulle schede per aprire l'analisi delle fonti.</p>", unsafe_allow_html=True)
            
            html_rag = "<div style='display:flex; flex-direction:column; align-items:center; width:100%; gap:15px;'>"
            for i, ev in enumerate(st.session_state.final_evaluations):
                sc = ev.get("subclaim", "")
                chunks = ev.get("retrieved_chunks", [])[:5]
                chunks_html = "".join([f"<div style='background:#1e293b; padding:15px; margin:10px 0; border-left:4px solid #38bdf8; border-radius:8px; font-size:0.9rem;'><strong style='color:#38bdf8; display:block; margin-bottom:8px;'>{c.get('metadata', {}).get('title', 'Ref')}</strong><span style='color:#cbd5e1; line-height:1.6;'>{highlight_quotes(c.get('text', ''), ev.get('supporting_quotes', []), ev.get('refuting_quotes', []))}</span></div>" for c in chunks])
                
                modal_html = f"<input type='checkbox' id='modal-rag-{i}' class='modal-toggle' style='display:none;'><div class='modal-wrapper'><div class='modal-card'><label for='modal-rag-{i}' class='close-btn'>✖</label><h3 style='color:#38bdf8; margin-top:0;'>Fonti Subclaim {i+1}</h3><p style='color:#e2e8f0; font-style:italic;'>\"{sc}\"</p><hr style='border:none; border-top:1px solid rgba(255,255,255,0.1); margin:15px 0;'><strong style='color:#a78bfa; margin-top:20px; display:block;'>📄 Documenti estratti:</strong>{chunks_html if chunks else '<p>Nessun documento trovato.</p>'}</div></div>"
                
                html_rag += f"<label for='modal-rag-{i}' class='card-btn' style='width:100%; max-width:800px;'><div style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>Fonti Subclaim {i+1}</div><div style='font-size:1.05rem; color:#f8fafc;'>\"{sc}\"</div><div style='position:absolute; right:20px; top:50%; transform:translateY(-50%); font-size:1.5rem;'>📚</div></label>{modal_html}"
            html_rag += "</div>"
            st.markdown(html_rag, unsafe_allow_html=True)

        # --- FASE 3: Valutazione Clinica (Con Finestre Modali/Popup) ---
        elif "Fase 3" in fase_selezionata:
            st.markdown("<h2 style='color:#f8fafc; margin-top:0; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;'>3. Analisi e Ragionamento Clinico</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color:#94a3b8; margin-bottom:25px;'>Spiegazione logica del modello per ogni singola componente. Clicca sulle schede per aprire l'analisi.</p>", unsafe_allow_html=True)
            
            html_eval = "<div style='display:flex; flex-wrap:wrap; gap:15px; justify-content:center;'>"
            for i, ev in enumerate(st.session_state.final_evaluations):
                sc = ev.get("subclaim", "")
                lbl = ev.get("label", "NEI").upper()
                reasoning = ev.get("justification", ev.get("selection_reasoning", "No reasoning provided."))
                c_col, c_icon = ("#10b981", "✅") if lbl == "SUPPORTED" else ("#ef4444", "❌") if lbl == "REFUTED" else ("#f59e0b", "⚠️")
                
                chunks_html = "".join([f"<div style='background:#1e293b; padding:10px; margin:8px 0; border-left:4px solid {c_col}; border-radius:6px; font-size:0.85rem; text-align:left;'><strong style='color:{c_col};'>{c.get('metadata', {}).get('title', 'Ref')}</strong><br><em style='color:#cbd5e1;'>{highlight_quotes(c.get('text', ''), ev.get('supporting_quotes', []), ev.get('refuting_quotes', []))}</em></div>" for c in ev.get("retrieved_chunks", [])[:5]])
                
                modal_html = f"<input type='checkbox' id='modal-eval-{i}' class='modal-toggle' style='display:none;'><div class='modal-wrapper'><div class='modal-card'><label for='modal-eval-{i}' class='close-btn'>✖</label><h3 style='color:#38bdf8; margin-top:0;'>Analisi Subclaim {i+1}</h3><p style='color:#e2e8f0; font-style:italic;'>\"{sc}\"</p><hr style='border:none; border-top:1px solid rgba(255,255,255,0.1); margin:15px 0;'><strong style='color:#a78bfa; font-size:1.1rem;'>🧠 Ragionamento:</strong><p style='color:#f8fafc; font-size:0.95rem; line-height:1.6;'>{reasoning}</p><strong style='color:#a78bfa; font-size:1.1rem; margin-top:20px; display:block;'>📄 Top 5 Evidenze:</strong>{chunks_html}</div></div>"
                
                html_eval += f"<label for='modal-eval-{i}' class='card-btn' style='width:100%; max-width:400px; border-left:4px solid {c_col}; flex-grow:1;'><div style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>SUBCLAIM {i+1}</div><div style='font-size:0.95rem; color:#f8fafc; margin-bottom:10px;'>\"{sc}\"</div><div style='font-size:0.85rem; font-weight:700; color:{c_col};'> {c_icon} Evaluated: {lbl}</div></label>{modal_html}"
            html_eval += "</div>"
            st.markdown(html_eval, unsafe_allow_html=True)

        # --- FASE 4: Verdetto Orizzontale Proporzionato + Bypass 0% ---
        elif "Fase 4" in fase_selezionata:
            st.markdown("<h2 style='color:#f8fafc; margin-top:0; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;'>4. Aggregazione e Verdetto Finale</h2>", unsafe_allow_html=True)
            
            raw_dict = st.session_state.current_final
            verdict = str(raw_dict.get("label", raw_dict.get("final_verdict", "NEI"))).strip().upper()
            raw_conf = raw_dict.get("confidence", raw_dict.get("confidence_score", 0.0))
            try: raw_conf = float(raw_conf)
            except: raw_conf = 0.0
            
            # BYPASS MEDIA SUBCLAIMS (Per ovviare alla logica AND del backend che sputa 0.0)
            if raw_conf < 0.01 and st.session_state.final_evaluations:
                confs_list = []
                for ev in st.session_state.final_evaluations:
                    try: confs_list.append(float(ev.get("confidence", ev.get("confidence_score", 0.0))))
                    except: pass
                if confs_list: raw_conf = sum(confs_list) / len(confs_list)
            
            conf = int(raw_conf * 100) if 0.0 < raw_conf <= 1.0 else int(raw_conf)
            just = raw_dict.get("justification", raw_dict.get("reasoning", "Nessuna giustificazione fornita."))
            c_col, c_icon = ("#10b981", "✅") if verdict == "SUPPORTED" else ("#ef4444", "❌") if verdict == "REFUTED" else ("#f59e0b", "⚠️")

            # Box Orizzontale Pulito
            st.markdown(f"""
            <div style='background:rgba(30,41,59,0.4); border:1px solid rgba(255,255,255,0.05); border-radius:16px; padding:35px; display:flex; flex-direction:row; align-items:center; gap:40px; box-shadow:0 10px 30px -10px rgba(0,0,0,0.3); margin-top:20px; margin-bottom: 30px;'>
                <div style='flex-shrink:0; position:relative; width:160px; height:160px; border-radius:50%; background:conic-gradient({c_col} {conf}%, #1e293b 0); display:flex; align-items:center; justify-content:center; box-shadow:0 0 25px {c_col}30;'>
                    <div style='position:absolute; width:135px; height:135px; background:#0f172a; border-radius:50%; display:flex; flex-direction:column; align-items:center; justify-content:center;'>
                        <span style='font-size:2.8rem; font-weight:800; color:#f8fafc;'>{conf}%</span>
                        <span style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; letter-spacing:1px;'>Confidence</span>
                    </div>
                </div>
                <div style='flex-grow:1; display:flex; flex-direction:column; justify-content:center;'>
                    <div style='display:flex; align-items:center; gap:15px; margin-bottom:20px;'>
                        <span style='font-size:2.8rem;'>{c_icon}</span>
                        <span style='color:{c_col}; font-size:2.4rem; font-weight:900; letter-spacing:1px; text-transform:uppercase;'>{verdict}</span>
                    </div>
                    <div style='background:rgba(0,0,0,0.2); padding:20px; border-radius:12px; border-left:4px solid {c_col};'>
                        <h3 style='color:#a78bfa; margin-top:0; margin-bottom:10px; font-size:1.05rem; text-transform:uppercase; letter-spacing:1px;'>Medical Justification</h3>
                        <div style='color:#cbd5e1; font-size:1.05rem; line-height:1.6;'>{just}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Bottoni allineati sotto la card dei risultati
            btn_col1, btn_col2, _ = st.columns([1, 1, 1.5])
            with btn_col1:
                try:
                    from utils.pdf_generator import generate_fact_check_pdf
                    pdf_bytes = generate_fact_check_pdf(claim=st.session_state.final_claim, final_verdict=st.session_state.current_final, subclaims=st.session_state.final_evaluations)
                    st.download_button("📄 Download PDF Report", data=pdf_bytes, file_name="FactCheck_Report.pdf", use_container_width=True)
                except Exception: pass
            with btn_col2:
                if st.button("🔄 New Analysis", use_container_width=True):
                    for key in ["current_final", "final_evaluations", "final_claim", "final_subclaims", "max_step", "source_selections", "downloader_status", "retriever_status"]:
                        if key in st.session_state: del st.session_state[key]
                    st.rerun()

    components.html("<script>setTimeout(function(){const el = window.parent.document.getElementById('results-anchor'); if(el) el.scrollIntoView({behavior: 'smooth', block: 'start'});}, 500);</script>", height=0, width=0)

# ==========================================
# FOOTER RIPRISTINATO
# ==========================================
st.markdown("""
<div class="footer">
    MedFactCheck Project • Big Data Engineering MSc Unina • Powered by RAG & LLMs
</div>
""", unsafe_allow_html=True)