# ============================================================
# app_ulys_bdc_vision_ai_FINAL.py
# BDC ULYS — EXTRACTION COMPLÈTE DE TOUTES LES LIGNES
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
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(
    page_title="BDC ULYS — Vision AI (complet)",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Bon de Commande ULYS")
st.caption("Extraction COMPLÈTE — aucune ligne manquante (Vision AI)")

# ============================================================
# IMAGE PREPROCESS
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
# EXTRACTION ULYS — LOGIQUE "1 QUANTITÉ = 1 LIGNE"
# ============================================================
def extract_bdc_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # Métadonnées
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?[\s\-]*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # -----------------------------
    # PARSING ROBUSTE
    # -----------------------------
    in_table = False
    current_designation = ""
    waiting_qty = False

    def is_valid_qty(s: str) -> bool:
        s = s.replace("D", "").replace("O", "0").replace("G", "0")
        return re.fullmatch(r"\d{1,3}", s) is not None

    def clean_designation(s: str) -> str:
        s = re.sub(r"\b\d{6,}\b", "", s)  # codes longs
        s = s.replace("PAQ", "").replace("/PC", "")
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip()

    for line in lines:
        up = line.upper()

        # Début du tableau (tolérant OCR)
        if "DESCRIPTION DE L'ARTICLE" in up:
            in_table = True
            continue

        if not in_table:
            continue

        # Fin du tableau
        if "TOTAL DE LA COMMANDE" in up:
            break

        # Ignorer sections
        if re.match(r"\d{6}\s+(VINS|CONSIGNE|LIQUEUR)", up):
            continue

        # -------------------------
        # DÉSIGNATION = CONTEXTE
        # -------------------------
        if ("VIN " in up or "CONS." in up) and not re.match(r"\d{6,}", line):
            current_designation = clean_designation(line)
            waiting_qty = False
            continue

        # -------------------------
        # UNITÉ → attente quantité
        # -------------------------
        if up in ["PAQ", "/PC"]:
            waiting_qty = True
            continue

        # -------------------------
        # QUANTITÉ = ÉVÉNEMENT
        # -------------------------
        if current_designation and waiting_qty:
            clean = (
                line.replace("D", "")
                    .replace("O", "0")
                    .replace("G", "0")
            )
            if is_valid_qty(clean):
                result["articles"].append({
                    "Désignation": current_designation.title(),
                    "Quantité": int(clean)
                })
                # ⚠️ on NE RÉINITIALISE PAS la désignation
                waiting_qty = False
                continue

    return result

# ============================================================
# PIPELINE
# ============================================================
def bdc_pipeline(image_bytes: bytes, creds_dict: dict):
    img = preprocess_image(image_bytes)
    raw = google_vision_ocr(img, creds_dict)
    raw = clean_text(raw)
    return extract_bdc_ulys(raw), raw

# ============================================================
# UI
# ============================================================
uploaded = st.file_uploader(
    "📤 Importer le Bon de Commande ULYS",
    type=["jpg", "jpeg", "png"]
)

if uploaded:
    image = Image.open(uploaded)
    st.image(image, caption="Aperçu BDC ULYS", use_column_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Ajoute les credentials Google Vision dans .streamlit/secrets.toml")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("🔍 Analyse Vision AI..."):
        result, raw_text = bdc_pipeline(
            buf.getvalue(),
            dict(st.secrets["gcp_vision"])
        )

    st.subheader("📋 Informations BDC")
    st.write(f"**Client :** {result['client']}")
    st.write(f"**Numéro :** {result['numero']}")
    st.write(f"**Date :** {result['date']}")

    st.subheader("🛒 Articles détectés (COMPLETS)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw_text, height=300)

