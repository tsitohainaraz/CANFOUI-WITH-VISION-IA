# ============================================================
# BDC ULYS — EXTRACTION PRÉCISE PAR LISTE BLANCHE
# API : Google Vision AI
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd
import unicodedata

# ============================================================
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(
    page_title="BDC ULYS — Extraction précise",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Bon de Commande ULYS")
st.caption("Extraction précise basée sur désignations standardisées")

# ============================================================
# LISTE BLANCHE DES DÉSIGNATIONS (FOURNIE PAR TOI)
# ============================================================
RAW_PRODUCTS = [
    "Côte de Fianar Rouge 75 cl",
    "Côte de Fianar Rouge 37 cl",
    "Côte de Fianar Rouge 3L",
    "Côte de Fianar Blanc 3L",
    "Côte de Fianar Rosé 3L",
    "Blanc doux Maroparasy 3L",
    "Côte de Fianar Blanc 75 cl",
    "Côte de Fianar Blanc 37 cl",
    "Côte de Fianar Rosé 75 cl",
    "Côte de Fianar Rosé 37 cl",
    "Côte de Fianar Gris 75 cl",
    "Côte de Fianar Gris 37 cl",
    "Maroparasy Rouge 75 cl",
    "Maroparasy Rouge 37 cl",
    "Blanc doux Maroparasy 75 cl",
    "Blanc doux Maroparasy 37 cl",
    "Côteau d'Ambalavao Rouge 75 cl",
    "Côteau d'Ambalavao Blanc 75 cl",
    "Côteau d'Ambalavao Rosé 75 cl",
    "Côteau d'Ambalavao Spécial 75 cl",
    "Aperao Orange 75 cl",
    "Aperao Pêche 75 cl",
    "Aperao Ananas 75 cl",
    "Aperao Epices 75 cl",
    "Aperao Ratafia 75 cl",
    "Aperao Eau de vie 75 cl",
    "Aperao Eau de vie 37 cl",
    "Vin de Champêtre 100 cl",
    "Vin de Champêtre 50 cl",
    "Jus de raisin Rouge 70 cl",
    "Jus de raisin Rouge 20 cl",
    "Jus de raisin Blanc 70 cl",
    "Jus de raisin Blanc 20 cl",
    "Sambatra 20 cl",
    "Vin rouge Côte de fianar btl 75 CL nu",
    "Vin rouge Côte de fianar btl 37 CL nu",
    "Vin rouge 3l cote de fianar",
    "Vin blanc 3l cote de fianar",
    "Vin Rose 3L COTE DE FIANAR",
    "Vin blanc côte de fianar btl 75 CL nu",
    "Vin rose cote de fianar btl 75 CL",
    "Vin Gris côte de fianar btl 75 CL nu",
    "VIN APERITIF ROUGE MAROPARASY 75CL",
    "VIN BLANC DOUX MAROPARASY 75CL",
    "Vin rouge coteau d'amb/vao btl 75 CL",
    "Vin Blanc Ambalavao 750ML NU",
    "Côteau d'Ambalavao Cuvee Spécial Rouge 75 CL",
    "JUS DE RAISIN ROUGE 75CL LP7",
    "JUS DE RAISIN BLANC 75CL LP7",
    "VIN ROUGE COTE DE FIANARA 750 ML NU",
    "VIN ROUGE COTE DE FIANARA 370 ML NU",
    "VIN BLANC COTE DE FIANARA 750 ML NU",
    "VIN ROSE COTE DE FIANARA 750 ML NU",
    "VIN GRIS COTE DE FIANARA 750 ML NU",
    "APERITIF MAROPARASY 75 CL",
    "VIN BLANC DOUX MAROPARASY 750 ML NU",
    "VIN DE MADAGASCAR 75 CL ROUGE",
    "VIN DE MADAGASCAR 75 CL ROSE",
    "Vin rouge cuvee special Ambalavao 750 ML NU",
    "JUS DE RAISIN 70cl",
    "VIN ROUGE DOUX MAROPARASY 750 ML NU",
    "Coteau d'Ambalavao Cuvée special RGE",
]

# ============================================================
# NORMALISATION TEXTE
# ============================================================
def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

STANDARD_PRODUCTS = {
    normalize_text(p): p for p in RAW_PRODUCTS
}

# ============================================================
# IMAGE PREPROCESS
# ============================================================
def preprocess_image(image_bytes):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# ============================================================
# OCR
# ============================================================
def vision_ocr(image_bytes, creds_dict):
    creds = Credentials.from_service_account_info(creds_dict)
    client = vision.ImageAnnotatorClient(credentials=creds)
    image = vision.Image(content=image_bytes)
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

# ============================================================
# EXTRACTION ULYS
# ============================================================
def extract_bdc_ulys(text: str):
    norm = normalize_text(text)

    result = {
        "Client": "ULYS",
        "Articles": []
    }

    for norm_name, display_name in STANDARD_PRODUCTS.items():
        if norm_name in norm:
            pos = norm.find(norm_name)
            window = norm[pos:pos + 150]

            qty_match = re.search(r"\b(\d{1,3})\b", window)
            if qty_match:
                qty = int(qty_match.group(1))
                if 1 <= qty <= 500:
                    result["Articles"].append({
                        "Désignation": display_name,
                        "Quantité": qty
                    })

    return result

# ============================================================
# PIPELINE
# ============================================================
def pipeline(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
    return extract_bdc_ulys(raw), raw

# ============================================================
# UI
# ============================================================
uploaded = st.file_uploader(
    "📤 Importer un Bon de Commande ULYS",
    ["jpg", "jpeg", "png"]
)

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Vision AI manquants")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("🔍 Analyse du BDC ULYS..."):
        result, raw = pipeline(
            buf.getvalue(),
            dict(st.secrets["gcp_vision"])
        )

    st.subheader("🛒 Tableau des articles (fidèle)")
    df = pd.DataFrame(result["Articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw, height=300)
