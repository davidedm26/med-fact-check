import streamlit as st

st.set_page_config(
    page_title="Med Fact Check",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a modern, beautiful UI
st.markdown("""
    <style>
    /* Hide the default sidebar navigation */
    [data-testid="stSidebarNav"] {
        display: none;
    }
    
    .main-title {
        font-size: 3.5rem;
        font-weight: 800;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 0px;
        font-family: 'Inter', sans-serif;
    }
    .subtitle {
        font-size: 1.2rem;
        font-weight: 400;
        color: #64748B;
        text-align: center;
        margin-top: 10px;
        margin-bottom: 40px;
        font-family: 'Inter', sans-serif;
    }
    

    
    /* Sidebar styling */
    .sidebar-title {
        font-size: 1.2rem;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 10px;
    }
    .sidebar-step {
        margin-bottom: 15px;
    }
    .sidebar-step-title {
        font-weight: bold;
        color: #334155;
        font-size: 1rem;
    }
    .sidebar-step-desc {
        color: #64748B;
        font-size: 0.9rem;
    }
    .sidebar-disclaimer {
        background-color: #eff6ff;
        border-left: 4px solid #3b82f6;
        padding: 10px;
        border-radius: 4px;
        font-size: 0.85rem;
        color: #1e3a8a;
        margin-top: 30px;
    }
    
    .footer {
        text-align: center;
        padding: 20px;
        color: #64748B;
        font-size: 0.85rem;
        border-top: 1px solid #e2e8f0;
        margin-top: 100px;
    }
    
    </style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown('<div class="sidebar-title">How does it work?</div>', unsafe_allow_html=True)
    st.markdown('<p style="color: #64748B; font-size: 0.9rem; margin-bottom: 20px;">Welcome to Med Fact Check. This tool assists you in verifying the scientific validity of medical claims.</p>', unsafe_allow_html=True)
    
    st.markdown("""
        <div class="sidebar-step">
            <div class="sidebar-step-title">1. Input Claim</div>
            <div class="sidebar-step-desc">Provide a medical claim via text, file, or URL.</div>
        </div>
        <div class="sidebar-step">
            <div class="sidebar-step-title">2. AI Analysis</div>
            <div class="sidebar-step-desc">The system cross-references the claim with verified medical literature.</div>
        </div>
        <div class="sidebar-step">
            <div class="sidebar-step-title">3. Get Report</div>
            <div class="sidebar-step-desc">Receive a detailed breakdown of subclaims and a downloadable PDF report.</div>
        </div>
        
        <div class="sidebar-disclaimer">
            💡 <strong>Disclaimer:</strong> This tool provides decision support based on automated analysis and does not replace professional medical advice.
        </div>
    """, unsafe_allow_html=True)


# Main Header
st.markdown('<div class="main-title">⚕️ Med Fact Check</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Your intelligent consultant for verifying medical claims.<br>Navigate complex information with confidence and precision.</div>', unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)

# Giant Emoji Link in the Center
st.markdown("""
    <style>
    .emoji-link {
        font-size: 10rem;
        text-align: center;
        display: inline-block;
        transition: transform 0.3s ease;
        text-decoration: none;
        cursor: pointer;
        line-height: 1;
        margin-bottom: 10px;
    }
    .emoji-link:hover {
        transform: scale(1.15);
    }
    .emoji-container {
        text-align: center;
        margin: 20px auto;
        max-width: 600px;
    }
    
    .footer {
        text-align: center;
        padding: 20px;
        color: #64748B;
        font-size: 0.85rem;
        border-top: 1px solid #e2e8f0;
        margin-top: 100px;
    }
    
    </style>
    
    <div class="emoji-container">
        <a href="Fact_Check" target="_self" style="text-decoration: none;">
            <div class="emoji-link">🩺</div>
        </a>
        <h2 style="color: #1E3A8A; font-weight: 800; margin-top: 10px; margin-bottom: 10px;">Click to Start Fact Check</h2>
        <p style="color: #64748B;">The analysis engine is ready to process your medical documentation against scientific literature.</p>
    </div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="footer">
    MedFactCheck Project • Big Data Engineering MSc Unina • Powered by RAG & LLMs
</div>
""", unsafe_allow_html=True)
