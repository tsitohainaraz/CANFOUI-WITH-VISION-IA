import streamlit as st
import re
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ================= STREAMLIT =================
st.set_page_config(page_title="BDC ULYS – Métier", page_icon="🧾")
st.title("🧾 BDC ULYS — Extraction fidèle (règles métier)")

# ================= IMAGE =================
def preprocess_image(b):
    img = Image.open(BytesIO(b)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=150))
    out = BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

# ================= OCR =================
def vision_ocr(b, creds):
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=b)
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

# ================= EXTRACTION MÉTIER =================
def extract_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # Métadonnées
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?[\s\-]*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    current_designation = None

    def is_quantity(line):
        return re.fullmatch(r"\d{1,3}", line) is not None

    def is_noise(line):
        return any(x in line.upper() for x in [
            "PAQ", "/PC", "1 PAQ", "IPAQ", "D3", "D31",
            "CONV", "DATE", "LIVRAISON"
        ])

    def is_designation(line):
        return (
            len(line) > 12
            and not re.search(r"\d{5,}", line)
            and not is_noise(line)
        )

    for line in lines:
        up = line.upper()

        if "TOTAL DE LA COMMANDE" in up:
            break

        if is_noise(line):
            continue

        # Désignation (peut être sur plusieurs lignes)
        if is_designation(line):
            if current_designation:
                current_designation += " " + line
            else:
                current_designation = line
            current_designation = re.sub(r"\s{2,}", " ", current_designation).title()
            continue

        # Quantité
        if current_designation and is_quantity(line):
            result["articles"].append({
                "Désignation": current_designation,
                "Quantité": int(line)
            })
            current_designation = None

    return result

# ================= PIPELINE =================
def pipeline(image_bytes, creds):
    img = preprocess_image(image_bytes)
    raw = vision_ocr(img, creds)
    return extract_ulys(raw), raw

# ================= UI =================
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

    st.subheader("🛒 Articles (FIDÈLES)")
    df = pd.DataFrame(result["articles"])

    if df.empty:
        st.warning("Aucun article détecté")
    else:
        st.dataframe(df, use_container_width=True)
        st.success(f"{len(df)} lignes détectées")

    with st.expander("OCR brut"):
        st.text_area("OCR", raw, height=300)
