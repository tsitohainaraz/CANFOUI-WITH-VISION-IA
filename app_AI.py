# ============================================================
# FACTURE EN COMPTE — CHAN FOUI & FILS
# Extraction fidèle :
# - Date
# - Facture en compte N°
# - Adresse de livraison
# - DOIT
# - Articles : Désignation / Quantité (Nb btlls)
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
st.set_page_config(page_title="FACTURE — Chan Foui & Fils", page_icon="🧾")
st.title("🧾 Facture en compte — Chan Foui & Fils")

# ---------------- IMAGE PREPROCESS ----------------
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

# ---------------- EXTRACTION FACTURE ----------------
def extract_facture(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "date": "",
        "facture_numero": "",
        "adresse_livraison": "",
        "doit": "",
        "articles": []
    }

    # DATE
    m = re.search(r"le\s+(\d{1,2}\s+\w+\s+\d{4})", text, re.IGNORECASE)
    if m:
        result["date"] = m.group(1)

    # FACTURE N°
    m = re.search(r"FACTURE EN COMPTE\s+N[°o]?\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["facture_numero"] = m.group(1)

    # DOIT
    m = re.search(r"DOIT\s*:\s*([A-Z0-9]+)", text)
    if m:
        result["doit"] = m.group(1)

    # ADRESSE LIVRAISON
    m = re.search(r"Adresse de livraison\s*:\s*(.+)", text, re.IGNORECASE)
    if m:
        result["adresse_livraison"] = m.group(1).strip()

    # -------- TABLEAU --------
    in_table = False
    current_designation = None

    def is_qty(s):
        s = s.replace("D", "").replace("O", "0")
        return re.fullmatch(r"\d{1,3}", s)

    for i, line in enumerate(lines):
        up = line.upper()

        # Début tableau
        if "DÉSIGNATION DES MARCHANDISES" in up:
            in_table = True
            continue

        if not in_table:
            continue

        # Fin tableau
        if "TOTAL HT" in up or "ARRÊTÉE LA PRÉSENTE FACTURE" in up:
            break

        # Désignation (ligne texte sans chiffres)
        if (
            len(line) > 15
            and not re.search(r"\d{2,}", line)
            and not any(x in up for x in ["NB", "PU", "MONTANT", "COLIS"])
        ):
            current_designation = line.strip()
            continue

        # Quantité = Nb btlls
        if current_designation and is_qty(line):
            result["articles"].append({
                "Désignation": current_designation,
                "Quantité": int(line)
            })
            current_designation = None

    return result

# ---------------- PIPELINE ----------------
def pipeline(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
    return extract_facture(raw), raw

# ---------------- UI ----------------
uploaded = st.file_uploader("📤 Importer la FACTURE", ["jpg", "jpeg", "png"])

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Vision AI manquants")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    result, raw = pipeline(buf.getvalue(), dict(st.secrets["gcp_vision"]))

    st.subheader("📋 Informations facture")
    st.write("📅 Date :", result["date"])
    st.write("🧾 Facture n° :", result["facture_numero"])
    st.write("📦 Adresse :", result["adresse_livraison"])
    st.write("👤 DOIT :", result["doit"])

    st.subheader("🛒 Articles (fidèles)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw, height=300)
