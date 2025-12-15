import streamlit as st
import re
import pandas as pd
from io import BytesIO
from PIL import Image, ImageOps, ImageFilter
from google.cloud import vision
from google.oauth2.service_account import Credentials

# --------------------------------------------------
# STREAMLIT CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Facture Chan Foui", page_icon="🧾")
st.title("🧾 Facture en compte – Chan Foui & Fils")
st.caption("Extraction fidèle : Désignation + Nb bills")

# --------------------------------------------------
# IMAGE PREPROCESS
# --------------------------------------------------
def preprocess_image(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=160))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# --------------------------------------------------
# GOOGLE VISION OCR
# --------------------------------------------------
def vision_ocr(image_bytes: bytes, creds: dict) -> str:
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=image_bytes)
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

# --------------------------------------------------
# EXTRACTION FIDÈLE (LOGIQUE OCR RÉEL)
# --------------------------------------------------
def extract_designation_nb_bills(ocr_text: str) -> pd.DataFrame:
    lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]

    # ---------- 1. DÉSIGNATIONS ----------
    designations = []
    in_designation = False

    for line in lines:
        up = line.upper()

        if "DÉSIGNATION DES MARCHANDISES" in up:
            in_designation = True
            continue

        if in_designation and "SUIVANT VOTRE BON DE COMMANDE" in up:
            break

        if in_designation:
            if up == "CONSIGNE":
                continue
            if len(line) > 10 and not re.search(r"\d", line):
                designations.append(line)

    # ---------- 2. NB BILLS ----------
    nb_bills = []
    in_nb_bills = False

    for line in lines:
        up = line.upper()

        if "NB BILLS" in up:
            in_nb_bills = True
            continue

        if in_nb_bills:
            if "TOTAL HT" in up:
                break

            # ignorer montants
            if "." in line or "," in line:
                continue

            # extraire TOUS les nombres de la ligne
            nums = re.findall(r"\d{1,3}", line)
            for n in nums:
                val = int(n)
                if 1 <= val <= 150:
                    nb_bills.append(val)

    # ---------- 3. ASSOCIATION STRICTE ----------
    rows = []
    for d, q in zip(designations, nb_bills):
        rows.append({
            "Désignation": d,
            "Nb bills": q
        })

    return pd.DataFrame(rows)

# --------------------------------------------------
# UI
# --------------------------------------------------
uploaded = st.file_uploader(
    "📤 Importer une facture en compte (image)",
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

    with st.spinner("🔍 OCR en cours…"):
        ocr_text = vision_ocr(
            preprocess_image(buf.getvalue()),
            dict(st.secrets["gcp_vision"])
        )

    st.subheader("🛒 Articles (fidèles)")
    df = extract_designation_nb_bills(ocr_text)
    st.dataframe(df, use_container_width=True)

    with st.expander("🔎 OCR brut"):
        st.text_area("OCR brut", ocr_text, height=350)
