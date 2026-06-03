import streamlit as st
import requests
import json
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="Fact Check | Med Fact Check",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    /* Hide the default sidebar navigation */
    [data-testid="stSidebarNav"] {
        display: none;
    }
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0px;
        font-family: 'Inter', sans-serif;
    }
    .subtitle {
        font-size: 1.2rem;
        font-weight: 400;
        color: #64748B;
        margin-top: 5px;
        margin-bottom: 30px;
        font-family: 'Inter', sans-serif;
    }
    
    
    
    div.stButton > button[kind="secondary"] {
        border: 1px solid #1E3A8A !important;
        color: #1E3A8A !important;
        background-color: white !important;
        font-weight: 600 !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #eff6ff !important;
        border-color: #1E3A8A !important;
    }
    
    
    
    div.stButton > button[kind="primary"],
div.stDownloadButton > button[kind="primary"] {
        background-color: #1E3A8A !important;
        border: none !important;
        outline: none !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        transition: background-color 0.3s ease !important;
    }
    div.stButton > button[kind="primary"]:hover,
div.stDownloadButton > button[kind="primary"]:hover {
        background-color: #1e40af !important;
        border: none !important;
    }
    div.stButton > button[kind="secondary"] {
        border: 1px solid #1E3A8A !important;
        color: #1E3A8A !important;
        background-color: white !important;
        font-weight: 600 !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #eff6ff !important;
        border-color: #1e40af !important;
    }

    .verdict-box {
        padding: 20px;
        border-radius: 8px;
        margin-top: 20px;
        text-align: center;
        font-weight: bold;
        font-size: 1.5rem;
    }
    .supported { background-color: #d1fae5; color: #065f46; border: 1px solid #10b981; }
    .refuted { background-color: #fee2e2; color: #991b1b; border: 1px solid #ef4444; }
    .nei { background-color: #f3f4f6; color: #374151; border: 1px solid #9ca3af; }
    
    /* Sidebar Legend Styling */
    .legend-title {
        font-size: 1.1rem;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 15px;
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 5px;
    }
    .legend-item {
        display: flex;
        align-items: center;
        margin-bottom: 15px;
    }
    .legend-icon {
        font-size: 1.2rem;
        margin-right: 10px;
    }
    .legend-text {
        font-weight: 600;
        color: #334155;
    }
    .legend-desc {
        font-size: 0.85rem;
        color: #64748B;
        margin-left: 30px;
        margin-top: -5px;
        margin-bottom: 10px;
    }
    /* Custom Subclaim Card Styling */
    .subclaim-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border: 1px solid #e2e8f0;
    }
    .subclaim-card.SUPPORTED { border-top: 5px solid #10b981; }
    .subclaim-card.REFUTED { border-top: 5px solid #ef4444; }
    .subclaim-card.NEI { border-top: 5px solid #9ca3af; }
    
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
        margin-bottom: 10px;
        text-transform: uppercase;
    }
    .badge.SUPPORTED { background-color: #d1fae5; color: #065f46; }
    .badge.REFUTED { background-color: #fee2e2; color: #991b1b; }
    .badge.NEI { background-color: #f3f4f6; color: #374151; }
    
    .justification-title {
        font-weight: 700;
        color: #334155;
        margin-top: 15px;
        margin-bottom: 5px;
    }
    .justification-text {
        color: #475569;
        font-size: 1rem;
        line-height: 1.6;
    }
    .evidence-box {
        background-color: #f8fafc;
        border-left: 4px solid #cbd5e1;
        padding: 10px 15px;
        margin-top: 10px;
        font-size: 0.95rem;
        color: #334155;
        border-radius: 0 8px 8px 0;
    }
    
    /* Custom Spinner */
    .custom-spinner {
        border: 3px solid #e2e8f0;
        border-top: 3px solid #3b82f6;
        border-radius: 50%;
        width: 20px;
        height: 20px;
        animation: spin 1s linear infinite;
        display: inline-block;
        margin-right: 15px;
        vertical-align: middle;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .status-box {
        background-color: #eff6ff;
        border-left: 4px solid #3b82f6;
        padding: 15px;
        border-radius: 8px;
        color: #1e3a8a;
        font-size: 1.05rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        margin-bottom: 20px;
    }
    
    .footer {
        text-align: center;
        padding: 20px;
        color: #64748B;
        font-size: 0.85rem;
        border-top: 1px solid #e2e8f0;
        margin-top: 50px;
    }
    
    </style>
""", unsafe_allow_html=True)

# Top Home Button
_, col_home = st.columns([10, 1])
with col_home:
    if st.button("🏠 Home", width='stretch'):
        st.switch_page("app.py")

# Sidebar
with st.sidebar:
    st.markdown('<div class="legend-title">ℹ️ Legend</div>', unsafe_allow_html=True)
    st.markdown('<p style="color: #64748B; font-size: 0.9rem;">Verdicts Levels:</p>', unsafe_allow_html=True)
    
    st.markdown("""
        <div class="legend-item"><span class="legend-icon">✅</span><span class="legend-text">Supported</span></div>
        <div class="legend-desc">The claim is completely backed by the scientific literature retrieved.</div>
        
        <div class="legend-item"><span class="legend-icon">❌</span><span class="legend-text">Refuted</span></div>
        <div class="legend-desc">The scientific evidence directly contradicts the claim.</div>
        
        <div class="legend-item"><span class="legend-icon">❓</span><span class="legend-text">Not Enough Info (NEI)</span></div>
        <div class="legend-desc">There is insufficient evidence to either support or refute the claim.</div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    if st.button("🗑️ Clear Analysis", width='stretch'):
        st.session_state.real_results = None
        st.rerun()

st.markdown('<div class="main-title">🩺 Medical Fact Check</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Submit a medical claim and rigorously verify it against trusted scientific literature.</div>', unsafe_allow_html=True)

input_method = st.radio(

    "Choose Input Method:",
    ["✍️ Text Input", "📄 Upload TXT", "🔗 Provide URL"],
    horizontal=True
)

claim = ""

with st.container(border=True):
    if input_method == "✍️ Text Input":
        claim = st.text_area("Medical Claim:", height=100, placeholder="E.g., Taking a daily vitamin D supplement helps prevent osteoporosis...")
        
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
                            for script in soup(["script", "style"]):
                                script.extract()
                            claim = soup.get_text(separator=' ', strip=True)
                            st.success("Content loaded successfully!")
                            preview = claim[:1000] + ("..." if len(claim) > 1000 else "")
                            st.text_area("Extracted Content (Preview):", value=preview, height=100, disabled=True)
                        else:
                            st.error(f"Failed to fetch URL. Status code: {res.status_code}")
                except Exception as e:
                    st.error(f"Error fetching URL: {str(e)}")

if "real_results" not in st.session_state:
    st.session_state.real_results = None

verify_clicked = st.button("Verify Claim", type="primary")

if verify_clicked:
    if not claim.strip():
        st.warning("Please provide a valid claim or document before verifying.")
    else:
        # Containers
        status_container = st.container()
        
        # We will collect the data as it streams to save it to session_state
        current_subclaims = []
        current_evaluations = []
        
        with status_container:
            status_placeholder = st.empty()
            status_placeholder.markdown('<div class="status-box"><div class="custom-spinner"></div>🧠 Decomposing claim...</div>', unsafe_allow_html=True)
            try:
                # Call the streaming endpoint
                response = requests.post(
                    "http://127.0.0.1:8000/api/v1/fact-check-stream",
                    json={"claim": claim},
                    stream=True,
                    timeout=900
                )
                
                if response.status_code == 200:
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: "):
                                data_str = decoded_line[6:]
                                try:
                                    step_data = json.loads(data_str)
                                
                                    if "error" in step_data:
                                        status_placeholder.error("❌ Pipeline Error")
                                        st.error(step_data["error"])
                                        break
                                    
                                    if "decompose" in step_data:
                                        status_placeholder.markdown('<div class="status-box"><div class="custom-spinner"></div>🔎 Retrieving evidence and evaluating...</div>', unsafe_allow_html=True)
                                        scs = step_data["decompose"].get("verifiable_subclaims", [])
                                        for sc in scs:
                                            sc_text = sc if isinstance(sc, str) else sc.get("claim", str(sc))
                                            current_subclaims.append(sc_text)
                                        
                                    elif "verify_subclaim" in step_data:
                                        eval_results = step_data["verify_subclaim"].get("evaluation_results", [])
                                        for er in eval_results:
                                            current_evaluations.append(er)
                                                    
                                    elif "aggregate" in step_data:
                                        status_placeholder.success("✅ Pipeline complete!")
                                        current_final = step_data["aggregate"].get("final_verdict", {})
                                    
                                        # Save to session state
                                        st.session_state.real_results = {
                                            "subclaims": current_subclaims,
                                            "evaluations": current_evaluations,
                                            "final": current_final,
                                            "claim": claim
                                        }
                                    
                                except json.JSONDecodeError:
                                    pass # Ignore malformed chunks
                else:
                    status_placeholder.error("❌ Connection Error")
                    st.error(f"Error from server: {response.text}")
            except Exception as e:
                status_placeholder.error("❌ Fatal Error")
                st.error(f"Failed to connect to the backend API: {str(e)}")

# Display results from session state
if st.session_state.real_results:
    res = st.session_state.real_results
    
    st.write(f"**Found {len(res['subclaims'])} verifiable subclaims:**")
    for sc in res['subclaims']:
        st.write(f"- 🩺 {sc}")
    st.markdown("<hr>", unsafe_allow_html=True)
    
    for ev in res['evaluations']:
        sc_text = ev.get("subclaim", "Unknown Subclaim")
        lbl = ev.get("label", "nei").upper()
        conf = ev.get("confidence", 0.0)
        just = ev.get("justification", "No justification provided.")
        
        icon = "✅" if lbl == "SUPPORTED" else "❌" if lbl == "REFUTED" else "❓"
        with st.expander(f"{icon} Analysis: {sc_text[:50]}... ({lbl})"):
            st.markdown(f"""
                <div style="padding-top: 10px;">
                    <div class="badge {lbl}">{icon} {lbl} (Conf: {conf:.2f})</div>
                    <div class="justification-title">Justification</div>
                    <div class="justification-text">{just}</div>
                </div>
            """, unsafe_allow_html=True)
            
            evidence = ev.get("retrieved_chunks", [])
            if evidence:
                evidence_html_list = []
                for chunk in evidence:
                    if isinstance(chunk, dict):
                        text = chunk.get("text", "")
                        meta = chunk.get("metadata", {})
                        url = meta.get("url", "")
                        source_title = meta.get("title", meta.get("id", "Unknown Source"))
                        html_chunk = f'<div class="evidence-box"><strong><a href="{url}" target="_blank">{source_title}</a></strong>: <em>{text}</em></div>' if url else f'<div class="evidence-box"><strong>{source_title}</strong>: <em>{text}</em></div>'
                        evidence_html_list.append(html_chunk)
                    else:
                        evidence_html_list.append(f'<div class="evidence-box"><em>{chunk}</em></div>')
                
                if evidence_html_list:
                    all_evidence_html = "".join(evidence_html_list)
                    st.markdown(f"""
                    <details style="margin-top: 20px; margin-bottom: 15px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px;">
                        <summary style="font-weight: 600; cursor: pointer; color: #334155;">📄 Show Evidence Documents</summary>
                        <div style="margin-top: 15px;">
                            {all_evidence_html}
                        </div>
                    </details>
                    """, unsafe_allow_html=True)
                
    st.markdown("<hr>", unsafe_allow_html=True)
    st.subheader("📊 Final Summary")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        lbl = res['final'].get("label", "nei").lower()
        conf = res['final'].get("confidence", 0.0)
        css_class = lbl if lbl in ["supported", "refuted"] else "nei"
        st.markdown(f"""
            <div class="verdict-box {css_class}">
                Final Verdict: {lbl.upper()} <br>
                <span style="font-size: 1rem; font-weight: normal;">Overall Confidence: {conf:.2f}</span>
            </div>
        """, unsafe_allow_html=True)
            
    with col2:
        try:
            import pandas as pd
            import plotly.express as px
            # Pie Chart
            df = pd.DataFrame([e.get('label', 'nei').upper() for e in res['evaluations']], columns=['Verdict'])
            verdict_counts = df['Verdict'].value_counts().reset_index()
            verdict_counts.columns = ['Verdict', 'Count']
            
            color_map = {
                "SUPPORTED": "#10b981",
                "REFUTED": "#ef4444",
                "NEI": "#9ca3af"
            }
            
            fig = px.pie(
                verdict_counts, 
                values='Count', 
                names='Verdict', 
                color='Verdict',
                color_discrete_map=color_map,
                hole=0.4
            )
            fig.update_layout(
                height=250, 
                margin=dict(t=10, b=10, l=0, r=0),
                showlegend=False
            )
            # Add labels to slices to compensate for no legend
            fig.update_traces(textposition='inside', textinfo='percent+label')
            
            st.plotly_chart(fig, width='stretch')
        except:
            pass
            
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, center_col, _ = st.columns([1, 1, 1])
    with center_col:
        try:
            import utils.pdf_generator
            import importlib
            importlib.reload(utils.pdf_generator)
            from utils.pdf_generator import generate_fact_check_pdf
            pdf_bytes = generate_fact_check_pdf(res['claim'], res['final'], res['evaluations'])
            st.download_button(
                label="📄 Download PDF Report",
                data=pdf_bytes,
                file_name="fact_check_report.pdf",
                mime="application/pdf",
                type="primary",
                width='stretch'
            )
        except Exception as e:
            st.error(f"Could not generate PDF: {str(e)}")

st.markdown("""
<div class="footer">
    MedFactCheck Project • Big Data Engineering MSc Unina • Powered by RAG & LLMs
</div>
""", unsafe_allow_html=True)
