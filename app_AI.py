# ============================================================
# BDC ULYS — EXTRACTION FIDÈLE ET COMPLÈTE
# Client : ULYS
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
    page_title="BDC ULYS — Extraction fidèle",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Bon de Commande ULYS")
st.caption("Extraction fidèle ligne par ligne — Vision AI")

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
# OCR GOOGLE VISION
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
# EXTRACTION BDC ULYS — LOGIQUE MÉTIER
# ============================================================
def extract_bdc_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # -------- MÉTADONNÉES --------
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?[\s\-]*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # -------- TABLE --------
    in_table = False
    current_lines = []

    VALID_QTYS = {"1", "3", "6", "10", "12", "24", "72", "120"}

    def is_designation_start(line):
        up = line.upper()
        return (
            "VIN " in up
            or up.startswith("CONS.")
            or "CONSIGNE" in up
        )

    def clean_designation(lines):
        s = " ".join(lines)
        s = re.sub(r"\b\d{6,}\b", "", s)   # Supprimer GTIN
        s = s.replace("PAQ", "").replace("/PC", "")
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip().title()

    for line in lines:
        up = line.upper()

        # Début tableau
        if "DESCRIPTION DE L'ARTICLE" in up:
            in_table = True
            continue

        if not in_table:
            continue

        # Fin tableau
        if "TOTAL DE LA COMMANDE" in up:
            break

        # Ignorer catégories
        if re.match(r"\d{6}\s+(VINS|LIQUEUR|CONSIGNE)", up):
            continue

        # ---- NOUVEL ARTICLE ----
        if is_designation_start(line):
            if current_lines:
                result["articles"].append({
                    "Désignation": clean_designation(current_lines),
                    "Quantité": None
                })
                current_lines = []

            current_lines.append(line)
            continue

        # ---- TEXTE DE SUITE ----
        if current_lines and not re.search(r"\b\d+\b", line):
            current_lines.append(line)
            continue

        # ---- QUANTITÉ ----
        qty = (
            line.replace("D", "")
                .replace("O", "0")
                .replace("G", "0")
        )

        if qty in VALID_QTYS and current_lines:
            result["articles"].append({
                "Désignation": clean_designation(current_lines),
                "Quantité": int(qty)
            })
            current_lines = []

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
    st.image(image, caption="Aperçu BDC ULYS", use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Google Vision manquants (.streamlit/secrets.toml)")
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

    st.subheader("🛒 Articles détectés (FIDÈLES)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw_text, height=350)
