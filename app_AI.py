# ============================================================
# BDC ULYS — EXTRACTION FIDÈLE (SANS EMPTY / SANS FUSION)
# API : Google Vision AI
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
    page_title="BDC ULYS — Extraction fiable",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Bon de Commande ULYS")
st.caption("Extraction fidèle des articles — Vision AI")

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
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[^\S\r\n]+", " ", text)
    return text.strip()

# ============================================================
# EXTRACTION BDC ULYS — LOGIQUE CORRECTE
# 1 désignation = 1 quantité
# ============================================================
def extract_bdc_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # ---------------- MÉTADONNÉES ----------------
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?\s*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # ---------------- RÈGLES MÉTIER ----------------
    VALID_QTY = {
        "1", "2", "3", "6", "10", "12",
        "24", "36", "48", "60", "72", "120", "231"
    }

    def is_category(line: str) -> bool:
        return bool(re.match(r"\d{6}\s+(VINS|LIQUEUR|CONSIGNE)", line.upper()))

    def is_noise(line: str) -> bool:
        up = line.upper()
        return (
            up in {"PAQ", "/PC", "PC"}
            or "PAQ=" in up
            or "PC=" in up
            or re.search(r"\d{2}\.\d{2}\.\d{4}", up)
        )

    def clean_designation(s: str) -> str:
        s = re.sub(r"\b\d{6,}\b", "", s)  # codes GTIN
        s = s.replace("PAQ", "").replace("/PC", "")
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip().title()

    # ---------------- PARSING ----------------
    current_designation = None

    for line in lines:
        # ignorer bruit et catégories
        if is_category(line) or is_noise(line):
            continue

        # quantité → clôture article
        if line in VALID_QTY and current_designation:
            result["articles"].append({
                "Désignation": current_designation,
                "Quantité": int(line)
            })
            current_designation = None
            continue

        # nouvelle désignation (remplace l’ancienne)
        if not re.fullmatch(r"\d+", line):
            cleaned = clean_designation(line)
            if len(cleaned) > 10:
                current_designation = cleaned

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
        st.error("❌ Credentials Google Vision manquants")
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

    st.subheader("🛒 Articles extraits (fidèles)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw_text, height=300)
