import streamlit as st

st.set_page_config(
    page_title="Med Fact Check",
    page_icon="🏥",
    layout="wide"
)

# Custom CSS for a modern, beautiful UI
st.markdown("""
    <style>
    .main-title {
        font-size: 3.5rem;
        font-weight: 800;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 0px;
        font-family: 'Inter', sans-serif;
    }
    .subtitle {
        font-size: 1.5rem;
        font-weight: 400;
        color: #64748B;
        text-align: center;
        margin-top: 10px;
        margin-bottom: 40px;
        font-family: 'Inter', sans-serif;
    }
    .card {
        background-color: white;
        border-radius: 12px;
        padding: 30px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        margin-bottom: 20px;
        border-top: 4px solid #3B82F6;
    }
    .feature-title {
        color: #0F172A;
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 10px;
    }
    .feature-text {
        color: #475569;
        font-size: 1rem;
        line-height: 1.6;
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
    </style>
""", unsafe_allow_html=True)

# Main Header
st.markdown('<div class="main-title">Med Fact Check</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Empowering Healthcare with AI-Driven Truth Discovery</div>', unsafe_allow_html=True)

# Engaging Description wrapped in a card
st.markdown("""
    <div class="card">
        <div class="feature-title">Why Med Fact Check?</div>
        <div class="feature-text">
            In the era of rapid information sharing, distinguishing medically sound claims from misinformation is critical. 
            <strong>Med Fact Check</strong> leverages advanced Natural Language Processing to dissect complex medical texts, 
            extract individual claims, and verify them against established scientific literature.
        </div>
        <br>
        <div class="feature-text">
            Whether you are a healthcare professional, a researcher, or a curious individual, our tool provides 
            transparent, evidence-backed evaluations to help you make informed decisions.
        </div>
    </div>
""", unsafe_allow_html=True)

# Features Section using Streamlit columns
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div style="text-align: center;">
        <h1 style="font-size: 3rem; margin-bottom: 0;">🔍</h1>
        <h3 style="color: #1E3A8A; font-size: 1.2rem;">Deep Analysis</h3>
        <p style="color: #64748B; font-size: 0.95rem;">Extracts atomic sub-claims from complex documents for precise evaluation.</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="text-align: center;">
        <h1 style="font-size: 3rem; margin-bottom: 0;">📚</h1>
        <h3 style="color: #1E3A8A; font-size: 1.2rem;">Evidence Backed</h3>
        <p style="color: #64748B; font-size: 0.95rem;">Retrieves and highlights relevant scientific evidence to support or refute claims.</p>
    </div>
    """, unsafe_allow_html=True)
    
with col3:
    st.markdown("""
    <div style="text-align: center;">
        <h1 style="font-size: 3rem; margin-bottom: 0;">📊</h1>
        <h3 style="color: #1E3A8A; font-size: 1.2rem;">Clear Insights</h3>
        <p style="color: #64748B; font-size: 0.95rem;">Visualizes results with intuitive charts and provides downloadable PDF reports.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)

# Call to Action
st.markdown('<p style="text-align: center; color: #475569;">Ready to verify a medical claim?</p>', unsafe_allow_html=True)

# Center the button using 3 equal columns
_, btn_col, _ = st.columns([1, 1, 1])
with btn_col:
    if st.button("Start Fact Checking", type="primary", use_container_width=True):
        st.switch_page("pages/Fact_Check.py")
