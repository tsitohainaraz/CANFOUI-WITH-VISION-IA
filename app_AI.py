# ============================================================
# app_ulys_bdc_final.py
# BDC ULYS — Extraction fiable Désignation / Quantité
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
    page_title="BDC ULYS — Extraction fiable",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Bon de Commande ULYS")
st.caption("Extraction fidèle — Désignation & Quantité (Vision AI)")

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
# EXTRACTION BDC ULYS (LOGIQUE MÉTIER STRICTE)
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

    # ------------------------------------------------
    # EXTRACTION DES ARTICLES (SEULEMENT DANS LE TABLEAU)
    # ------------------------------------------------
    in_table = False
    current_designation = ""

    for line in lines:
        up = line.upper()

        # Début du tableau
        if "DESCRIPTION DE L'ARTICLE" in up and "QTÉ" in up:
            in_table = True
            continue

        if not in_table:
            continue

        # Fin du tableau
        if "TOTAL DE LA COMMANDE" in up:
            break

        # Ignorer les catégories (VINS ROUGES, BLANCS, etc.)
        if re.match(r"\d{6}\s+(VINS|CONSIGNE|LIQUEUR)", up):
            continue

        # Construire la désignation (multi-lignes)
        if any(k in up for k in ["VIN ", "CONS."]) and not up.endswith("PAQ") and not up.endswith("/PC"):
            current_designation += " " + line
            continue

        # Ignorer unité
        if up in ["PAQ", "/PC"]:
            continue

        # Quantité = nombre seul sur la ligne
        if current_designation and re.fullmatch(r"\d{1,3}", line):
            result["articles"].append({
                "Désignation": current_designation.strip().title(),
                "Quantité": int(line)
            })
            current_designation = ""

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
    st.subheader("🛒 Articles détectés (fidèles)")
    if result["articles"]:
        df = pd.DataFrame(result["articles"])
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Aucun article détecté")

    # OCR DEBUG
    with st.expander("🔎 Voir le texte OCR brut"):
        st.text_area("OCR brut", raw_text, height=300)
