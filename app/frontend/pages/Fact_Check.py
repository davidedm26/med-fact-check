import streamlit as st
import streamlit.components.v1 as components
import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px
import importlib
import re
import sys
import os
from datetime import datetime

# 1. Configurazione della Pagina
st.set_page_config(
    page_title="Fact Check | Med Fact Check",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)
def autoscroll_to_results():
    """Esegue l'autoscroll alla sezione dei risultati in modo affidabile"""
    components.html("""
    <script>
        function scrollToResults() {
            const anchor = window.parent.document.getElementById('results-anchor');
            
            if (anchor) {
                anchor.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'start',
                    inline: 'nearest'
                });
            } else {
                const totalHeight = document.body.scrollHeight;
                window.parent.scrollTo({
                    top: totalHeight * 0.5,
                    behavior: 'smooth'
                });
            }
        }
        
        // Esegui dopo che la pagina è caricata
        setTimeout(scrollToResults, 500);
        setTimeout(scrollToResults, 1500);
    </script>
    """, height=0, width=0)

# Funzione per dividere il testo in frasi
def split_into_sentences(text):
    """Divide il testo in frasi usando la punteggiatura come separatore."""
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?;])\s+', text)
    
    clean_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence.split()) >= 3 and len(sentence) >= 15:
            clean_sentences.append(sentence)
    
    if not clean_sentences:
        return [text]
    
    return clean_sentences


def render_claim_checklist(sentences, context=""):
    """Renderizza una checklist interattiva per selezionare i claim."""
    if not sentences:
        return []
    
    st.markdown("### 📋 Seleziona i Claim da Verificare")
    
    if context:
        st.info(f"📄 **Contesto:** {context}")
    
    # Pulsanti per selezione rapida
    col_select_all, col_deselect_all = st.columns([1, 1])
    
    with col_select_all:
        if st.button("✅ Seleziona Tutti", use_container_width=True):
            # Imposta TUTTE le checkbox come selezionate
            for i in range(len(sentences)):
                st.session_state[f"claim_cb_{i}"] = True
            st.rerun()
    
    with col_deselect_all:
        if st.button("❌ Deseleziona Tutti", use_container_width=True):
            # Imposta TUTTE le checkbox come NON selezionate
            for i in range(len(sentences)):
                st.session_state[f"claim_cb_{i}"] = False
            st.rerun()
    
    st.markdown("---")
    
    # Renderizza ogni frase come checkbox
    selected_claims = []
    
    for i, sentence in enumerate(sentences):
        # Inizializza la chiave della checkbox se non esiste
        cb_key = f"claim_cb_{i}"
        if cb_key not in st.session_state:
            st.session_state[cb_key] = False
        
        col_check, col_text = st.columns([0.1, 0.9])
        
        with col_check:
            # La checkbox usa direttamente la sua key nel session_state
            checked = st.checkbox(
                " ",
                key=cb_key,
                label_visibility="collapsed"
            )
        
        with col_text:
            preview = sentence[:200] + "..." if len(sentence) > 200 else sentence
            
            if checked:
                st.markdown(f"""
                <div style="background: rgba(16, 185, 129, 0.1); 
                            border-left: 4px solid #10b981; 
                            padding: 12px 15px; 
                            border-radius: 8px;
                            margin: 5px 0;">
                    <span style="color: #34d399; font-weight: 600;">✓ Claim #{i+1}</span><br>
                    <span style="color: #f8fafc; line-height: 1.5;">{preview}</span>
                </div>
                """, unsafe_allow_html=True)
                selected_claims.append(sentence)
            else:
                st.markdown(f"""
                <div style="background: rgba(255, 255, 255, 0.02); 
                            border-left: 4px solid rgba(255, 255, 255, 0.1); 
                            padding: 12px 15px; 
                            border-radius: 8px;
                            margin: 5px 0;
                            opacity: 0.7;">
                    <span style="color: #94a3b8;">Claim #{i+1}</span><br>
                    <span style="color: #cbd5e1; line-height: 1.5;">{preview}</span>
                </div>
                """, unsafe_allow_html=True)
    
    return selected_claims

# Funzione per evidenziare le citazioni
def highlight_quotes(text, supp, ref):
    hl = text
    if isinstance(supp, str): supp = [supp]
    if isinstance(ref, str): ref = [ref]
    for q in (supp or []):
        if q and len(q) > 5:
            q_pattern = r'\s+'.join(re.escape(word) for word in q.split())
            pattern = re.compile(q_pattern, re.IGNORECASE)
            hl = pattern.sub(r"<span class='eval-highlight-support' style='background: linear-gradient(120deg, rgba(16, 185, 129, 0.4) 0%, rgba(16, 185, 129, 0.15) 100%); color: #34d399 !important; font-weight: 700; padding: 3px 8px; border-radius: 4px; border-left: 4px solid #10b981;'>\g<0></span>", hl)
    for q in (ref or []):
        if q and len(q) > 5:
            q_pattern = r'\s+'.join(re.escape(word) for word in q.split())
            pattern = re.compile(q_pattern, re.IGNORECASE)
            hl = pattern.sub(r"<span class='eval-highlight-refute' style='background: linear-gradient(120deg, rgba(239, 68, 68, 0.4) 0%, rgba(239, 68, 68, 0.15) 100%); color: #f87171 !important; font-weight: 700; padding: 3px 8px; border-radius: 4px; border-left: 4px solid #ef4444;'>\g<0></span>", hl)
    return hl


