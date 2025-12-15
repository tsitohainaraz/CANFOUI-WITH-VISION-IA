# ============================================================
# app_supermaki_bdc.py
# Extraction fiable BDC SUPERMAKI (Désignation / Quantité)
# Google Vision AI + Streamlit
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ============================================================
# CONFIG STREAMLIT
# ============================================================
st.set_page_config(
    page_title="BDC SUPERMAKI — Extraction fidèle",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 BDC SUPERMAKI — Extraction fidèle")
st.caption("Google Vision AI · Désignation & Quantité exactes")

# ============================================================
# PRETRAITEMENT IMAGE
# ============================================================
def preprocess_image(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# ============================================================
# GOOGLE VISION OCR
# ============================================================
def google_vision_ocr(image_bytes: bytes, creds_dict: dict) -> str:
    creds = Credentials.from_service_account_info(creds_dict)
    client = vision.ImageAnnotatorClient(credentials=creds)
    image = vision.Image(content=image_bytes)

    response = client.document_text_detection(image=image)
    if response.error.message:
        raise Exception(response.error.message)

    return response.full_text_annotation.text or ""

def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[^\S\r\n]+", " ", text)
    return text.strip()

# ============================================================
# NORMALISATION DES DÉSIGNATIONS
# ============================================================
def normalize_designation(designation: str) -> str:
    d = designation.upper()
    d = re.sub(r"\s+", " ", d)

    if "COTE DE FIANAR" in d:
        if "ROUGE" in d:
            return "Côte de Fianar Rouge 75 cl"
        if "BLANC" in d:
            return "Côte de Fianar Blanc 75 cl"
        if "ROSE" in d or "ROSÉ" in d:
            return "Côte de Fianar Rosé 75 cl"
        if "GRIS" in d:
            return "Côte de Fianar Gris 75 cl"
        return "Côte de Fianar Rouge 75 cl"

    if "CONS" in d and "CHAN" in d:
        return "CONS 2000 CHANFOUI"

    if "MAROPARASY" in d:
        return "Maroparasy Rouge 75 cl"

    return designation.title()

# ============================================================
# EXTRACTION BDC SUPERMAKI (PAR BLOCS VERTICAUX)
# ============================================================
def extract_bdc_supermaki(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "SUPERMAKI",
        "numero": "",
        "date": "",
        "adresse_livraison": "",
        "articles": []
    }

    # Numéro BDC
    m = re.search(r"Bon de commande n[°o]\s*(\d{8})", text)
    if m:
        result["numero"] = m.group(1)

    # Date
    m = re.search(r"Date\s+[ée]mission\s*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # Adresse livraison
    for i, l in enumerate(lines):
        if "Adresse de livraison" in l and i + 1 < len(lines):
            result["adresse_livraison"] = lines[i + 1]
            break

    # --- EXTRACTION PAR BLOCS ---
    i = 0
    while i < len(lines):

        # REF = exactement 6 chiffres
        if re.fullmatch(r"\d{6}", lines[i]):

            # Vérifier qu'il reste assez de lignes
            if i + 5 < len(lines):
                ean = lines[i + 1]
                designation = lines[i + 2]
                pcb = lines[i + 3]
                nb_colis = lines[i + 4]
                quantite = lines[i + 5]

                if (
                    re.fullmatch(r"\d{13}\.?", ean) and
                    any(k in designation.upper() for k in ["COTE", "CONS", "MAROPARASY"]) and
                    pcb.isdigit() and
                    nb_colis.isdigit() and
                    quantite.isdigit()
                ):
                    result["articles"].append({
                        "Désignation": normalize_designation(designation),
                        "Quantité": int(quantite)
                    })
                    i += 6
                    continue

        i += 1

    return result

# ============================================================
# PIPELINE COMPLET
# ============================================================
def bdc_pipeline(image_bytes: bytes, creds_dict: dict):
    img = preprocess_image(image_bytes)
    raw = google_vision_ocr(img, creds_dict)
    raw = clean_text(raw)
    return extract_bdc_supermaki(raw), raw

# ============================================================
# INTERFACE STREAMLIT
# ============================================================
uploaded = st.file_uploader(
    "📤 Importer l’image du BDC SUPERMAKI",
    type=["jpg", "jpeg", "png"]
)

if uploaded:
    image = Image.open(uploaded)
    st.image(image, caption="Aperçu du BDC", use_column_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Ajoute les credentials Google Vision dans .streamlit/secrets.toml")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("🔍 Analyse avec Google Vision AI..."):
        try:
            result, raw_text = bdc_pipeline(
                buf.getvalue(),
                dict(st.secrets["gcp_vision"])
            )
        except Exception as e:
            st.error(str(e))
            st.stop()

    # INFOS BDC
    st.subheader("📋 Informations BDC")
    st.write(f"**Client :** {result['client']}")
    st.write(f"**Numéro BDC :** {result['numero']}")
    st.write(f"**Date :** {result['date']}")
    st.write(f"**Adresse livraison :** {result['adresse_livraison']}")

    # ARTICLES
    st.subheader("🛒 Articles détectés (fidèles)")
    if result["articles"]:
        df = pd.DataFrame(result["articles"])
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Aucun article détecté")

    # OCR DEBUG
    with st.expander("🔎 Voir le texte OCR brut"):
        st.text_area("OCR brut", raw_text, height=300)
