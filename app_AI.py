# ============================================================
# OCR FACTURES & BDC — OPENAI VISION (OPTIMISÉ TOKENS)
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
st.caption("OpenAI Vision • Prompt optimisé • Suivi tokens réel")

# ============================================================
# SECRETS
# ============================================================

if "OPENAI_API_KEY" not in st.secrets:
    st.error("❌ OPENAI_API_KEY non trouvé dans les secrets Streamlit")
    st.stop()

# ============================================================
# OPENAI CLIENT
# ============================================================

openai_client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    project=st.secrets.get("OPENAI_PROJECT_ID")
)

# ============================================================
# SUIVI BUDGET / TOKENS
# ============================================================

BUDGET_USD = 5.0
USD_PER_1K_TOKENS = 0.003  # estimation gpt-4.1-mini
TOTAL_BUDGET_TOKENS = int((BUDGET_USD / USD_PER_1K_TOKENS) * 1000)

if "used_tokens" not in st.session_state:
    st.session_state.used_tokens = 0

# ============================================================
# BARRE DE CRÉDIT
# ============================================================

remaining_tokens = TOTAL_BUDGET_TOKENS - st.session_state.used_tokens
remaining_tokens = max(0, remaining_tokens)

progress = min(st.session_state.used_tokens / TOTAL_BUDGET_TOKENS, 1.0)

st.subheader("🔋 Crédit OpenAI (tokens réels)")
st.progress(progress)

st.caption(
    f"Tokens utilisés : {st.session_state.used_tokens:,} / {TOTAL_BUDGET_TOKENS:,} "
    f"— Restants estimés : {remaining_tokens:,}"
)

if remaining_tokens < 50_000:
    st.warning("⚠️ Crédit bientôt épuisé")

# ============================================================
# PRÉTRAITEMENT IMAGE (VISION SAFE)
# ============================================================

def prepare_image_for_openai(image_bytes: bytes) -> str:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((1600, 1600))

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=75, optimize=True)

    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

# ============================================================
# PROMPT OPTIMISÉ (–20 % TOKENS)
# ============================================================

PROMPT_OPTIMISE = """
Analyse un document commercial scanné à Madagascar.

Type possible :
- FACTURE
- BDC ULYS
- BDC LEADER PRICE
- BDC S2M / SUPERMARKI
- AUTRE BDC

Règles :
- Ignore prix, montants, TVA, EAN, PCB, codes
- Regroupe lignes cassées
- Corrige erreurs OCR évidentes
- Ne commente rien

Extraire si visible :
- type_document
- fournisseur
- numero_document
- date_document

Articles :
Pour chaque ligne valide :
- designation
- qte

Retourne UNIQUEMENT ce JSON valide :

{
  "type_document": "",
  "fournisseur": "",
  "numero_document": "",
  "date_document": "",
  "articles": [
    {
      "designation": "",
      "qte": ""
    }
  ]
}
"""

# ============================================================
# EXTRACTION PAR OPENAI VISION
# ============================================================

def extract_facture_bdc(image_bytes: bytes) -> dict:
    image_url = prepare_image_for_openai(image_bytes)

    response = openai_client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": PROMPT_OPTIMISE},
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
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_tokens": usage["total_tokens"]
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

    with st.spinner("Analyse du document par IA…"):
        result = extract_facture_bdc(image_bytes)

    data = result["data"]
    usage = result["usage"]

    # MAJ TOKENS
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
    # TABLE ARTICLES
    # ========================================================

    st.subheader("📦 Articles détectés")

    df = pd.DataFrame(data.get("articles", []))

    df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True
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
            "articles": df.to_dict(orient="records"),
            "validated_at": datetime.now().isoformat()
        }

        st.success("🎉 Données validées")
        st.json(output)

# ============================================================
# FOOTER
# ============================================================

st.caption("⚡ OpenAI Vision • Prompt optimisé • Suivi tokens réel")
