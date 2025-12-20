# ============================================================
# OCR FACTURES & BDC — OPENAI VISION (UX PRO FINALE)
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
    page_title="OCR Factures & BDC — IA",
    page_icon="🧾",
    layout="centered"
)

# ============================================================
# CSS — HIDE FILE UPLOADER DEFAULT + THEME
# ============================================================

st.markdown("""
<style>
/* Cache complètement le file uploader Streamlit */
[data-testid="stFileUploader"] section {
    display: none;
}

/* Progress bar custom spacing */
.stProgress > div > div > div {
    height: 20px;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================

st.title("🧾 OCR Factures & Bons de Commande")
st.caption("OpenAI Vision • Prompt optimisé • Standardisation produits")

# ============================================================
# SECRETS
# ============================================================

if "OPENAI_API_KEY" not in st.secrets:
    st.error("❌ OPENAI_API_KEY non trouvé dans les secrets Streamlit")
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

def normalize_designation(raw):
    if not raw:
        return ""
    txt = raw.lower()
    for p in STANDARD_PRODUCTS:
        for a in p["aliases"]:
            if a in txt:
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
# PROMPT OPTIMISÉ
# ============================================================

PROMPT = """
Analyse un document commercial scanné à Madagascar.

Types possibles :
- FACTURE
- BDC ULYS
- BDC LEADER PRICE
- BDC S2M / SUPERMARKI

Ignore prix, montants, TVA, codes.
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
# ZONE UPLOAD — UX PRO (UNE SEULE)
# ============================================================

st.markdown("""
<div style="
    border:3px dashed #4CAF50;
    border-radius:16px;
    padding:50px;
    text-align:center;
    font-size:22px;
    background:#f9fff9;
    cursor:pointer;
">
📤 <b>Importer une facture ou un BDC</b><br><br>
<span style="font-size:14px;color:#666;">
Cliquez ou glissez un fichier (JPG, JPEG, PNG)
</span>
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed"
)

# ============================================================
# TRAITEMENT AVEC PROGRESSION
# ============================================================

if uploaded_file:
    image_bytes = uploaded_file.read()

    st.image(Image.open(BytesIO(image_bytes)), use_container_width=True)

    progress = st.progress(0)
    status = st.empty()

    progress.progress(10)
    status.info("📥 Fichier chargé")

    progress.progress(30)
    status.info("🧠 Analyse du document par IA…")

    data = extract_facture_bdc(image_bytes)

    progress.progress(60)
    status.info("📊 Extraction des articles")

    df_raw = pd.DataFrame(data.get("articles", []))

    progress.progress(85)
    status.info("📘 Standardisation des produits")

    df_std = df_raw.copy()
    df_std["designation_standardisee"] = df_std["designation"].apply(normalize_designation)

    progress.progress(100)
    status.success("✅ Votre fichier a été analysé avec succès")

    # ========================================================
    # INFOS DOCUMENT
    # ========================================================

    st.markdown(f"""
**📄 Type :** {data.get('type_document','')}  
**🏢 Fournisseur :** {data.get('fournisseur','')}  
**🧾 Numéro :** {data.get('numero_document','')}  
**📅 Date :** {data.get('date_document','')}
""")

    # ========================================================
    # TABLEAU OCR BRUT
    # ========================================================

    st.subheader("📦 Articles détectés (OCR brut)")
    st.data_editor(df_raw, num_rows="dynamic", use_container_width=True)

    # ========================================================
    # TABLEAU STANDARDISÉ + WARNING ROUGE
    # ========================================================

    st.subheader("📘 Articles standardisés")

    def highlight(row):
        if row["designation_standardisee"] == "❓ Non standardisé":
            return ["background-color:#ffdddd"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_std[["designation", "designation_standardisee", "qte"]]
        .style.apply(highlight, axis=1),
        use_container_width=True
    )

    if "❓ Non standardisé" in df_std["designation_standardisee"].values:
        st.warning("⚠️ Certains articles ne sont pas standardisés. Veuillez les corriger.")

# ============================================================
# FOOTER
# ============================================================

st.caption("⚡ OCR OpenAI Vision • UX Pro • Version finale")
