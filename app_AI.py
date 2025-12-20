import streamlit as st
from PIL import Image
from io import BytesIO
import time
import os

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
# CSS — THEME CHAN FOUI & FILS
# ============================================================

st.markdown("""
<style>
.stApp {
    background-color: #F5F5F3;
    font-family: Inter, system-ui, sans-serif;
}

/* Carte */
.card {
    background: #FFFFFF;
    border-radius: 22px;
    padding: 2.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 10px 30px rgba(39, 65, 74, 0.12);
}

/* Header */
.header {
    text-align: center;
    padding-top: 2.5rem;
    padding-bottom: 2.5rem;
}

/* Titre */
.app-title {
    font-size: 2.3rem;
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
    padding: 18px 34px;
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

/* Cache uploader Streamlit */
[data-testid="stFileUploader"] section {
    display: none;
}

/* Progress bar */
.stProgress > div > div > div {
    height: 20px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER + LOGO (AUTO-DETECTION)
# ============================================================

st.markdown('<div class="card header">', unsafe_allow_html=True)

logo_paths = [
    "CF_LOGOS.png",
    "assets/CF_LOGOS.png",
    "static/CF_LOGOS.png",
    "images/CF_LOGOS.png",
]

logo_found = False
for path in logo_paths:
    if os.path.exists(path):
        st.image(path, width=220)
        logo_found = True
        break

if not logo_found:
    st.markdown("🍷", unsafe_allow_html=True)

st.markdown('<div class="app-title">CHAN FOUI & FILS</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Scanner intelligent • Factures & Bons de Commande</div>',
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# BOUTON IMPORT DOCUMENT
# ============================================================

st.markdown('<div class="card" style="text-align:center;">', unsafe_allow_html=True)

st.markdown("""
<label class="upload-btn" for="file_upload">
📤 Importer un document
</label>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "",
    type=["jpg", "jpeg", "png"],
    key="file_upload",
    label_visibility="collapsed"
)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TRAITEMENT + PROGRESSION
# ============================================================

if uploaded_file:
    image_bytes = uploaded_file.read()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.image(Image.open(BytesIO(image_bytes)), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🤖 Analyse du document")

    progress = st.progress(0)
    status = st.empty()

    steps = [
        (15, "📥 Document chargé"),
        (40, "🧠 Lecture OCR"),
        (65, "📊 Extraction des lignes"),
        (85, "📘 Standardisation produits"),
        (100, "✅ Analyse terminée"),
    ]

    for value, message in steps:
        time.sleep(0.3)
        progress.progress(value)
        status.info(message)

    st.success("Votre fichier a été analysé avec succès")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

st.caption("© CHAN FOUI & FILS — Scanner Pro • Interface professionnelle")
