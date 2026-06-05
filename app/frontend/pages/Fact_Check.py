import streamlit as st
import streamlit.components.v1 as components
import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px
import importlib

# 1. Configurazione della Pagina
st.set_page_config(
    page_title="Fact Check | Med Fact Check",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. CSS Avanzato
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
    
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stHeader"], header { display: none !important; height: 0px !important; padding: 0 !important; }
    
    [data-testid="stAppViewContainer"] {
        overflow-x: hidden;
        background-color: #0f172a !important;
    }
    
    .main .block-container, [data-testid="stMainBlockContainer"], .block-container {
        padding-top: 0rem !important; padding-left: 0rem !important; padding-right: 0rem !important;
        padding-bottom: 0rem !important; margin: 0rem !important; max-width: 100% !important;
        width: 100% !important; min-height: 100vh !important; position: relative !important;
        box-sizing: border-box !important;
    }

    html, body { font-family: 'Inter', sans-serif; background-color: #0f172a !important; color: #f8fafc; margin: 0 !important; padding: 0 !important; }

    .navbar {
        position: fixed; top: 0; left: 0; width: 100%; background-color: #0b1120;
        border-bottom: 1px solid rgba(255,255,255,0.05); padding: 1.5rem 4rem; display: flex; 
        justify-content: space-between; align-items: center; z-index: 9999; box-sizing: border-box;
    }
    .nav-logo { font-size: 1.5rem; font-weight: 800; color: #3b82f6; }

    .panel-title { font-size: 2.8rem; font-weight: 800; letter-spacing: -0.05em; background: linear-gradient(to right, #00f2fe, #4facfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 5px; }
    .panel-subtitle { font-size: 1.1rem; color: #94a3b8; margin-bottom: 35px; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 20px !important; border: 1px solid rgba(255, 255, 255, 0.05) !important;
        background: rgba(30, 41, 59, 0.4) !important; backdrop-filter: blur(12px) !important;
        padding: 1.8rem !important; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.3) !important;
    }

    .metric-container { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .metric-card { background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255, 255, 255, 0.05); padding: 1.2rem; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .metric-val { font-size: 2rem; font-weight: 800; color: #f1f5f9; margin-bottom: 2px;}
    .metric-label { font-size: 0.8rem; text-transform: uppercase; color: #94a3b8; font-weight: 600; letter-spacing: 0.05em; }

    .subclaim-card { background: rgba(30, 41, 59, 0.5); backdrop-filter: blur(8px); border-radius: 16px; padding: 1.8rem; margin-bottom: 1.2rem; border: 1px solid rgba(255, 255, 255, 0.03); border-left: 6px solid #64748b; transition: all 0.3s ease; }
    .subclaim-card:hover { transform: translateX(6px); background: rgba(30, 41, 59, 0.7); box-shadow: 0 10px 25px -5px rgba(59, 130, 246, 0.15); }
    .subclaim-card.SUPPORTED { border-left-color: #10b981; }
    .subclaim-card.REFUTED { border-left-color: #ef4444; }
    .subclaim-card.NEI { border-left-color: #f59e0b; }
    
    .badge { display: inline-block; padding: 6px 14px; border-radius: 30px; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.03em; }
    .badge.SUPPORTED { background-color: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge.REFUTED { background-color: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge.NEI { background-color: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }
    
    .evidence-box { background-color: #0b1120; border-left: 4px solid #3b82f6; padding: 14px; margin-top: 12px; font-size: 0.9rem; color: #cbd5e1; border-radius: 6px; }

    .verdict-box { padding: 2rem; border-radius: 16px; text-align: center; font-weight: 800; font-size: 1.8rem; text-transform: uppercase; letter-spacing: 0.02em; }
    .verdict-box.supported { background: linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, rgba(16, 185, 129, 0.15) 100%); color: #10b981; border: 1px solid #10b981; }
    .verdict-box.refuted { background: linear-gradient(135deg, rgba(239, 68, 68, 0.05) 0%, rgba(239, 68, 68, 0.15) 100%); color: #ef4444; border: 1px solid #ef4444; }
    .verdict-box.nei { background: linear-gradient(135deg, rgba(245, 158, 11, 0.05) 0%, rgba(245, 158, 11, 0.15) 100%); color: #f59e0b; border: 1px solid #f59e0b; }

    div.stButton > button, div.stDownloadButton > button { background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%) !important; border: none !important; color: #0f172a !important; font-weight: 800 !important; font-size: 1.15rem !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; border-radius: 50px !important; padding: 0.9rem 2.5rem !important; box-shadow: 0 0 25px rgba(0, 242, 254, 0.4) !important; transition: all 0.4s ease !important; position: relative !important; z-index: 999 !important; }
    div.stButton > button p, div.stDownloadButton > button p { white-space: nowrap !important; margin: 0 !important; color: #0f172a !important; font-weight: 800 !important; }
    div.stButton > button:hover, div.stDownloadButton > button:hover { transform: scale(1.04) translateY(-2px) !important; box-shadow: 0 0 35px rgba(0, 242, 254, 0.7) !important; color: #000000 !important; }
    
    div.stButton > button[kind="secondary"] { border-radius: 30px !important; background-color: rgba(255,255,255,0.02) !important; border: 1px solid rgba(255,255,255,0.08) !important; color: #cbd5e1 !important; padding: 0.5rem 1.5rem !important; font-weight: 600 !important; box-shadow: none !important; margin-bottom: 2rem !important; }
    div.stButton > button[kind="secondary"] p { color: #cbd5e1 !important; font-weight: 600 !important; }
    div.stButton > button[kind="secondary"]:hover { border-color: #3b82f6 !important; background-color: rgba(59, 130, 246, 0.1) !important; color: #38bdf8 !important; }
    
    .footer { width: 100%; text-align: center; padding: 2rem 0; color: #64748b; font-size: 0.85rem; border-top: 1px solid rgba(255,255,255,0.05); background-color: #0b1120; margin-top: 150px; display: block; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="navbar">
        <div class="nav-logo">⚕️ Med Fact Check</div>
        <div style="font-size: 0.9rem; color: #94a3b8; font-weight:600;">MSc Unina • Big Data Engineering</div>
    </div>
""", unsafe_allow_html=True)

st.markdown('<div style="margin-top: 8rem;"></div>', unsafe_allow_html=True)

# 4. WRAPPER PRINCIPALE
_, col_main, _ = st.columns([1, 14, 1])

with col_main:
    if st.button("← Back to Home", type="secondary"):
        st.switch_page("app.py")

    st.markdown('<div class="panel-title">Medical Fact Check Panel</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-subtitle">Submit a medical claim and rigorously verify it against trusted scientific literature. (💡 Hint: Press <b>Ctrl+Enter</b> or <b>Cmd+Enter</b> to submit)</div>', unsafe_allow_html=True)

    input_method = st.radio("Choose Input Method:", ["✍️ Text Input", "📄 Upload TXT", "🔗 Provide URL"], horizontal=True)
    claim = ""

    with st.container():
        if input_method == "✍️ Text Input":
            claim = st.text_area("Medical Claim:", height=130, placeholder="E.g., Taking a daily vitamin D supplement helps prevent osteoporosis...")
        elif input_method == "📄 Upload TXT":
            uploaded_file = st.file_uploader("Choose a .txt file", type="txt")
            if uploaded_file is not None:
                claim = uploaded_file.getvalue().decode("utf-8")
                st.text_area("File Content (Preview):", value=claim, height=100, disabled=True)
        elif input_method == "🔗 Provide URL":
            url_input = st.text_input("Enter Article URL:", placeholder="https://example.com/article")
            if url_input:
                if not url_input.startswith(("http://", "https://")):
                    st.warning("Please enter a valid URL starting with http:// or https://")
                else:
                    try:
                        with st.spinner("Fetching content from URL..."):
                            res = requests.get(url_input, timeout=10)
                            if res.status_code == 200:
                                soup = BeautifulSoup(res.text, "html.parser")
                                for script in soup(["script", "style"]): script.extract()
                                claim = soup.get_text(separator=' ', strip=True)
                                st.success("Content loaded successfully!")
                                preview = claim[:1000] + ("..." if len(claim) > 1000 else "")
                                st.text_area("Extracted Content (Preview):", value=preview, height=100, disabled=True)
                            else: st.error(f"Failed to fetch URL. Status code: {res.status_code}")
                    except Exception as e: st.error(f"Error fetching URL: {str(e)}")

    if "real_results" not in st.session_state:
        st.session_state.real_results = None

    st.markdown("<br>", unsafe_allow_html=True)
    error_placeholder = st.empty()
    
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        verify_clicked = st.button("Verify Claim", type="primary", use_container_width=True)

    # ==========================================
    # 5. LOGICA BACKEND E ANIMAZIONE DI CARICAMENTO PULITA
    # ==========================================
    if verify_clicked:
        if not claim.strip():
            st.warning("Please provide a valid claim or document before verifying.")
        else:
            current_subclaims, current_evaluations = [], []
            overlay_placeholder = st.empty()
            error_placeholder.empty() 
            
            def update_interactive_loading(step=1, subclaims=None, verified_count=0, total_to_verify=1):
                if subclaims is None: subclaims = []
                
                if step == 1:
                    central_title = "Initializing Medical AI Pipeline"
                    central_subtitle = "Warming up decomposition agents..."
                    anim_color = "#38bdf8"
                elif step == 2:
                    central_title = "RAG Database Ingestion"
                    central_subtitle = "<span class='rag-messages'></span>"
                    anim_color = "#818cf8"
                elif step == 3:
                    central_title = "Clinical Reasoning Agent"
                    central_subtitle = f"Validating {verified_count} of {total_to_verify} extracted claims..."
                    anim_color = "#a78bfa"
                else:
                    central_title = "Generating Final Consensus"
                    central_subtitle = "Aggregating verdicts and calculating confidence score..."
                    anim_color = "#10b981"
                
                sc_html = ""
                if step >= 2 and subclaims:
                    # NOTA BENE: Nessun a capo o indentazione all'interno di questa stringa f-string per evitare bug markdown!
                    sc_html += "<div style='display:flex; flex-wrap:wrap; gap:10px; justify-content:center; margin-top:20px; width:100%; max-width:800px;'>"
                    for i, sc in enumerate(subclaims):
                        if step == 2: status = "⏳ Ingesting Literature..."
                        elif step == 3 and i < verified_count: status = "✅ Verified"
                        elif step == 3 and i == verified_count: status = "🔍 Evaluating..."
                        else: status = "⏳ Pending"
                        # Schiacciamo tutto su una sola riga senza indentazioni per evitare che diventi un blocco di codice
                        sc_html += f"<div style='background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); padding:12px 18px; border-radius:12px; width:calc(50% - 5px); min-width:300px; text-align:left;'><div style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>SUBCLAIM {i+1}</div><div style='font-size:0.95rem; color:#f8fafc; margin-bottom:8px; line-height:1.4;'>\"{sc}\"</div><div style='font-size:0.8rem; font-weight:600; color:#38bdf8;'>{status}</div></div>"
                    sc_html += "</div>"

                # TUTTO L'HTML A MARGINE SINISTRO
                html_content = f"""
<style>
.stApp {{ pointer-events: none !important; overflow: hidden !important; }}
.cyber-overlay {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(15, 23, 42, 0.97); backdrop-filter: blur(20px); z-index: 9999999 !important; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2rem; pointer-events: auto !important; }}
.pulse-container {{ position: relative; width: 150px; height: 150px; display: flex; align-items: center; justify-content: center; margin-bottom: 2rem; }}
.pulse-ring {{ position: absolute; width: 100%; height: 100%; border-radius: 50%; border: 2px solid {anim_color}; animation: pulsate 2s infinite ease-out; }}
.pulse-ring:nth-child(2) {{ animation-delay: 0.6s; }}
.pulse-ring:nth-child(3) {{ animation-delay: 1.2s; }}
.pulse-core {{ width: 50px; height: 50px; background-color: {anim_color}; border-radius: 50%; box-shadow: 0 0 20px {anim_color}; z-index: 10; animation: core-glow 2s infinite alternate; }}
@keyframes pulsate {{ 0% {{ transform: scale(0.5); opacity: 1; }} 100% {{ transform: scale(1.5); opacity: 0; }} }}
@keyframes core-glow {{ 0% {{ transform: scale(0.9); box-shadow: 0 0 10px {anim_color}; }} 100% {{ transform: scale(1.1); box-shadow: 0 0 30px {anim_color}; }} }}
.stage-title {{ font-size: 2.2rem; font-weight: 800; color: #f8fafc; letter-spacing: 1px; margin: 0 0 10px 0; text-align: center; }}
.stage-subtitle {{ font-size: 1.1rem; color: #94a3b8; font-weight: 400; text-align: center; max-width: 600px; line-height:1.5; }}
.phase-indicator {{ margin-top: 30px; font-size: 0.85rem; font-weight: 700; color: #475569; letter-spacing: 2px; text-transform: uppercase; }}
.rag-messages::after {{ content: "Vectorizing PMC Literature..."; animation: changeText 12s infinite; }}
@keyframes changeText {{ 
0%, 25% {{ content: "Querying dense embeddings database..."; }} 
26%, 50% {{ content: "Cross-referencing global medical trials..."; }} 
51%, 75% {{ content: "Applying Reciprocal Rank Fusion..."; }} 
76%, 100% {{ content: "Fetching highest accuracy documents..."; }} 
}}
</style>
<div class="cyber-overlay">
<div class="pulse-container"><div class="pulse-ring"></div><div class="pulse-ring"></div><div class="pulse-ring"></div><div class="pulse-core"></div></div>
<div class="stage-title">{central_title}</div>
<div class="stage-subtitle">{central_subtitle}</div>
<div class="phase-indicator">PIPELINE PHASE {step} / 4</div>
{sc_html}
</div>
"""
                overlay_placeholder.markdown(html_content, unsafe_allow_html=True)
            
            # Step 1
            update_interactive_loading(step=1)
                
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
                                        overlay_placeholder.empty()
                                        error_placeholder.error(f"❌ Pipeline Error: {step_data['error']}")
                                        break
                                    if "decompose" in step_data:
                                        scs = step_data["decompose"].get("verifiable_subclaims", [])
                                        for sc in scs:
                                            sc_text = sc if isinstance(sc, str) else sc.get("claim", str(sc))
                                            current_subclaims.append(sc_text)
                                        update_interactive_loading(step=2, subclaims=current_subclaims, verified_count=0, total_to_verify=len(current_subclaims))
                                        
                                    elif "verify_subclaim" in step_data:
                                        eval_results = step_data["verify_subclaim"].get("evaluation_results", [])
                                        for er in eval_results:
                                            if er not in current_evaluations:
                                                current_evaluations.append(er)
                                        update_interactive_loading(step=3, subclaims=current_subclaims, verified_count=len(current_evaluations), total_to_verify=len(current_subclaims))
                                        
                                    elif "aggregate" in step_data:
                                        update_interactive_loading(step=4, subclaims=current_subclaims, verified_count=len(current_evaluations), total_to_verify=len(current_subclaims))
                                        current_final = step_data["aggregate"].get("final_verdict", {})
                                        st.session_state.real_results = {
                                            "subclaims": current_subclaims,
                                            "evaluations": current_evaluations,
                                            "final": current_final,
                                            "claim": claim
                                        }
                                        st.rerun()
                                except json.JSONDecodeError: pass
                else:
                    overlay_placeholder.empty()
                    error_placeholder.error(f"❌ Backend Connection Error (Status Code: {response.status_code})")
            except Exception as e:
                overlay_placeholder.empty()
                error_placeholder.error(f"❌ Failed to connect to the backend API: {str(e)}")

    # ==========================================
    # 6. RENDERING DINAMICO DEI RISULTATI
    # ==========================================
    if st.session_state.real_results:
        res = st.session_state.real_results
        
        st.markdown("<div id='results-anchor'></div>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:rgba(255,255,255,0.05); margin: 2rem 0;'>", unsafe_allow_html=True)
        
        total_sc = len(res['subclaims'])
        supported_count = sum(1 for e in res['evaluations'] if e.get('label', '').upper() == 'SUPPORTED')
        refuted_count = sum(1 for e in res['evaluations'] if e.get('label', '').upper() == 'REFUTED')
        avg_conf = pd.DataFrame([e.get('confidence', 0.0) for e in res['evaluations']])[0].mean() if res['evaluations'] else 0.0

        st.markdown(f"""
            <div class="metric-container">
                <div class="metric-card"><div class="metric-val" style="color:#38bdf8;">{total_sc}</div><div class="metric-label">Subclaims Found</div></div>
                <div class="metric-card"><div class="metric-val" style="color:#10b981;">{supported_count}</div><div class="metric-label">Verified Components</div></div>
                <div class="metric-card"><div class="metric-val" style="color:#ef4444;">{refuted_count}</div><div class="metric-label">Refuted Components</div></div>
                <div class="metric-card"><div class="metric-val" style="color:#f59e0b;">{avg_conf:.2f}</div><div class="metric-label">Avg Pipeline Confidence</div></div>
            </div>
        """, unsafe_allow_html=True)
        
        st.write("### 🧬 Granular Evidence Breakdown")
        
        for ev in res['evaluations']:
            sc_text = ev.get("subclaim", "Unknown Subclaim")
            lbl = ev.get("label", "nei").upper()
            conf = ev.get("confidence", 0.0)
            just = ev.get("justification", "No justification provided.")
            icon = "✅" if lbl == "SUPPORTED" else "❌" if lbl == "REFUTED" else "❓"
            
            st.markdown(f"""
                <div class="subclaim-card {lbl}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700; font-size:1.15rem; color:#f8fafc; display:flex; align-items:center; gap:8px;">{icon} Statement Component</span>
                        <span class="badge {lbl}">{lbl} • CONF: {conf:.2f}</span>
                    </div>
                    <p style="margin-top:10px; font-size:1.05rem; color:#e2e8f0; font-style:italic; line-height:1.5;">"{sc_text}"</p>
                    <div style="margin-top:15px; border-top: 1px solid rgba(255,255,255,0.04); padding-top:10px;">
                        <span style="font-size:0.8rem; font-weight:700; text-transform:uppercase; color:#64748b; display:block; margin-bottom:4px;">Scientific Justification</span>
                        <p style="color:#cbd5e1; font-size:0.95rem; line-height:1.6; margin:0;">{just}</p>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            evidence = ev.get("retrieved_chunks", [])
            if evidence:
                with st.expander("🔬 Toggle Evidence Documents (Literature Sources)"):
                    for chunk in evidence:
                        if isinstance(chunk, dict):
                            text = chunk.get("text", "")
                            meta = chunk.get("metadata", {})
                            url = meta.get("url", "")
                            source_title = meta.get("title", meta.get("id", "Unknown Source"))
                            if url:
                                st.markdown(f'<div class="evidence-box"><strong><a href="{url}" target="_blank" style="color:#38bdf8; text-decoration:none;">{source_title} ↗</a></strong>: <em>{text}</em></div>', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<div class="evidence-box"><strong>{source_title}</strong>: <em>{text}</em></div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="evidence-box"><em>{chunk}</em></div>', unsafe_allow_html=True)

        st.markdown("<hr style='border-color:rgba(255,255,255,0.05); margin: 3rem 0;'>", unsafe_allow_html=True)
        st.write("### 📊 System Consensus Summary")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            lbl = res['final'].get("label", "nei").lower()
            conf = res['final'].get("confidence", 0.0)
            css_class = lbl if lbl in ["supported", "refuted"] else "nei"
            st.markdown(f"""
                <div class="verdict-box {css_class}">
                    Final Consensus Verdict: {lbl.upper()} <br>
                    <span style="font-size: 0.95rem; font-weight: 500; color:#94a3b8; text-transform:none; letter-spacing:0;">Calculated Pipeline Confidence Score: {conf:.2f}</span>
                </div>
            """, unsafe_allow_html=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑_ Clear Analysis & Start New Check", type="secondary", use_container_width=True):
                st.session_state.real_results = None
                st.rerun()
                
        with col2:
            try:
                df = pd.DataFrame([e.get('label', 'nei').upper() for e in res['evaluations']], columns=['Verdict'])
                verdict_counts = df['Verdict'].value_counts().reset_index()
                verdict_counts.columns = ['Verdict', 'Count']
                
                fig = px.pie(verdict_counts, values='Count', names='Verdict', color='Verdict', color_discrete_map={"SUPPORTED": "#10b981", "REFUTED": "#ef4444", "NEI": "#f59e0b"}, hole=0.45)
                fig.update_layout(height=200, margin=dict(t=0, b=0, l=0, r=0), showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="#f8fafc")
                fig.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color='#0f172a', width=2)))
                st.plotly_chart(fig, use_container_width=True)
            except: pass
                
        st.markdown("<br>", unsafe_allow_html=True)
        _, center_down_col, _ = st.columns([1, 1, 1])
        with center_down_col:
            try:
                import utils.pdf_generator
                importlib.reload(utils.pdf_generator)
                pdf_bytes = utils.pdf_generator.generate_fact_check_pdf(claim=res['claim'], final_verdict=res['final'], subclaims=res['evaluations'])
                st.download_button(label="📄 Download Certified PDF Report", data=pdf_bytes, file_name="fact_check_report.pdf", mime="application/pdf", use_container_width=True)
            except Exception as e: st.error(f"Could not generate PDF: {str(e)}")

        components.html("""<script>var element = window.parent.document.getElementById('results-anchor'); if (element) {element.scrollIntoView({behavior: 'smooth', block: 'start'});}</script>""", height=0)

components.html("""
    <script>
    const doc = window.parent.document;
    doc.addEventListener('keydown', function(event) {
        if (event.key === 'Enter') {
            const active = doc.activeElement;
            const isTextarea = active && active.tagName.toLowerCase() === 'textarea';
            if (isTextarea && !(event.ctrlKey || event.metaKey)) return;
            if (!event.shiftKey) {
                const buttons = Array.from(doc.querySelectorAll('button[kind="primary"]'));
                const verifyBtn = buttons.find(b => b.innerText && b.innerText.toLowerCase().includes('verify claim'));
                if (verifyBtn) { verifyBtn.click(); event.preventDefault(); }
            }
        }
    });
    </script>
""", height=0, width=0)

st.markdown("""
<div class="footer">
    MedFactCheck Project • Big Data Engineering MSc Unina • Powered by RAG & LLMs
</div>
""", unsafe_allow_html=True)