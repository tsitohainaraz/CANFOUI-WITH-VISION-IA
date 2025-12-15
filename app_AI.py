# ============================================================
# FACTURE EN COMPTE — CHAN FOUI & FILS (VERSION STABLE)
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
st.caption("Extraction automatique (Vision AI)")

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

# ---------------- EXTRACTION ----------------
def extract_facture(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "date": "",
        "facture_numero": "",
        "adresse_livraison": "",
        "doit": "",
        "articles": []
    }

    # -------- DATE --------
    m = re.search(r"le\s+(\d{1,2}\s+\w+\s+\d{4})", text, re.IGNORECASE)
    if m:
        result["date"] = m.group(1)

    # -------- FACTURE --------
    m = re.search(r"FACTURE EN COMPTE\s+N[°o]?\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["facture_numero"] = m.group(1)

    # -------- DOIT --------
    m = re.search(r"DOIT\s*:\s*(S2M|ULYS|DLP)", text, re.IGNORECASE)
    if m:
        result["doit"] = m.group(1)

    # -------- ADRESSE --------
    m = re.search(r"Adresse de livraison\s*:\s*(.+)", text, re.IGNORECASE)
    if m:
        result["adresse_livraison"] = m.group(1).strip()

    # -------- TABLEAU --------
    in_table = False
    designation_queue = []

    def clean_designation(s: str) -> str:
        return re.sub(r"\s{2,}", " ", s).strip()

    for line in lines:
        up = line.upper()

        # Début tableau
        if "DÉSIGNATION DES MARCHANDISES" in up:
            in_table = True
            continue

        if not in_table:
            continue

        # Fin tableau (plus robuste)
        if "ARRÊTÉE LA PRÉSENTE FACTURE" in up or "TOTAL HT" in up:
            break

        # Désignation (autorise 75 CL / 750 ML)
        if (
            len(line) > 12
            and not any(x in up for x in [
                "NB", "BTLL", "PU", "MONTANT", "TOTAL"
            ])
            and not re.fullmatch(r"\d+", line)
        ):
            designation_queue.append(clean_designation(line))
            continue

        # Quantité réaliste métier
        qty_match = re.search(r"\b(6|12|24|48|60|72|120)\b", line)
        if qty_match and designation_queue:
            qty = int(qty_match.group(1))
            designation = designation_queue.pop(0)

            result["articles"].append({
                "Désignation": designation,
                "Quantité": qty
            })

    return result

# ---------------- PIPELINE ----------------
def pipeline(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
    return extract_facture(raw), raw

# ---------------- UI ----------------
uploaded = st.file_uploader("📤 Importer la FACTURE EN COMPTE", ["jpg", "jpeg", "png"])

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
    st.write("📦 Adresse de livraison :", result["adresse_livraison"])
    st.write("👤 DOIT :", result["doit"])

    st.subheader("🛒 Articles")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR brut", raw, height=300)
