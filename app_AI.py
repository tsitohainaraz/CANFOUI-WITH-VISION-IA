# ============================================================
# app_ulys_bdc.py
# Extraction BDC ULYS — Désignation / Quantité (lignes séparées)
# API : Google Vision AI (document_text_detection)
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
    page_title="BDC ULYS — Extraction fidèle",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Bon de Commande ULYS")
st.caption("Extraction fidèle — Désignation & Quantité (lignes séparées)")

# ============================================================
# PRETRAITEMENT IMAGE
# ============================================================
def preprocess_image(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.1, percent=160))
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
# EXTRACTION BDC ULYS (FORMAT HORIZONTAL)
# ============================================================
def extract_bdc_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # Numéro BDC
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    # Date
    m = re.search(r"Date de la Commande\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # ----------------------------
    # Extraction des lignes articles
    # ----------------------------
    for line in lines:

        line_upper = line.upper()

        # Ignorer les titres / catégories / totaux
        if any(k in line_upper for k in [
            "GTIN", "ARTICLE NO", "DESCRIPTION", "UNITE",
            "TOTAL", "CREÉ", "APPROUVÉ", "VINS ROUGES",
            "VINS BLANCS", "VINS ROSES", "LIQUEUR",
            "DETAILS DU", "BON DE COMMANDE"
        ]):
            continue

        # Chercher une quantité (Qté)
        qty_match = re.search(r"\b(\d{1,3})\b", line)
        if not qty_match:
            continue

        quantite = int(qty_match.group(1))

        # Désignation = texte avant la quantité
        designation = line[:qty_match.start()].strip()

        # Filtre anti-faux positifs
        if len(designation) < 5:
            continue

        if any(k in designation.upper() for k in [
            "PAQ", "/PC", "CONV", "DATE"
        ]):
            continue

        result["articles"].append({
            "Désignation": designation.title(),
            "Quantité": quantite
        })

    return result

# ============================================================
# PIPELINE COMPLET
# ============================================================
def bdc_pipeline(image_bytes: bytes, creds_dict: dict):
    img = preprocess_image(image_bytes)
    raw = google_vision_ocr(img, creds_dict)
    raw = clean_text(raw)
    return extract_bdc_ulys(raw), raw

# ============================================================
# INTERFACE STREAMLIT
# ============================================================
uploaded = st.file_uploader(
    "📤 Importer l’image du Bon de Commande ULYS",
    type=["jpg", "jpeg", "png"]
)

if uploaded:
    image = Image.open(uploaded)
    st.image(image, caption="Aperçu du BDC ULYS", use_column_width=True)

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

    # ARTICLES
    st.subheader("🛒 Articles détectés (lignes séparées)")
    if result["articles"]:
        df = pd.DataFrame(result["articles"])
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Aucun article détecté")

    # OCR DEBUG
    with st.expander("🔎 Voir le texte OCR brut"):
        st.text_area("OCR brut", raw_text, height=300)
