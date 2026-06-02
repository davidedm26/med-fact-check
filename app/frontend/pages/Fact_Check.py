import streamlit as st
import requests
import json
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="Fact Check | Med Fact Check",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
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
    div.stButton > button[kind="primary"] {
        background-color: #2563EB;
        color: white;
        font-weight: 600;
        border-radius: 8px;
        transition: background-color 0.3s ease;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #1D4ED8;
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
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Submit a Claim</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Select how you want to input a medical claim for verification.</div>', unsafe_allow_html=True)

input_method = st.radio(
    "Choose Input Method:",
    ["✍️ Text Input", "📄 Upload TXT", "🔗 Provide URL"],
    horizontal=True
)

claim = ""

with st.container(border=True):
    if input_method == "✍️ Text Input":
        claim = st.text_area("Medical Claim:", height=150, placeholder="E.g., Taking a daily vitamin D supplement helps prevent osteoporosis...")
        
    elif input_method == "📄 Upload TXT":
        uploaded_file = st.file_uploader("Choose a .txt file", type="txt")
        if uploaded_file is not None:
            claim = uploaded_file.getvalue().decode("utf-8")
            st.text_area("File Content (Preview):", value=claim, height=150, disabled=True)
            
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
                            st.text_area("Extracted Content (Preview):", value=preview, height=150, disabled=True)
                        else:
                            st.error(f"Failed to fetch URL. Status code: {res.status_code}")
                except Exception as e:
                    st.error(f"Error fetching URL: {str(e)}")

if st.button("Verify Claim", type="primary"):
    if not claim.strip():
        st.warning("Please provide a valid claim or document before verifying.")
    else:
        # Create a placeholder for the final verdict
        final_verdict_placeholder = st.empty()
        
        with st.status("🧠 Decomposing claim...", expanded=True) as status:
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
                                        status.update(label="❌ Pipeline Error", state="error")
                                        st.error(step_data["error"])
                                        break
                                        
                                    if "decompose" in step_data:
                                        # Decompose finished, next step is retrieval
                                        status.update(label="🔎 Retrieving evidence and evaluating...")
                                        subclaims = step_data["decompose"].get("verifiable_subclaims", [])
                                        st.write(f"**Found {len(subclaims)} verifiable subclaims:**")
                                        for sc in subclaims:
                                            # Subclaim structure can vary depending on prompt output
                                            sc_text = sc if isinstance(sc, str) else sc.get("claim", str(sc))
                                            st.write(f"- 🧩 {sc_text}")
                                            
                                    elif "verify_subclaim" in step_data:
                                        eval_results = step_data["verify_subclaim"].get("evaluation_results", [])
                                            
                                        # Render an expander for each subclaim processed in this step
                                        for er in eval_results:
                                            sc_text = er.get("subclaim", "Unknown Subclaim")
                                            lbl = er.get("label", "nei").upper()
                                            conf = er.get("confidence", 0.0)
                                            just = er.get("justification", "No justification provided.")
                                            
                                            # Use emoji based on label
                                            icon = "✅" if lbl == "SUPPORTED" else "❌" if lbl == "REFUTED" else "❓"
                                            
                                            with st.expander(f"{icon} Analysis: {sc_text[:50]}... ({lbl})"):
                                                st.markdown(f"**Subclaim:** {sc_text}")
                                                st.markdown(f"**Verdict:** {lbl} (Confidence: {conf:.2f})")
                                                st.markdown(f"**Justification:** {just}")
                                                
                                                evidence = er.get("retrieved_chunks", [])
                                                if evidence:
                                                    st.markdown("**Evidence Chunks:**")
                                                    for chunk in evidence:
                                                        if isinstance(chunk, dict):
                                                            text = chunk.get("text", "")
                                                            meta = chunk.get("metadata", {})
                                                            url = meta.get("url", "")
                                                            source_title = meta.get("title", meta.get("id", "Unknown Source"))
                                                            if url:
                                                                st.markdown(f"- **[{source_title}]({url})**: _{text}_")
                                                            else:
                                                                st.markdown(f"- **{source_title}**: _{text}_")
                                                        else:
                                                            st.markdown(f"- _{chunk}_")
                                                        
                                    elif "aggregate" in step_data:
                                        status.update(label="✅ Pipeline complete!", state="complete")
                                        
                                        verdict = step_data["aggregate"].get("final_verdict", {})
                                        label = verdict.get("label", "nei").lower()
                                        confidence = verdict.get("confidence", 0.0)
                                        css_class = label if label in ["supported", "refuted"] else "nei"
                                        
                                        # Render outside the status block
                                        final_verdict_placeholder.markdown(f"""
                                            <div class="verdict-box {css_class}">
                                                Final Verdict: {label.upper()} <br>
                                                <span style="font-size: 1rem; font-weight: normal;">Confidence: {confidence:.2f}</span>
                                            </div>
                                        """, unsafe_allow_html=True)
                                        
                                except json.JSONDecodeError:
                                    pass # Ignore malformed chunks
                else:
                    status.update(label="❌ Connection Error", state="error")
                    st.error(f"Error from server: {response.text}")
            except Exception as e:
                status.update(label="❌ Fatal Error", state="error")
                st.error(f"Failed to connect to the backend API: {str(e)}")
