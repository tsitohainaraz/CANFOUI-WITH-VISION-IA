# ============================================================
# app_ulys_bdc_FINAL_STABLE.py
# Extraction ULYS robuste (Vision AI + règles métier)
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(
    page_title="BDC ULYS — Extraction fiable",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Bon de Commande ULYS")
st.caption("Extraction fidèle par règles métier")

# ============================================================
# OCR
# ============================================================
def preprocess_image(image_bytes):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=150))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def vision_ocr(image_bytes, creds):
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=image_bytes)
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

def clean_text(txt):
    txt = txt.replace("\r", "\n")
    txt = re.sub(r"[^\S\r\n]+", " ", txt)
    return txt.strip()

# ============================================================
# PRODUITS ULYS (MOTS CLÉS)
# ============================================================
PRODUCT_KEYWORDS = [
    "VIN ROUGE COTE DE",
    "VIN BLANC COTE DE",
    "VIN BLANC DOUX MAROPARASY",
    "VIN ROUGE DOUX MAROPARASY",
    "VIN GRIS COTE DE",
    "CONS. CHAN FOUI 75CL",
    "CONS. CHAN FOUL 75CL"
]

def normalize_designation(text):
    t = re.sub(r"[^A-Z0-9 ]", " ", text.upper())
    t = re.sub(r"\s+", " ", t)
    return t.strip()

# ============================================================
# EXTRACTION MÉTIER (CLÉ)
# ============================================================
def extract_ulys(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    rows = []

    i = 0
    while i < len(lines):
        line = normalize_designation(lines[i])

        # Détection début article
        if any(k in line for k in PRODUCT_KEYWORDS):
            designation_parts = [line]
            qty = None

            # Fenêtre métier
            for j in range(i + 1, min(i + 10, len(lines))):
                candidate = normalize_designation(lines[j])

                # Reconstruction désignation
                if (
                    not re.search(r"\d{1,3}", candidate)
                    and not any(x in candidate for x in ["PAQ", "/PC", "PC"])
                ):
                    designation_parts.append(candidate)

                # Détection quantité
                num = re.sub(r"[^\d]", "", candidate)
                if num.isdigit():
                    val = int(num)
                    if 1 <= val <= 300:
                        qty = val
                        break

            designation = " ".join(designation_parts)
            designation = re.sub(r"\s+", " ", designation)

            if qty:
                rows.append({
                    "Désignation": designation.title(),
                    "Quantité": qty
                })

            i = j
        i += 1

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Agrégation finale
    df = df.groupby("Désignation", as_index=False)["Quantité"].sum()
    return df

# ============================================================
# PIPELINE
# ============================================================
def pipeline(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
    raw = clean_text(raw)
    df = extract_ulys(raw)
    return df, raw

# ============================================================
# UI
# ============================================================
uploaded = st.file_uploader(
    "📤 Importer un BDC ULYS",
    type=["jpg", "jpeg", "png"]
)

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_column_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Vision manquants")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("Analyse en cours..."):
        df, raw = pipeline(buf.getvalue(), dict(st.secrets["gcp_vision"]))

    st.subheader("🛒 Articles extraits (FIDÈLES)")
    if df.empty:
        st.warning("⚠️ Aucun article détecté")
    else:
        st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw, height=350)
