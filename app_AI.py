# ============================================================
# BDC ULYS — EXTRACTION FIDÈLE (RÈGLES MÉTIER)
# Google Vision AI uniquement (sans OpenCV)
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
st.caption("Extraction fidèle basée sur règles métier (Vision AI)")

# ============================================================
# IMAGE PREPROCESS (LÉGER, SÛR)
# ============================================================
def preprocess_image(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=150))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ============================================================
# OCR — GOOGLE VISION
# ============================================================
def vision_ocr(image_bytes: bytes, creds: dict) -> str:
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=image_bytes)
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

# ============================================================
# EXTRACTION MÉTIER ULYS
# ============================================================
def extract_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # ---------------- METADONNÉES ----------------
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?[\s\-]*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # ---------------- RÈGLES MÉTIER ----------------
    current_designation = None

    def is_designation(line: str) -> bool:
        return (
            len(line) > 12
            and not re.search(r"\d{4,}", line)
            and not any(x in line.upper() for x in [
                "PAQ", "/PC", "DATE", "TOTAL", "FACTEUR",
                "GTIN", "ARTICLE", "UNITE", "CONV"
            ])
        )

    def is_quantity(line: str) -> bool:
        return re.fullmatch(r"\d{1,3}", line) is not None

    for line in lines:
        up = line.upper()

        # STOP TABLE
        if "TOTAL DE LA COMMANDE" in up:
            break

        # IGNORE TECHNIQUE
        if any(x in up for x in [
            "PAQ", "/PC", "1 PAQ", "PC",
            "D3", "CONV", "DATE", "LIVRAISON"
        ]):
            continue

        # DÉSIGNATION
        if is_designation(line):
            current_designation = re.sub(r"\s{2,}", " ", line).title()
            continue

        # QUANTITÉ
        if current_designation and is_quantity(line):
            result["articles"].append({
                "Désignation": current_designation,
                "Quantité": int(line)
            })
            current_designation = None

    return result

# ============================================================
# PIPELINE
# ============================================================
def pipeline(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
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
    st.image(image, use_column_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Vision AI manquants")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("🔍 Analyse Vision AI..."):
        result, raw = pipeline(buf.getvalue(), dict(st.secrets["gcp_vision"]))

    st.subheader("📋 Informations BDC")
    st.write("**Client :**", result["client"])
    st.write("**Numéro :**", result["numero"])
    st.write("**Date :**", result["date"])

    st.subheader("🛒 Articles extraits (FIDÈLES)")
    df = pd.DataFrame(result["articles"])

    if df.empty:
        st.warning("⚠️ Aucun article détecté — vérifier la qualité du scan")
    else:
        st.dataframe(df, use_container_width=True)
        st.success(f"✅ {len(df)} lignes détectées")

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw, height=300)
