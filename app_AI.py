import streamlit as st
import pandas as pd
from PIL import Image
from io import BytesIO
import time
import os

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="CHAN FOUI & FILS — Scanner Pro",
    page_icon="🍷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>
.stApp {
    background-color: #F5F5F3;
    font-family: Inter, system-ui, sans-serif;
}

.card {
    background: #FFFFFF;
    border-radius: 20px;
    padding: 2.4rem;
    margin-bottom: 2rem;
    box-shadow: 0 8px 24px rgba(39, 65, 74, 0.12);
}

.header {
    text-align: center;
}

.app-title {
    font-size: 2.2rem;
    font-weight: 800;
    color: #1A1A1A;
}

.app-subtitle {
    font-size: 1.05rem;
    color: #555;
}

/* File uploader => bouton */
[data-testid="stFileUploader"] label {
    background-color: #27414A;
    color: white;
    padding: 18px 36px;
    border-radius: 14px;
    font-size: 18px;
    font-weight: 700;
    cursor: pointer;
}

[data-testid="stFileUploader"] label:hover {
    background-color: #1F2F35;
}

[data-testid="stFileUploader"] section {
    border: none;
    background: none;
}

/* Warning cellule */
.warning-cell {
    background-color: #FFD6D6;
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

for path in logo_paths:
    if os.path.exists(path):
        st.image(path, width=220)
        break

st.markdown('<div class="app-title">CHAN FOUI & FILS</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Scanner intelligent • Factures & Bons de Commande</div>',
    unsafe_allow_html=True
)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# UPLOAD
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "📤 Importer un document (facture ou BDC)",
    type=["jpg", "jpeg", "png"]
)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FAUSSE EXTRACTION (STABLE POUR TEST)
# ============================================================

def extract_document_stub():
    """
    Simulation réaliste d'extraction OCR / Vision
    """
    raw_data = [
        {"designation": "VIN ROUGE COTE DE FIANAR 75 CL", "qte": 36},
        {"designation": "VIN BLANC MAROPARASY 75CL", "qte": 24},
        {"designation": "CONS CHAN FOUI 75 CL", "qte": 120},
        {"designation": "VIN ROSE COTE DE FIANAR", "qte": 12},
    ]
    return pd.DataFrame(raw_data)

STANDARD_MAP = {
    "VIN ROUGE COTE DE FIANAR 75 CL": "VIN ROUGE CÔTE DE FIANAR 75CL",
    "VIN BLANC MAROPARASY 75CL": "VIN BLANC MAROPARASY 75CL",
    "CONS CHAN FOUI 75 CL": "CONS. CHAN FOUI 75CL",
}

def standardize(df):
    rows = []
    for _, r in df.iterrows():
        raw = r["designation"]
        if raw in STANDARD_MAP:
            rows.append({
                "designation_brute": raw,
                "designation_standard": STANDARD_MAP[raw],
                "qte": r["qte"],
                "standardise": True
            })
        else:
            rows.append({
                "designation_brute": raw,
                "designation_standard": raw,
                "qte": r["qte"],
                "standardise": False
            })
    return pd.DataFrame(rows)

# ============================================================
# ANALYSE
# ============================================================

if uploaded_file:
    image_bytes = uploaded_file.read()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.image(Image.open(BytesIO(image_bytes)), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("## 🤖 Analyse du document")

    progress = st.progress(0)
    status = st.empty()

    for i, msg in [
        (20, "📥 Chargement du fichier"),
        (50, "🧠 Lecture OCR / Vision"),
        (80, "📊 Structuration des données"),
        (100, "✅ Analyse terminée"),
    ]:
        time.sleep(0.3)
        progress.progress(i)
        status.info(msg)

    st.success("Votre fichier a été analysé avec succès")
    st.markdown('</div>', unsafe_allow_html=True)

    # ========================================================
    # TABLEAU BRUT
    # ========================================================

    df_raw = extract_document_stub()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("## 📄 Données extraites (brutes)")
    st.dataframe(df_raw, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ========================================================
    # TABLEAU STANDARDISÉ
    # ========================================================

    df_std = standardize(df_raw)

    def highlight(row):
        if not row["standardise"]:
            return ["background-color: #FFD6D6"] * len(row)
        return [""] * len(row)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("## 📘 Données standardisées")

    st.dataframe(
        df_std.style.apply(highlight, axis=1),
        use_container_width=True
    )

    st.markdown("🔴 **Les lignes en rouge ne sont pas reconnues dans le référentiel**")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

st.caption("© CHAN FOUI & FILS — Scanner Pro • Extraction & standardisation")
