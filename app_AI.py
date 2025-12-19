# ============================================================
# OCR FACTURES & BDC — OPENAI VISION + STANDARDISATION
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
USD_PER_1K_TOKENS = 0.003  # gpt-4.1-mini
TOTAL_BUDGET_TOKENS = int((BUDGET_USD / USD_PER_1K_TOKENS) * 1000)

if "used_tokens" not in st.session_state:
    st.session_state.used_tokens = 0

remaining_tokens = max(0, TOTAL_BUDGET_TOKENS - st.session_state.used_tokens)
progress = min(st.session_state.used_tokens / TOTAL_BUDGET_TOKENS, 1.0)

st.subheader("🔋 Crédit OpenAI (estimation)")
st.progress(progress)
st.caption(
    f"Tokens utilisés : {st.session_state.used_tokens:,} / {TOTAL_BUDGET_TOKENS:,} "
    f"— Restants ≈ {remaining_tokens:,}"
)

# ============================================================
# TABLE DE STANDARDISATION PRODUITS
# ============================================================

STANDARD_PRODUCTS = [
    {
        "standard": "Côte de Fianar Rouge 75 cl",
        "aliases": [
            "vin rouge cote de fianar",
            "vin rouge cote de fianara",
            "cote de fianar rouge"
        ]
    },
    {
        "standard": "Côte de Fianar Blanc 75 cl",
        "aliases": [
            "vin blanc cote de fianar",
            "vin blanc cote de fianara",
            "cote de fianar blanc"
        ]
    },
    {
        "standard": "Côte de Fianar Rosé 75 cl",
        "aliases": [
            "vin rose cote de fianar",
            "vin rose cote de fianara",
            "cote de fianar rose"
        ]
    },
    {
        "standard": "Côte de Fianar Gris 75 cl",
        "aliases": [
            "vin gris cote de fianar",
            "vin gris cote de fianara"
        ]
    },
    {
        "standard": "Blanc doux Maroparasy 75 cl",
        "aliases": [
            "vin blanc doux maroparasy",
            "blanc doux maroparasy"
        ]
    },
    {
        "standard": "Maroparasy Rouge 75 cl",
        "aliases": [
            "vin rouge doux maroparasy",
            "vin aperitif rouge maroparasy"
        ]
    },
    {
        "standard": "Côteau d'Ambalavao Rouge 75 cl",
        "aliases": [
            "vin rouge ambalavao",
            "coteau ambalavao rouge"
        ]
    },
    {
        "standard": "Côteau d'Ambalavao Blanc 75 cl",
        "aliases": [
            "vin blanc ambalavao",
            "coteau ambalavao blanc"
        ]
    }
]

# ============================================================
# NORMALISATION DÉSIGNATION
# ============================================================

def normalize_designation(raw_name: str) -> str:
    if not raw_name:
        return ""

    name = raw_name.lower()

    for product in STANDARD_PRODUCTS:
        for alias in product["aliases"]:
            if alias in name:
                return product["standard"]

    return "❓ Non standardisé"

# ============================================================
# IMAGE → BASE64 (VISION SAFE)
# ============================================================

def image_to_base64(image_bytes: bytes) -> str:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((1600, 1600))

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75, optimize=True)

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

Ignore prix, montants, TVA, EAN, PCB, codes.
Regroupe lignes cassées. Corrige OCR évident.
Ne commente rien.

Retourne UNIQUEMENT ce JSON :

{
  "type_document": "",
  "fournisseur": "",
  "numero_document": "",
  "date_document": "",
  "articles": [
    { "designation": "", "qte": "" }
  ]
}
"""

# ============================================================
# EXTRACTION OPENAI VISION
# ============================================================

def extract_facture_bdc(image_bytes: bytes) -> dict:
    image_url = image_to_base64(image_bytes)

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": PROMPT},
                    {"type": "input_image", "image_url": image_url}
                ]
            }
        ],
        temperature=0,
        max_output_tokens=1000
    )

    usage = response.usage

    return {
        "data": json.loads(response.output_text),
        "usage": {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens
        }
    }

# ============================================================
# UPLOAD DOCUMENT
# ============================================================

uploaded_file = st.file_uploader(
    "📤 Importer une facture ou un BDC (image)",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file:
    image_bytes = uploaded_file.read()

    st.image(
        Image.open(BytesIO(image_bytes)),
        caption="Document importé",
        use_container_width=True
    )

    with st.spinner("Analyse IA en cours…"):
        result = extract_facture_bdc(image_bytes)

    data = result["data"]
    usage = result["usage"]

    st.session_state.used_tokens += usage["total_tokens"]

    st.success("✅ Analyse terminée")

    # ========================================================
    # INFOS DOCUMENT
    # ========================================================

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**📄 Type :** {data.get('type_document','')}")
        st.markdown(f"**🏢 Fournisseur :** {data.get('fournisseur','')}")
    with col2:
        st.markdown(f"**🧾 Numéro :** {data.get('numero_document','')}")
        st.markdown(f"**📅 Date :** {data.get('date_document','')}")

    # ========================================================
    # TABLEAU 1 — OCR BRUT
    # ========================================================

    st.subheader("📦 Articles (OCR brut)")

    df_raw = pd.DataFrame(data.get("articles", []))

    df_raw = st.data_editor(
        df_raw,
        num_rows="dynamic",
        use_container_width=True,
        key="raw_table"
    )

    # ========================================================
    # TABLEAU 2 — STANDARDISÉ
    # ========================================================

    st.subheader("📘 Articles standardisés")

    df_standard = df_raw.copy()
    df_standard["designation_standardisee"] = df_standard["designation"].apply(
        normalize_designation
    )

    df_standard = st.data_editor(
        df_standard[["designation", "designation_standardisee", "qte"]],
        num_rows="dynamic",
        use_container_width=True,
        key="standard_table"
    )

    st.caption(
        f"🧮 Dernier scan : {usage['total_tokens']} tokens "
        f"(entrée {usage['input_tokens']} / sortie {usage['output_tokens']})"
    )

    # ========================================================
    # VALIDATION
    # ========================================================

    if st.button("✅ Valider les données"):
        output = {
            "type_document": data.get("type_document"),
            "fournisseur": data.get("fournisseur"),
            "numero_document": data.get("numero_document"),
            "date_document": data.get("date_document"),
            "articles_standardises": df_standard.to_dict(orient="records"),
            "validated_at": datetime.now().isoformat()
        }

        st.success("🎉 Données validées")
        st.json(output)

# ============================================================
# FOOTER
# ============================================================

st.caption("⚡ OpenAI Vision • Standardisation produits • Version finale")
