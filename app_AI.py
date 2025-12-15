# ============================================================
# FACTURE EN COMPTE — VERSION FINALE V3 (OCR RÉEL)
# Extraction fidèle :
# - Date
# - Facture en compte n°
# - Adresse de livraison
# - DOIT (S2M / ULYS / DLP)
# - Tableau Désignation / Quantité (FIFO robuste)
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
st.set_page_config(page_title="FACTURE EN COMPTE", page_icon="🧾")
st.title("🧾 Facture en compte — Chan Foui & Fils")
st.caption("Extraction fidèle (OCR réel)")

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

# ---------------- EXTRACTION ----------------
def extract_facture_en_compte(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "date": "",
        "facture_numero": "",
        "adresse_livraison": "",
        "doit": "",
        "articles": []
    }

    # ---- MÉTADONNÉES ----
    m = re.search(r"le\s+(\d{1,2}\s+\w+\s+\d{4})", text, re.IGNORECASE)
    if m:
        result["date"] = m.group(1)

    m = re.search(r"FACTURE EN COMPTE\s+N[°o]?\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["facture_numero"] = m.group(1)

    m = re.search(r"DOIT\s*:\s*(S2M|ULYS|DLP)", text, re.IGNORECASE)
    if m:
        result["doit"] = m.group(1)

    m = re.search(r"Adresse de livraison\s*:\s*(.+)", text, re.IGNORECASE)
    if m:
        result["adresse_livraison"] = m.group(1).strip()

    # ---- 1️⃣ COLLECTE DES DÉSIGNATIONS ----
    designation_queue = []
    in_designation = False

    for line in lines:
        up = line.upper()

        if "DÉSIGNATION DES MARCHANDISES" in up:
            in_designation = True
            continue

        if in_designation and up == "CONSIGNE":
            designation_queue.append("CONSIGNE")
            in_designation = False
            continue

        if in_designation:
            if len(line) > 10 and not re.search(r"\d", line):
                designation_queue.append(line)
            continue

    # ---- 2️⃣ COLLECTE DES QUANTITÉS (APRÈS LE TABLEAU) ----
    quantity_list = []

    for line in lines:
        # quantité = entier seul, pas prix, pas année
        if re.fullmatch(r"\d{2,3}", line):
            val = int(line)

            # filtre anti-bruit
            if val not in [16, 17, 20, 24] or val == 24:
                quantity_list.append(val)

    # ---- 3️⃣ ASSOCIATION FIFO ----
    for d, q in zip(designation_queue, quantity_list):
        result["articles"].append({
            "Désignation": d,
            "Quantité": q
        })

    return result

# ---------------- PIPELINE ----------------
def pipeline(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
    return extract_facture_en_compte(raw), raw

# ---------------- UI ----------------
uploaded = st.file_uploader("📤 Importer FACTURE EN COMPTE", ["jpg", "jpeg", "png"])

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
    st.write("🧾 Facture en compte n° :", result["facture_numero"])
    st.write("📦 Adresse de livraison :", result["adresse_livraison"])
    st.write("👤 DOIT :", result["doit"])

    st.subheader("🛒 Articles (fidèles)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR brut", raw, height=350)
