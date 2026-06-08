import streamlit as st

# 1. Configurazione della pagina (Sidebar nascosta permanentemente)
st.set_page_config(
    page_title="Med Fact Check",
    page_icon="⚕️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inizializzazione del disclaimer obbligatorio
if "disclaimer_accepted" not in st.session_state:
    st.session_state.disclaimer_accepted = False

# 2. ARCHITETTURA CSS DEFINITIVA 
st.markdown("""
    <style>
    /* 1. IMPORTAZIONE FONT IN CIMA ASSOLUTA */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');

    /* RIMOZIONE TOTALE SIDEBAR ED HEADER NATIVO */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stHeader"], header { display: none !important; height: 0px !important; padding: 0 !important; } 
    
    [data-testid="stAppViewContainer"] {
        overflow-x: hidden;
        background-color: #0f172a !important;
    }
    
    /* RESET DEI PADDING DI STREAMLIT */
    .main .block-container, [data-testid="stMainBlockContainer"], .block-container {
        padding-top: 0rem !important;
        padding-left: 0rem !important;
        padding-right: 0rem !important;
        padding-bottom: 140px !important; /* Spazio protettivo sul fondo per il footer */
        margin: 0rem !important;
        max-width: 100% !important;
        width: 100% !important;
        min-height: 100vh !important;
        position: relative !important; /* Base per il posizionamento assoluto del footer */
        box-sizing: border-box !important;
    }
    
    html, body {
        font-family: 'Inter', sans-serif;
        background-color: #0f172a !important;
        color: #f8fafc;
        margin: 0 !important; padding: 0 !important;
    }

    /* LA NAVBAR BLOCATA AL SOFFITTO */
    .navbar {
        background-color: #0b1120;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        padding: 1.5rem 4rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
        box-sizing: border-box;
        margin: 0;
    }
    .nav-logo { font-size: 1.5rem; font-weight: 800; color: #3b82f6; }

    /* L'HERO BANNER CON ROTAZIONE IMMAGINI */
    .hero-banner {
        width: 100%;
        padding: 8rem 2rem;
        text-align: center;
        border-bottom: 1px solid rgba(59, 130, 246, 0.3);
        background-size: cover !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
        box-sizing: border-box;
        margin: 0 !important;
        animation: medicalCarousel 18s infinite ease-in-out;
    }
    
    @keyframes medicalCarousel {
        0%, 100% {
            background-image: linear-gradient(rgba(15, 23, 42, 0.6), rgba(15, 23, 42, 0.9)), 
                              url('https://images.unsplash.com/photo-1530497610245-94d3c16cda28?q=80&w=1600&auto=format&fit=crop');
        }
        33% {
            background-image: linear-gradient(rgba(15, 23, 42, 0.6), rgba(15, 23, 42, 0.9)), 
                              url('https://images.unsplash.com/photo-1576086213369-97a306d36557?q=80&w=1600&auto=format&fit=crop');
        }
        66% {
            background-image: linear-gradient(rgba(15, 23, 42, 0.6), rgba(15, 23, 42, 0.9)), 
                              url('https://images.unsplash.com/photo-1526256262350-7da7584cf5eb?q=80&w=1600&auto=format&fit=crop');
        }
    }
    
    .hero-title {
        font-size: 4.2rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        background: linear-gradient(to right, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .hero-subtitle {
        font-size: 1.3rem;
        color: #e2e8f0;
        line-height: 1.6;
        max-width: 800px;
        margin: 0 auto;
    }

    /* I TRE BLOCCHI INFORMATIVI */
    .card-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 1.5rem;
        margin: 4rem auto 2rem auto;
        max-width: 1200px;
        padding: 0 2rem;
        box-sizing: border-box;
    }
    .action-card {
        background: #1e293b;
        border: 1px solid rgba(255,255,255,0.05);
        padding: 2.5rem 2rem;
        border-radius: 16px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .card-icon { font-size: 2.5rem; margin-bottom: 1.5rem; }
    .card-title { font-size: 1.3rem; font-weight: 700; margin-bottom: 0.5rem; color: #f1f5f9; }
    .card-desc { font-size: 0.95rem; color: #94a3b8; line-height: 1.6; }
    
    /* Disclaimer Card iniziale per bloccare lo schermo */
    .disclaimer-wall {
        background: #1e293b; border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 3rem; border-radius: 24px; max-width: 700px;
        margin: 6rem auto 2rem auto; text-align: center;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }
    .disclaimer-title { font-size: 1.8rem; font-weight: 800; color: #ef4444; margin-bottom: 1.5rem; }
    .disclaimer-body { color: #cbd5e1; font-size: 1rem; line-height: 1.6; margin-bottom: 2rem; text-align: left; }

    /* IL BOTTONE GLOW NEON CORRETTO */
    div.stButton {
        display: flex;
        justify-content: center;
    }
    div.stButton > button[kind="primary"] { 
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%) !important; 
        border: none !important; 
        color: #0f172a !important; 
        font-weight: 800 !important; 
        font-size: 1.1rem !important; 
        text-transform: uppercase !important; 
        letter-spacing: 0.05em !important; 
        border-radius: 50px !important; 
        padding: 1rem 3rem !important; 
        box-shadow: 0 0 20px rgba(0, 242, 254, 0.4) !important; 
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important; 
        width: 100% !important;
        max-width: 450px !important; /* Impedisce che diventi troppo largo su grandi schermi */
    }
    /* Questa riga salva il testo: impedisce di andare a capo! */
    div.stButton > button[kind="primary"] p {
        white-space: nowrap !important; 
        margin: 0 !important;
    }
    div.stButton > button[kind="primary"]:hover { 
        transform: scale(1.04) translateY(-2px) !important; 
        box-shadow: 0 0 30px rgba(0, 242, 254, 0.7) !important; 
        color: #000000 !important; 
    }
    
    /* SEZIONE WHY (GLASSMORPHISM) */
    .why-section {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255,255,255,0.05);
        backdrop-filter: blur(12px);
        padding: 3rem;
        border-radius: 20px;
        max-width: 1000px;
        margin: 4rem auto 6rem auto; /* Spinge via il footer in modo perfetto */
        box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.3);
    }
    .why-title {
        font-size: 1.8rem;
        font-weight: 800;
        color: #38bdf8;
        margin-bottom: 1rem;
        text-align: center;
    }
    .why-text {
        color: #cbd5e1;
        font-size: 1.05rem;
        line-height: 1.7;
        text-align: justify;
    }
    
    /* IL FOOTER ANCORATO CHIRURGICAMENTE IN BASSO */
    .footer { 
        position: absolute; 
        bottom: 0; 
        left: 0; 
        width: 100%; 
        text-align: center; 
        padding: 2rem 0; 
        color: #64748b; 
        font-size: 0.85rem; 
        border-top: 1px solid rgba(255,255,255,0.05); 
        background-color: #0b1120; 
        z-index: 99;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# GESTIONE DISCLAIMER COCKPIT
# ==========================================
if not st.session_state.disclaimer_accepted:
    st.markdown("""
        <div class="disclaimer-wall">
            <div class="disclaimer-title">🚨 Legal Disclaimer & Terms of Use</div>
            <div class="disclaimer-body">
                This tool is an automated decision-support system driven by Artificial Intelligence and Big Data technologies. 
                <br><br>
                By clicking "Accept & Continue", you acknowledge and agree that:
                <ul>
                    <li>The generated reports are for <strong>informational and research purposes only</strong>.</li>
                    <li>This system <strong>does not provide medical advice</strong>, professional diagnosis, or clinical treatment plans.</li>
                    <li>It should never be used as a substitute for a consultation with a qualified healthcare professional.</li>
                </ul>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    _, btn_center_col, _ = st.columns([1, 1, 1])
    with btn_center_col:
        if st.button("Accept & Continue", type="primary", use_container_width=True):
            st.session_state.disclaimer_accepted = True
            st.rerun()

else:
    # 1. NAVBAR
    st.markdown("""
        <div class="navbar">
            <div class="nav-logo">⚕️ Med Fact Check</div>
            <div style="font-size: 0.9rem; color: #94a3b8; font-weight:600;">MSc Unina • Big Data Engineering</div>
        </div>
    """, unsafe_allow_html=True)

    # 2. HERO BANNER CON IMMAGINI GIREVOLI
    st.markdown("""
        <div class="hero-banner">
            <div class="hero-title">Med Fact Check</div>
            <div class="hero-subtitle">Your intelligent consultant for verifying medical claims. Navigating complex scientific information with confidence, clarity and maximum precision.</div>
        </div>
    """, unsafe_allow_html=True)
    
    # 3. I TRE BLOCCHI INFORMATIVI
    st.markdown("""
        <div class="card-grid">
            <div class="action-card">
                <div class="card-icon">1️⃣</div>
                <div class="card-title">Input Claim</div>
                <div class="card-desc">Provide a medical claim via text, file, or URL. Your data is handled securely.</div>
            </div>
            <div class="action-card">
                <div class="card-icon">2️⃣</div>
                <div class="card-title">AI Analysis</div>
                <div class="card-desc">The system cross-references the claim with verified and trusted medical literature via RAG pipeline.</div>
            </div>
            <div class="action-card">
                <div class="card-icon">3️⃣</div>
                <div class="card-title">Get Report</div>
                <div class="card-desc">Receive a detailed breakdown of subclaims, confidence scoring and a downloadable PDF report.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # 4. IL BOTTONE NEON DI REINDIRIZZAMENTO NATIVO
    _, center_col, _ = st.columns([1, 1.2, 1])
    with center_col:
        if st.button("Click to Start Fact Check", type="primary", use_container_width=True):
            st.switch_page("pages/Fact_check.py")

    # 5. NUOVA SEZIONE INTERATTIVA "WHY"
    st.markdown("""
       <div class="why-section">
            <div class="why-title">Why Med Fact Check?</div>
            <div class="why-text">
                In the era of digital information overload, the proliferation of unverified medical claims and fake news represents a critical threat to public health. <strong>Med Fact Check</strong> was developed as a <em>Big Data Engineering project at the University of Naples Federico II</em> to bridge this gap through computational rigor. 
                <br><br>
                Unlike standard language models that can suffer from hallucinations, this platform implements an <strong>advanced RAG (Retrieval-Augmented Generation) pipeline</strong>. Every submitted claim is decomposed, analyzed, and cross-referenced in real-time exclusively against certified clinical literature and authoritative scientific databases. The result is a transparent, traceable, and evidence-based validation ecosystem, designed to provide intelligent decision support for healthcare professionals and citizens alike.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 6. FOOTER ASSOLUTO
    st.markdown('<div class="footer">MedFactCheck Project • Big Data Engineering MSc Unina • Powered by RAG & LLMs</div>', unsafe_allow_html=True)