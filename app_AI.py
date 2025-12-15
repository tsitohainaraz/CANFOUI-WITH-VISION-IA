# ============================================================
# BDC LEADER PRICE — VERSION FINALE V3 (QUEUE LOGIC)
# Association correcte VIN / CONSIGNE ↔ Quantités
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
st.caption("Extraction fidèle VIN + CONSIGNE — Vision AI")

# ---------------- IMAGE ----------------
def preprocess_image(b: bytes) -> bytes:
    img = Image.open(BytesIO(b)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=170))
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

# ---------------- EXTRACTION ----------------
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
    designation_queue = []

    def clean_designation(s: str) -> str:
        s = re.sub(r"\b\d{4}\b", "", s)
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip()

    for line in lines:
        up = line.upper()

        # ---- DÉBUT TABLEAU ----
        if up == "RÉF" or "DÉSIGNATION" in up:
            in_table = True
            continue

        if not in_table:
            continue

        if "TOTAL HT" in up:
            break

        # ---- DÉSIGNATION ----
        if (
            not re.search(r"\d+\.\d{3}", line)
            and len(line) >= 15
            and not any(x in up for x in [
                "PIÈCES", "C/12", "PX", "REM",
                "MONTANT", "QTÉ", "DATE", "TOTAL"
            ])
        ):
            designation_queue.append(clean_designation(line))
            continue

        # ---- QUANTITÉ ----
        qty_match = re.search(r"(\d{2,4})\.(\d{3})", line)
        if qty_match and designation_queue:
            qty = int(qty_match.group(1))
            designation = designation_queue.pop(0)

            result["articles"].append({
                "Désignation": designation.title(),
                "Quantité": qty
            })

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

    st.subheader("🛒 Articles détectés (LEADER PRICE)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw, height=300)
