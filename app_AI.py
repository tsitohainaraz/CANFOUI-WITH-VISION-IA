# ============================================================
# app_leaderprice_bdc_vision_ai.py
# BDC LEADER PRICE — Extraction Désignation / Qté Cédée
# API : Google Cloud Vision AI (document_text_detection)
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ============================================================
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(
    page_title="BDC LEADER PRICE — Vision AI",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Bon de Commande LEADER PRICE")
st.caption("Extraction fidèle — Qté Cédée (Google Vision AI)")

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
# EXTRACTION LEADER PRICE (LOGIQUE LIGNE PAR LIGNE)
# ============================================================
def extract_bdc_leaderprice(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "LEADER PRICE",
        "numero": "",
        "date": "",
        "articles": []
    }

    # Numéro commande
    m = re.search(r"N[°o]\s*de\s*Commande\s*:?[\s\-]*([A-Z0-9]+)", text, re.IGNORECASE)
    if m:
        result["numero"] = m.group(1)

    # Date
    m = re.search(r"Date\s*:?[\s\-]*(\d{2}/\d{2}/\d{2,4})", text)
    if m:
        result["date"] = m.group(1)

    in_table = False

    for line in lines:
        up = line.upper()

        # Début tableau
        if "DÉSIGNATION" in up and "QTÉ" in up:
            in_table = True
            continue

        if not in_table:
            continue

        # Fin tableau
        if "TOTAL HT" in up:
            break

        # Qté Cédée = nombre finissant par .000
        qty_match = re.search(r"(\d+\.\d{3})", line)
        if not qty_match:
            continue

        qty = int(float(qty_match.group(1)))

        # Nettoyage désignation
        designation = line
        designation = re.sub(r"^\d+\s*", "", designation)          # Ref
        designation = re.sub(r"\d+\.\d{3}.*$", "", designation)    # après Qté
        designation = designation.replace("Pièces", "")
        designation = re.sub(r"\s{2,}", " ", designation)

        if len(designation.strip()) < 5:
            continue

        result["articles"].append({
            "Désignation": designation.strip().title(),
            "Quantité": qty
        })

    return result

# ============================================================
# PIPELINE COMPLET
# ============================================================
def bdc_pipeline(image_bytes: bytes, creds_dict: dict):
    img = preprocess_image(image_bytes)
    raw = google_vision_ocr(img, creds_dict)
    raw = clean_text(raw)
    return extract_bdc_leaderprice(raw), raw

# ============================================================
# INTERFACE STREAMLIT
# ============================================================
uploaded = st.file_uploader(
    "📤 Importer le Bon de Commande LEADER PRICE",
    type=["jpg", "jpeg", "png"]
)

if uploaded:
    image = Image.open(uploaded)
    st.image(image, caption="Aperçu BDC LEADER PRICE", use_column_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Ajoute les credentials Google Vision dans .streamlit/secrets.toml")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("🔍 Analyse avec Vision AI..."):
        result, raw_text = bdc_pipeline(
            buf.getvalue(),
            dict(st.secrets["gcp_vision"])
        )

    # INFOS BDC
    st.subheader("📋 Informations BDC")
    st.write(f"**Client :** {result['client']}")
    st.write(f"**Numéro :** {result['numero']}")
    st.write(f"**Date :** {result['date']}")

    # ARTICLES
    st.subheader("🛒 Articles détectés (LEADER PRICE)")
    if result["articles"]:
        df = pd.DataFrame(result["articles"])
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Aucun article détecté")

    # OCR brut
    with st.expander("🔎 Voir le texte OCR brut"):
        st.text_area("OCR brut", raw_text, height=300)
