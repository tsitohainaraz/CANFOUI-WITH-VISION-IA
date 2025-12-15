# ============================================================
# BDC ULYS — EXTRACTION FIDÈLE
# OpenCV (structure) + Google Vision AI (texte)
# ============================================================

import streamlit as st
import cv2
import numpy as np
import re
from io import BytesIO
from PIL import Image
from google.cloud import vision
from google.oauth2.service_account import Credentials
import pandas as pd

# ============================================================
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(page_title="BDC ULYS — OpenCV + Vision", page_icon="🧾")
st.title("🧾 BDC ULYS — Extraction fidèle")
st.caption("OpenCV (tableau) + Vision AI (OCR)")

# ============================================================
# GOOGLE VISION OCR (PAR ZONE)
# ============================================================
def vision_ocr_bytes(image_bytes, creds):
    client = vision.ImageAnnotatorClient(
        credentials=Credentials.from_service_account_info(creds)
    )
    image = vision.Image(content=image_bytes)
    res = client.document_text_detection(image=image)
    return res.full_text_annotation.text or ""

# ============================================================
# OPENCV — DÉTECTION DES COLONNES
# ============================================================
def detect_columns(image_cv):
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
    vertical = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_v, iterations=2)

    contours, _ = cv2.findContours(vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    columns = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if h > image_cv.shape[0] * 0.2:
            columns.append((x, y, w, h))

    columns = sorted(columns, key=lambda c: c[0])
    return columns

# ============================================================
# OPENCV — EXTRACTION ZONES LIGNES
# ============================================================
def extract_row_boxes(image_cv):
    gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h, iterations=2)

    contours, _ = cv2.findContours(horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    rows = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > image_cv.shape[1] * 0.3:
            rows.append((x, y, w, h))

    rows = sorted(rows, key=lambda r: r[1])
    return rows

# ============================================================
# EXTRACTION ARTICLES ULYS
# ============================================================
def extract_ulys_articles(image_pil, creds):
    image_cv = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)

    columns = detect_columns(image_cv)
    rows = extract_row_boxes(image_cv)

    if len(columns) < 2:
        return []

    # Hypothèse ULYS :
    # colonne 0 = désignation
    # colonne dernière = quantité
    desc_col = columns[0]
    qty_col = columns[-1]

    articles = []

    for row in rows:
        y1 = row[1]
        y2 = row[1] + row[3]

        # Zone désignation
        dx, dy, dw, dh = desc_col
        crop_desc = image_cv[y1:y2, dx:dx+dw]

        # Zone quantité
        qx, qy, qw, qh = qty_col
        crop_qty = image_cv[y1:y2, qx:qx+qw]

        def to_bytes(img):
            buf = BytesIO()
            Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).save(buf, format="PNG")
            return buf.getvalue()

        desc_text = vision_ocr_bytes(to_bytes(crop_desc), creds).strip()
        qty_text = vision_ocr_bytes(to_bytes(crop_qty), creds).strip()

        qty_match = re.search(r"\b(\d{1,3})\b", qty_text)
        if desc_text and qty_match:
            articles.append({
                "Désignation": desc_text.replace("\n", " ").strip(),
                "Quantité": int(qty_match.group(1))
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
        st.error("❌ Credentials Vision AI manquants")
        st.stop()

    with st.spinner("🔍 Analyse OpenCV + Vision AI..."):
        articles = extract_ulys_articles(
            image,
            dict(st.secrets["gcp_vision"])
        )

    st.subheader("🛒 Articles extraits (structure visuelle)")
    df = pd.DataFrame(articles)
    st.dataframe(df, use_container_width=True)
