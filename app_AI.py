# ============================================================
# BDC ULYS — EXTRACTION FIABLE (Vision AI)
# Désignation multilignes + Quantité robuste
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ------------------------------------------------------------
# STREAMLIT
# ------------------------------------------------------------
st.set_page_config(page_title="BDC ULYS — Stable", page_icon="🧾")
st.title("🧾 Bon de Commande ULYS (fiable)")
st.caption("Vision AI — logique robuste anti-OCR bruité")

# ------------------------------------------------------------
# IMAGE PREPROCESS
# ------------------------------------------------------------
def preprocess_image(b: bytes) -> bytes:
    img = Image.open(BytesIO(b)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.1, percent=160))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# ------------------------------------------------------------
# OCR
# ------------------------------------------------------------
def vision_ocr(b: bytes, creds: dict) -> str:
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=b)
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

# ------------------------------------------------------------
# EXTRACTION ULYS (LOGIQUE STABLE)
# ------------------------------------------------------------
def extract_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # -------- META --------
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?[\s]*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # -------- PRODUITS ULYS (clé métier) --------
    PRODUCT_KEYWORDS = [
        "VIN ROUGE", "VIN BLANC", "VIN GRIS",
        "VIN DOUX", "COTE DE FIANAR",
        "MAROPARASY", "AMBALAVAO",
        "CONS. CHAN FOUI"
    ]

    def is_product_line(l):
        up = l.upper()
        return any(k in up for k in PRODUCT_KEYWORDS)

    def is_quantity(l):
        l = l.replace("D", "").replace("O", "0")
        return re.fullmatch(r"\d{1,3}", l) is not None

    i = 0
    while i < len(lines):
        line = lines[i]

        # ---- DÉTECTION DÉSIGNATION MULTI-LIGNES ----
        if is_product_line(line):
            designation = line

            # concat lignes suivantes si elles complètent le nom
            j = i + 1
            while j < len(lines) and not is_quantity(lines[j]) and "PAQ" not in lines[j]:
                if not re.search(r"\d{6,}", lines[j]):
                    designation += " " + lines[j]
                j += 1

            designation = re.sub(r"\s{2,}", " ", designation).strip().title()

            # ---- CHERCHER LA QUANTITÉ DANS LES 10 LIGNES SUIVANTES ----
            qty = None
            for k in range(j, min(j + 10, len(lines))):
                if is_quantity(lines[k]):
                    qty = int(lines[k])
                    break

            if qty is not None:
                result["articles"].append({
                    "Désignation": designation,
                    "Quantité": qty
                })

            i = j
            continue

        i += 1

    return result

# ------------------------------------------------------------
# PIPELINE
# ------------------------------------------------------------
def pipeline(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
    return extract_ulys(raw), raw

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
uploaded = st.file_uploader("📤 Importer le BDC ULYS", ["jpg", "jpeg", "png"])

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Vision manquants")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    result, raw = pipeline(buf.getvalue(), dict(st.secrets["gcp_vision"]))

    st.subheader("📋 Informations BDC")
    st.write("Client :", result["client"])
    st.write("Numéro :", result["numero"])
    st.write("Date :", result["date"])

    st.subheader("🛒 Articles détectés (FIDÈLES)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw, height=350)
