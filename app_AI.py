# ============================================================
# BDC LEADER PRICE — VERSION OCR RÉEL (ROBUSTE)
# API : Google Vision AI
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ---------------- STREAMLIT ----------------
st.set_page_config(page_title="BDC LEADER PRICE", page_icon="🧾")
st.title("🧾 Bon de Commande LEADER PRICE")
st.caption("Extraction fidèle — OCR réel Vision AI")

# ---------------- IMAGE ----------------
def preprocess_image(b: bytes) -> bytes:
    img = Image.open(BytesIO(b)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.1, percent=160))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# ---------------- OCR ----------------
def vision_ocr(b: bytes, creds: dict) -> str:
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=b)
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

# ---------------- EXTRACTION LEADER PRICE ----------------
def extract_leaderprice(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "LEADER PRICE",
        "numero": "",
        "date": "",
        "articles": []
    }

    # Métadonnées
    m = re.search(r"BCD\d+", text)
    if m:
        result["numero"] = m.group(0)

    m = re.search(r"Date\s*(\d{2}/\d{2}/\d{2,4})", text)
    if m:
        result["date"] = m.group(1)

    in_table = False
    current_designation = ""

    def clean_designation(s: str) -> str:
        s = re.sub(r"\b\d{4}\b", "", s)        # refs
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip()

    for line in lines:
        up = line.upper()

        # Début tableau
        if "DÉSIGNATION" in up and "QTÉ" in up:
            in_table = True
            continue

        if not in_table:
            continue

        # Fin tableau
        if "TOTAL HT" in up:
            break

        # Désignation = contexte
        if any(k in up for k in [
            "VIN ", "CONSIGNE"
        ]) and not re.search(r"\d+\.\d{3}", line):
            current_designation = clean_designation(line)
            continue

        # Quantité = événement
        qty_match = re.search(r"(\d{2,4})\.(\d{3})", line)
        if qty_match and current_designation:
            qty = int(qty_match.group(1))
            result["articles"].append({
                "Désignation": current_designation.title(),
                "Quantité": qty
            })
            continue

    return result

# ---------------- PIPELINE ----------------
def pipeline(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
    return extract_leaderprice(raw), raw

# ---------------- UI ----------------
uploaded = st.file_uploader("📤 Importer BDC LEADER PRICE", ["jpg", "jpeg", "png"])

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Vision AI manquants")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    result, raw = pipeline(buf.getvalue(), dict(st.secrets["gcp_vision"]))

    st.subheader("📋 Informations BDC")
    st.write("Client :", result["client"])
    st.write("Numéro :", result["numero"])
    st.write("Date :", result["date"])

    st.subheader("🛒 Articles détectés")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw, height=300)
