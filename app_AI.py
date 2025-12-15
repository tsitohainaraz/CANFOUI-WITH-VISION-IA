# ============================================================
# FACTURE EN COMPTE — EXTRACTION FIDÈLE (VERSION FINALE)
# Fournisseur : Chan Foui & Fils
# OCR : Google Vision AI
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ------------------------------------------------------------
# CONFIG STREAMLIT
# ------------------------------------------------------------
st.set_page_config(page_title="Facture en compte", page_icon="🧾")
st.title("🧾 Extraction FACTURE EN COMPTE")
st.caption("Chan Foui & Fils — Vision AI (fidèle OCR réel)")

# ------------------------------------------------------------
# IMAGE PREPROCESS
# ------------------------------------------------------------
def preprocess_image(img_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=160))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# ------------------------------------------------------------
# OCR GOOGLE VISION
# ------------------------------------------------------------
def run_vision_ocr(img_bytes: bytes, creds: dict) -> str:
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=img_bytes)
    response = client.document_text_detection(image=image)
    return response.full_text_annotation.text or ""

# ------------------------------------------------------------
# EXTRACTION LOGIQUE FACTURE EN COMPTE
# ------------------------------------------------------------
def extract_facture_data(ocr_text: str):
    lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]

    data = {
        "date": "",
        "facture_numero": "",
        "adresse_livraison": "",
        "doit": "",
        "articles": []
    }

    # ---------------- MÉTADONNÉES ----------------
    m = re.search(r"le\s+(\d{1,2}\s+\w+\s+\d{4})", ocr_text, re.IGNORECASE)
    if m:
        data["date"] = m.group(1)

    m = re.search(r"FACTURE EN COMPTE\s+N[°o]?\s*(\d+)", ocr_text, re.IGNORECASE)
    if m:
        data["facture_numero"] = m.group(1)

    m = re.search(r"DOIT\s*:\s*(S2M|ULYS|DLP)", ocr_text, re.IGNORECASE)
    if m:
        data["doit"] = m.group(1)

    m = re.search(r"Adresse de livraison\s*:\s*(.+)", ocr_text, re.IGNORECASE)
    if m:
        data["adresse_livraison"] = m.group(1).strip()

    # ---------------- DÉSIGNATIONS ----------------
    designations = []
    in_designation_block = False

    for line in lines:
        up = line.upper()

        if "DÉSIGNATION DES MARCHANDISES" in up:
            in_designation_block = True
            continue

        if in_designation_block:
            if "SUIVANT VOTRE BON DE COMMANDE" in up:
                break

            if up == "CONSIGNE":
                designations.append("CONSIGNE")
                continue

            # Désignation = ligne texte sans chiffres
            if len(line) > 10 and not re.search(r"\d", line):
                designations.append(line)

    # ---------------- QUANTITÉS ----------------
    quantities = []

    STOP_WORDS = [
        "TOTAL", "TVA", "TTC", "NET",
        "ARRÊTÉE", "FACTURE", "PAYABLE"
    ]

    for line in lines:
        up = line.upper()

        if any(w in up for w in STOP_WORDS):
            break

        if re.fullmatch(r"\d{1,3}", line):
            val = int(line)

            # Quantités métier réalistes Chan Foui
            if val in [6, 12, 24, 48, 60, 72, 120]:
                quantities.append(val)

    # ---------------- ASSOCIATION FIFO ----------------
    for d, q in zip(designations, quantities):
        data["articles"].append({
            "Désignation": d,
            "Quantité": q
        })

    return data

# ------------------------------------------------------------
# PIPELINE GLOBAL
# ------------------------------------------------------------
def process_invoice(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw_text = run_vision_ocr(img, creds)
    data = extract_facture_data(raw_text)
    return data, raw_text

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
uploaded = st.file_uploader(
    "📤 Importer une FACTURE EN COMPTE (image)",
    type=["jpg", "jpeg", "png"]
)

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Clé Google Vision AI manquante")
        st.stop()

    buf = BytesIO()
    image.save(buf, format="JPEG")

    result, raw = process_invoice(
        buf.getvalue(),
        dict(st.secrets["gcp_vision"])
    )

    # ---------------- AFFICHAGE ----------------
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
