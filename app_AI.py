# ============================================================
# OCR FACTURES & BDC — OPENAI VISION (VERSION FINALE UX)
# ============================================================

import streamlit as st
import pandas as pd
import base64
import json
from openai import OpenAI
from PIL import Image
from io import BytesIO
from datetime import datetime

# ============================================================
# CONFIG STREAMLIT
# ============================================================

st.set_page_config(
    page_title="OCR Factures & BDC — IA",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 OCR Factures & Bons de Commande")
st.caption("OpenAI Vision • Prompt optimisé • Standardisation produits")

# ============================================================
# SECRETS
# ============================================================

if "OPENAI_API_KEY" not in st.secrets:
    st.error("❌ OPENAI_API_KEY non trouvé dans les secrets Streamlit")
    st.stop()

# ============================================================
# CLIENT OPENAI
# ============================================================

client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    project=st.secrets.get("OPENAI_PROJECT_ID")
)

# ============================================================
# BUDGET / TOKENS (ESTIMATION)
# ============================================================

BUDGET_USD = 5.0
USD_PER_1K_TOKENS = 0.003
TOTAL_BUDGET_TOKENS = int((BUDGET_USD / USD_PER_1K_TOKENS) * 1000)

if "used_tokens" not in st.session_state:
    st.session_state.used_tokens = 0

remaining_tokens = max(0, TOTAL_BUDGET_TOKENS - st.session_state.used_tokens)
progress_credit = min(st.session_state.used_tokens / TOTAL_BUDGET_TOKENS, 1.0)

st.subheader("🔋 Crédit OpenAI (estimation)")
st.progress(progress_credit)
st.caption(
    f"Tokens utilisés : {st.session_state.used_tokens:,} / {TOTAL_BUDGET_TOKENS:,} "
    f"— Restants ≈ {remaining_tokens:,}"
)

# ============================================================
# STANDARDISATION PRODUITS
# ============================================================

STANDARD_PRODUCTS = [
    {"standard": "Côte de Fianar Rouge 75 cl", "aliases": ["vin rouge cote de fianar", "cote de fianara rouge"]},
    {"standard": "Côte de Fianar Blanc 75 cl", "aliases": ["vin blanc cote de fianar", "cote de fianara blanc"]},
    {"standard": "Côte de Fianar Rosé 75 cl", "aliases": ["vin rose cote de fianar"]},
    {"standard": "Côte de Fianar Gris 75 cl", "aliases": ["vin gris cote de fianar"]},
    {"standard": "Maroparasy Rouge 75 cl", "aliases": ["vin rouge doux maroparasy"]},
    {"standard": "Blanc doux Maroparasy 75 cl", "aliases": ["vin blanc doux maroparasy"]},
    {"standard": "Côteau d'Ambalavao Rouge 75 cl", "aliases": ["vin rouge ambalavao"]},
    {"standard": "Côteau d'Ambalavao Blanc 75 cl", "aliases": ["vin blanc ambalavao"]}
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

Types :
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

    usage = response.usage

    return json.loads(response.output_text), {
        "total": usage.total_tokens
    }

# ============================================================
# ZONE UPLOAD LARGE
# ============================================================

st.markdown("""
<div style="border:2px dashed #4CAF50;border-radius:12px;
padding:30px;text-align:center;font-size:18px;background:#f9fff9;">
📤 <b>Importer une facture ou un BDC</b><br>
<span style="font-size:14px;color:#666;">JPG, JPEG, PNG</span>
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
    st.image(Image.open(BytesIO(image_bytes)), use_container_width=True)

    progress_bar = st.progress(0)
    status = st.empty()

    progress_bar.progress(10)
    status.info("📥 Fichier chargé")

    progress_bar.progress(30)
    status.info("🧠 Analyse du document par IA…")

    data, usage = extract_facture_bdc(image_bytes)

    progress_bar.progress(70)
    status.info("📊 Structuration des données")

    st.session_state.used_tokens += usage["total"]

    progress_bar.progress(100)
    status.success("✅ Votre fichier a été analysé avec succès")

    # ========================================================
    # INFOS DOC
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

    st.subheader("📦 Articles (OCR brut)")
    df_raw = pd.DataFrame(data.get("articles", []))
    df_raw = st.data_editor(df_raw, num_rows="dynamic", use_container_width=True)

    # ========================================================
    # TABLEAU STANDARDISÉ AVEC WARNING
    # ========================================================

    st.subheader("📘 Articles standardisés")

    df_std = df_raw.copy()
    df_std["designation_standardisee"] = df_std["designation"].apply(normalize_designation)

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
        st.warning("⚠️ Certains articles ne sont pas standardisés. Veuillez vérifier.")