def update_interactive_loading(claim, step=1, subclaims=None, evaluations=None, verified_count=0, total_to_verify=1, final_verdict=None):
    all_modals_html = ""
    if subclaims is None: subclaims = []
    if evaluations is None: evaluations = []
    
    central_title = "Processing..."
    central_subtitle = "Please wait..."
    anim_color = "#38bdf8"
    
    if final_verdict:
        raw_label = final_verdict.get("label", "not_enough_information")
        if raw_label == "supported":
            verdict = "SUPPORTED"
        elif raw_label == "refuted":
            verdict = "REFUTED"
        else:
            verdict = "NEI"
        
        raw_conf = final_verdict.get("confidence", 0.0)
        if raw_conf <= 1.0:
            conf = int(raw_conf * 100)
        else:
            conf = int(raw_conf)
            
        if verdict == "SUPPORTED":
            anim_color = "#10b981"
        elif verdict == "REFUTED":
            anim_color = "#ef4444"
        else:
            anim_color = "#f59e0b"
        
        central_title = "Fact-Checking Completed!"
        central_subtitle = "Final results are ready for analysis."
    else:
        if step == 1:
            central_title = "Initializing Medical AI Pipeline"
            central_subtitle = "Warming up decomposition agents..."
            anim_color = "#38bdf8"
        elif step == 2:
            central_title = "RAG Database Ingestion"
            source_selections = getattr(st.session_state, "source_selections", {})
            if source_selections:
                all_selected = set()
                for srcs in source_selections.values():
                    all_selected.update(srcs)
                sources_str = ", ".join(sorted(all_selected))
                central_subtitle = f"Fonti selezionate: {sources_str}"
            else:
                central_subtitle = "Selecting sources and preparing queries..."
            anim_color = "#818cf8"
        elif step == 3:
            central_title = "Clinical Reasoning Agent"
            if verified_count == total_to_verify:
                central_subtitle = "Aggregating Subclaims verdicts..."
            else:
                central_subtitle = f"Validating {verified_count} of {total_to_verify} extracted claims..."
            anim_color = "#a78bfa"
        else:
            central_title = "Generating Final Consensus"
            central_subtitle = "Aggregating verdicts and calculating confidence score..."
            anim_color = "#10b981"
    
    modal_css = "<style>.modal-wrapper{position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.85);z-index:10000000;display:none;align-items:center;justify-content:center;backdrop-filter:blur(8px);}.modal-toggle:checked+.modal-wrapper{display:flex!important;}.modal-card{background:#0f172a;border:1px solid #38bdf8;border-radius:16px;padding:2rem;max-width:700px;width:90%;max-height:85vh;overflow-y:auto;box-shadow:0 0 40px rgba(56,189,248,0.4);animation:zoomIn 0.3s cubic-bezier(0.175,0.885,0.32,1.275) forwards;}@keyframes zoomIn{0%{transform:scale(0.5);opacity:0;}100%{transform:scale(1);opacity:1;}}.close-btn{float:right;cursor:pointer;color:#f8fafc;background:#ef4444;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;transition:0.2s;font-size:14px;}.close-btn:hover{background:#dc2626;transform:scale(1.1);}</style>"
    
    def get_cards_html(target_phase):
        nonlocal all_modals_html
        if not subclaims: return "<div style='color:#94a3b8; margin-top:20px; font-style:italic;'>⏳ Waiting for pipeline...</div>"
        html = "<div style='display:flex; flex-wrap:wrap; gap:10px; justify-content:center; margin-top:20px; width:100%; max-width:900px;'>"
        for i, sc in enumerate(subclaims):
            ev_data = next((e for e in evaluations if e.get("subclaim") == sc), None)
            if target_phase == 2:
                if step < 2: status = "⏳ Pending..."
                elif step == 2:
                    sub_id = f"sub_{i+1:02d}"
                    source_selections = getattr(st.session_state, "source_selections", {})
                    downloader_status = getattr(st.session_state, "downloader_status", {})
                    retriever_status = getattr(st.session_state, "retriever_status", {})
                    if sub_id in retriever_status:
                        status = f"✅ Selected {retriever_status[sub_id]} final chunks"
                    elif sub_id in downloader_status:
                        status = f"⏳ Ingesting {downloader_status[sub_id]} chunks..."
                    elif sub_id in source_selections:
                        srcs = ", ".join(source_selections[sub_id])
                        status = f"🔍 Querying: {srcs}..."
                    else:
                        status = "⏳ Selecting Sources..."
                else: status = "✅ Documents Retrieved"
                has_modal = False
            elif target_phase == 3:
                if step < 3: status = "⏳ Pending..."
                elif step == 3 and ev_data: status = f"✅ Evaluated: {ev_data.get('label', 'NEI')}"
                elif step == 3 and i == verified_count: status = "🔍 Evaluating..."
                elif step == 3: status = "⏳ Waiting in queue..."
                else: status = f"✅ Evaluated: {ev_data.get('label', 'NEI')}" if ev_data else "✅ Evaluated"
                has_modal = bool(ev_data)
            else:
                status = f"✅ Evaluated: {ev_data.get('label', 'NEI')}" if ev_data else "✅ Completed"
                has_modal = bool(ev_data)
                
            if has_modal:
                card_html = f"<label for='modal-p{target_phase}-{i}' style='display:block; cursor:pointer; position:relative; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); padding:12px 18px; border-radius:12px; width:calc(50% - 5px); min-width:300px; text-align:left; transition: transform 0.2s, border-color 0.2s;'><div style='position:absolute; right:10px; bottom:10px; font-size:4rem; opacity:0.04; pointer-events:none; z-index:0;'>🔍</div><div style='position:relative; z-index:2; font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>SUBCLAIM {i+1}</div><div style='position:relative; z-index:2; font-size:0.95rem; color:#f8fafc; margin-bottom:8px; line-height:1.4;'>\"{sc}\"</div><div style='position:relative; z-index:2; font-size:0.8rem; font-weight:600; color:#38bdf8;'>{status}</div>"
            else:
                card_html = f"<div style='background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); padding:12px 18px; border-radius:12px; width:calc(50% - 5px); min-width:300px; text-align:left;'><div style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>SUBCLAIM {i+1}</div><div style='font-size:0.95rem; color:#f8fafc; margin-bottom:8px; line-height:1.4;'>\"{sc}\"</div><div style='font-size:0.8rem; font-weight:600; color:#38bdf8;'>{status}</div>"
            if has_modal:
                reasoning = ev_data.get("justification", ev_data.get("selection_reasoning", "No reasoning provided."))
                chunks = ev_data.get("retrieved_chunks", [])[:5]
                supp = ev_data.get("supporting_quotes", [])
                ref = ev_data.get("refuting_quotes", [])
                chunks_html = ""
                for c in chunks:
                    c_text = c.get("text", "") if isinstance(c, dict) else str(c)
                    c_meta = c.get("metadata", {}) if isinstance(c, dict) else {}
                    c_source = c_meta.get("title") or c_meta.get("id") or (c.get("source") if isinstance(c, dict) else None) or "Reference Document"
                    hl_text = highlight_quotes(c_text, supp, ref)
                    chunks_html += f"<div style='background:#1e293b; padding:10px; margin:8px 0; border-left:4px solid #38bdf8; border-radius:6px; font-size:0.85rem; text-align:left;'><strong style='color:#38bdf8;'>{c_source}</strong><br><em style='color:#cbd5e1;'>{hl_text}</em></div>"
                modal_html = f"<input type='checkbox' id='modal-p{target_phase}-{i}' class='modal-toggle' style='display:none;'><div class='modal-wrapper'><div class='modal-card'><label for='modal-p{target_phase}-{i}' class='close-btn'>✖</label><h3 style='color:#38bdf8; margin-top:0; text-align:left;'>Subclaim Analysis {i+1}</h3><p style='color:#e2e8f0; font-size:1.05rem; font-style:italic; text-align:left;'>\"{sc}\"</p><hr style='border:none; border-top:1px solid rgba(255,255,255,0.1); margin:15px 0;'><div style='text-align:left;'><strong style='color:#a78bfa; font-size:1.1rem;'>🧠 Reasoning:</strong><p style='color:#f8fafc; font-size:0.95rem; line-height:1.6;'>{reasoning}</p></div><div style='text-align:left; margin-top:20px;'><strong style='color:#a78bfa; font-size:1.1rem;'>📄 Top 5 Evidences:</strong>{chunks_html}</div></div></div>"
                all_modals_html += modal_html
                card_html += "</label>"
            else:
                card_html += "</div>"
            html += card_html
        html += "</div>"
        return html

    sc_html_p2 = get_cards_html(2)
    sc_html_p3 = get_cards_html(3)
    
    if final_verdict:
        raw_label = final_verdict.get("label", "not_enough_information")
        if raw_label == "supported":
            verdict = "SUPPORTED"
        elif raw_label == "refuted":
            verdict = "REFUTED"
        else:
            verdict = "NEI"
        
        raw_conf = final_verdict.get("confidence", 0.0)
        if raw_conf <= 1.0:
            conf = int(raw_conf * 100)
        else:
            conf = int(raw_conf)
            
        just = final_verdict.get("justification", "")
        if verdict == "SUPPORTED": v_color, v_icon = "#10b981", "✅"
        elif verdict == "REFUTED": v_color, v_icon = "#ef4444", "❌"
        else: v_color, v_icon = "#f59e0b", "⚠️"

        slide4_content = f"""
          <div class="slide-header">Final Fact-Checking Result</div>
          <div style="display:flex; width:100%; max-width:900px; gap:30px; margin-top:20px;">
            <div style="flex:1; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); border-radius:16px; padding:30px; display:flex; flex-direction:column; align-items:center; text-align:center; box-shadow: 0 0 30px rgba(0,0,0,0.3);">
               <div style="font-size:3rem; margin-bottom:10px;">{v_icon}</div>
               <div style="color:{v_color}; font-size:2rem; font-weight:900; letter-spacing:2px; margin-bottom:20px;">{verdict}</div>
               <div style="position:relative; width:150px; height:150px; border-radius:50%; background:conic-gradient({v_color} {conf}%, #1e293b 0); display:flex; align-items:center; justify-content:center; box-shadow:0 0 20px {v_color}40;">
                   <div style="position:absolute; width:130px; height:130px; background:#0f172a; border-radius:50%; display:flex; flex-direction:column; align-items:center; justify-content:center;">
                       <span style="font-size:2.5rem; font-weight:800; color:#f8fafc;">{conf}%</span>
                       <span style="font-size:0.8rem; color:#94a3b8; text-transform:uppercase;">Confidence</span>
                   </div>
               </div>
            </div>
            <div style="flex:1.5; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); border-radius:16px; padding:30px; text-align:left; display:flex; flex-direction:column; box-shadow: 0 0 30px rgba(0,0,0,0.3);">
                <h3 style="color:#a78bfa; margin-top:0; font-size:1.3rem;">Medical Justification</h3>
                <div style="color:#f8fafc; font-size:1.05rem; line-height:1.6; flex:1; overflow-y:auto; max-height: 200px; padding-right: 10px;">{just}</div>
            </div>
          </div>
        """
    else:
        slide4_content = f"""
          <div class="slide-header">Final Consensus & Aggregation</div>
          <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; margin-top: 40px;">
            <div style="font-size: 4rem; margin-bottom: 20px;">⚖️</div>
            <div style="color: #10b981; font-size: 1.5rem; font-weight: 700; text-align: center; margin-bottom: 15px;">
                Drafting Final Verdict
            </div>
            <div style="color: #94a3b8; font-size: 1.1rem; text-align: center; max-width: 600px; line-height: 1.6;">
                The pipeline is aggregating the Clinical Agent's results across all extracted claims.<br><br>
                <em style="color: #a78bfa;">Calculating the overall confidence score and formulating the final medical justification...</em>
            </div>
          </div>
        """
    
    if step == 1:
        slide1_status = "<div style='color:#38bdf8; margin-top:15px; font-weight:600;'>⏳ Awaiting decomposition...</div>"
        slide1_tree = ""
    else:
        slide1_status = ""
        tree_cards = ""
        for i, sc in enumerate(subclaims):
            tree_cards += f'<div style="flex:1; min-width:250px; background:rgba(255,255,255,0.03); border:1px solid rgba(129,140,248,0.3); border-top:4px solid #818cf8; border-radius:12px; padding:15px; color:#e2e8f0; font-size:0.95rem; text-align:left; box-shadow: 0 4px 10px rgba(0,0,0,0.2);"><div style="font-size:0.75rem; color:#818cf8; font-weight:bold; margin-bottom:8px; text-transform:uppercase; letter-spacing:1px;">Subclaim {i+1}</div>{sc}</div>'
        slide1_tree = f'<div style="display:flex; flex-direction:column; align-items:center; margin: 15px 0;"><div style="width:2px; height:40px; background:linear-gradient(to bottom, #38bdf8, #818cf8);"></div><div style="width:0; height:0; border-left:8px solid transparent; border-right:8px solid transparent; border-top:10px solid #818cf8;"></div></div><div style="display:flex; justify-content:center; flex-wrap:wrap; gap:20px; width:100%; max-width:1000px; position:relative;">{tree_cards}</div>'
    
    safe_claim = claim.replace('"', '&quot;')
    slide1_content = f'''
      <div class="slide-header">Original Claim Decomposition</div>
      <div style="background:#0f172a; border:2px solid #38bdf8; border-radius:12px; padding:20px 30px; color:#f8fafc; font-size:1.1rem; text-align:center; font-style:italic; max-width:800px; box-shadow: 0 0 20px rgba(56,189,248,0.2); margin-top:20px;">
          "{safe_claim}"
      </div>
      {slide1_status}
      {slide1_tree}
    '''
    
    progress_percent = (step - 1) * 33.33
    slide1_checked = 'checked' if step == 1 else ''
    slide2_checked = 'checked' if step == 2 else ''
    slide3_checked = 'checked' if step == 3 else ''
    
    css_content = f"""
    <style>
    .cyber-overlay {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(15, 23, 42, 0.97); backdrop-filter: blur(20px); z-index: 9999999 !important; overflow: hidden; pointer-events: auto !important; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding-top: 60px; }}
    .carousel-viewport {{ width: 100vw; height: calc(100vh - 350px); position: relative; overflow: hidden; margin-top: 30px; }}
    .slider-container {{ display: flex; width: 300vw; height: 100%; transition: transform 0.5s cubic-bezier(0.25, 0.8, 0.25, 1); }}
    #slide-1:checked ~ .carousel-viewport .slider-container {{ transform: translateX(0); }}
    #slide-2:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-100vw); }}
    #slide-3:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-200vw); }}
    .slide {{ width: 100vw; height: 100%; position: relative; padding: 0 80px; box-sizing: border-box; }}
    .slide-content {{ width: 100%; height: 100%; overflow-y: auto; display: flex; flex-direction: column; align-items: center; padding-bottom: 50px; text-align: center; }}
    .global-arrow {{ position: absolute; top: 50%; transform: translateY(-50%); background: rgba(56,189,248,0.1); color: #38bdf8; width: 50px; height: 50px; border-radius: 50%; display: none; align-items: center; justify-content: center; font-size: 24px; cursor: pointer; transition: 0.3s; border: 1px solid rgba(56,189,248,0.3); z-index: 10000; }}
    .global-arrow:hover {{ background: rgba(56,189,248,0.4); color: #fff; transform: translateY(-50%) scale(1.1); }}
    .left-arrow {{ left: 30px; }}
    .right-arrow {{ right: 30px; }}
    #slide-1:checked ~ .carousel-viewport .show-1 {{ display: flex; }}
    #slide-2:checked ~ .carousel-viewport .show-2 {{ display: flex; }}
    #slide-3:checked ~ .carousel-viewport .show-3 {{ display: flex; }}
    .slide-header {{ color: rgba(248,250,252,0.6); font-size: 1.2rem; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 2px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; width: 100%; max-width: 900px; text-align: center; }}
    .pulse-container {{ position: relative; width: 120px; height: 120px; display: flex; align-items: center; justify-content: center; margin-bottom: 1rem; }}
    .pulse-ring {{ position: absolute; width: 100%; height: 100%; border-radius: 50%; border: 2px solid {anim_color}; animation: pulsate 2s infinite ease-out; }}
    .pulse-ring:nth-child(2) {{ animation-delay: 0.6s; }}
    .pulse-ring:nth-child(3) {{ animation-delay: 1.2s; }}
    .pulse-core {{ width: 40px; height: 40px; background-color: {anim_color}; border-radius: 50%; box-shadow: 0 0 20px {anim_color}; z-index: 10; animation: core-glow 2s infinite alternate; }}
    @keyframes pulsate {{ 0% {{ transform: scale(0.5); opacity: 1; }} 100% {{ transform: scale(1.5); opacity: 0; }} }}
    @keyframes core-glow {{ 0% {{ transform: scale(0.9); box-shadow: 0 0 10px {anim_color}; }} 100% {{ transform: scale(1.1); box-shadow: 0 0 30px {anim_color}; }} }}
    .stage-title {{ font-size: 2rem; font-weight: 800; color: #f8fafc; letter-spacing: 1px; margin: 0 0 5px 0; text-align: center; }}
    .stage-subtitle {{ font-size: 1rem; color: #94a3b8; font-weight: 400; text-align: center; max-width: 600px; line-height:1.5; }}
    .stepper-container {{ width: 100%; max-width: 500px; margin: 20px auto 0 auto; position: relative; padding-top: 10px; }}
    .stepper-line {{ position: absolute; top: 25px; left: 12.5%; width: 75%; height: 4px; background: rgba(255, 255, 255, 0.1); border-radius: 2px; z-index: 1; }}
    .stepper-progress {{ height: 100%; background: linear-gradient(90deg, #38bdf8, #818cf8, #a78bfa, #10b981); border-radius: 2px; transition: width 0.5s ease-in-out; }}
    .stepper-steps {{ display: flex; justify-content: space-between; position: relative; z-index: 2; }}
    .step {{ display: flex; flex-direction: column; align-items: center; width: 25%; position: relative; }}
    .step-dot {{ width: 30px; height: 30px; border-radius: 50%; background: #0f172a; border: 2px solid rgba(255, 255, 255, 0.2); display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; color: #64748b; transition: all 0.4s; margin-bottom: 8px; z-index: 2; }}
    .step.active .step-dot {{ border-color: {anim_color}; color: #f8fafc; background: #0f172a; }}
    .step-label {{ font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 1px; text-align: center; transition: color 0.3s; margin-top: 5px; }}
    .step.active .step-label {{ color: #e2e8f0; }}
    .step {{ cursor: pointer; }}
    .step:hover {{ opacity: 0.8; }}
    #slide-1:checked ~ .stepper-container .step-ui-1 .step-dot {{ background: {anim_color}; border-color: {anim_color}; box-shadow: 0 0 15px {anim_color}; }}
    #slide-2:checked ~ .stepper-container .step-ui-2 .step-dot {{ background: {anim_color}; border-color: {anim_color}; box-shadow: 0 0 15px {anim_color}; }}
    #slide-3:checked ~ .stepper-container .step-ui-3 .step-dot {{ background: {anim_color}; border-color: {anim_color}; box-shadow: 0 0 15px {anim_color}; }}
    </style>
    """
    
    html_structure = f"""
    {modal_css}
    {css_content}
    <div class="cyber-overlay">
        <input type="radio" name="slider" id="slide-1" {slide1_checked} style="display:none;">
        <input type="radio" name="slider" id="slide-2" {slide2_checked} style="display:none;">
        <input type="radio" name="slider" id="slide-3" {slide3_checked} style="display:none;">
        <div class="pulse-container"><div class="pulse-ring"></div><div class="pulse-ring"></div><div class="pulse-ring"></div><div class="pulse-core"></div></div>
        <div class="stage-title">{central_title}</div>
        <div class="stage-subtitle">{central_subtitle}</div>
        <div class="stepper-container">
            <div class="stepper-line"><div class="stepper-progress" style="width: {progress_percent}%;"></div></div>
            <div class="stepper-steps">
                <label for="slide-1" class="step step-ui-1 {'active' if step >= 1 else ''}"><div class="step-dot">1</div><div class="step-label">Input</div></label>
                <label for="slide-2" class="step step-ui-2 {'active' if step >= 2 else ''}"><div class="step-dot">2</div><div class="step-label">RAG</div></label>
                <label for="slide-3" class="step step-ui-3 {'active' if step >= 3 else ''}"><div class="step-dot">3</div><div class="step-label">Eval</div></label>
                <label for="slide-1" class="step step-ui-4 {'active' if step >= 4 else ''}"><div class="step-dot">4</div><div class="step-label">Done</div></label>
            </div>
        </div>
        <div class="carousel-viewport">
            <div class="slider-container">
                <div class="slide"><div class="slide-content">{slide1_content}</div></div>
                <div class="slide"><div class="slide-content"><div class="slide-header">Document Retrieval Extracts (RAG)</div>{sc_html_p2}</div></div>
                <div class="slide"><div class="slide-content"><div class="slide-header">Clinical Reasoning Agent Results</div>{sc_html_p3}</div></div>
            </div>
        </div>
        {all_modals_html}
    </div>
    """
    
    html_content = html_structure
    try:
        overlay_placeholder.markdown(html_content, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Rendering error: {str(e)}")
        components.html(html_content, height=1200)


# 2. CSS Avanzato Originale
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
    .streamlit-expanderHeader { font-size: 1.1rem !important; font-weight: 600 !important; color: #f8fafc !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="navbar">
        <div class="nav-logo">⚕️ Med Fact Check</div>
        <div style="font-size: 0.9rem; color: #94a3b8; font-weight:600;">MSc Unina • Big Data Engineering</div>
    </div>
""", unsafe_allow_html=True)

st.markdown('<div style="margin-top: 8rem;"></div>', unsafe_allow_html=True)

# 3. WRAPPER PRINCIPALE
_, col_main, _ = st.columns([1, 14, 1])

# Gestione cambio metodo input
if 'last_input_method' not in st.session_state:
    st.session_state.last_input_method = None

with col_main:
    overlay_placeholder = st.empty()
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
        if input_method == "✍️ Text Input":
            claim = st.text_area("Medical Claim:", height=130, placeholder="E.g., Taking a daily vitamin D supplement helps prevent osteoporosis...")
            
        elif input_method == "📄 Upload TXT":
            uploaded_file = st.file_uploader("Choose a .txt file", type="txt")
            if uploaded_file is not None:
                file_content = uploaded_file.getvalue().decode("utf-8")
                
                # Mostra preview del file
                with st.expander("📄 Contenuto del File", expanded=True):
                    st.text_area(
                        "File Content:", 
                        value=file_content[:1000] + ("..." if len(file_content) > 1000 else ""), 
                        height=150, 
                        disabled=True
                    )
                
                # Dividi in frasi e mostra checklist
                sentences = split_into_sentences(file_content)
                
                if sentences:
                    st.markdown(f"**📊 Trovate {len(sentences)} frasi nel documento**")
                    
                    # Usa la checklist per selezionare i claim
                    selected_claims = render_claim_checklist(
                        sentences, 
                        context=f"File: {uploaded_file.name}"
                    )
                    
                    # Combina i claim selezionati
                    if selected_claims:
                        claim = " ".join(selected_claims)
                        st.success(f"✅ {len(selected_claims)} claim selezionati per la verifica")
                        
                        # Mostra i claim selezionati
                        with st.expander("📋 Claim Selezionati", expanded=False):
                            for i, sc in enumerate(selected_claims):
                                st.markdown(f"""
                                <div style="background: rgba(16, 185, 129, 0.1); 
                                            border-left: 4px solid #10b981; 
                                            padding: 10px 15px; 
                                            border-radius: 8px;
                                            margin: 8px 0;">
                                    <strong style="color: #34d399;">Claim {i+1}:</strong> 
                                    <span style="color: #f8fafc;">{sc[:200]}...</span>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ Seleziona almeno un claim da verificare")
                else:
                    st.warning("⚠️ Nessuna frase valida trovata nel documento")
                    
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
                                page_content = soup.get_text(separator=' ', strip=True)
                                st.success("✅ Contenuto caricato con successo!")
                                
                                # Mostra preview del contenuto
                                with st.expander("🌐 Contenuto della Pagina", expanded=True):
                                    preview = page_content[:1000] + ("..." if len(page_content) > 1000 else "")
                                    st.text_area(
                                        "Page Content:", 
                                        value=preview, 
                                        height=150, 
                                        disabled=True
                                    )
                                
                                # Dividi in frasi e mostra checklist
                                sentences = split_into_sentences(page_content)
                                
                                if sentences:
                                    st.markdown(f"**📊 Trovate {len(sentences)} frasi nella pagina**")
                                    
                                    # Usa la checklist per selezionare i claim
                                    selected_claims = render_claim_checklist(
                                        sentences, 
                                        context=f"URL: {url_input}"
                                    )
                                    
                                    # Combina i claim selezionati
                                    if selected_claims:
                                        claim = " ".join(selected_claims)
                                        st.success(f"✅ {len(selected_claims)} claim selezionati per la verifica")
                                        
                                        # Mostra i claim selezionati
                                        with st.expander("📋 Claim Selezionati", expanded=False):
                                            for i, sc in enumerate(selected_claims):
                                                st.markdown(f"""
                                                <div style="background: rgba(16, 185, 129, 0.1); 
                                                            border-left: 4px solid #10b981; 
                                                            padding: 10px 15px; 
                                                            border-radius: 8px;
                                                            margin: 8px 0;">
                                                    <strong style="color: #34d399;">Claim {i+1}:</strong> 
                                                    <span style="color: #f8fafc;">{sc[:200]}...</span>
                                                </div>
                                                """, unsafe_allow_html=True)
                                    else:
                                        st.warning("⚠️ Seleziona almeno un claim da verificare")
                                else:
                                    st.warning("⚠️ Nessuna frase valida trovata nella pagina")
                            else:
                                st.error(f"Failed to fetch URL. Status code: {res.status_code}")
                    except Exception as e:
                        st.error(f"Error fetching URL: {str(e)}")

    if "real_results" not in st.session_state:
        st.session_state.real_results = None
    if "current_subclaims" not in st.session_state:
        st.session_state.current_subclaims = []
    if "current_evaluations" not in st.session_state:
        st.session_state.current_evaluations = []

    st.markdown("<br>", unsafe_allow_html=True)
    error_placeholder = st.empty()
    
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        verify_clicked = st.button("Verify Claim", type="primary", use_container_width=True)

    # ==========================================
    # 4. LOGICA BACKEND E ANIMAZIONE
    # ==========================================
    if verify_clicked:
        if not claim.strip():
            st.warning("Please provide a valid claim or document before verifying.")
        else:
            st.session_state.fact_check_claim = claim
            st.session_state.current_subclaims = []
            st.session_state.current_evaluations = []
            st.session_state.source_selections = {}
            st.session_state.downloader_status = {}
            st.session_state.retriever_status = {}
            if "current_final" in st.session_state:
                del st.session_state["current_final"]
                
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
                                        overlay_placeholder.empty()
                                        error_placeholder.error(f"❌ Pipeline Error: {step_data['error']}")
                                        break
                                    
                                    if "decompose" in step_data:
                                        scs = step_data["decompose"].get("verifiable_subclaims", [])
                                        for sc in scs:
                                            sc_text = sc if isinstance(sc, str) else sc.get("claim", str(sc))
                                            st.session_state.current_subclaims.append(sc_text)
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
                                        
                                    elif any(k in step_data for k in ["verify_subclaim", "evaluate_subclaim", "reasoning", "veracity"]):
                                        inner_data = step_data.get("verify_subclaim", step_data.get("evaluate_subclaim", step_data.get("veracity", step_data.get("reasoning", {}))))
                                        eval_results = inner_data.get("evaluation_results", []) if isinstance(inner_data, dict) else []
                                        for er in eval_results:
                                            if er not in st.session_state.current_evaluations:
                                                st.session_state.current_evaluations.append(er)
                                        st.session_state.max_step = max(st.session_state.get("max_step", 1), 3)
                                        update_interactive_loading(claim=claim, step=st.session_state.max_step, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=len(st.session_state.current_evaluations), total_to_verify=len(st.session_state.current_subclaims))
                                        
                                    elif "aggregate" in step_data:
                                        current_final = step_data["aggregate"].get("final_verdict", {})
                                        st.session_state.real_results = {
                                            "subclaims": st.session_state.current_subclaims,
                                            "evaluations": st.session_state.current_evaluations,
                                            "final": current_final,
                                            "claim": claim
                                        }
                                        overlay_placeholder.empty()
                                        # Forza la fase DONE
                                        st.session_state.selected_phase = "Done"
                                        st.session_state.results_just_arrived = False
                                        autoscroll_to_results()

                                        st.rerun()
                                except json.JSONDecodeError:
                                    pass
                else:
                    overlay_placeholder.empty()
                    error_placeholder.error(f"❌ Backend Connection Error (Status Code: {response.status_code})")
            except Exception as e:
                overlay_placeholder.empty()
                error_placeholder.error(f"❌ Failed to connect to the backend API: {str(e)}")

    # ==========================================
    # 5. DASHBOARD RISULTATI
    # ==========================================
    if st.session_state.real_results:
        res = st.session_state.real_results
        
        # Forza la fase DONE quando i risultati sono appena arrivati
        if 'results_just_arrived' not in st.session_state:
            st.session_state.results_just_arrived = False
        
        if not st.session_state.results_just_arrived:
            st.session_state.selected_phase = "Done"
            st.session_state.results_just_arrived = True
        autoscroll_to_results()
        # Fix della confidence
        raw_conf = res['final'].get("confidence", res['final'].get("confidence_score", 0.0))
        try:
            raw_conf = float(raw_conf)
        except:
            raw_conf = 0.0
        
        if raw_conf < 0.01 and res['evaluations']:
            confs = []
            for e in res['evaluations']:
                try:
                    confs.append(float(e.get("confidence", e.get("confidence_score", 0.0))))
                except:
                    pass
            if confs:
                raw_conf = sum(confs) / len(confs)
            
        res['final']['confidence'] = raw_conf
        avg_conf_percent = (raw_conf * 100) if raw_conf <= 1.0 else raw_conf
        
        st.markdown("<div id='results-anchor'></div>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:rgba(255,255,255,0.05); margin: 2rem 0;'>", unsafe_allow_html=True)
        
        # CSS per la dashboard
        st.markdown("""
            <style>
            div[role="radiogroup"][aria-orientation="vertical"] { gap: 0; position: relative; padding-left: 20px; margin-top: 20px; }
            div[role="radiogroup"][aria-orientation="vertical"]::before { content: ''; position: absolute; left: 34px; top: 30px; bottom: 30px; width: 2px; background: rgba(255,255,255,0.15); z-index: 0; }
            div[role="radiogroup"][aria-orientation="vertical"] > label { padding: 25px 0 25px 50px; cursor: pointer; display: flex; align-items: center; background: transparent !important; border: none !important; margin: 0; position: relative; z-index: 1; }
            div[role="radiogroup"][aria-orientation="vertical"] > label > div:first-child { display: none !important; }
            div[role="radiogroup"][aria-orientation="vertical"] > label::before { content: ''; position: absolute; left: 19px; top: 50%; transform: translateY(-50%); width: 32px; height: 32px; border-radius: 50%; background: #0f172a; border: 2px solid rgba(255, 255, 255, 0.2); z-index: 2; transition: 0.3s; display:flex; align-items:center; justify-content:center; color:#64748b; font-weight:bold; font-size:13px; }
            div[role="radiogroup"][aria-orientation="vertical"] > label:nth-child(1)::before { content: '1'; }
            div[role="radiogroup"][aria-orientation="vertical"] > label:nth-child(2)::before { content: '2'; }
            div[role="radiogroup"][aria-orientation="vertical"] > label:nth-child(3)::before { content: '3'; }
            div[role="radiogroup"][aria-orientation="vertical"] > label:nth-child(4)::before { content: '4'; }
            div[role="radiogroup"][aria-orientation="vertical"] > label[data-checked="true"]:nth-child(1)::before { border-color: #38bdf8; background: #0f172a; box-shadow: 0 0 15px #38bdf8; color: #38bdf8; }
            div[role="radiogroup"][aria-orientation="vertical"] > label[data-checked="true"]:nth-child(2)::before { border-color: #818cf8; background: #0f172a; box-shadow: 0 0 15px #818cf8; color: #818cf8; }
            div[role="radiogroup"][aria-orientation="vertical"] > label[data-checked="true"]:nth-child(3)::before { border-color: #a78bfa; background: #0f172a; box-shadow: 0 0 15px #a78bfa; color: #a78bfa; }
            div[role="radiogroup"][aria-orientation="vertical"] > label[data-checked="true"]:nth-child(4)::before { border-color: #10b981; background: #0f172a; box-shadow: 0 0 15px #10b981; color: #10b981; }
            div[role="radiogroup"][aria-orientation="vertical"] > label p { color: #64748b; font-weight: 700; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; margin: 0; transition: 0.3s; }
            div[role="radiogroup"][aria-orientation="vertical"] > label[data-checked="true"] p { color: #f8fafc; font-weight: 800; }
            
            .modal-wrapper { position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(0,0,0,0.85); z-index:10000000; display:none; align-items:center; justify-content:center; backdrop-filter:blur(8px); }
            .modal-toggle:checked + .modal-wrapper { display:flex !important; }
            .modal-card { background:#0f172a; border:1px solid #38bdf8; border-radius:16px; padding:2.5rem; max-width:850px; width:90%; max-height:85vh; overflow-y:auto; box-shadow:0 0 40px rgba(56,189,248,0.4); position:relative; animation:zoomIn 0.3s forwards; text-align:left; }
            @keyframes zoomIn { 0% { transform:scale(0.8); opacity:0; } 100% { transform:scale(1); opacity:1; } }
            .close-btn { position:absolute; top:20px; right:20px; cursor:pointer; color:#f8fafc; background:#ef4444; width:35px; height:35px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:bold; z-index:9999; }
            .card-btn { display:block; cursor:pointer; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); padding:15px 20px; border-radius:12px; transition: 0.2s; position:relative; text-align:left; margin-bottom: 15px;}
            .card-btn:hover { background:rgba(255,255,255,0.06); transform:translateY(-3px); box-shadow:0 5px 15px rgba(0,0,0,0.3); border-color:#38bdf8; }
            </style>
        """, unsafe_allow_html=True)
        
        # Layout: Menu a Sinistra e Contenuto a Destra
        col_menu, col_dettagli = st.columns([1, 2.5], gap="large")
        
        with col_menu:
            st.markdown("<h3 style='color:#38bdf8; margin-top:0; margin-bottom: 10px; font-weight:800; font-size:1.1rem; text-transform: uppercase; letter-spacing: 1px;'>Pipeline Nav</h3>", unsafe_allow_html=True)
            
            if 'selected_phase' not in st.session_state:
                st.session_state.selected_phase = "Done"
            
            st.markdown("""
            <style>
            .v-pipe-container { display: flex; flex-direction: column; gap: 0; position: relative; padding-left: 40px; margin: 20px 0; }
            .v-pipe-container::before { content: ''; position: absolute; left: 25px; top: 40px; bottom: 40px; width: 2px; background: linear-gradient(180deg, rgba(255,255,255,0.2), rgba(255,255,255,0.05)); z-index: 0; }
            </style>
            """, unsafe_allow_html=True)
            
            phases = ["Input", "RAG", "Eval", "Done"]
            phase_idx = phases.index(st.session_state.selected_phase)
            
            with st.container():
                st.markdown("<div class='v-pipe-container'>", unsafe_allow_html=True)
                for i, phase in enumerate(phases):
                    if i < phase_idx:
                        status = "completed"
                    elif i == phase_idx:
                        status = "active"
                    else:
                        status = "pending"
                    
                    if status == "active":
                        color, glow = "#38bdf8", "0 0 15px #38bdf8"
                    elif status == "completed":
                        color, glow = "#10b981", "0 0 10px #10b981"
                    else:
                        color, glow = "rgba(255,255,255,0.2)", "none"
                    
                    col_dot, col_label = st.columns([0.3, 0.7])
                    with col_dot:
                        st.markdown(f"<div style='position:relative; left:-20px; top:8px;'><div style='width:28px; height:28px; border-radius:50%; background:#0f172a; border:2px solid {color}; display:flex; align-items:center; justify-content:center; font-weight:bold; color:{color}; box-shadow:{glow}; font-size:11px;'>{i+1}</div></div>", unsafe_allow_html=True)
                    with col_label:
                        btn_text = f"{'✓ ' if status == 'completed' else '→ ' if status == 'active' else '  '}{phase}"
                        if st.button(btn_text, key=f"phase_{phase}", use_container_width=True):
                            st.session_state.selected_phase = phase
                            st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)
            
            fase_selezionata = st.session_state.selected_phase
            
        with col_dettagli:
            
            # --- FASE 1: INPUT ---
            if fase_selezionata == "Input":
                st.markdown("<h2 style='color:#f8fafc; margin-top:0; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;'>1. Input & Decomposizione</h2>", unsafe_allow_html=True)
                st.info(f"**Claim Analizzato:**\n{res['claim']}")
                st.markdown("<br><h4 style='color:#94a3b8; font-weight:600;'>Componenti Estratte (Subclaims):</h4>", unsafe_allow_html=True)
                
                st.markdown("<div style='display:flex; flex-direction:column; align-items:center; width:100%;'>", unsafe_allow_html=True)
                for i, sc in enumerate(res['subclaims']):
                    st.markdown(f"""
                    <div style='background:rgba(255,255,255,0.03); padding:15px 25px; border-radius:12px; margin-bottom:15px; border-left: 4px solid #38bdf8; box-shadow: 0 4px 10px rgba(0,0,0,0.15); width:100%; max-width:800px; text-align:left;'>
                        <div style='color:#38bdf8; font-size:0.75rem; font-weight:800; text-transform:uppercase; margin-bottom:8px; letter-spacing:1px;'>Subclaim {i+1}</div>
                        <div style='color:#f8fafc; font-size:1.1rem; line-height:1.5;'>{sc}</div>
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                    
            # --- FASE 2: RAG ---
            elif fase_selezionata == "RAG":
                st.markdown("<h2 style='color:#f8fafc; margin-top:0; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;'>2. Documenti Recuperati (RAG)</h2>", unsafe_allow_html=True)
                st.markdown("<p style='color:#94a3b8; margin-bottom:25px;'>Documentazione scientifica estrapolata per ciascun subclaim. Clicca sulle schede per esplorare le fonti.</p>", unsafe_allow_html=True)
                
                html_rag = "<div style='display:flex; flex-direction:column; align-items:center; width:100%; gap:15px;'>"
                for i, ev in enumerate(res['evaluations']):
                    sc = ev.get("subclaim", "")
                    chunks = ev.get("retrieved_chunks", [])[:5]
                    
                    chunks_html = ""
                    for c in chunks:
                        c_text = c.get("text", "") if isinstance(c, dict) else str(c)
                        c_meta = c.get("metadata", {}) if isinstance(c, dict) else {}
                        c_source = c_meta.get("title") or c_meta.get("id") or "Reference Document"
                        hl_text = highlight_quotes(c_text, ev.get("supporting_quotes", []), ev.get("refuting_quotes", []))
                        chunks_html += f"<div style='background:#1e293b; padding:15px; margin:10px 0; border-left:4px solid #818cf8; border-radius:8px; font-size:0.9rem;'><strong style='color:#818cf8; display:block; margin-bottom:8px;'>{c_source}</strong><span style='color:#cbd5e1; line-height:1.6;'>{hl_text}</span></div>"
                        
                    modal_html = f"<input type='checkbox' id='modal-rag-{i}' class='modal-toggle' style='display:none;'><div class='modal-wrapper'><div class='modal-card'><label for='modal-rag-{i}' class='close-btn'>✖</label><h3 style='color:#818cf8; margin-top:0;'>Fonti Subclaim {i+1}</h3><p style='color:#e2e8f0; font-style:italic;'>\"{sc}\"</p><hr style='border:none; border-top:1px solid rgba(255,255,255,0.1); margin:15px 0;'><strong style='color:#a78bfa; margin-top:20px; display:block;'>📄 Documenti estratti:</strong>{chunks_html if chunks else '<p>Nessun documento trovato.</p>'}</div></div>"
                    html_rag += f"<label for='modal-rag-{i}' class='card-btn' style='width:100%; max-width:800px; border-left: 4px solid #818cf8;'><div style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>Fonti Subclaim {i+1}</div><div style='font-size:1.05rem; color:#f8fafc;'>\"{sc}\"</div><div style='position:absolute; right:20px; top:50%; transform:translateY(-50%); font-size:1.5rem;'>📚</div></label>{modal_html}"
                html_rag += "</div>"
                st.markdown(html_rag, unsafe_allow_html=True)

            # --- FASE 3: EVAL ---
            elif fase_selezionata == "Eval":
                st.markdown("<h2 style='color:#f8fafc; margin-top:0; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;'>3. Analisi e Ragionamento Clinico</h2>", unsafe_allow_html=True)
                st.markdown("<p style='color:#94a3b8; margin-bottom:25px;'>Spiegazione logica del modello per ogni singola componente. Clicca sulle schede per leggere l'analisi.</p>", unsafe_allow_html=True)
                
                html_eval = "<div style='display:flex; flex-direction:column; align-items:center; width:100%; gap:15px;'>"
                for i, ev in enumerate(res['evaluations']):
                    sc = ev.get("subclaim", "")
                    lbl = ev.get("label", "NEI").upper()
                    reasoning = ev.get("justification", ev.get("selection_reasoning", "No reasoning provided."))
                    c_col, c_icon = ("#10b981", "✅") if lbl == "SUPPORTED" else ("#ef4444", "❌") if lbl == "REFUTED" else ("#f59e0b", "⚠️")
                    
                    chunks_html = ""
                    for c in ev.get("retrieved_chunks", [])[:5]:
                        c_text = c.get("text", "") if isinstance(c, dict) else str(c)
                        c_meta = c.get("metadata", {}) if isinstance(c, dict) else {}
                        c_source = c_meta.get("title") or c_meta.get("id") or "Reference Document"
                        hl_text = highlight_quotes(c_text, ev.get("supporting_quotes", []), ev.get("refuting_quotes", []))
                        chunks_html += f"<div style='background:#1e293b; padding:10px; margin:8px 0; border-left:4px solid {c_col}; border-radius:6px; font-size:0.85rem; text-align:left;'><strong style='color:{c_col};'>{c_source}</strong><br><span style='color:#cbd5e1; line-height:1.6;'>{hl_text}</span></div>"
                        
                    modal_html = f"<input type='checkbox' id='modal-eval-{i}' class='modal-toggle' style='display:none;'><div class='modal-wrapper'><div class='modal-card'><label for='modal-eval-{i}' class='close-btn'>✖</label><h3 style='color:#38bdf8; margin-top:0;'>Analisi Subclaim {i+1}</h3><p style='color:#e2e8f0; font-style:italic;'>\"{sc}\"</p><hr style='border:none; border-top:1px solid rgba(255,255,255,0.1); margin:15px 0;'><strong style='color:#a78bfa; font-size:1.1rem;'>🧠 Ragionamento:</strong><p style='color:#f8fafc; font-size:0.95rem; line-height:1.6;'>{reasoning}</p><strong style='color:#a78bfa; font-size:1.1rem; margin-top:20px; display:block;'>📄 Top 5 Evidenze:</strong>{chunks_html}</div></div>"
                    html_eval += f"<label for='modal-eval-{i}' class='card-btn' style='width:100%; max-width:800px; border-left:4px solid {c_col};'><div style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>SUBCLAIM {i+1}</div><div style='font-size:0.95rem; color:#f8fafc; margin-bottom:10px;'>\"{sc}\"</div><div style='font-size:0.85rem; font-weight:700; color:{c_col};'> {c_icon} Evaluated: {lbl}</div></label>{modal_html}"
                html_eval += "</div>"
                st.markdown(html_eval, unsafe_allow_html=True)
                
                st.markdown("""
                <style>
                .eval-highlight-support { background: linear-gradient(120deg, rgba(16, 185, 129, 0.3) 0%, rgba(16, 185, 129, 0.1) 100%); color: #34d399 !important; font-weight: bold; padding: 2px 6px; border-radius: 4px; border-left: 3px solid #10b981; }
                .eval-highlight-refute { background: linear-gradient(120deg, rgba(239, 68, 68, 0.3) 0%, rgba(239, 68, 68, 0.1) 100%); color: #f87171 !important; font-weight: bold; padding: 2px 6px; border-radius: 4px; border-left: 3px solid #ef4444; }
                </style>
                """, unsafe_allow_html=True)

            # --- FASE 4: DONE (Verdetto Finale) ---
            elif fase_selezionata == "Done":
                st.markdown("<h2 style='color:#f8fafc; margin-top:0; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px;'>4. Aggregazione e Verdetto Finale</h2>", unsafe_allow_html=True)
                
                verdict = str(res['final'].get("label", res['final'].get("final_verdict", "NEI"))).strip().upper()
                just = res['final'].get("justification", res['final'].get("reasoning", "Nessuna giustificazione medica fornita."))
                c_col, c_icon = ("#10b981", "✅") if verdict == "SUPPORTED" else ("#ef4444", "❌") if verdict == "REFUTED" else ("#f59e0b", "⚠️")

                html_flex_row = (
                    f"<div style='background:rgba(30,41,59,0.4); border:1px solid rgba(255,255,255,0.05); border-radius:16px; padding:35px; display:flex; flex-direction:row; align-items:center; gap:40px; box-shadow:0 10px 30px -10px rgba(0,0,0,0.3); margin-top:10px; margin-bottom: 30px;'>"
                    f"<div style='flex-shrink:0; position:relative; width:160px; height:160px; border-radius:50%; background:conic-gradient({c_col} {int(avg_conf_percent)}%, #1e293b 0); display:flex; align-items:center; justify-content:center; box-shadow:0 0 25px {c_col}30;'>"
                    f"<div style='position:absolute; width:135px; height:135px; background:#0f172a; border-radius:50%; display:flex; flex-direction:column; align-items:center; justify-content:center;'>"
                    f"<span style='font-size:2.8rem; font-weight:800; color:#f8fafc;'>{int(avg_conf_percent)}%</span>"
                    f"<span style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; letter-spacing:1px;'>Confidence</span>"
                    f"</div></div>"
                    f"<div style='flex-grow:1; display:flex; flex-direction:column; justify-content:center;'>"
                    f"<div style='display:flex; align-items:center; gap:15px; margin-bottom:20px;'>"
                    f"<span style='font-size:2.8rem;'>{c_icon}</span>"
                    f"<span style='color:{c_col}; font-size:2.4rem; font-weight:900; letter-spacing:1px; text-transform:uppercase;'>{verdict}</span>"
                    f"</div>"
                    f"<div style='background:rgba(0,0,0,0.2); padding:20px; border-radius:12px; border-left:4px solid {c_col};'>"
                    f"<h3 style='color:#a78bfa; margin-top:0; margin-bottom:10px; font-size:1.05rem; text-transform:uppercase; letter-spacing:1px;'>Medical Justification</h3>"
                    f"<div style='color:#cbd5e1; font-size:1.05rem; line-height:1.6;'>{just}</div>"
                    f"</div></div></div>"
                )
                st.markdown(html_flex_row, unsafe_allow_html=True)
                
                # BOTTONI PDF E NEW ANALYSIS
                st.markdown("<br>", unsafe_allow_html=True)
                col_btn1, col_btn2 = st.columns([1, 1])
                
                with col_btn1:
                    try:
                        # Import corretto del modulo PDF
                        from utils.pdf_generator import generate_fact_check_pdf
                        
                        pdf_bytes = generate_fact_check_pdf(
                            claim=res['claim'], 
                            final_verdict=res['final'], 
                            subclaims=res['evaluations']
                        )
                        
                        st.download_button(
                            label="📄 Download PDF Report",
                            data=pdf_bytes,
                            file_name=f"FactCheck_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="pdf_download_done"
                        )
                    except ImportError as e:
                        st.error(f"❌ Module not found: {str(e)}")
                        st.info("Make sure 'utils/pdf_generator.py' exists with __init__.py in utils folder.")
                    except Exception as e:
                        st.error(f"❌ PDF generation failed: {str(e)}")
                
                with col_btn2:
                
                    if st.button("🔄 New Analysis", use_container_width=True, key="new_analysis_done"):
                        # Mostra un messaggio di reset
                        st.success("🧹 Resetting everything...")
                        
                        # Cancella TUTTO il session_state
                        for key in list(st.session_state.keys()):
                            del st.session_state[key]
                        
                        # Piccolo delay per mostrare il messaggio
                        import time
                        time.sleep(0.5)
                        
                        # JavaScript per forzare il reload completo
                        components.html("""
                        <script>
                            // Pulisce tutto lo storage
                            localStorage.clear();
                            sessionStorage.clear();
                            
                            // Ricarica la pagina forzando il bypass della cache
                            window.parent.location.reload(true);
                        </script>
                        """, height=0)
                        
                        st.rerun()

                        components.html("<script>setTimeout(function(){const el = window.parent.document.getElementById('results-anchor'); if(el) el.scrollIntoView({behavior: 'smooth', block: 'start'});}, 500);</script>", height=0, width=0)

st.markdown("""
<div class="footer">
    MedFactCheck Project • Big Data Engineering MSc Unina • Powered by RAG & LLMs
</div>
""", unsafe_allow_html=True)