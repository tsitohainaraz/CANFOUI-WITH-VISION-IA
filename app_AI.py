# ============================================================
# BDC ULYS — EXTRACTION FIDÈLE AVEC NORMALISATION MÉTIER
# Vision AI + règles métier
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ============================================================
# PRODUITS STANDARDISÉS (EXTRAIT DE TON EXCEL)
# ============================================================

PRODUITS = {
    "Côte de Fianar Rouge 3L": [
        "VIN ROUGE COTE DE FIANAR 3L",
        "VIN ROUGE COTE DE FIANARA 3L",
        "VIN ROUGE COTE DE FIANAR",
    ],
    "Côte de Fianar Rouge 75 cl": [
        "VIN ROUGE COTE DE FIANARA 750 ML NU",
        "VIN ROUGE COTE DE FIANAR 750ML",
    ],
    "Vin Blanc Doux Maroparasy 75 cl": [
        "VIN BLANC DOUX MAROPARASY 750 ML NU",
    ],
    "Vin Gris Côte de Fianar 75 cl": [
        "VIN GRIS COTE DE FIANARA 750ML NU",
    ],
    "Vin Rouge Doux Maroparasy 75 cl": [
        "VIN ROUGE DOUX MAROPARASY 750 ML NU",
    ],
    "Consigne Chan Foui 75CL": [
        "CONS. CHAN FOUI 75CL",
        "CONS CHAN FOUI 75CL",
    ],
}

# ============================================================
# STREAMLIT CONFIG
# ============================================================

st.set_page_config("BDC ULYS", "🧾")
st.title("🧾 BDC ULYS — Extraction métier fidèle")

# ============================================================
# OCR
# ============================================================

def preprocess(img_bytes):
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(1.2, 180))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

def ocr_vision(img_bytes, creds):
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=img_bytes)
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

# ============================================================
# NORMALISATION PRODUIT
# ============================================================

def normaliser_produit(designation):
    d = designation.upper()
    for produit, variantes in PRODUITS.items():
        for v in variantes:
            if v in d:
                return produit
    return None

# ============================================================
# EXTRACTION ULYS
# ============================================================

def extract_ulys(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    articles = []

    current_designation = None
    attente_qte = False

    for line in lines:
        up = line.upper()

        # Désignation candidate
        if "VIN " in up or "CONS" in up:
            prod = normaliser_produit(up)
            if prod:
                current_designation = prod
                attente_qte = False
            continue

        # Détection unité
        if up in ["PAQ", "/PC"]:
            attente_qte = True
            continue

        # Quantité valide (métier)
        if attente_qte and current_designation:
            clean = re.sub(r"[^\d]", "", line)
            if clean.isdigit():
                qte = int(clean)
                if 1 <= qte <= 300:
                    articles.append({
                        "Désignation": current_designation,
                        "Quantité": qte
                    })
                    attente_qte = False

    # Regroupement final
    df = pd.DataFrame(articles)
    if not df.empty:
        df = df.groupby("Désignation", as_index=False)["Quantité"].sum()

    return df

# ============================================================
# UI
# ============================================================

uploaded = st.file_uploader("📤 Importer le BDC ULYS", ["jpg", "png", "jpeg"])

if uploaded:
    img = Image.open(uploaded)
    st.image(img, use_container_width=True)

    buf = BytesIO()
    img.save(buf, format="JPEG")

    raw = ocr_vision(preprocess(buf.getvalue()), dict(st.secrets["gcp_vision"]))
    df = extract_ulys(raw)

    st.subheader("🛒 Articles (FIDÈLES)")
    st.dataframe(df, use_container_width=True)

    with st.expander("OCR brut"):
        st.text_area("", raw, height=300)
