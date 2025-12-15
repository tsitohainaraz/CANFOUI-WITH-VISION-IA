import streamlit as st
import re
import pandas as pd
from io import BytesIO
from PIL import Image, ImageOps, ImageFilter
from google.cloud import vision
from google.oauth2.service_account import Credentials

# =========================================================
# CONFIG STREAMLIT
# =========================================================
st.set_page_config(page_title="Facture Chan Foui", page_icon="🧾")
st.title("🧾 Facture en compte – Chan Foui & Fils")
st.caption("Extraction fidèle : Désignation + Nb bills (Google Vision AI)")

# =========================================================
# IMAGE PREPROCESS (OCR PROPRE)
# =========================================================
def preprocess_image(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=160))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# =========================================================
# GOOGLE VISION OCR
# =========================================================
def vision_ocr(image_bytes: bytes, creds: dict) -> str:
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)
    return response.full_text_annotation.text or ""

# =========================================================
# EXTRACTION FIDÈLE (DÉSIGNATION + NB BILLS)
# =========================================================
def extract_designation_nb_bills(ocr_text: str) -> pd.DataFrame:
    lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]

    # ---------- DÉSIGNATIONS ----------
    designations = []
    in_table = False

    for line in lines:
        up = line.upper()

        if "DÉSIGNATION DES MARCHANDISES" in up:
            in_table = True
            continue

        if in_table and ("TOTAL HT" in up or "MONTANT HT" in up):
            break

        if in_table:
            if up == "CONSIGNE":
                continue

            if len(line) > 10 and not re.search(r"\d", line):
                designations.append(line)

    # ---------- NB BILLS ----------
    nb_bills = []
    in_nb_bills = False

    for line in lines:
        up = line.upper()

        if "NB BILLS" in up:
            in_nb_bills = True
            continue

        if in_nb_bills:
            if "TOTAL HT" in up or "MONTANT HT" in up:
                break

            # ignorer montants
            if "," in line or "." in line:
                continue

            nums = re.findall(r"\d{1,3}", line)
            for n in nums:
                nb_bills.append(int(n))

    # ---------- ASSOCIATION STRICTE ----------
    rows = []
    for d, q in zip(designations, nb_bills):
        rows.append({
            "Désignation": d,
            "Nb bills": q
        })

    return pd.DataFrame(rows)

# =========================================================
# INTERFACE STREAMLIT
# =========================================================
uploaded_file = st.file_uploader(
    "📤 Importer une facture en compte (image)",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Clé Google Vision AI manquante (st.secrets)")
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
