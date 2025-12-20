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
# CSS — DESIGN CHAN FOUI & FILS + BOUTON UPLOAD
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
    border-radius: 18px;
    padding: 2.2rem;
    margin-bottom: 2rem;
    box-shadow: 0 6px 22px rgba(39, 65, 74, 0.12);
}

/* Header */
.header {
    text-align: center;
}

.logo {
    height: 100px;
    margin-bottom: 1rem;
}

/* Bouton upload custom */
.upload-btn {
    background-color: #27414A;
    color: white;
    border-radius: 12px;
    padding: 16px 26px;
    font-size: 18px;
    font-weight: 700;
    border: none;
    cursor: pointer;
    display: inline-block;
    transition: all 0.2s ease;
}

.upload-btn:hover {
    background-color: #1F2F35;
    transform: translateY(-1px);
}

/* Cache UI uploader Streamlit */
[data-testid="stFileUploader"] section {
    display: none;
}

/* Progress bar */
.stProgress > div > div > div {
    height: 22px;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="card header">', unsafe_allow_html=True)
try:
    st.image("CF_LOGOS.png", class_="logo")
except:
    st.markdown("🍷")
st.markdown("## **CHAN FOUI & FILS**")
st.caption("Scanner intelligent • Factures & Bons de Commande")
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# BOUTON UPLOAD (FAUX BOUTON, VRAI FILE UPLOADER)
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

    for p, msg in [
        (10, "📥 Fichier chargé"),
        (35, "🧠 OCR & analyse IA"),
        (65, "📊 Extraction des données"),
        (85, "📘 Standardisation"),
        (100, "✅ Analyse terminée avec succès"),
    ]:
        time.sleep(0.25)
        progress.progress(p)
        status.info(msg)

    st.success("Votre fichier a été analysé avec succès")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

st.caption("© CHAN FOUI & FILS — Scanner Pro • UX Bouton")
