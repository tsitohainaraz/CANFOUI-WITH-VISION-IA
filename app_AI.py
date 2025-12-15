# ============================================================
# BDC ULYS — VERSION FINALE STABLE (Vision AI only)
# ============================================================

import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ---------------- CONFIG ----------------
st.set_page_config(page_title="BDC ULYS", page_icon="🧾")
st.title("🧾 Bon de Commande ULYS — Extraction fiable")

# ---------------- IMAGE PREPROCESS ----------------
def preprocess_image(b):
    img = Image.open(BytesIO(b)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.1, percent=160))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# ---------------- OCR ----------------
def vision_ocr(b, creds):
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=b)
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

# ---------------- EXTRACTION METIER ----------------
def extract_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # ---- META ----
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?\s*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # ---- TABLE ----
    in_table = False
    current_designation = None

    def normalize_qty(s):
        s = s.replace("D", "").replace("O", "0").replace("G", "0")
        return s if s.isdigit() else None

    def clean_designation(s):
        s = re.sub(r"\b\d{6,}\b", "", s)
        s = s.replace("PAQ", "").replace("/PC", "")
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip()

    i = 0
    while i < len(lines):
        line = lines[i]
        up = line.upper()

        # Start table
        if "DESCRIPTION DE L'ARTICLE" in up:
            in_table = True
            i += 1
            continue

        if not in_table:
            i += 1
            continue

        # End table
        if "TOTAL DE LA COMMANDE" in up:
            break

        # Ignore category headers
        if re.match(r"\d{6}\s+(VINS|CONSIGNE|LIQUEUR)", up):
            i += 1
            continue

        # Detect designation
        if (
            ("VIN " in up or "CONS." in up)
            and not re.fullmatch(r"\d+", line)
        ):
            current_designation = clean_designation(line)
            i += 1
            continue

        # Detect quantity (may be next or next+1 line)
        qty = normalize_qty(line)
        if qty and current_designation:
            result["articles"].append({
                "Désignation": current_designation.title(),
                "Quantité": int(qty)
            })
            i += 1
            continue

        # Handle D3 / split quantities
        if line.startswith("D") and i + 1 < len(lines):
            q = normalize_qty(lines[i + 1])
            if q and current_designation:
                result["articles"].append({
                    "Désignation": current_designation.title(),
                    "Quantité": int(q)
                })
                i += 2
                continue

        i += 1

    return result

# ---------------- PIPELINE ----------------
def pipeline(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
    return extract_ulys(raw), raw

# ---------------- UI ----------------
uploaded = st.file_uploader("📤 Importer le BDC ULYS", ["jpg", "jpeg", "png"])

if uploaded:
    img = Image.open(uploaded)
    st.image(img, use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Vision AI manquants")
        st.stop()

    buf = BytesIO()
    img.save(buf, format="JPEG")

    result, raw = pipeline(buf.getvalue(), dict(st.secrets["gcp_vision"]))

    st.subheader("📋 Informations")
    st.write("Client :", result["client"])
    st.write("Numéro :", result["numero"])
    st.write("Date :", result["date"])

    st.subheader("🛒 Articles extraits (FIDÈLES)")
    df = pd.DataFrame(result["articles"])
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR", raw, height=300)
