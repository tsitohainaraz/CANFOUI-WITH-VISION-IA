# ============================================================
# BDC ULYS — EXTRACTION FIDÈLE (Vision AI ONLY)
# Aucun OpenCV — 100% Streamlit Cloud compatible
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
st.caption("Extraction robuste — aucune ligne ratée")

# ============================================================
# IMAGE PREPROCESS (SANS OPENCV)
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
        raise RuntimeError(response.error.message)

    return response.full_text_annotation.text or ""

def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[^\S\r\n]+", " ", text)
    return text.strip()

# ============================================================
# SAFE INTEGER EXTRACTION (ANTI ValueError)
# ============================================================
def safe_extract_int(s: str):
    if not s:
        return None

    s = s.replace("D", "").replace("O", "0").replace("G", "0")
    match = re.search(r"\b(\d{1,3})\b", s)
    if match:
        return int(match.group(1))
    return None

# ============================================================
# ULYS — EXTRACTION LOGIQUE FIDÈLE
# ============================================================
def extract_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # ---------------- METADATA ----------------
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?\s*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # ---------------- TABLE PARSING ----------------
    in_table = False
    current_designation = None
    waiting_qty = False

    def clean_designation(s: str) -> str:
        s = re.sub(r"\b\d{6,}\b", "", s)   # codes longs
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

        # Ignorer titres de sections
        if re.match(r"\d{6}\s+(VINS|CONSIGNE|LIQUEUR)", up):
            continue

        # ---------------- DESIGNATION ----------------
        if (
            ("VIN " in up or "CONS." in up)
            and not re.search(r"\d{6,}", line)
            and len(line) > 15
        ):
            current_designation = clean_designation(line)
            waiting_qty = False
            continue

        # ---------------- UNITÉ ----------------
        if up in ["PAQ", "/PC"]:
            waiting_qty = True
            continue

        # ---------------- QUANTITÉ ----------------
        if current_designation and waiting_qty:
            qty = safe_extract_int(line)
            if qty is not None:
                result["articles"].append({
                    "Désignation": current_designation,
                    "Quantité": qty
                })
                waiting_qty = False

    return result

# ============================================================
# PIPELINE
# ============================================================
def pipeline(image_bytes: bytes, creds_dict: dict):
    img = preprocess_image(image_bytes)
    raw = google_vision_ocr(img, creds_dict)
    raw = clean_text(raw)
    return extract_ulys(raw), raw

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
        st.error("❌ Ajoute les credentials Vision AI dans secrets.toml")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("🔍 Analyse Vision AI en cours..."):
        result, raw_text = pipeline(
            buf.getvalue(),
            dict(st.secrets["gcp_vision"])
        )

    st.subheader("📋 Informations BDC")
    st.write("**Client :**", result["client"])
    st.write("**Numéro :**", result["numero"])
    st.write("**Date :**", result["date"])

    st.subheader("🛒 Articles extraits (fidèles)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR brut", raw_text, height=300)
