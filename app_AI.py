# ============================================================
# FACTURE & BDC — OCR IA AVANCÉ (CHATGPT VISION)
# Compatible : Facture en compte | BDC ULYS | BDC S2M | SUPERMARKI
# ============================================================

import streamlit as st
import pandas as pd
import base64
import json
from openai import OpenAI
from datetime import datetime
from PIL import Image
from io import BytesIO

# ============================================================
# CONFIG STREAMLIT
# ============================================================

st.set_page_config(
    page_title="OCR Facture & BDC — IA",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 OCR Factures & Bons de Commande — IA Avancée")
st.caption("Analyse par ChatGPT Vision (OpenAI)")

# ============================================================
# OPENAI CLIENT
# ============================================================

openai_client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"]
)

# ============================================================
# FONCTION IA — CHATGPT VISION
# ============================================================

def extract_document_with_chatgpt_vision(image_bytes: bytes) -> dict:
    """
    Analyse une facture ou un bon de commande avec ChatGPT Vision
    et retourne les informations structurées.
    """

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
Tu es un expert en analyse de documents commerciaux (factures et bons de commande).

À partir de l'image fournie :

1. Identifie le type de document :
   - Facture en compte
   - BDC ULYS
   - BDC S2M
   - BDC SUPERMARKI

2. Ignore les prix, montants, TVA, codes EAN, PCB, références inutiles.

3. Extrais si visible :
   - fournisseur
   - numero_document
   - date_document

4. Extrais le tableau des articles avec :
   - Désignation
   - Qté

5. Regroupe les lignes cassées et corrige les erreurs OCR évidentes.

Retourne STRICTEMENT un JSON valide, sans texte autour :

{
  "type_document": "",
  "fournisseur": "",
  "numero_document": "",
  "date_document": "",
  "articles": [
    {
      "Désignation": "",
      "Qté": ""
    }
  ]
}
"""

    response = openai_client.responses.create(
        model="gpt-4.1",
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_base64": image_b64}
            ]
        }],
        temperature=0,
        max_output_tokens=1200
    )

    try:
        return json.loads(response.output_text)
    except Exception:
        return {
            "type_document": "",
            "fournisseur": "",
            "numero_document": "",
            "date_document": "",
            "articles": []
        }

# ============================================================
# UPLOAD IMAGE
# ============================================================

uploaded_file = st.file_uploader(
    "📤 Importer une facture ou un bon de commande",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file:
    image_bytes = uploaded_file.read()

    st.image(
        Image.open(BytesIO(image_bytes)),
        caption="Document importé",
        use_container_width=True
    )

    with st.spinner("Analyse du document par IA..."):
        result = extract_document_with_chatgpt_vision(image_bytes)

    # ========================================================
    # INFORMATIONS GÉNÉRALES
    # ========================================================

    st.success("✅ Analyse terminée")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**📄 Type :** {result['type_document']}")
        st.markdown(f"**🏢 Fournisseur :** {result['fournisseur']}")

    with col2:
        st.markdown(f"**🧾 Numéro :** {result['numero_document']}")
        st.markdown(f"**📅 Date :** {result['date_document']}")

    # ========================================================
    # TABLEAU ARTICLES
    # ========================================================

    st.subheader("📦 Articles détectés")

    df = pd.DataFrame(result["articles"])

    df = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        key="articles_editor"
    )

    # ========================================================
    # VALIDATION
    # ========================================================

    if st.button("✅ Valider les données"):
        st.success("Données validées avec succès 🎉")

        st.json({
            "type_document": result["type_document"],
            "fournisseur": result["fournisseur"],
            "numero_document": result["numero_document"],
            "date_document": result["date_document"],
            "articles": df.to_dict(orient="records"),
            "validated_at": datetime.now().isoformat()
        })

# ============================================================
# FOOTER
# ============================================================

st.caption("⚡ Powered by OpenAI Vision — Extraction intelligente de documents")
