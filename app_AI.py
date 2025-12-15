# ============================================================
# ULYS — BDC EXTRACTION FINALE (STABLE & EXECUTABLE)
# Vision AI uniquement (sans OpenCV)
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageOps, ImageFilter
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
st.caption("Extraction robuste (Vision AI)")

# ============================================================
# IMAGE PREPROCESS (simple & sûr)
# ============================================================
def preprocess_image(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.1, percent=150))
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
# EXTRACTION ULYS — RÈGLES MÉTIER
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
    buffer = []

    def is_qty(s: str) -> bool:
        clean = (
            s.replace("D", "")
             .replace("O", "0")
             .replace("I", "1")
        )
        return clean.isdigit() and 1 <= int(clean) <= 999

    def is_noise(s: str) -> bool:
        up = s.upper()
        return (
            "PAQ" in up or
            "/PC" in up or
            "PAQ=" in up or
            re.search(r"\d{2}\.\d{2}\.\d{4}", s)
        )

    def is_section(s: str) -> bool:
        return re.match(r"\d{6}\s+(VINS|CONSIGNE|LIQUEUR)", s.upper())

    for line in lines:
        up = line.upper()

        if "DESCRIPTION DE L'ARTICLE" in up:
            in_table = True
            continue

        if not in_table:
            continue

        if "TOTAL DE LA COMMANDE" in up:
            break

        if is_section(line) or is_noise(line):
            continue

        # ---------- QUANTITÉ ----------
        if buffer and is_qty(line):
            designation = " ".join(buffer)
            designation = re.sub(r"\s{2,}", " ", designation).strip()

            result["articles"].append({
                "Désignation": designation.title(),
                "Quantité": int(line.replace("D", "").replace("O", "0"))
            })

            buffer = []
            continue

        # ---------- DÉSIGNATION ----------
        if any(k in up for k in [
            "VIN", "CONS.", "MAROPARASY", "COTE", "FIANAR", "GRIS"
        ]):
            buffer.append(line)

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
    st.image(image, use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Google Vision manquants")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("Analyse OCR en cours..."):
        result, raw = pipeline(buf.getvalue(), dict(st.secrets["gcp_vision"]))

    st.subheader("📋 Informations BDC")
    st.write("Client :", result["client"])
    st.write("Numéro :", result["numero"])
    st.write("Date :", result["date"])

    st.subheader("🛒 Articles extraits (fidèles)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw, height=350)
