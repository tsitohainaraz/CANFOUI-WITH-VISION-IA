# ============================================================
# app_ulys_bdc_FINAL.py
# BDC ULYS — EXTRACTION FIABLE PAR RÈGLES MÉTIER
# OCR : Google Vision AI
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ============================================================
# CONFIG STREAMLIT
# ============================================================
st.set_page_config(
    page_title="BDC ULYS — Extraction fiable",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Bon de Commande ULYS")
st.caption("Extraction fidèle par règles métier (Vision AI)")

# ============================================================
# IMAGE PREPROCESS (léger, compatible cloud)
# ============================================================
def preprocess_image(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=150))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# ============================================================
# GOOGLE VISION OCR
# ============================================================
def vision_ocr(image_bytes: bytes, creds_dict: dict) -> str:
    creds = Credentials.from_service_account_info(creds_dict)
    client = vision.ImageAnnotatorClient(credentials=creds)
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)
    if response.error.message:
        raise RuntimeError(response.error.message)
    return response.full_text_annotation.text or ""

def clean_text(txt: str) -> str:
    txt = txt.replace("\r", "\n")
    txt = re.sub(r"[^\S\r\n]+", " ", txt)
    return txt.strip()

# ============================================================
# NORMALISATION PRODUITS (ULYS)
# ============================================================
PRODUCT_MAP = {
    "VIN ROUGE COTE DE FIANAR 3L": "Côte de Fianar Rouge 3L",
    "VIN ROUGE COTE DE FIANARA 750ML": "Côte de Fianar Rouge 75 cl",
    "VIN BLANC COTE DE FIANAR 3L": "Côte de Fianar Blanc 3L",
    "VIN BLANC COTE DE FIANARA 750ML": "Côte de Fianar Blanc 75 cl",
    "VIN BLANC DOUX MAROPARASY 750ML": "Blanc doux Maroparasy 75 cl",
    "VIN GRIS COTE DE FIANARA 750ML": "Côte de Fianar Gris 75 cl",
    "VIN ROUGE DOUX MAROPARASY 750ML": "Maroparasy Rouge 75 cl",
    "CONS. CHAN FOUI 75CL": "Consigne Chan Foui 75CL"
}

def normalize_product(text: str):
    t = re.sub(r"[^A-Z0-9 ]", " ", text.upper())
    t = re.sub(r"\s+", " ", t)

    for key, value in PRODUCT_MAP.items():
        if key in t:
            return value
    return None

# ============================================================
# EXTRACTION MÉTIER ULYS (LOGIQUE ROBUSTE)
# ============================================================
def extract_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    rows = []

    for i, line in enumerate(lines):
        product = normalize_product(line)
        if not product:
            continue

        qty = None
        # 🔎 fenêtre métier : 6 lignes suivantes
        for j in range(i + 1, min(i + 7, len(lines))):
            candidate = re.sub(r"[^\d]", "", lines[j])

            if not candidate.isdigit():
                continue

            val = int(candidate)

            # règles anti-erreur OCR
            if 1 <= val <= 300:
                qty = val
                break

        if qty:
            rows.append({"Désignation": product, "Quantité": qty})

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # agrégation finale
    df = df.groupby("Désignation", as_index=False)["Quantité"].sum()
    return df

# ============================================================
# PIPELINE
# ============================================================
def pipeline(image_bytes: bytes, creds: dict):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
    raw = clean_text(raw)
    df = extract_ulys(raw)
    return df, raw

# ============================================================
# UI
# ============================================================
uploaded = st.file_uploader(
    "📤 Importer un Bon de Commande ULYS",
    type=["jpg", "jpeg", "png"]
)

if uploaded:
    image = Image.open(uploaded)
    st.image(image, caption="Aperçu du BDC", use_column_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Ajoute les credentials Google Vision dans .streamlit/secrets.toml")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("🔍 Analyse OCR + règles métier..."):
        df, raw_text = pipeline(buf.getvalue(), dict(st.secrets["gcp_vision"]))

    st.subheader("📋 Informations BDC")
    st.write("**Client :** ULYS")

    st.subheader("🛒 Articles extraits (FIDÈLES)")
    if df.empty:
        st.warning("⚠️ Aucun article détecté")
    else:
        st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw_text, height=350)
