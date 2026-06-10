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
    
    st.markdown("### 📋 Select Claims to Verify")
    
    if context:
        st.info(f"📄 **Context:** {context}")
    
    # Inizializza la sessione per i claim selezionati
    if 'selected_claims' not in st.session_state:
        st.session_state.selected_claims = {}
    
    # Pulsanti per selezione rapida
    col_select_all, col_deselect_all, col_info = st.columns([1, 1, 2])
    with col_select_all:
        if st.button("✅ Select All", use_container_width=True):
            for i in range(len(sentences)):
                st.session_state.selected_claims[i] = True
    
    with col_deselect_all:
        if st.button("❌ Deselect All", use_container_width=True):
            for i in range(len(sentences)):
                st.session_state.selected_claims[i] = False
    
    with col_info:
        selected_count = sum(1 for v in st.session_state.selected_claims.values() if v)
        st.markdown(f"**{selected_count}/{len(sentences)} claims selected**")
    
    st.markdown("---")
    
    # Renderizza ogni frase come checkbox
    selected_claims = []
    
    for i, sentence in enumerate(sentences):
        is_selected = st.session_state.selected_claims.get(i, False)
        
        col_check, col_text = st.columns([0.1, 0.9])
        
        with col_check:
            checked = st.checkbox(
                f"##{i}",
                value=is_selected,
                key=f"claim_{i}",
                label_visibility="collapsed"
            )
            st.session_state.selected_claims[i] = checked
        
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
                central_subtitle = f"Selected Sources: {sources_str}"
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
                card_html = f"<label for='modal-p{target_phase}-{i}' style='display:block; cursor:pointer; position:relative; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); padding:12px 18px; border-radius:12px; width:calc(50% - 5px); min-width:300px; text-align:left; transition: transform 0.2s, border-color 0.2s;'><span style='position:absolute; right:10px; bottom:10px; font-size:4rem; opacity:0.04; pointer-events:none; z-index:0;'>🔍</span><span style='display:block; position:relative; z-index:2; font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px; pointer-events:none;'>SUBCLAIM {i+1}</span><span style='display:block; position:relative; z-index:2; font-size:0.95rem; color:#f8fafc; margin-bottom:8px; line-height:1.4; pointer-events:none;'>\"{sc}\"</span><span style='display:block; position:relative; z-index:2; font-size:0.8rem; font-weight:600; color:#38bdf8; pointer-events:none;'>{status}</span>"
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
          <div style="height: 150px; width: 100%; flex-shrink: 0;"></div>
        """

    if not final_verdict:
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
    
    # Sync with active slide state
    active_slide_str = st.session_state.get("active_slide_key", "")
    active_slide = int(active_slide_str) if (active_slide_str and active_slide_str.isdigit()) else None
    
    if final_verdict is not None or st.session_state.get("keep_overlay_open", False):
        if active_slide is not None:
            target_slide = active_slide
        else:
            target_slide = 4
    else:
        target_slide = step if step <= 4 else 4

    slide1_checked = 'checked' if target_slide == 1 else ''
    slide2_checked = 'checked' if target_slide == 2 else ''
    slide3_checked = 'checked' if target_slide == 3 else ''
    slide4_checked = 'checked' if target_slide == 4 else ''
    
    progress_percent = int((target_slide - 1) * 33.33)
    
    is_done = final_verdict is not None
    
    if is_done:
        overlay_position = "relative !important"
        overlay_width = "100% !important"
        overlay_height = "auto !important"
        overlay_overflow = "visible !important"
        overlay_z_index = "999 !important"
        viewport_height = "auto !important"
        viewport_overflow = "visible !important"
        slide_height = "auto !important"
        slide_overflow = "visible !important"
        slide_content_padding = "0 0 40px 0 !important"
    else:
        overlay_position = "fixed"
        overlay_width = "100vw"
        overlay_height = "100vh"
        overlay_overflow = "hidden"
        overlay_z_index = "9999999 !important"
        viewport_height = "calc(100vh - 350px)"
        viewport_overflow = "hidden"
        slide_height = "100%"
        slide_overflow = "hidden"
        slide_content_padding = "0 0 50px 0"

    css_content = f"""
    <style>
    .cyber-overlay {{ position: {overlay_position}; top: 0; left: 0; width: {overlay_width}; height: {overlay_height}; background: rgba(15, 23, 42, 0.97); backdrop-filter: blur(20px); z-index: {overlay_z_index}; overflow: {overlay_overflow}; pointer-events: auto !important; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding-top: 60px; }}
    div[data-testid="stHorizontalBlock"]:has(.panel-title) {{
        display: none !important;
    }}
    .carousel-viewport {{ width: 100vw; height: {viewport_height}; position: relative; overflow: {viewport_overflow}; margin-top: 30px; }}
    .slider-container {{ display: flex; width: 400vw; height: 100%; transition: transform 0.5s cubic-bezier(0.25, 0.8, 0.25, 1); }}
    #slide-1:checked ~ .carousel-viewport .slider-container {{ transform: translateX(0); }}
    #slide-2:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-100vw); }}
    #slide-3:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-200vw); }}
    #slide-4:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-300vw); }}
    .slide {{ width: 100vw; height: {slide_height}; position: relative; padding: 0 80px; box-sizing: border-box; }}
    .slide-content {{ width: 100%; height: 100%; overflow-y: {slide_overflow}; display: flex; flex-direction: column; align-items: center; padding: {slide_content_padding}; text-align: center; }}
    .global-arrow {{ position: absolute; top: 50%; transform: translateY(-50%); background: rgba(56,189,248,0.1); color: #38bdf8; width: 50px; height: 50px; border-radius: 50%; display: none; align-items: center; justify-content: center; font-size: 24px; cursor: pointer; transition: 0.3s; border: 1px solid rgba(56,189,248,0.3); z-index: 10000; }}
    .global-arrow:hover {{ background: rgba(56,189,248,0.4); color: #fff; transform: translateY(-50%) scale(1.1); }}
    .left-arrow {{ left: 30px; }}
    .right-arrow {{ right: 30px; }}
    #slide-1:checked ~ .carousel-viewport .show-1 {{ display: flex; }}
    #slide-2:checked ~ .carousel-viewport .show-2 {{ display: flex; }}
    #slide-3:checked ~ .carousel-viewport .show-3 {{ display: flex; }}
    #slide-4:checked ~ .carousel-viewport .show-4 {{ display: flex; }}
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
    .stepper-line {{ position: absolute; top: 25px; left: 10%; width: 80%; height: 4px; background: rgba(255, 255, 255, 0.1); border-radius: 2px; z-index: 1; }}
    .stepper-progress {{ height: 100%; background: linear-gradient(90deg, #38bdf8, #818cf8, #a78bfa, #10b981); border-radius: 2px; transition: width 0.5s ease-in-out; }}
    .stepper-steps {{ display: flex; justify-content: space-between; position: relative; z-index: 2; }}
    .step {{ display: flex; flex-direction: column; align-items: center; width: 25%; position: relative; }}
    .step-dot {{ width: 30px; height: 30px; border-radius: 50%; background: #0f172a; border: 2px solid rgba(255, 255, 255, 0.2); display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; color: #64748b; transition: all 0.4s; margin-bottom: 8px; z-index: 2; pointer-events: none; }}
    .step.active .step-dot {{ border-color: {anim_color}; color: #f8fafc; background: #0f172a; }}
    .step-label {{ font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 1px; text-align: center; transition: color 0.3s; margin-top: 5px; pointer-events: none; }}
    .step.active .step-label {{ color: #e2e8f0; }}
    .step {{ cursor: pointer; }}
    .step:hover {{ opacity: 0.8; }}
    #slide-1:checked ~ .stepper-container .step-ui-1 .step-dot {{ background: {anim_color}; border-color: {anim_color}; box-shadow: 0 0 15px {anim_color}; }}
    #slide-2:checked ~ .stepper-container .step-ui-2 .step-dot {{ background: {anim_color}; border-color: {anim_color}; box-shadow: 0 0 15px {anim_color}; }}
    #slide-3:checked ~ .stepper-container .step-ui-3 .step-dot {{ background: {anim_color}; border-color: {anim_color}; box-shadow: 0 0 15px {anim_color}; }}
    #slide-4:checked ~ .stepper-container .step-ui-4 .step-dot {{ background: {anim_color}; border-color: {anim_color}; box-shadow: 0 0 15px {anim_color}; }}
    </style>
    """
    
    html_structure = f"""{modal_css}
{css_content}
<div class="cyber-overlay" id="main-cyber-overlay">
    <input type="radio" name="slider" id="slide-1" {slide1_checked} style="display:none;">
    <input type="radio" name="slider" id="slide-2" {slide2_checked} style="display:none;">
    <input type="radio" name="slider" id="slide-3" {slide3_checked} style="display:none;">
    <input type="radio" name="slider" id="slide-4" {slide4_checked} style="display:none;">
    <div class="pulse-container"><div class="pulse-ring"></div><div class="pulse-ring"></div><div class="pulse-ring"></div><div class="pulse-core"></div></div>
    <div class="stage-title">{central_title}</div>
    <div class="stage-subtitle">{central_subtitle}</div>
    <div class="stepper-container">
        <div class="stepper-line"><div class="stepper-progress" style="width: {progress_percent}%;"></div></div>
        <div class="stepper-steps">
            <label for="slide-1" class="step step-ui-1 {'active' if step >= 1 else ''}"><div class="step-dot">1</div><div class="step-label">Input</div></label>
            <label for="slide-2" class="step step-ui-2 {'active' if step >= 2 else ''}"><div class="step-dot">2</div><div class="step-label">RAG</div></label>
            <label for="slide-3" class="step step-ui-3 {'active' if step >= 3 else ''}"><div class="step-dot">3</div><div class="step-label">Eval</div></label>
            <label for="slide-4" class="step step-ui-4 {'active' if step >= 4 else ''}"><div class="step-dot">4</div><div class="step-label">Done</div></label>
        </div>
    </div>
    <div class="carousel-viewport">
        <div class="slider-container">
            <div class="slide"><div class="slide-content">{slide1_content}</div></div>
            <div class="slide"><div class="slide-content"><div class="slide-header">Document Retrieval Extracts (RAG)</div>{sc_html_p2}</div></div>
            <div class="slide"><div class="slide-content"><div class="slide-header">Clinical Reasoning Agent Results</div>{sc_html_p3}</div></div>
            <div class="slide"><div class="slide-content">{slide4_content}</div></div>
        </div>
    </div>
</div>
"""
    
    # Remove all blank lines and indentation to force Streamlit to parse it as a single contiguous HTML block.
    # This prevents both the Markdown code block bug and the max-line-length crash in markdown-it-py.
    html_content = "\n".join([line.strip() for line in html_structure.split('\n') if line.strip()])
    
    try:
        overlay_placeholder.markdown(html_content, unsafe_allow_html=True)
    except Exception as e:
        error_placeholder.error(f"Rendering error: {str(e)}")


# 2. CSS Avanzato Originale
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
    
    div[data-testid="stTextInput"]:has(input[aria-label="active_slide_input"]) {
        display: none !important;
    }
    
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
    div[data-testid="stMainBlockContainer"]:has(.cyber-overlay) div[data-testid="stHorizontalBlock"]:has(.panel-title) {
        display: none !important;
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
    
    /* Change color of radio buttons labels to match subtitle */
    div[data-testid="stRadio"] label[data-testid="stWidgetLabel"] p { color: #94a3b8 !important; }
    div[data-testid="stRadio"] div[role="radiogroup"] label p { color: #94a3b8 !important; }
    
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
st.text_input("active_slide_input", value=str(st.session_state.get("active_slide_key", "")), label_visibility="collapsed", key="active_slide_key")
overlay_placeholder = st.empty()

_, col_main, _ = st.columns([1, 14, 1])

# Gestione cambio metodo input
if 'last_input_method' not in st.session_state:
    st.session_state.last_input_method = None

with col_main:
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
                with st.expander("📄 File Content", expanded=True):
                    st.text_area(
                        "File Content:", 
                        value=file_content[:1000] + ("..." if len(file_content) > 1000 else ""), 
                        height=150, 
                        disabled=True
                    )
                
                # Dividi in frasi e mostra checklist
                sentences = split_into_sentences(file_content)
                
                if sentences:
                    st.markdown(f"**📊 Found {len(sentences)} sentences in the document**")
                    
                    # Usa la checklist per selezionare i claim
                    selected_claims = render_claim_checklist(
                        sentences, 
                        context=f"File: {uploaded_file.name}"
                    )
                    
                    # Combina i claim selezionati
                    if selected_claims:
                        claim = " ".join(selected_claims)
                        st.success(f"✅ {len(selected_claims)} claims selected for verification")
                        
                        # Mostra i claim selezionati
                        with st.expander("📋 Selected Claims", expanded=False):
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
                        st.warning("⚠️ Please select at least one claim to verify")
                else:
                    st.warning("⚠️ No valid sentences found in the document")
                    
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
                                st.success("✅ Content fetched successfully!")
                                
                                # Mostra preview del contenuto
                                with st.expander("🌐 Page Content", expanded=True):
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
                                    st.markdown(f"**📊 Found {len(sentences)} sentences on the page**")
                                    
                                    # Usa la checklist per selezionare i claim
                                    selected_claims = render_claim_checklist(
                                        sentences, 
                                        context=f"URL: {url_input}"
                                    )
                                    
                                    # Combina i claim selezionati
                                    if selected_claims:
                                        claim = " ".join(selected_claims)
                                        st.success(f"✅ {len(selected_claims)} claims selected for verification")
                                        
                                        # Mostra i claim selezionati
                                        with st.expander("📋 Selected Claims", expanded=False):
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
                                        st.warning("⚠️ Please select at least one claim to verify")
                                else:
                                    st.warning("⚠️ No valid sentences found on the page")
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
                    error_occurred = False
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
                                        error_occurred = True
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
                                        if sub_id: st.session_state.source_selections[sub_id] = [k for k, v in (info.get("retrieval_source") or {}).items() if v > 0]
                                        update_interactive_loading(claim=claim, step=2, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=0, total_to_verify=len(st.session_state.current_subclaims))
                                        
                                    elif "downloader_agent" in step_data:
                                        info = step_data["downloader_agent"]
                                        sub_id = info.get("subclaim_id")
                                        if sub_id: st.session_state.downloader_status[sub_id] = len(info.get("downloaded_chunks", []))
                                        update_interactive_loading(claim=claim, step=2, subclaims=st.session_state.current_subclaims, evaluations=st.session_state.current_evaluations, verified_count=0, total_to_verify=len(st.session_state.current_subclaims))
                                        
                                    elif "hybrid_retriever" in step_data:
                                        info = step_data["hybrid_retriever"]
                                        sub_id = info.get("subclaim_id")
                                        if sub_id: st.session_state.retriever_status[sub_id] = len(info.get("retrieved_chunks", []))
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
                                        st.session_state.pdf_filename = f"FactCheck_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                                        # Do not empty overlay, keep it and update to step 4
                                        st.session_state.selected_phase = "Done"
                                        st.session_state.results_just_arrived = False
                                        update_interactive_loading(
                                            claim=claim, 
                                            step=4, 
                                            subclaims=st.session_state.current_subclaims, 
                                            evaluations=st.session_state.current_evaluations, 
                                            verified_count=len(st.session_state.current_evaluations), 
                                            total_to_verify=len(st.session_state.current_subclaims),
                                            final_verdict=current_final
                                        )
                                        st.session_state.keep_overlay_open = True
                                        st.rerun()
                                except json.JSONDecodeError:
                                    pass
                    
                    if not error_occurred and not st.session_state.get("keep_overlay_open", False):
                        current_final = {
                            "label": "not_enough_information",
                            "confidence": 1.0,
                            "reasoning": "The input text did not contain any verifiable medical claims."
                        }
                        st.session_state.real_results = {
                            "subclaims": st.session_state.current_subclaims,
                            "evaluations": st.session_state.current_evaluations,
                            "final": current_final,
                            "claim": claim
                        }
                        st.session_state.pdf_filename = f"FactCheck_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                        st.session_state.selected_phase = "Done"
                        st.session_state.results_just_arrived = False
                        st.session_state.keep_overlay_open = True
                        st.rerun()
                else:
                    overlay_placeholder.empty()
                    error_placeholder.error(f"❌ Backend Connection Error (Status Code: {response.status_code})")
            except Exception as e:
                overlay_placeholder.empty()
                error_placeholder.error(f"❌ Failed to connect to the backend API: {str(e)}")

# ==========================================
# 5. FINAL BUTTONS E OVERLAY MANTENUTO
# ==========================================
if st.session_state.get("keep_overlay_open", False) and st.session_state.real_results:
    res = st.session_state.real_results
    update_interactive_loading(
        claim=res["claim"], 
        step=4, 
        subclaims=res["subclaims"], 
        evaluations=res["evaluations"], 
        verified_count=len(res["evaluations"]), 
        total_to_verify=len(res["subclaims"]),
        final_verdict=res["final"]
    )
    
    # CSS ottimizzato per posizionare i pulsanti in modo statico e pulito sotto i risultati
    st.markdown("""
        <style>
        .slide-content {
            padding-bottom: 20px !important; 
        }
        
        div[data-testid="stHorizontalBlock"]:has([class*="st-key-new_analysis_btn"]) {
            position: static !important;
            transform: none !important;
            margin: 40px auto 60px auto !important;
            max-width: 900px !important;
            z-index: 1000 !important;
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            width: 100% !important;
            display: flex !important;
            justify-content: center !important;
            gap: 20px !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Contenitore vero e proprio
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("← Back to Home", use_container_width=True, key="back_to_home_done"):
            st.switch_page("app.py")

    with col2:
        try:
            from utils.pdf_generator import generate_fact_check_pdf
            from datetime import datetime
            pdf_bytes = generate_fact_check_pdf(
                claim=res['claim'], 
                final_verdict=res['final'], 
                subclaims=res['evaluations']
            )
            pdf_filename = st.session_state.get("pdf_filename", "FactCheck_Report.pdf")
            st.download_button(
                label="📄 Download PDF Report",
                data=pdf_bytes,
                file_name=pdf_filename,
                mime="application/pdf",
                use_container_width=True,
                key="pdf_download_done"
            )
        except Exception as e:
            pdf_content = "Med Fact Check Report\n" + "="*40 + "\n\n"
            pdf_content += "Claim:\n" + res["claim"] + "\n\n"
            pdf_content += "Verdict: " + res["final"].get("label", "NEI").upper() + "\n"
            st.download_button("📥 Download Report", data=pdf_content, file_name="fact_check_report.txt", use_container_width=True)

    with col3:
        if st.button("🔄 New Analysis", use_container_width=True, type="primary", key="new_analysis_btn"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # JS Sync component to keep Streamlit in sync with CSS slider changes
    components.html("""
    <script>
        function setupSync() {
            const parentDoc = window.parent.document;
            if (!parentDoc) return;
            
            let targetInput = parentDoc.querySelector('input[aria-label="active_slide_input"]');
            if (!targetInput) {
                const labels = parentDoc.querySelectorAll('label');
                labels.forEach(label => {
                    if (label.textContent && label.textContent.includes('active_slide_input')) {
                        const container = label.closest('div[data-testid="stTextInput"]');
                        if (container) {
                            targetInput = container.querySelector('input');
                        }
                    }
                });
            }
            
            if (!targetInput) {
                setTimeout(setupSync, 50);
                return;
            }
            
            const radios = parentDoc.querySelectorAll('input[name="slider"]');
            if (radios.length === 0) {
                setTimeout(setupSync, 50);
                return;
            }

            // Sync immediately on load if client checked state differs from targetInput value
            const checkedRadio = parentDoc.querySelector('input[name="slider"]:checked');
            if (checkedRadio) {
                const activeIndex = checkedRadio.id.split('-')[1];
                if (targetInput.value !== activeIndex) {
                    targetInput.value = activeIndex;
                    targetInput.dispatchEvent(new Event('input', { bubbles: true }));
                    targetInput.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }

            radios.forEach(radio => {
                radio.removeEventListener('change', radio._syncHandler);
                
                const handler = (e) => {
                    if (e.target.checked) {
                        const slideIndex = e.target.id.split('-')[1];
                        if (targetInput.value !== slideIndex) {
                            targetInput.value = slideIndex;
                            targetInput.dispatchEvent(new Event('input', { bubbles: true }));
                            targetInput.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }
                };
                radio._syncHandler = handler;
                radio.addEventListener('change', handler);
            });
        }
        
        setupSync();
        for (let t of [100, 200, 500, 1000]) {
            setTimeout(setupSync, t);
        }
    </script>
    """, height=0, width=0)

st.markdown("""
<div class="footer">
    MedFactCheck Project • Big Data Engineering MSc Unina • Powered by RAG & LLMs
</div>
""", unsafe_allow_html=True)