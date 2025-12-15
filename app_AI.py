# ============================================================
# BDC ULYS — EXTRACTION FIABLE ET COMPLÈTE
# API : Google Vision AI (document_text_detection)
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
st.caption("Extraction fidèle — aucune ligne manquante")

# ============================================================
# IMAGE PREPROCESSING
# ============================================================
def preprocess_image(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180))
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
    return response.full_text_annotation.text or ""

def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[^\S\r\n]+", " ", text)
    return text.strip()

# ============================================================
# EXTRACTION LOGIQUE — ULYS (FENÊTRE GLISSANTE)
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
    i = 0

    def is_designation(line: str) -> bool:
        up = line.upper()
        return (
            up.startswith("VIN ")
            or up.startswith("CONS.")
            or "CONSIGNE" in up
        )

    def clean_designation(s: str) -> str:
        s = re.sub(r"\b\d{6,}\b", "", s)  # codes longs
        s = s.replace("PAQ", "").replace("/PC", "")
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip().title()

    def normalize_qty(s: str):
        s = s.replace("D", "").replace("O", "0").replace("G", "0")
        if re.fullmatch(r"\d{1,3}", s):
            return int(s)
        return None

    while i < len(lines):
        line = lines[i]
        up = line.upper()

        # Début tableau
        if "DESCRIPTION DE L'ARTICLE" in up:
            in_table = True
            i += 1
            continue

        if not in_table:
            i += 1
            continue

        # Fin tableau
        if "TOTAL DE LA COMMANDE" in up:
            break

        # Désignation détectée
        if is_designation(line):
            designation = clean_designation(line)
            qty = None

            # 🔍 Recherche quantité dans les lignes suivantes
            for j in range(i + 1, min(i + 8, len(lines))):
                candidate = normalize_qty(lines[j])
                if candidate is not None:
                    qty = candidate
                    break

            result["articles"].append({
                "Désignation": designation,
                "Quantité": qty
            })

        i += 1

    return result

# ============================================================
# PIPELINE
# ============================================================
def pipeline(image_bytes: bytes, creds_dict: dict):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds_dict)
    raw = clean_text(raw)
    return extract_bdc_ulys(raw), raw

# ============================================================
# UI
# ============================================================
uploaded = st.file_uploader(
    "📤 Importer le Bon de Commande ULYS",
    type=["jpg", "jpeg", "png"]
)

if uploaded:
    image = Image.open(uploaded)
    st.image(image, caption="Aperçu BDC ULYS", use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Google Vision manquants")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    with st.spinner("🔍 Analyse Vision AI..."):
        result, raw_text = pipeline(
            buf.getvalue(),
            dict(st.secrets["gcp_vision"])
        )

    # ---------------- AFFICHAGE ----------------
    st.subheader("📋 Informations BDC")
    st.write("**Client :**", result["client"])
    st.write("**Numéro :**", result["numero"])
    st.write("**Date :**", result["date"])

    st.subheader("🛒 Articles détectés (FIDÈLES)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR brut", raw_text, height=350)
