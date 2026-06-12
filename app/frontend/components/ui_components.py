import streamlit as st
from utils.text_processing import highlight_quotes

def load_global_css():
    """Carica il CSS principale dell'applicazione."""
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

        div.stButton > button, div.stDownloadButton > button { background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%) !important; border: none !important; color: #0f172a !important; font-weight: 800 !important; font-size: 1.15rem !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; border-radius: 50px !important; padding: 0.9rem 2.5rem !important; box-shadow: 0 0 25px rgba(0, 242, 254, 0.4) !important; transition: all 0.4s ease !important; position: relative !important; z-index: 999 !important; }
        div.stButton > button p, div.stDownloadButton > button p { white-space: nowrap !important; margin: 0 !important; color: #0f172a !important; font-weight: 800 !important; }
        div.stButton > button:hover, div.stDownloadButton > button:hover { transform: scale(1.04) translateY(-2px) !important; box-shadow: 0 0 35px rgba(0, 242, 254, 0.7) !important; color: #000000 !important; }
        
        div.stButton > button[kind="secondary"] { border-radius: 30px !important; background-color: rgba(255,255,255,0.02) !important; border: 1px solid rgba(255,255,255,0.08) !important; color: #cbd5e1 !important; padding: 0.5rem 1.5rem !important; font-weight: 600 !important; box-shadow: none !important; margin-bottom: 2rem !important; }
        div.stButton > button[kind="secondary"] p { color: #cbd5e1 !important; font-weight: 600 !important; }
        div.stButton > button[kind="secondary"]:hover { border-color: #3b82f6 !important; background-color: rgba(59, 130, 246, 0.1) !important; color: #38bdf8 !important; }
        
        /* Change color of input labels to match subtitle */
        label[data-testid="stWidgetLabel"] p { color: #94a3b8 !important; }
        div[data-testid="stRadio"] div[role="radiogroup"] label p { color: #94a3b8 !important; }
        
        .footer { width: 100%; text-align: center; padding: 2rem 0; color: #64748b; font-size: 0.85rem; border-top: 1px solid rgba(255,255,255,0.05); background-color: #0b1120; margin-top: 150px; display: block; }
        .streamlit-expanderHeader { font-size: 1.1rem !important; font-weight: 600 !important; color: #f8fafc !important; }
        </style>
    """, unsafe_allow_html=True)

def render_navbar():
    st.markdown("""
        <div class="navbar">
            <div class="nav-logo">⚕️ Med Fact Check</div>
            <div style="font-size: 0.9rem; color: #94a3b8; font-weight:600;">MSc Unina • Big Data Engineering</div>
        </div>
        <div style="margin-top: 8rem;"></div>
    """, unsafe_allow_html=True)

def render_footer():
    st.markdown("""
    <div class="footer">
        MedFactCheck Project • Big Data Engineering MSc Unina • Powered by RAG & LLMs
    </div>
    """, unsafe_allow_html=True)

def render_claim_checklist(sentences, context=""):
    """Renderizza un selettore interattivo per selezionare UN SOLO claim."""
    if not sentences:
        return []
    
    st.markdown("### 📋 Select a Claim to Verify")
    
    if context:
        st.info(f"📄 **Context:** {context}")
        
    st.markdown("---")
    options = [f"Claim #{i+1}: {s[:100]}..." if len(s) > 100 else f"Claim #{i+1}: {s}" for i, s in enumerate(sentences)]
    
    selected_idx = st.radio(
        "Choose one sentence from the extracted text:",
        options=range(len(sentences)),
        format_func=lambda i: options[i],
        key=f"claim_radio"
    )
    
    if selected_idx is not None:
        selected_sentence = sentences[selected_idx]
        st.markdown(f"""
        <div style="background: rgba(16, 185, 129, 0.1); border-left: 4px solid #10b981; padding: 15px; border-radius: 8px; margin: 15px 0;">
            <span style="color: #34d399; font-weight: 600;">✓ Selected Claim #{selected_idx+1}</span><br><br>
            <span style="color: #f8fafc; font-size: 1.05rem; line-height: 1.5;">{selected_sentence}</span>
        </div>
        """, unsafe_allow_html=True)
        return [selected_sentence]
    return []

def inject_floating_buttons_css():
    st.markdown("""
    <style>
    .element-container:has(.marker-dl-btn) + .element-container,
    .element-container:has(.marker-new-btn) + .element-container {
        position: fixed !important;
        bottom: 40px !important;
        z-index: 2147483647 !important;
        pointer-events: auto !important;
        width: auto !important;
        height: 48px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .element-container:has(.marker-dl-btn) + .element-container { right: 250px !important; }
    .element-container:has(.marker-new-btn) + .element-container { right: 40px !important; }
    .element-container:has(.marker-dl-btn) + .element-container a { display: flex !important; align-items: center !important; height: 100% !important; text-decoration: none !important; }
    
    .element-container:has(.marker-dl-btn) + .element-container button, 
    .element-container:has(.marker-new-btn) + .element-container button {
        height: 48px !important; margin: 0 !important; padding: 0 28px !important; font-size: 15px !important; border-radius: 50px !important; border: none !important; font-weight: 800 !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; box-shadow: 0 4px 15px rgba(0,0,0,0.5) !important; pointer-events: auto !important; cursor: pointer !important; transition: all 0.3s ease !important; display: flex !important; align-items: center !important; justify-content: center !important; box-sizing: border-box !important; line-height: 1 !important;
    }
    .element-container:has(.marker-dl-btn) + .element-container button:hover, 
    .element-container:has(.marker-new-btn) + .element-container button:hover { transform: scale(1.04) translateY(-2px) !important; box-shadow: 0 6px 20px rgba(0,0,0,0.6) !important; }
    .element-container:has(.marker-dl-btn) + .element-container button { background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important; box-shadow: 0 0 20px rgba(16, 185, 129, 0.4) !important; }
    .element-container:has(.marker-dl-btn) + .element-container button:hover { box-shadow: 0 0 30px rgba(16, 185, 129, 0.7) !important; }
    .element-container:has(.marker-new-btn) + .element-container button { background: linear-gradient(135deg, #38bdf8 0%, #0284c7 100%) !important; box-shadow: 0 0 20px rgba(56, 189, 248, 0.4) !important; }
    .element-container:has(.marker-new-btn) + .element-container button:hover { box-shadow: 0 0 30px rgba(56, 189, 248, 0.7) !important; }
    .element-container:has(.marker-dl-btn) + .element-container button p, 
    .element-container:has(.marker-new-btn) + .element-container button p { color: white !important; font-weight: 800 !important; font-size: 15px !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; margin: 0 !important; padding: 0 !important; line-height: 1 !important; }
    </style>
    """, unsafe_allow_html=True)

def update_interactive_loading(placeholder, claim, step=1, subclaims=None, evaluations=None, verified_count=0, total_to_verify=1, final_verdict=None):
    all_modals_html = ""
    if subclaims is None: subclaims = []
    if evaluations is None: evaluations = []
    
    central_title = "Processing..."
    central_subtitle = "Please wait..."
    anim_color = "#38bdf8"
    
    if final_verdict:
        raw_label = final_verdict.get("label", "not_enough_information")
        if raw_label == "supported": verdict = "SUPPORTED"
        elif raw_label == "refuted": verdict = "REFUTED"
        else: verdict = "NEI"
        
        raw_conf = final_verdict.get("confidence", 0.0)
        conf = int(raw_conf * 100) if raw_conf <= 1.0 else int(raw_conf)
            
        if verdict == "SUPPORTED": anim_color = "#10b981"
        elif verdict == "REFUTED": anim_color = "#ef4444"
        else: anim_color = "#f59e0b"
        
        central_title = "Fact-Checking Completed!"
        central_subtitle = "Final results are ready for analysis."
    else:
        if step == 1:
            central_title = "Claim Analysis & Decomposition"
            central_subtitle = "Warming up decomposition agents..."
            anim_color = "#38bdf8"
        elif step == 2:
            central_title = "Medical Evidence Retrieval"
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
    
    modal_css = "<style>.modal-wrapper{position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.85);z-index:10000000;display:none;align-items:center;justify-content:center;backdrop-filter:blur(8px);}.modal-toggle:checked+.modal-wrapper{display:flex!important;}.modal-card{background:#0f172a;border:1px solid #38bdf8;border-radius:16px;padding:2rem;max-width:700px;width:90%;max-height:85vh;overflow-y:auto;box-shadow:0 0 40px rgba(56,189,248,0.4);animation:zoomIn 0.3s cubic-bezier(0.175,0.885,0.32,1.275) forwards;}@keyframes zoomIn{0%{transform:scale(0.5);opacity:0;}100%{transform:scale(1);opacity:1;}}.close-btn{float:right;cursor:pointer;color:#f8fafc;background:#ef4444;width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;transition:0.2s;font-size:14px;}.close-btn:hover{background:#dc2626;transform:scale(1.1);}.eval-highlight-support{background-color:rgba(16,185,129,0.25);color:#10b981;padding:2px 4px;border-radius:4px;font-weight:bold;}.eval-highlight-refute{background-color:rgba(239,68,68,0.25);color:#ef4444;padding:2px 4px;border-radius:4px;font-weight:bold;}</style>"
    
    def get_cards_html(target_phase):
        nonlocal all_modals_html
        if not subclaims: 
            if final_verdict:
                return "<div style='color:#ef4444; margin-top:20px; font-weight:bold; font-size: 1.1rem;'>⚠️ Pipeline Skipped: Unverifiable Claim</div>"
            return "<div style='color:#94a3b8; margin-top:20px; font-style:italic;'>⏳ Waiting for pipeline...</div>"
            
        hint_html = ""
        if target_phase == 3 and len(evaluations) == len(subclaims) and len(subclaims) > 0:
            if len(subclaims) == 1:
                tip_text = "Click on the evaluated subclaim card below to view the detailed clinical reasoning and supporting evidence."
            else:
                tip_text = "Click on any of the evaluated subclaim cards below to view the detailed clinical reasoning and supporting evidence."
            hint_html = f"<div style='background:rgba(167, 139, 250, 0.15); border:1px solid rgba(167, 139, 250, 0.4); color:#e2e8f0; padding:10px 15px; border-radius:8px; margin-top:10px; font-size:0.95rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width:800px; margin-left:auto; margin-right:auto;'>💡 <strong>Tip:</strong> {tip_text}</div>"
            
        html = f"{hint_html}<div style='display:flex; flex-wrap:wrap; gap:10px; justify-content:center; margin-top:20px; width:100%; max-width:900px;'>"
        for i, sc in enumerate(subclaims):
            ev_data = next((e for e in evaluations if e.get("subclaim") == sc), None)
            sub_id = f"sub_{i+1:02d}"
            queries = getattr(st.session_state, "queries_by_source", {}).get(sub_id, {})
            stats = getattr(st.session_state, "download_stats", {}).get(sub_id, {})
            stats_html = ""
            if queries or stats:
                stats_html = "<div style='margin-top: 15px; text-align: left; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1);'><strong style='color:#a78bfa; font-size:0.9rem;'>📊 Retrieval Statistics:</strong>"
                all_sources = set(list(queries.keys()) + list(stats.keys()))
                for src in sorted(all_sources):
                    src_queries = queries.get(src, [])
                    src_stats = stats.get(src, {})
                    docs_found = src_stats.get('documents_found', 0)
                    chunks_ext = src_stats.get('chunks_extracted', 0)
                    stats_html += f"<div style='background:rgba(255,255,255,0.02); padding:8px; margin-top:8px; border-radius:6px; border-left:3px solid #818cf8;'>"
                    stats_html += f"<div style='color:#38bdf8; font-weight:bold; margin-bottom:3px; text-transform:capitalize; font-size:0.8rem;'>{src.replace('_', ' ')}</div>"
                    if src_queries:
                        q_formatted = ", ".join(src_queries)
                        stats_html += f"<div style='color:#94a3b8; font-size:0.75rem; margin-bottom:3px;'>Queries: <em style='color:#e2e8f0;'>{q_formatted}</em></div>"
                    stats_html += f"<div style='color:#94a3b8; font-size:0.75rem;'>Found Documents: <strong style='color:#f8fafc;'>{docs_found}</strong> | Extracted Passages: <strong style='color:#f8fafc;'>{chunks_ext}</strong></div></div>"
                stats_html += "</div>"

            def get_eval_status(ev):
                if not ev: return "✅ Evaluated"
                lbl_up = ev.get('label', 'NEI').upper()
                display_lbl = "NOT ENOUGH INFORMATION" if lbl_up == "NEI" else lbl_up
                c = "#10b981" if lbl_up == "SUPPORTED" else ("#ef4444" if lbl_up == "REFUTED" else "#f59e0b")
                raw_conf = ev.get('confidence', 0.0)
                conf = int(raw_conf * 100) if raw_conf <= 1.0 else int(raw_conf) if isinstance(raw_conf, (int, float)) else 0
                return f"<div style='margin-bottom:5px; color:#38bdf8;'>✅ Evaluation Completed</div><div style='display:inline-block; padding:4px 10px; border-radius:6px; background:rgba(255,255,255,0.05); border:1px solid {c}; color:{c}; font-weight:800; font-size:0.85rem; letter-spacing:1px;'>{display_lbl} &bull; {conf}%</div>"

            if target_phase == 2:
                if step < 2: status = "⏳ Pending..."
                elif step == 2:
                    source_selections = getattr(st.session_state, "source_selections", {})
                    downloader_status = getattr(st.session_state, "downloader_status", {})
                    retriever_status = getattr(st.session_state, "retriever_status", {})
                    if sub_id in retriever_status: status = f"✅ Selected {retriever_status[sub_id]} final chunks"
                    elif sub_id in downloader_status: status = f"⏳ Ingesting {downloader_status[sub_id]} chunks..."
                    elif sub_id in source_selections:
                        srcs = ", ".join(source_selections[sub_id])
                        status = f"🔍 Querying: {srcs}..."
                    else: status = "⏳ Selecting Sources..."
                else: status = "✅ Documents Retrieved"
                has_modal = False
            elif target_phase == 3:
                if step < 3: status = "⏳ Pending..."
                elif step == 3 and ev_data: status = get_eval_status(ev_data)
                elif step == 3 and i == verified_count: status = "🔍 Evaluating..."
                elif step == 3: status = "⏳ Waiting in queue..."
                else: status = get_eval_status(ev_data) if ev_data else "✅ Evaluated"
                has_modal = bool(ev_data)
            else:
                status = get_eval_status(ev_data) if ev_data else "✅ Completed"
                has_modal = bool(ev_data)
                
            if has_modal:
                card_html = f"<label for='modal-p{target_phase}-{i}' style='display:block; cursor:pointer; position:relative; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); padding:12px 18px; border-radius:12px; width:calc(50% - 5px); min-width:300px; text-align:left; transition: transform 0.2s, border-color 0.2s;'><span style='position:absolute; right:10px; bottom:10px; font-size:4rem; opacity:0.04; pointer-events:none; z-index:0;'>🔍</span><span style='display:block; position:relative; z-index:2; font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px; pointer-events:none;'>SUBCLAIM {i+1}</span><span style='display:block; position:relative; z-index:2; font-size:0.95rem; color:#f8fafc; margin-bottom:8px; line-height:1.4; pointer-events:none;'>\"{sc}\"</span><span style='display:block; position:relative; z-index:2; font-size:0.8rem; font-weight:600; color:#38bdf8; pointer-events:none;'>{status}</span>"
            else:
                card_html = f"<div style='background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); padding:12px 18px; border-radius:12px; width:calc(50% - 5px); min-width:300px; text-align:left;'><div style='font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700; margin-bottom:5px;'>SUBCLAIM {i+1}</div><div style='font-size:0.95rem; color:#f8fafc; margin-bottom:8px; line-height:1.4;'>\"{sc}\"</div><div style='font-size:0.8rem; font-weight:600; color:#38bdf8;'>{status}</div>"
                if target_phase == 2 and step >= 2:
                    card_html += stats_html

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
                    c_url = c_meta.get("url")
                    if isinstance(c_url, str) and c_url.startswith("http"): c_source_html = f"<a href='{c_url}' target='_blank' style='color:#38bdf8; text-decoration:underline; pointer-events:auto;'>{c_source}</a>"
                    elif isinstance(c_source, str) and c_source.startswith("http"): c_source_html = f"<a href='{c_source}' target='_blank' style='color:#38bdf8; text-decoration:underline; pointer-events:auto;'>{c_source}</a>"
                    else: c_source_html = f"<strong style='color:#38bdf8;'>{c_source}</strong>"
                    
                    hl_text = highlight_quotes(c_text, supp, ref)
                    chunks_html += f"<div style='background:#1e293b; padding:10px; margin:8px 0; border-left:4px solid #38bdf8; border-radius:6px; font-size:0.85rem; text-align:left;'>{c_source_html}<br><em style='color:#cbd5e1;'>{hl_text}</em></div>"
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
        if raw_label == "supported": verdict = "SUPPORTED"
        elif raw_label == "refuted": verdict = "REFUTED"
        else: verdict = "NOT ENOUGH INFORMATION"
        
        raw_conf = final_verdict.get("confidence", 0.0)
        conf = int(raw_conf * 100) if raw_conf <= 1.0 else int(raw_conf)
            
        just = final_verdict.get("justification", "")
        if verdict == "SUPPORTED": v_color, v_icon = "#10b981", "✅"
        elif verdict == "REFUTED": v_color, v_icon = "#ef4444", "❌"
        else: v_color, v_icon = "#f59e0b", "⚠️"

        safe_claim = claim.replace('"', '&quot;')
        exec_time = getattr(st.session_state, 'execution_time', 0)
        agg_analysis = final_verdict.get("aggregation_analysis", "No detailed analysis provided.")
        sub_breakdown = final_verdict.get("subclaim_breakdown", [])
        
        sc_html = ""
        if sub_breakdown:
            sc_html += "<h3 style='color:#38bdf8; margin-top:30px; font-size:1.2rem; text-align:left; max-width:1000px; margin-left:auto; margin-right:auto;'>Subclaim Breakdown</h3>"
            sc_html += f"<div style='background:rgba(255,255,255,0.03); border:1px solid rgba(167,139,250,0.3); border-left:4px solid #a78bfa; border-radius:12px; padding:20px; margin:15px auto 25px auto; max-width:1000px; text-align:left;'><h4 style='color:#a78bfa; margin-top:0; font-size:1.05rem; margin-bottom:8px; text-transform:uppercase; letter-spacing:1px;'>⚙️ Aggregation Analysis</h4><div style='color:#f8fafc; font-size:0.95rem; line-height:1.5;'>{agg_analysis}</div></div>"
            sc_html += "<div style='display:flex; flex-direction:column; gap:10px; width:100%; max-width:1000px; margin:0 auto; text-align:left;'>"
            for sc_res in sub_breakdown:
                sc_text = sc_res.get("subclaim", "")
                sc_lbl = str(sc_res.get("label", "NEI")).upper()
                if sc_lbl == "NEI": sc_lbl = "NOT ENOUGH INFORMATION"
                sc_conf = sc_res.get("confidence", 0)
                sc_conf = int(sc_conf * 100) if sc_conf <= 1.0 else int(sc_conf)
                
                sc_c = "#10b981" if sc_lbl == "SUPPORTED" else ("#ef4444" if sc_lbl == "REFUTED" else "#f59e0b")
                    
                sc_just = sc_res.get("justification", "No justification provided.")
                sc_html += f"<div style='background:rgba(255,255,255,0.03); border-left:4px solid {sc_c}; border-radius:8px; padding:15px; margin-bottom:10px;'>"
                sc_html += f"<div style='display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;'><div style='font-size:1rem; color:#f8fafc; font-weight:600;'>\"{sc_text}\"</div><div style='background:rgba(255,255,255,0.05); border:1px solid {sc_c}; color:{sc_c}; padding:3px 8px; border-radius:4px; font-size:0.8rem; font-weight:bold; white-space:nowrap; margin-left:15px;'>{sc_lbl} &bull; {sc_conf}%</div></div>"
                sc_html += f"<div style='font-size:0.9rem; color:#cbd5e1; line-height:1.5;'>{sc_just}</div></div>"
            sc_html += "</div>"

        slide4_content = f"""
          <div class="slide-header">Final Fact-Checking Result</div>
          <div style="text-align:center; color:#94a3b8; font-size:0.95rem; margin-bottom:15px;">
             ⏱️ <strong>Execution Time:</strong> {exec_time:.1f} seconds
          </div>
          <div style="background:#0f172a; border:2px solid #38bdf8; border-radius:12px; padding:20px 30px; color:#f8fafc; font-size:1.1rem; text-align:center; font-style:italic; max-width:800px; box-shadow: 0 0 20px rgba(56,189,248,0.2); margin:0 auto 20px auto;">
              "{safe_claim}"
          </div>
          <div style="display:flex; width:100%; max-width:1000px; gap:20px; margin:20px auto;">
            <div style="flex:1; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); border-radius:16px; padding:25px; display:flex; flex-direction:column; align-items:center; text-align:center; box-shadow: 0 0 30px rgba(0,0,0,0.3);">
               <div style="font-size:3rem; margin-bottom:10px;">{v_icon}</div>
               <div style="color:{v_color}; font-size:1.8rem; font-weight:900; letter-spacing:2px; margin-bottom:20px;">{verdict}</div>
               <div style="position:relative; width:120px; height:120px; border-radius:50%; background:conic-gradient({v_color} {conf}%, #1e293b 0); display:flex; align-items:center; justify-content:center; box-shadow:0 0 20px {v_color}40;">
                   <div style="position:absolute; width:100px; height:100px; background:#0f172a; border-radius:50%; display:flex; flex-direction:column; align-items:center; justify-content:center;">
                       <span style="font-size:2rem; font-weight:800; color:#f8fafc;">{conf}%</span>
                       <span style="font-size:0.7rem; color:#94a3b8; text-transform:uppercase;">Confidence</span>
                   </div>
               </div>
            </div>
            <div style="flex:2; display:flex; flex-direction:column; justify-content:center;">
                <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); border-radius:16px; padding:20px; text-align:left; box-shadow: 0 0 30px rgba(0,0,0,0.3); height:100%;">
                    <h3 style="color:#a78bfa; margin-top:0; font-size:1.2rem; margin-bottom:12px;">Medical Justification</h3>
                    <div style="color:#f8fafc; font-size:1.05rem; line-height:1.6; overflow-y:auto; max-height:220px; padding-right:10px;">{just}</div>
                </div>
            </div>
          </div>
          {sc_html}
          <div style="height: 150px; width: 100%; flex-shrink: 0;"></div>
        """

    if not final_verdict:
        slide4_content = f"""
          <div class="slide-header">Final Consensus & Aggregation</div>
          <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; margin-top: 40px;">
            <div style="font-size: 4rem; margin-bottom: 20px;">⚖️</div>
            <div style="color: #10b981; font-size: 1.5rem; font-weight: 700; text-align: center; margin-bottom: 15px;">Drafting Final Verdict</div>
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
        if not subclaims and final_verdict:
            slide1_tree = "<div style='color:#ef4444; margin-top:20px; font-weight:bold; font-size: 1.1rem;'>⚠️ The claim could not be decomposed into verifiable medical statements. Proceed to Phase 4.</div>"
        else:
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
    
    progress_percent = int((step - 1) * 33.33)
    
    css_content = f"""
    <style>
    .cyber-overlay {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(15, 23, 42, 0.97); backdrop-filter: blur(20px); z-index: 9999999; overflow: hidden; pointer-events: auto !important; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding-top: 60px; }}
    .carousel-viewport {{ width: 100vw; height: calc(100vh - 350px); position: relative; overflow: hidden; margin-top: 30px; }}
    .slider-container {{ display: flex; width: 400vw; height: 100%; transition: transform 0.5s cubic-bezier(0.25, 0.8, 0.25, 1); }}
    #slide-1:checked ~ .carousel-viewport .slider-container {{ transform: translateX(0); }}
    #slide-2:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-100vw); }}
    #slide-3:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-200vw); }}
    #slide-4:checked ~ .carousel-viewport .slider-container {{ transform: translateX(-300vw); }}
    .slide {{ width: 100vw; height: 100%; position: relative; padding: 0 80px; box-sizing: border-box; }}
    .slide-content {{ width: 100%; height: 100%; overflow-y: auto; display: flex; flex-direction: column; align-items: center; padding: 0 0 50px 0; text-align: center; }}
    .global-arrow {{ position: absolute; top: 50%; transform: translateY(-50%); background: rgba(56,189,248,0.1); color: #38bdf8; width: 50px; height: 50px; border-radius: 50%; display: none; align-items: center; justify-content: center; font-size: 24px; cursor: pointer; transition: 0.3s; border: 1px solid rgba(56,189,248,0.3); z-index: 10000; }}
    .global-arrow:hover {{ background: rgba(56,189,248,0.4); color: #fff; transform: translateY(-50%) scale(1.1); }}
    .global-arrow.disabled {{ opacity: 0.2 !important; cursor: not-allowed !important; pointer-events: none !important; background: transparent !important; border-color: rgba(255,255,255,0.1) !important; color: #64748b !important; }}
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
    .step {{ display: flex; flex-direction: column; align-items: center; width: 25%; position: relative; cursor: pointer; }}
    .step.disabled {{ cursor: not-allowed !important; pointer-events: none !important; opacity: 0.5 !important; }}
    .step:hover:not(.disabled) {{ opacity: 0.8; }}
    .step-dot {{ width: 30px; height: 30px; border-radius: 50%; background: #0f172a; border: 2px solid rgba(255, 255, 255, 0.2); display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: bold; color: #64748b; transition: all 0.4s; margin-bottom: 8px; z-index: 2; pointer-events: none; }}
    .step.active .step-dot {{ border-color: {anim_color}; color: #f8fafc; background: #0f172a; }}
    .step-label {{ font-size: 0.75rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 1px; text-align: center; transition: color 0.3s; margin-top: 5px; pointer-events: none; }}
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
    """
    
    html_content = f"""{modal_css}
{css_content}
<div class="cyber-overlay">
    <input type="radio" name="slider" id="slide-1" {'checked' if step == 1 else ''} style="display:none;">
    <input type="radio" name="slider" id="slide-2" {'checked' if step == 2 else ''} style="display:none;">
    <input type="radio" name="slider" id="slide-3" {'checked' if step == 3 else ''} style="display:none;">
    <input type="radio" name="slider" id="slide-4" {'checked' if step == 4 else ''} style="display:none;">

  <div class="pulse-container"><div class="pulse-ring"></div><div class="pulse-ring"></div><div class="pulse-ring"></div><div class="pulse-core"></div></div>
  <div class="stage-title">{central_title}</div>
  <div class="stage-subtitle">{central_subtitle}</div>
  <div class="stepper-container">
      <div class="stepper-line"><div class="stepper-progress" style="width: {progress_percent}%;"></div></div>
      <div class="stepper-steps">
          <label for="slide-1" class="step step-ui-1 {'active' if step >= 1 else ''}"><div class="step-dot">1</div><div class="step-label">Decomposition</div></label>
          <label for="slide-2" class="step step-ui-2 {'active' if step >= 2 else ''} {'disabled' if step < 2 else ''}"><div class="step-dot">2</div><div class="step-label">Retrieval</div></label>
          <label for="slide-3" class="step step-ui-3 {'active' if step >= 3 else ''} {'disabled' if step < 3 else ''}"><div class="step-dot">3</div><div class="step-label">Evaluation</div></label>
          <label for="slide-4" class="step step-ui-4 {'active' if step >= 4 else ''} {'disabled' if step < 4 else ''}"><div class="step-dot">4</div><div class="step-label">Aggregation</div></label>
      </div>
  </div>

  <div class="carousel-viewport">
    <div class="slider-container">
      <div class="slide"><div class="slide-content">{slide1_content}</div></div>
      <div class="slide"><div class="slide-content"><div class="slide-header">Evidence Retrieval</div>{sc_html_p2}</div></div>
      <div class="slide"><div class="slide-content"><div class="slide-header">Clinical Reasoning Agent Results</div>{sc_html_p3}</div></div>
      <div class="slide"><div class="slide-content">{slide4_content}</div></div>
    </div>
    <label for="slide-1" class="global-arrow left-arrow show-2">&#10094;</label>
    <label for="slide-2" class="global-arrow left-arrow show-3">&#10094;</label>
    <label for="slide-3" class="global-arrow left-arrow show-4">&#10094;</label>
    
    <label for="slide-2" class="global-arrow right-arrow show-1 {'disabled' if step < 2 else ''}">&#10095;</label>
    <label for="slide-3" class="global-arrow right-arrow show-2 {'disabled' if step < 3 else ''}">&#10095;</label>
    <label for="slide-4" class="global-arrow right-arrow show-3 {'disabled' if step < 4 else ''}">&#10095;</label>
  </div>
  {all_modals_html}
</div>
"""
    placeholder.html(html_content)