# ============================================================
# FACTURES & BDC — OCR IA AVANCÉ (OPENAI CHATGPT VISION)
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
st.caption("Analyse intelligente par ChatGPT Vision (OpenAI)")

# ============================================================
# VÉRIFICATION DES SECRETS
# ============================================================

if "OPENAI_API_KEY" not in st.secrets:
    st.error("❌ OPENAI_API_KEY non trouvé dans les secrets Streamlit")
    st.stop()

# ============================================================
# INITIALISATION OPENAI
# ============================================================

openai_client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    project=st.secrets.get("OPENAI_PROJECT_ID")
)

# ============================================================
# FONCTION D'ANALYSE PAR CHATGPT VISION
# ============================================================

def extract_facture_bdc(image_bytes: bytes) -> dict:
    """
    Analyse une facture ou BDC via ChatGPT Vision
    et retourne un JSON structuré.
    """

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
Tu es un expert en analyse de factures et bons de commande à Madagascar.

À partir de l'image fournie :

1. Identifie le type de document :
   - Facture
   - BDC ULYS
   - BDC S2M
   - BDC SUPERMARKET
   - Autre BDC

2. Extrais si visible :
   - fournisseur
   - numero_document
   - date_document

3. Analyse le tableau des articles.
   Ignore les prix, montants, TVA, EAN, PCB, codes internes.

4. Pour chaque ligne d'article, extrais :
   - Désignation
   - Qté

5. Corrige les erreurs OCR évidentes.
6. Regroupe les lignes cassées.

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
        model="gpt-4.1-mini",
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
    # TABLEAU DES ARTICLES
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
    # VALIDATION & EXPORT
    # ========================================================

    if st.button("✅ Valider les données"):
        output = {
            "type_document": result["type_document"],
            "fournisseur": result["fournisseur"],
            "numero_document": result["numero_document"],
            "date_document": result["date_document"],
            "articles": df.to_dict(orient="records"),
            "validated_at": datetime.now().isoformat()
        }

        st.success("🎉 Données validées")
        st.json(output)

# ============================================================
# FOOTER
# ============================================================

st.caption("⚡ Powered by OpenAI Vision — Factures & BDC intelligents")
