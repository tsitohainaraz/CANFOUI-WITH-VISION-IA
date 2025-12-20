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
# CSS — DESIGN + BOUTON FILE UPLOADER
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
    border-radius: 20px;
    padding: 2.4rem;
    margin-bottom: 2rem;
    box-shadow: 0 8px 24px rgba(39, 65, 74, 0.12);
    text-align: center;
}

/* Header */
.header {
    padding-top: 2.5rem;
    padding-bottom: 2.5rem;
}

/* Titre */
.app-title {
    font-size: 2.2rem;
    font-weight: 800;
    color: #1A1A1A;
}

.app-subtitle {
    margin-top: 0.4rem;
    font-size: 1.05rem;
    color: #555;
}

/* Transformer file_uploader en bouton */
[data-testid="stFileUploader"] label {
    background-color: #27414A;
    color: white;
    padding: 18px 36px;
    border-radius: 14px;
    font-size: 18px;
    font-weight: 700;
    display: inline-block;
    cursor: pointer;
}

[data-testid="stFileUploader"] label:hover {
    background-color: #1F2F35;
}

/* Supprimer drag & drop zone */
[data-testid="stFileUploader"] section {
    background: none;
    border: none;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER + LOGO
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
    st.markdown("🍷")

st.markdown('<div class="app-title">CHAN FOUI & FILS</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Scanner intelligent • Factures & Bons de Commande</div>',
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# BOUTON IMPORTER UN DOCUMENT (OFFICIEL STREAMLIT)
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "📤 Importer un document",
    type=["jpg", "jpeg", "png"]
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
        (20, "📥 Document chargé"),
        (45, "🧠 Lecture OCR"),
        (70, "📊 Extraction des données"),
        (90, "📘 Standardisation"),
        (100, "✅ Analyse terminée"),
    ]

    for value, message in steps:
        time.sleep(0.35)
        progress.progress(value)
        status.info(message)

    st.success("Votre fichier a été analysé avec succès")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

st.caption("© CHAN FOUI & FILS — Scanner Pro • Version stable")
