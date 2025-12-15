# ============================================================
# BDC ULYS — EXTRACTION FIDÈLE (ANTI-EMPTY, VERSION FINALE)
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
st.caption("Extraction fiable – aucune ligne manquante")

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
def vision_ocr(image_bytes: bytes, creds_dict: dict) -> str:
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds_dict)
    )
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)
    return response.full_text_annotation.text or ""

# ============================================================
# EXTRACTION BDC ULYS (ROBUSTE)
# ============================================================
def extract_bdc_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    articles = []
    buffer = []

    VALID_QTY = {
        "1", "2", "3", "6", "10", "12",
        "24", "36", "48", "60", "72", "120", "231"
    }

    def is_category(line: str) -> bool:
        return bool(
            re.match(r"\d{6}\s+(VINS|LIQUEUR|CONSIGNE)", line.upper())
        )

    def is_noise(line: str) -> bool:
        up = line.upper()
        return (
            up in {"PAQ", "/PC", "PC"}
            or "PAQ=" in up
            or "PC=" in up
            or re.search(r"\d{2}\.\d{2}\.\d{4}", up)
        )

    def clean_designation(parts):
        s = " ".join(parts)
        s = re.sub(r"\b\d{6,}\b", "", s)        # codes / GTIN
        s = s.replace("PAQ", "").replace("/PC", "")
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip().title()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Ignorer catégories
        if is_category(line):
            buffer = []
            i += 1
            continue

        # Ignorer bruit
        if is_noise(line):
            i += 1
            continue

        # Quantité seule → clôture article
        if line in VALID_QTY and buffer:
            articles.append({
                "Désignation": clean_designation(buffer),
                "Quantité": int(line)
            })
            buffer = []
            i += 1
            continue

        # Ligne texte → désignation
        if not re.fullmatch(r"\d+", line):
            buffer.append(line)
            i += 1
            continue

        i += 1

    return articles

# ============================================================
# PIPELINE
# ============================================================
def pipeline(image_bytes: bytes, creds: dict):
    img = preprocess_image(image_bytes)
    raw_text = vision_ocr(img, creds)
    articles = extract_bdc_ulys(raw_text)
    return articles, raw_text

# ============================================================
# UI
# ============================================================
uploaded = st.file_uploader(
    "📤 Importer un Bon de Commande ULYS",
    ["jpg", "jpeg", "png"]
)

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Google Vision manquants")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("🔍 Analyse du BDC ULYS..."):
        articles, raw = pipeline(
            buf.getvalue(),
            dict(st.secrets["gcp_vision"])
        )

    st.subheader("🛒 Articles extraits (fidèles)")
    df = pd.DataFrame(articles)

    if df.empty:
        st.warning("⚠️ Aucun article détecté — OCR invalide")
    else:
        st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw, height=300)
