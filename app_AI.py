# ============================================================
# CHANFOUI OCR — FACTURES & BDC (DESIGN PRO FINAL)
# ============================================================

import streamlit as st
import pandas as pd
import base64
import json
from openai import OpenAI
from PIL import Image
from io import BytesIO

# ============================================================
# CONFIG STREAMLIT
# ============================================================

st.set_page_config(
    page_title="CHANFOUI OCR",
    page_icon="🧾",
    layout="centered"
)

# ============================================================
# THEME / CSS GLOBAL
# ============================================================

st.markdown("""
<style>
body {
    background-color: #F6F8FA;
}

.block-card {
    background: #FFFFFF;
    border-radius: 14px;
    padding: 30px;
    margin-bottom: 25px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.04);
}

.header {
    display: flex;
    align-items: center;
    gap: 15px;
}

.logo {
    width: 48px;
    height: 48px;
    background: #1F7AE0;
    color: white;
    font-weight: bold;
    font-size: 22px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.title {
    font-size: 26px;
    font-weight: 700;
}

.subtitle {
    color: #6B7280;
    font-size: 14px;
}

/* Hide Streamlit file uploader UI */
[data-testid="stFileUploader"] section {
    display: none;
}

/* Progress bar height */
.stProgress > div > div > div {
    height: 20px;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================

st.markdown("""
<div class="block-card">
    <div class="header">
        <div class="logo">CF</div>
        <div>
            <div class="title">CHANFOUI OCR</div>
            <div class="subtitle">Factures & Bons de Commande • OpenAI Vision</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SECRETS / OPENAI CLIENT
# ============================================================

if "OPENAI_API_KEY" not in st.secrets:
    st.error("❌ OPENAI_API_KEY manquante dans les secrets")
    st.stop()

client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    project=st.secrets.get("OPENAI_PROJECT_ID")
)

# ============================================================
# STANDARDISATION PRODUITS
# ============================================================

STANDARD_PRODUCTS = [
    {"standard": "Côte de Fianar Rouge 75 cl", "aliases": ["vin rouge cote de fianar"]},
    {"standard": "Côte de Fianar Blanc 75 cl", "aliases": ["vin blanc cote de fianar"]},
    {"standard": "Côte de Fianar Rosé 75 cl", "aliases": ["vin rose cote de fianar"]},
    {"standard": "Côte de Fianar Gris 75 cl", "aliases": ["vin gris cote de fianar"]},
    {"standard": "Blanc doux Maroparasy 75 cl", "aliases": ["vin blanc doux maroparasy"]},
    {"standard": "Maroparasy Rouge 75 cl", "aliases": ["vin rouge doux maroparasy"]},
]

def normalize_designation(text):
    if not text:
        return ""
    t = text.lower()
    for p in STANDARD_PRODUCTS:
        for a in p["aliases"]:
            if a in t:
                return p["standard"]
    return "❓ Non standardisé"

# ============================================================
# IMAGE → BASE64
# ============================================================

def image_to_base64(image_bytes):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((1600, 1600))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

# ============================================================
# PROMPT
# ============================================================

PROMPT = """
Analyse un document commercial scanné à Madagascar.

Types possibles :
- FACTURE
- BDC ULYS
- BDC LEADER PRICE
- BDC S2M / SUPERMARKI

Ignore prix, TVA, montants, codes.
Corrige OCR évident. Regroupe lignes cassées.
Ne commente rien.

Retourne UNIQUEMENT ce JSON :
{
  "type_document": "",
  "fournisseur": "",
  "numero_document": "",
  "date_document": "",
  "articles": [
    {"designation": "", "qte": ""}
  ]
}
"""

# ============================================================
# EXTRACTION OPENAI
# ============================================================

def extract_facture_bdc(image_bytes):
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": PROMPT},
                {"type": "input_image", "image_url": image_to_base64(image_bytes)}
            ]
        }],
        temperature=0,
        max_output_tokens=1000
    )
    return json.loads(response.output_text)

# ============================================================
# UPLOAD CARD
# ============================================================

st.markdown("""
<div class="block-card" style="text-align:center;border:2px dashed #1F7AE0;">
    <h3>📤 Importer une facture ou un BDC</h3>
    <p style="color:#6B7280;">Cliquez ou glissez un fichier (JPG, JPEG, PNG)</p>
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed"
)

# ============================================================
# TRAITEMENT
# ============================================================

if uploaded_file:
    image_bytes = uploaded_file.read()

    st.markdown('<div class="block-card">', unsafe_allow_html=True)
    st.image(Image.open(BytesIO(image_bytes)), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="block-card">', unsafe_allow_html=True)
    progress = st.progress(0)
    status = st.empty()

    progress.progress(10)
    status.info("📥 Fichier chargé")

    progress.progress(35)
    status.info("🧠 Analyse du document par IA")

    data = extract_facture_bdc(image_bytes)

    progress.progress(70)
    status.info("📊 Extraction et standardisation")

    df_raw = pd.DataFrame(data.get("articles", []))
    df_std = df_raw.copy()
    df_std["designation_standardisee"] = df_std["designation"].apply(normalize_designation)

    progress.progress(100)
    status.success("✅ Votre fichier a été analysé avec succès")
    st.markdown('</div>', unsafe_allow_html=True)

    # ========================================================
    # INFOS DOCUMENT
    # ========================================================

    st.markdown(f"""
<div class="block-card">
<b>📄 Type :</b> {data.get('type_document','')}<br>
<b>🏢 Fournisseur :</b> {data.get('fournisseur','')}<br>
<b>🧾 Numéro :</b> {data.get('numero_document','')}<br>
<b>📅 Date :</b> {data.get('date_document','')}
</div>
""", unsafe_allow_html=True)

    # ========================================================
    # TABLES
    # ========================================================

    st.markdown('<div class="block-card">', unsafe_allow_html=True)
    st.subheader("📦 Articles détectés (OCR brut)")
    st.data_editor(df_raw, num_rows="dynamic", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="block-card">', unsafe_allow_html=True)
    st.subheader("📘 Articles standardisés")

    def highlight(row):
        if row["designation_standardisee"] == "❓ Non standardisé":
            return ["background-color:#FDE2E2"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_std[["designation", "designation_standardisee", "qte"]]
        .style.apply(highlight, axis=1),
        use_container_width=True
    )

    if "❓ Non standardisé" in df_std["designation_standardisee"].values:
        st.warning("⚠️ Certains articles ne sont pas standardisés.")
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================

st.caption("© CHANFOUI • OCR OpenAI Vision • Interface professionnelle")
