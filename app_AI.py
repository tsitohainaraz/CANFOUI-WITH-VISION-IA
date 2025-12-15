# ============================================================
# BDC ULYS — OpenCV + Google Vision AI
# Extraction fiable Désignation / Quantité
# Compatible Streamlit Cloud (opencv-python-headless)
# ============================================================

import streamlit as st
import cv2
import numpy as np
import re
from io import BytesIO
from PIL import Image
import pandas as pd
from google.cloud import vision
from google.oauth2.service_account import Credentials

# ============================================================
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(page_title="BDC ULYS — Vision + OpenCV", page_icon="🧾")
st.title("🧾 BDC ULYS — Extraction fidèle")
st.caption("OpenCV (structure) + Vision AI (OCR)")

# ============================================================
# GOOGLE VISION OCR (image -> texte)
# ============================================================
def vision_ocr(image_bytes, creds):
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)
    return response.full_text_annotation.text or ""

# ============================================================
# OPENCV — DETECTION DES LIGNES DU TABLEAU
# ============================================================
def detect_rows(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        25, 15
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 2))
    detect = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel, iterations=2)

    contours, _ = cv2.findContours(detect, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    rows = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w > img.shape[1] * 0.4 and h < 80:
            rows.append((x, y, w, h))

    return sorted(rows, key=lambda r: r[1])

# ============================================================
# EXTRACTION ARTICLES ULYS (STRUCTURE VISUELLE)
# ============================================================
def extract_articles_ulys(image_pil, creds):
    img = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
    rows = detect_rows(img)

    articles = []

    for (x, y, w, h) in rows:
        row_img = img[y:y+h, x:x+w]

        buf = BytesIO()
        Image.fromarray(cv2.cvtColor(row_img, cv2.COLOR_BGR2RGB)).save(buf, format="PNG")
        text = vision_ocr(buf.getvalue(), creds).upper()

        # Filtrer lignes non articles
        if not any(k in text for k in ["VIN", "MAROPARASY", "COTE", "AMBALAVAO", "CONS."]):
            continue

        # Nettoyage désignation
        designation = re.sub(r"\s{2,}", " ", text.replace("\n", " ")).strip()

        # Quantité (la PLUS GRANDE valeur entière de la ligne)
        qty_candidates = re.findall(r"\b\d{1,3}\b", text)
        if not qty_candidates:
            continue

        qty = max(map(int, qty_candidates))

        articles.append({
            "Désignation": designation.title(),
            "Quantité": qty
        })

    return articles

# ============================================================
# UI
# ============================================================
uploaded = st.file_uploader("📤 Importer le BDC ULYS", ["jpg", "jpeg", "png"])

if uploaded:
    image = Image.open(uploaded)
    st.image(image, use_container_width=True)

    if "gcp_vision" not in st.secrets:
        st.error("❌ Credentials Google Vision manquants")
        st.stop()

    with st.spinner("🔍 Analyse OpenCV + Vision AI..."):
        articles = extract_articles_ulys(
            image,
            dict(st.secrets["gcp_vision"])
        )

    st.subheader("🛒 Articles détectés")
    df = pd.DataFrame(articles)

    if df.empty:
        st.warning("⚠️ Aucun article détecté — vérifier la qualité du scan")
    else:
        st.dataframe(df, use_container_width=True)

    with st.expander("📊 Résumé"):
        st.write("Nombre d’articles :", len(df))
