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
# CSS — DESIGN PRO + LOGO MIS EN AVANT
# ============================================================

st.markdown("""
<style>
.stApp {
    background-color: #F5F5F3;
    font-family: Inter, system-ui, sans-serif;
}

/* Carte générique */
.card {
    background: #FFFFFF;
    border-radius: 22px;
    padding: 2.8rem;
    margin-bottom: 2.2rem;
    box-shadow: 0 10px 30px rgba(39, 65, 74, 0.12);
}

/* HEADER */
.header {
    text-align: center;
    padding-top: 3rem;
    padding-bottom: 3rem;
}

.logo-container {
    display: flex;
    justify-content: center;
    margin-bottom: 1.2rem;
}

.logo-img {
    height: 130px;
    max-width: 100%;
    object-fit: contain;
}

.app-title {
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: 1px;
    color: #1A1A1A;
}

.app-subtitle {
    margin-top: 0.4rem;
    font-size: 1.05rem;
    color: #555;
}

/* Bouton upload */
.upload-btn {
    background-color: #27414A;
    color: white;
    border-radius: 14px;
    padding: 18px 32px;
    font-size: 18px;
    font-weight: 700;
    border: none;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    transition: all 0.2s ease;
}

.upload-btn:hover {
    background-color: #1F2F35;
    transform: translateY(-1px);
}

/* Cache le uploader natif */
[data-testid="stFileUploader"] section {
    display: none;
}

/* Barre de progression */
.stProgress > div > div > div {
    height: 22px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER AVEC LOGO (VISIBLE & CENTRÉ)
# ============================================================

st.markdown('<div class="card header">', unsafe_allow_html=True)

try:
    st.markdown('<div class="logo-container">', unsafe_allow_html=True)
    st.image("assets/CF_LOGOS.png", class_="logo-img")
    st.markdown('</div>', unsafe_allow_html=True)
except:
    st.markdown("🍷", unsafe_allow_html=True)

st.markdown('<div class="app-title">CHAN FOUI & FILS</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Scanner intelligent • Factures & Bons de Commande</div>',
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# BOUTON IMPORT
# ============================================================

st.markdown('<div class="card" style="text-align:center;">', unsafe_allow_html=True)

st.markdown("""
<label class="upload-btn" for="file_uploader">
📤 Importer un document
</label>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "",
    type=["jpg", "jpeg", "png"],
    key="file_uploader",
    label_visibility="collapsed"
)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# SIMULATION ANALYSE (DESIGN)
# ============================================================

if uploaded_file:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.image(Image.open(uploaded_file), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🤖 Analyse du document")
    progress = st.progress(0)
    status = st.empty()

    for p, msg in [
        (15, "📥 Fichier chargé"),
        (40, "🧠 Analyse OCR"),
        (70, "📊 Extraction des données"),
        (90, "📘 Standardisation"),
        (100, "✅ Analyse terminée"),
    ]:
        time.sleep(0.25)
        progress.progress(p)
        status.info(msg)

    st.success("Votre fichier a été analysé avec succès")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

st.caption("© CHAN FOUI & FILS — Scanner Pro")
