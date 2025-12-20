import streamlit as st
from PIL import Image
from io import BytesIO
import time

# ============================================================
# CONFIG STREAMLIT
# ============================================================

st.set_page_config(
    page_title="CHAN FOUI & FILS — Scanner Pro",
    page_icon="🍷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CSS — DESIGN INSPIRÉ DU LOGO CHAN FOUI & FILS
# ============================================================

st.markdown("""
<style>
/* Fond global */
.stApp {
    background-color: #F5F5F3;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #1A1A1A;
}

/* Carte générique */
.card {
    background: #FFFFFF;
    border-radius: 20px;
    padding: 2.2rem;
    margin-bottom: 2rem;
    box-shadow: 0 6px 22px rgba(39, 65, 74, 0.10);
    border: 1px solid #D1D5DB;
}

/* Header */
.header {
    text-align: center;
    padding: 2.5rem 2rem;
}

.logo {
    height: 110px;
    margin-bottom: 1rem;
}

.title {
    font-size: 2.6rem;
    font-weight: 800;
    letter-spacing: 1px;
    color: #1A1A1A;
}

.subtitle {
    font-size: 1.1rem;
    color: #333333;
    margin-top: 0.3rem;
}

/* Upload box */
.upload-box {
    border: 3px dashed #2C5F73;
    border-radius: 20px;
    padding: 3rem;
    text-align: center;
    background: #FFFFFF;
    transition: all 0.25s ease;
}

.upload-box:hover {
    background: #F9FAFB;
    border-color: #27414A;
}

.upload-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #27414A;
}

.upload-sub {
    color: #333333;
    font-size: 0.95rem;
}

/* Progress container */
.progress-card {
    background: #27414A;
    color: white;
    border-radius: 20px;
    padding: 2.5rem;
    text-align: center;
    box-shadow: 0 6px 24px rgba(39, 65, 74, 0.25);
}

/* Cache UI file_uploader */
[data-testid="stFileUploader"] section {
    display: none;
}

/* Barre de progression */
.stProgress > div > div > div {
    height: 22px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER AVEC LOGO
# ============================================================

st.markdown('<div class="card header">', unsafe_allow_html=True)

try:
    st.image("CF_LOGOS.png", class_="logo")
except:
    st.markdown("🍷")

st.markdown('<div class="title">CHAN FOUI & FILS</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Scanner Intelligent • Factures & Bons de Commande</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# UPLOAD DESIGN
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)

st.markdown("""
<div class="upload-box">
    <div class="upload-title">📤 Importer un document</div>
    <p class="upload-sub">
        Facture ou Bon de Commande<br>
        JPG • JPEG • PNG
    </p>
</div>
""", unsafe_allow_html=True)

uploaded = st.file_uploader(
    "",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed"
)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# SIMULATION D’ANALYSE (DESIGN)
# ============================================================

if uploaded:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.image(Image.open(uploaded), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="progress-card">', unsafe_allow_html=True)
    st.markdown("### 🤖 Analyse du document en cours…")

    progress = st.progress(0)
    for i in range(0, 101, 10):
        time.sleep(0.12)
        progress.progress(i)

    st.success("✅ Votre fichier a été analysé avec succès")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

st.caption("© CHAN FOUI & FILS — Scanner Pro • Design inspiré du logo")
