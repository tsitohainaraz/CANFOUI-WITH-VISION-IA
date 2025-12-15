# ============================================================
# BDC ULYS — EXTRACTION STABLE ET COMPLÈTE
# Google Vision AI — document_text_detection
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
    page_title="BDC ULYS — Vision AI",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Bon de Commande — ULYS")
st.caption("Extraction fiable (aucune ligne manquante)")

# ============================================================
# IMAGE PREPROCESSING
# ============================================================
def preprocess_image(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.3, percent=190))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# ============================================================
# GOOGLE VISION OCR
# ============================================================
def vision_ocr(image_bytes: bytes, creds_dict: dict) -> str:
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

    # ---------------- METADONNEES ----------------
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?[\s\-]*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # ---------------- TABLE ----------------
    in_table = False
    designation_parts = []
    waiting_qty = False

    def clean_designation(parts):
        s = " ".join(parts)
        s = re.sub(r"\b\d{6,}\b", "", s)     # GTIN
        s = s.replace("PAQ", "").replace("/PC", "")
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip().title()

    def normalize_qty(s):
        s = (
            s.replace("D", "")
             .replace("O", "0")
             .replace("G", "0")
        )
        return int(s) if re.fullmatch(r"\d{1,3}", s) else None

    for line in lines:
        up = line.upper()

        # Début du tableau
        if "DESCRIPTION DE L'ARTICLE" in up:
            in_table = True
            continue

        if not in_table:
            continue

        # Fin du tableau
        if "TOTAL DE LA COMMANDE" in up:
            break

        # Ignorer titres de catégories
        if re.match(r"\d{6}\s+(VINS|CONSIGNE|LIQUEUR)", up):
            continue

        # ---------------- DÉSIGNATION (ACCUMULATION) ----------------
        if (
            not re.search(r"\b\d+\b", line)
            and up not in ["PAQ", "/PC"]
            and not re.search(r"\d{2}/\d{2}/\d{4}", line)
        ):
            designation_parts.append(line)
            continue

        # ---------------- UNITÉ ----------------
        if up in ["PAQ", "/PC"]:
            waiting_qty = True
            continue

        # ---------------- QUANTITÉ ----------------
        if waiting_qty and designation_parts:
            qty = normalize_qty(line)
            if qty is not None:
                result["articles"].append({
                    "Désignation": clean_designation(designation_parts),
                    "Quantité": qty
                })
                designation_parts = []
                waiting_qty = False

    return result

# ============================================================
# PIPELINE
# ============================================================
def bdc_pipeline(image_bytes: bytes, creds_dict: dict):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds_dict)
    raw = clean_text(raw)
    return extract_bdc_ulys(raw), raw

# ============================================================
# UI
# ============================================================
uploaded = st.file_uploader(
    "📤 Importer un Bon de Commande ULYS",
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

    with st.spinner("🔍 Analyse Vision AI en cours..."):
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
        st.text_area("OCR brut", raw_text, height=300)
