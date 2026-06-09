import streamlit as st
import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px
import importlib
import streamlit.components.v1 as components

# 1. Configurazione della Pagina
st.set_page_config(
    page_title="Fact Check | Med Fact Check",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

import re

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


def update_interactive_loading(claim, step=1, subclaims=None, evaluations=None, verified_count=0, total_to_verify=1, final_verdict=None):
    all_modals_html = ""
    if subclaims is None: subclaims = []
    if evaluations is None: evaluations = []
    
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
            central_title = "Fact-Checking Completed!"
            central_subtitle = "Final results are ready for analysis."
        elif verdict == "REFUTED":
            anim_color = "#ef4444"
            central_title = "Fact-Checking Completed!"
            central_subtitle = "Final results are ready for analysis."
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
    
    # CSS DELLE MODALI (POPUP) E DEL CAROSELLO A 4 FASI
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
                card_html = f"<label for='modal-p{target_phase}-{i}' style='display:block; cursor:pointer; position:relative; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); padding:12px 18px; border-radius:12px; width:calc(50% - 5px); min-width:300px; text-align:left; transition: transform 0.2s, border-color 0.2s;' onmouseover=\"this.style.transform='translateY(-3px)'; this.style.borderColor='#38bdf8';\" onmouseout=\"this.style.transform='translateY(0)'; this.style.borderColor='rgba(255,255,255,0.1)';\"><div style='position:absolute; right:10px; bottom:10px; font-size:4rem; opacity:0.04; pointer-events:none; z-index:0;'>🔍</div><div style='position:relative; z-index:2; font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>SUBCLAIM {i+1}</div><div style='position:relative; z-index:2; font-size:0.95rem; color:#f8fafc; margin-bottom:8px; line-height:1.4;'>\"{sc}\"</div><div style='position:relative; z-index:2; font-size:0.8rem; font-weight:600; color:#38bdf8;'>{status}</div>"
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
        
        buttons_html = ""

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
                {buttons_html}
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
                The pipeline is aggregating the Clinical Agent's results across all extracted claims.<br>
                <br>
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
    stepper_html = f"""
    <div class="stepper-container">
        <div class="stepper-line"><div class="stepper-progress" style="width: {progress_percent}%;"></div></div>
        <div class="stepper-steps">
            <label for="{f'slide-1' if step >= 1 else ''}" class="step step-ui-1 {'active' if step >= 1 else ''}" style="cursor:{'pointer' if step >= 1 else 'not-allowed'};"><div class="step-dot">1</div><div class="step-label">Input</div></label>
            <label for="{f'slide-2' if step >= 2 else ''}" class="step step-ui-2 {'active' if step >= 2 else ''}" style="cursor:{'pointer' if step >= 2 else 'not-allowed'};"><div class="step-dot">2</div><div class="step-label">RAG</div></label>
            <label for="{f'slide-3' if step >= 3 else ''}" class="step step-ui-3 {'active' if step >= 3 else ''}" style="cursor:{'pointer' if step >= 3 else 'not-allowed'};"><div class="step-dot">3</div><div class="step-label">Eval</div></label>
            <label for="{f'slide-4' if step >= 4 else ''}" class="step step-ui-4 {'active' if step >= 4 else ''}" style="cursor:{'pointer' if step >= 4 else 'not-allowed'};"><div class="step-dot">4</div><div class="step-label">Done</div></label>
        </div>
    </div>
    """

    html_content = f"""
{modal_css}
<style>
.stApp {{ pointer-events: none !important; overflow: hidden !important; }}
.cyber-overlay {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(15, 23, 42, 0.97); backdrop-filter: blur(20px); z-index: 9999999 !important; overflow: hidden; pointer-events: auto !important; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding-top: 60px; }}

.carousel-viewport {{ width: 100vw; height: calc(100vh - 350px); position: relative; overflow: hidden; margin-top: 30px; }}
.slider-container {{ display: flex; width: 400vw; height: 100%; transition: transform 0.5s cubic-bezier(0.25, 0.8, 0.25, 1); }}
#slide-1:checked ~ .carousel-viewport .slider-container {{ transform: translateX(0); }}
#slide-2:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-100vw); }}
#slide-3:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-200vw); }}
#slide-4:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-300vw); }}

.slide {{ width: 100vw; height: 100%; position: relative; padding: 0 80px; box-sizing: border-box; }}
.slide-content {{ width: 100%; height: 100%; overflow-y: auto; display: flex; flex-direction: column; align-items: center; padding-bottom: 50px; }}

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
.stepper-line {{ position: absolute; top: 25px; left: 12.5%; width: 75%; height: 4px; background: rgba(255, 255, 255, 0.1); border-radius: 2px; z-index: 1; }}
.stepper-progress {{ height: 100%; background: linear-gradient(90deg, #38bdf8, #818cf8, #a78bfa, #10b981); border-radius: 2px; transition: width 0.5s ease-in-out; }}
.stepper-steps {{ display: flex; justify-content: space-between; position: relative; z-index: 2; }}
.step {{ display: flex; flex-direction: column; align-items: center; width: 25%; position: relative; }}
.step-dot {{ width: 30px; height: 30px; border-radius: 50%; background: #0f172a; border: 2px solid rgba(255, 255, 255, 0.2); display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; color: #64748b; transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); margin-bottom: 8px; z-index: 2; }}
.step.active .step-dot {{ border-color: {anim_color}; color: #f8fafc; background: #0f172a; }}
.step-label {{ font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 1px; text-align: center; transition: color 0.3s; margin-top: 5px; }}
.step.active .step-label {{ color: #e2e8f0; }}

#slide-1:checked ~ .stepper-container .step-ui-1 .step-dot,
#slide-2:checked ~ .stepper-container .step-ui-2 .step-dot,
#slide-3:checked ~ .stepper-container .step-ui-3 .step-dot,
#slide-4:checked ~ .stepper-container .step-ui-4 .step-dot {{
    background: {anim_color}; color: #0f172a; border-color: {anim_color}; box-shadow: 0 0 15px {anim_color}; transform: scale(1.2);
}}

#slide-1:checked ~ .stepper-container .step-ui-1 .step-label,
#slide-2:checked ~ .stepper-container .step-ui-2 .step-label,
#slide-3:checked ~ .stepper-container .step-ui-3 .step-label,
#slide-4:checked ~ .stepper-container .step-ui-4 .step-label {{
    color: {anim_color}; text-shadow: 0 0 10px rgba(255,255,255,0.1);
}}
</style>

<div class="cyber-overlay">
    <input type="radio" name="slider" id="slide-1" {'checked' if step == 1 else ''} style="display:none;">
    <input type="radio" name="slider" id="slide-2" {'checked' if step == 2 else ''} style="display:none;">
    <input type="radio" name="slider" id="slide-3" {'checked' if step == 3 else ''} style="display:none;">
    <input type="radio" name="slider" id="slide-4" {'checked' if step == 4 else ''} style="display:none;">

  <div class="pulse-container"><div class="pulse-ring"></div><div class="pulse-ring"></div><div class="pulse-ring"></div><div class="pulse-core"></div></div>
  <div class="stage-title">{central_title}</div>
  <div class="stage-subtitle">{central_subtitle}</div>
  {stepper_html}

  <div class="carousel-viewport">

    <label for="slide-2" class="global-arrow right-arrow show-1" style="{'display:none !important;' if step < 2 else ''}">▶</label>
    <label for="slide-1" class="global-arrow left-arrow show-2">◀</label>
    <label for="slide-3" class="global-arrow right-arrow show-2" style="{'display:none !important;' if step < 3 else ''}">▶</label>
    <label for="slide-2" class="global-arrow left-arrow show-3">◀</label>
    <label for="slide-4" class="global-arrow right-arrow show-3" style="{'display:none !important;' if step < 4 else ''}">▶</label>
    <label for="slide-3" class="global-arrow left-arrow show-4">◀</label>

    <div class="slider-container">
      <div class="slide">
        <div class="slide-content">
          {slide1_content}
        </div>
      </div>
      <div class="slide">
        <div class="slide-content">
          <div class="slide-header">Document Retrieval Extracts (RAG)</div>
          {sc_html_p2}
        </div>
      </div>
      <div class="slide">
        <div class="slide-content">
          <div class="slide-header">Clinical Reasoning Agent Results</div>
          {sc_html_p3}
        </div>
      </div>
      <div class="slide">
        <div class="slide-content">
          {slide4_content}
        </div>
      </div>
    </div>
  </div>
  {all_modals_html}
</div>
"""
    overlay_placeholder.html(html_content)


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
    overlay_placeholder = st.empty()
    if st.button("← Back to Home", type="secondary"):
        st.switch_page("app.py")

    st.markdown('<div class="panel-title">Medical Fact Check Panel</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-subtitle">Submit a medical claim and rigorously verify it against trusted scientific literature.</div>', unsafe_allow_html=True)

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
    # 5. LOGICA BACKEND E ANIMAZIONE CON CARTE MODALI ZOOMANTI
    # ==========================================
    if verify_clicked:
        if not claim.strip():
            st.warning("Please provide a valid claim or document before verifying.")
        else:
            import base64
            from utils.pdf_generator import generate_fact_check_pdf
            
            # Initialize/reset session state variables
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
                                        update_interactive_loading(
                                            claim=claim,
                                            step=2, 
                                            subclaims=st.session_state.current_subclaims, 
                                            evaluations=st.session_state.current_evaluations, 
                                            verified_count=0, 
                                            total_to_verify=len(st.session_state.current_subclaims)
                                        )
                                        
                                    elif "source_selector" in step_data:
                                        info = step_data["source_selector"]
                                        sub_id = info.get("subclaim_id")
                                        ret_source = info.get("retrieval_source") or {}
                                        
                                        # Map coins to friendly names
                                        source_mapping = {
                                            "literature": "EuropePMC",
                                            "knowledge_base": "Uniprot",
                                            "systematic_reviews": "PubMed"
                                        }
                                        active_sources = []
                                        for src, amt in ret_source.items():
                                            if amt > 1 and src in source_mapping:
                                                active_sources.append(source_mapping[src])
                                        if not active_sources:
                                            active_sources = [source_mapping[k] for k, v in ret_source.items() if v > 0 and k in source_mapping]
                                        
                                        if sub_id:
                                            st.session_state.source_selections[sub_id] = active_sources
                                            
                                        update_interactive_loading(
                                            claim=claim,
                                            step=2, 
                                            subclaims=st.session_state.current_subclaims, 
                                            evaluations=st.session_state.current_evaluations, 
                                            verified_count=0, 
                                            total_to_verify=len(st.session_state.current_subclaims)
                                        )
                                        
                                    elif "downloader_agent" in step_data:
                                        info = step_data["downloader_agent"]
                                        sub_id = info.get("subclaim_id")
                                        chunks_count = info.get("downloaded_chunks_count", 0)
                                        if sub_id:
                                            st.session_state.downloader_status[sub_id] = chunks_count
                                        update_interactive_loading(
                                            claim=claim,
                                            step=2, 
                                            subclaims=st.session_state.current_subclaims, 
                                            evaluations=st.session_state.current_evaluations, 
                                            verified_count=0, 
                                            total_to_verify=len(st.session_state.current_subclaims)
                                        )
                                        
                                    elif "hybrid_retriever" in step_data:
                                        info = step_data["hybrid_retriever"]
                                        sub_id = info.get("subclaim_id")
                                        ret_count = info.get("retrieved_chunks_count", 0)
                                        if sub_id:
                                            st.session_state.retriever_status[sub_id] = ret_count
                                        st.session_state.max_step = max(st.session_state.get("max_step", 1), 2)
                                        update_interactive_loading(
                                            claim=claim,
                                            step=st.session_state.max_step, 
                                            subclaims=st.session_state.current_subclaims, 
                                            evaluations=st.session_state.current_evaluations, 
                                            verified_count=len(st.session_state.current_evaluations), 
                                            total_to_verify=len(st.session_state.current_subclaims)
                                        )
                                        
                                    elif "reasoning" in step_data or "veracity" in step_data:
                                        st.session_state.max_step = max(st.session_state.get("max_step", 1), 3)
                                        update_interactive_loading(
                                            claim=claim,
                                            step=st.session_state.max_step,
                                            subclaims=st.session_state.current_subclaims,
                                            evaluations=st.session_state.current_evaluations,
                                            verified_count=len(st.session_state.current_evaluations),
                                            total_to_verify=len(st.session_state.current_subclaims)
                                        )

                                    elif "evaluate_subclaim" in step_data:
                                        eval_results = step_data["evaluate_subclaim"].get("evaluation_results", [])
                                        for er in eval_results:
                                            if er not in st.session_state.current_evaluations:
                                                st.session_state.current_evaluations.append(er)
                                        st.session_state.max_step = max(st.session_state.get("max_step", 1), 3)
                                        update_interactive_loading(
                                            claim=claim,
                                            step=st.session_state.max_step, 
                                            subclaims=st.session_state.current_subclaims, 
                                            evaluations=st.session_state.current_evaluations, 
                                            verified_count=len(st.session_state.current_evaluations), 
                                            total_to_verify=len(st.session_state.current_subclaims)
                                        )
                                        
                                    elif "aggregate" in step_data:
                                        current_final = step_data["aggregate"].get("final_verdict", {})
                                        st.session_state.current_final = current_final
                                        update_interactive_loading(
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
                    error_placeholder.error(f"❌ Backend Connection Error (Status Code: {response.status_code})")
            except Exception as e:
                error_placeholder.error(f"❌ Failed to connect to the backend API: {str(e)}")

st.markdown("""
<div class="footer">
    MedFactCheck Project • Big Data Engineering MSc Unina • Powered by RAG & LLMs
</div>
""", unsafe_allow_html=True)

if getattr(st.session_state, "current_final", None):
    # RERUN MODE: Render the overlay showing Phase 4 (Done)
    update_interactive_loading(
        claim=st.session_state.get("fact_check_claim", claim),
        step=4,
        subclaims=st.session_state.get("current_subclaims", []),
        evaluations=st.session_state.get("current_evaluations", []),
        verified_count=len(st.session_state.get("current_evaluations", [])),
        total_to_verify=len(st.session_state.get("current_subclaims", [])),
        final_verdict=st.session_state.current_final
    )

    try:
        pdf_bytes = generate_fact_check_pdf(
            claim=st.session_state.get("fact_check_claim", claim), 
            final_verdict=st.session_state.current_final, 
            subclaims=st.session_state.get("current_evaluations", [])
        )
    except:
        pdf_bytes = b""
        
    st.markdown("""
    <style>
    /* Identify the elements precisely using adjacent sibling selectors and custom markers */
    .element-container:has(.marker-dl-btn) + .element-container {
        position: fixed !important;
        bottom: 40px !important;
        right: 240px !important;
        z-index: 2147483647 !important;
        pointer-events: auto !important;
        width: auto !important;
    }
    .element-container:has(.marker-new-btn) + .element-container {
        position: fixed !important;
        bottom: 40px !important;
        right: 40px !important;
        z-index: 2147483647 !important;
        pointer-events: auto !important;
        width: auto !important;
    }
    
    .element-container:has(.marker-dl-btn) + .element-container button, 
    .element-container:has(.marker-new-btn) + .element-container button {
        padding: 12px 28px !important;
        font-size: 15px !important;
        border-radius: 50px !important;
        border: none !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5) !important;
        pointer-events: auto !important;
        cursor: pointer !important;
        transition: all 0.3s ease !important;
    }
    
    .element-container:has(.marker-dl-btn) + .element-container button:hover, 
    .element-container:has(.marker-new-btn) + .element-container button:hover {
        transform: scale(1.04) translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.6) !important;
    }
    
    .element-container:has(.marker-dl-btn) + .element-container button { 
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important; 
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.4) !important;
    }
    .element-container:has(.marker-dl-btn) + .element-container button:hover { 
        box-shadow: 0 0 30px rgba(16, 185, 129, 0.7) !important;
    }
    
    .element-container:has(.marker-new-btn) + .element-container button { 
        background: linear-gradient(135deg, #38bdf8 0%, #0284c7 100%) !important; 
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.4) !important;
    }
    .element-container:has(.marker-new-btn) + .element-container button:hover { 
        box-shadow: 0 0 30px rgba(56, 189, 248, 0.7) !important;
    }
    
    .element-container:has(.marker-dl-btn) + .element-container button p, 
    .element-container:has(.marker-new-btn) + .element-container button p {
        color: white !important;
        font-weight: 800 !important;
        font-size: 15px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<span class="marker-dl-btn" style="display:none;"></span>', unsafe_allow_html=True)
    st.download_button("📄 Download PDF Report", data=pdf_bytes, file_name="FactCheck_Report.pdf", mime="application/pdf", key="pdf_dl")
    
    st.markdown('<span class="marker-new-btn" style="display:none;"></span>', unsafe_allow_html=True)
    if st.button("🔄 New Analysis", key="new_analysis"):
        if "current_final" in st.session_state: del st.session_state["current_final"]
        if "fact_check_claim" in st.session_state: del st.session_state["fact_check_claim"]
        if "current_subclaims" in st.session_state: del st.session_state["current_subclaims"]
        if "current_evaluations" in st.session_state: del st.session_state["current_evaluations"]
        if "source_selections" in st.session_state: del st.session_state["source_selections"]
        if "downloader_status" in st.session_state: del st.session_state["downloader_status"]
        if "retriever_status" in st.session_state: del st.session_state["retriever_status"]
        st.rerun()