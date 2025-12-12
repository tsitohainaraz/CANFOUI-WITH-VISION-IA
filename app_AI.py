# app_final_simple.py
# Chan Foui et Fils — AI Vision
# Mode Facture et Mode BDC avec extraction simplifiée

import streamlit as st
import numpy as np
import re
import time
import os
import base64
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps, ImageEnhance
from google.cloud import vision
from google.oauth2.service_account import Credentials as SA_Credentials
import gspread
from googleapiclient.discovery import build
import pandas as pd
import json

# ---------------------------
# Page config
# ---------------------------
st.set_page_config(
    page_title="Chan Foui et Fils — OCR PRO",
    layout="centered",
    page_icon="🍷",
    initial_sidebar_state="collapsed"
)

# ---------------------------
# Logo + topbar variables
# ---------------------------
LOGO_FILENAME = "CF_LOGOS.png"
BRAND_TITLE = "Chan Foui et Fils"
BRAND_SUB = "Google Vision AI — Édition Ultra-Précise"

# ---------------------------
# AUTH (updated)
# ---------------------------
AUTHORIZED_USERS = {
    "LATITIA": "CFF1",
    "ELODIE": "CFF2",
    "PATHOU": "CFF3",
    "ADMIN": "CFF4"
}

# ---------------------------
# Sheet IDs
# ---------------------------
BDC_SHEET_ID = "1FooEwQBwLjvyjAsvHu4eDes0o-eEm92fbEWv6maBNyE"
BDC_SHEET_GID = 1487110894
INVOICE_SHEET_ID = "1FooEwQBwLjvyjAsvHu4eDes0o-eEm92fbEWv6maBNyE"
INVOICE_SHEET_GID = 72936741

# ---------------------------
# Colors & styles
# ---------------------------
PALETTE = {
    "petrol": "#0F3A45",
    "gold": "#D4AF37",
    "ivory": "#FAF5EA",
    "muted": "#7a8a8f",
    "card": "#ffffff",
    "soft": "#f6f2ec"
}

st.markdown(
    f"""
    <style>
    :root{{
        --petrol: {PALETTE['petrol']};
        --gold: {PALETTE['gold']};
        --ivory: {PALETTE['ivory']};
        --muted: {PALETTE['muted']};
        --card: {PALETTE['card']};
        --soft: {PALETTE['soft']};
    }}
    html, body, [data-testid='stAppViewContainer'] {{
        background: linear-gradient(180deg, var(--ivory), #fffdf9);
        color: var(--petrol);
        font-family: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
    }}
    .card {{
        border-radius:14px;
        background: var(--card);
        padding:18px;
        box-shadow: 0 10px 30px rgba(15,58,69,0.04);
        border: 1px solid rgba(15,58,69,0.03);
        margin-bottom:14px;
    }}
    .stButton>button {{
        background: linear-gradient(180deg, var(--gold), #b58f2d);
        color: #081214;
        font-weight:700;
        border-radius:10px;
        padding:8px 12px;
    }}
    .secondary-button {{
        background: linear-gradient(180deg, #f0f0f0, #d0d0d0) !important;
        color: #333 !important;
        font-weight:600 !important;
        border-radius:10px !important;
        padding:8px 12px !important;
        border: 1px solid #ccc !important;
    }}
    .logo-title-container {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 20px;
        margin-bottom: 10px;
    }}
    .logo-img {{
        height: 80px;
        width: auto;
    }}
    .brand-title {{
        color: {PALETTE['petrol']};
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
    }}
    .brand-sub {{
        color: {PALETTE['muted']};
        text-align: center;
        font-size: 1.1rem;
        margin-top: 0;
    }}
    .client-badge {{
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 2px;
    }}
    .badge-supermaki {{
        background-color: #FF6B6B;
        color: white;
    }}
    .badge-leader {{
        background-color: #4ECDC4;
        color: white;
    }}
    .badge-ulys {{
        background-color: #45B7D1;
        color: white;
    }}
    .scan-option-card {{
        border: 2px solid transparent;
        transition: all 0.3s ease;
        cursor: pointer;
    }}
    .scan-option-card:hover {{
        border-color: var(--gold);
        transform: translateY(-2px);
    }}
    .scan-option-card.selected {{
        border-color: var(--gold);
        background-color: rgba(212, 175, 55, 0.05);
    }}
    .confidence-high {{
        background-color: rgba(76, 175, 80, 0.1);
        border-left: 4px solid #4CAF50;
        padding: 10px;
        border-radius: 4px;
        margin: 5px 0;
    }}
    .confidence-medium {{
        background-color: rgba(255, 193, 7, 0.1);
        border-left: 4px solid #FFC107;
        padding: 10px;
        border-radius: 4px;
        margin: 5px 0;
    }}
    .confidence-low {{
        background-color: rgba(244, 67, 54, 0.1);
        border-left: 4px solid #F44336;
        padding: 10px;
        border-radius: 4px;
        margin: 5px 0;
    }}
    .table-preview {{
        background: white;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        overflow-x: auto;
    }}
    .table-header {{
        background-color: var(--petrol);
        color: white;
        font-weight: bold;
        padding: 10px;
        text-align: left;
    }}
    .table-row {{
        border-bottom: 1px solid #eee;
    }}
    .table-row:nth-child(even) {{
        background-color: #f9f9f9;
    }}
    .table-cell {{
        padding: 8px 10px;
        vertical-align: top;
    }}
    .article-count {{
        display: inline-block;
        background: var(--gold);
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        margin-left: 8px;
    }}
    .simple-table {{
        width: 100%;
        border-collapse: collapse;
        margin: 15px 0;
    }}
    .simple-table th {{
        background-color: var(--petrol);
        color: white;
        padding: 10px;
        text-align: left;
    }}
    .simple-table td {{
        padding: 8px 10px;
        border-bottom: 1px solid #eee;
    }}
    .simple-table tr:nth-child(even) {{
        background-color: #f9f9f9;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------
# OCR Functions avec Google Vision AI
# ---------------------------
def advanced_preprocess_image(image_bytes: bytes) -> bytes:
    """Prétraitement avancé pour optimiser l'OCR des tableaux"""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    
    # Redimensionnement intelligent
    max_w = 2800
    if img.width > max_w:
        ratio = max_w / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_w, new_height), Image.LANCZOS)
    
    # Amélioration du contraste
    img = ImageOps.autocontrast(img, cutoff=2)
    
    # Filtre pour accentuer les contours
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=180, threshold=2))
    
    # Amélioration de la netteté
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.8)
    
    # Amélioration de la luminosité
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.1)
    
    # Conversion en niveaux de gris
    img_gray = img.convert('L')
    
    # Sauvegarde
    out = BytesIO()
    img_gray.save(out, format="PNG", optimize=True)
    
    return out.getvalue()

def get_vision_client():
    if "gcp_vision" in st.secrets:
        sa_info = dict(st.secrets["gcp_vision"])
    elif "google_service_account" in st.secrets:
        sa_info = dict(st.secrets["google_service_account"])
    else:
        raise RuntimeError("Credentials Google Vision introuvables dans st.secrets")
    creds = SA_Credentials.from_service_account_info(sa_info)
    client = vision.ImageAnnotatorClient(credentials=creds)
    return client

def google_vision_ai_ocr(img_bytes: bytes, language_hints=["fr", "en"]):
    """OCR avec Google Vision AI (document_text_detection) pour une meilleure précision"""
    
    client = get_vision_client()
    image = vision.Image(content=img_bytes)
    
    # Configuration pour documents avec hints de langue
    context = vision.ImageContext(
        language_hints=language_hints,
    )
    
    # Utiliser document_text_detection (spécifique pour les documents)
    response = client.document_text_detection(image=image, image_context=context)
    
    if response.error and response.error.message:
        raise Exception(f"Google Vision AI Error: {response.error.message}")
    
    raw_text = ""
    if response.full_text_annotation:
        raw_text = response.full_text_annotation.text
    
    # Extraire la structure de mise en page pour les tableaux
    blocks_info = []
    if response.full_text_annotation:
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                block_text = ""
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        word_text = ''.join([symbol.text for symbol in word.symbols])
                        block_text += word_text + " "
                
                blocks_info.append({
                    "text": block_text.strip(),
                    "bounding_box": block.bounding_box,
                    "confidence": block.confidence
                })
    
    return {
        "raw_text": raw_text,
        "blocks": blocks_info,
        "full_response": response
    }

def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[^\S\r\n]+", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    return text.strip()

# ---------------------------
# NOUVELLES FONCTIONS D'EXTRACTION SIMPLIFIÉES POUR LES 3 TYPES
# ---------------------------

# ==================== SUPERMAKI ====================
def extract_bdc_supermaki_simple(text: str):
    """Extraction SIMPLIFIÉE pour SUPERMAKI - 2 colonnes seulement"""
    result = {
        "client": "SUPERMAKI",
        "numero": "",
        "date": "",
        "adresse_livraison": "",
        "articles": []  # Liste de dictionnaires: {"Désignation": "", "Qté": ""}
    }
    
    # 1. Extraire numéro BDC
    bdc_match = re.search(r'Bon de commande n[°o]\s*(\d{8})', text)
    if bdc_match:
        result["numero"] = bdc_match.group(1)
    
    # 2. Extraire date
    date_match = re.search(r'Date\s+[ée]mission\s*(\d{2}/\d{2}/\d{4})', text)
    if date_match:
        result["date"] = date_match.group(1)
    
    # 3. Extraire adresse livraison
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if 'Adresse de livraison' in line:
            if i + 1 < len(lines):
                result["adresse_livraison"] = lines[i + 1].strip()
                break
    
    # 4. EXTRACTION SIMPLIFIÉE DES ARTICLES - 2 COLONNES
    articles = []
    
    # Chercher le tableau (après les en-têtes)
    table_started = False
    for i, line in enumerate(lines):
        line_clean = line.strip()
        
        # Détecter le début du tableau (en-tête)
        if 'REF' in line_clean and ('EAN' in line_clean or 'Désignation' in line_clean):
            table_started = True
            continue
        
        if table_started and line_clean:
            # Détecter la fin du tableau
            if line_clean.startswith('Montant') or line_clean.startswith('Seul'):
                break
            
            # Ligne d'article: commence par 6 chiffres (REF)
            if re.match(r'^\d{6}', line_clean):
                # Pattern pour extraire Désignation et Quantité
                pattern = r'\d{6}\s+\d{13}[\.]?\s+(.+?)\s+\d+\s+\d+\s+(\d+)'
                match = re.search(pattern, line_clean)
                
                if match:
                    designation_raw = match.group(1).strip()
                    qte = match.group(2)
                    
                    # Normaliser la désignation
                    designation = normalize_designation_simple(designation_raw, "SUPERMAKI")
                    
                    articles.append({
                        "Désignation": designation,
                        "Qté": qte
                    })
    
    # Méthode de secours si aucune ligne n'a été trouvée
    if not articles:
        # Chercher les lignes avec des noms de produits et des quantités
        for line in lines:
            line_clean = line.strip()
            
            # Chercher des motifs avec "COTE DE FIANAR" ou "CONS" suivis de nombres
            if ('COTE DE FIANAR' in line_clean.upper() or 
                'CONS' in line_clean.upper() or
                'MAROPARASY' in line_clean.upper()):
                
                # Chercher un nombre de 2-3 chiffres (quantité)
                qty_match = re.search(r'\b(\d{2,3})\b', line_clean)
                if qty_match:
                    qte = qty_match.group(1)
                    
                    # Extraire la désignation (enlever les nombres qui ne font pas partie du nom)
                    words = line_clean.split()
                    desig_parts = []
                    for word in words:
                        # Garder les mots qui ne sont pas juste des nombres (sauf "75", "CL", etc.)
                        if not re.match(r'^\d+$', word) or word in ['75', '37', 'CL', 'COTE', 'DE']:
                            desig_parts.append(word)
                    
                    if desig_parts:
                        designation_raw = ' '.join(desig_parts)
                        designation = normalize_designation_simple(designation_raw, "SUPERMAKI")
                        
                        articles.append({
                            "Désignation": designation,
                            "Qté": qte
                        })
    
    result["articles"] = articles
    return result

# ==================== ULYS ====================
def extract_bdc_ulys_simple(text: str):
    """Extraction SIMPLIFIÉE pour ULYS - 2 colonnes seulement"""
    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "nom_magasin": "",
        "articles": []  # Liste de dictionnaires: {"Désignation": "", "Qté": ""}
    }
    
    # 1. Extraire numéro BDC
    bdc_match = re.search(r'N[°o]\s+(\d{10})', text)
    if bdc_match:
        result["numero"] = bdc_match.group(1)
    
    # 2. Extraire date
    date_match = re.search(r'Date de la Commande\s*:\s*(\d{2}/\d{2}/\d{4})', text)
    if date_match:
        result["date"] = date_match.group(1)
    
    # 3. Extraire nom magasin
    magasin_match = re.search(r'Nom du Magasin\s*:\s*(.+)', text)
    if magasin_match:
        result["nom_magasin"] = magasin_match.group(1).strip()
        result["adresse_livraison"] = result["nom_magasin"]
    
    # 4. EXTRACTION SIMPLIFIÉE DES ARTICLES - 2 COLONNES
    articles = []
    lines = text.split('\n')
    
    # Chercher les sections avec "PAQ" (paquets) ou "/PC" (pièces)
    for line in lines:
        line_clean = line.strip()
        
        # Ignorer les lignes d'en-tête
        if 'GTIN' in line_clean or 'Article No' in line_clean or 'Description' in line_clean:
            continue
        
        # Détecter les lignes d'articles avec PAQ (paquets)
        if 'PAQ' in line_clean:
            # Chercher la quantité après PAQ
            qty_match = re.search(r'PAQ\s+(\d+)', line_clean)
            if qty_match:
                qte = qty_match.group(1)
                
                # Extraire la description de l'article (avant PAQ)
                paq_pos = line_clean.find('PAQ')
                if paq_pos > 0:
                    # Enlever GTIN et Article No si présents
                    description_part = line_clean[:paq_pos]
                    
                    # Enlever les séries de chiffres (GTIN: 13-14 chiffres, Article No: 8 chiffres)
                    description_clean = re.sub(r'\d{13,14}', '', description_part)
                    description_clean = re.sub(r'\d{8}', '', description_clean).strip()
                    
                    if description_clean:
                        designation = normalize_designation_simple(description_clean, "ULYS")
                        
                        articles.append({
                            "Désignation": designation,
                            "Qté": qte
                        })
        
        # Détecter les consignes avec /PC
        elif '/PC' in line_clean and ('CONS.' in line_clean.upper() or 'CONSIGNE' in line_clean.upper()):
            # Chercher la quantité après /PC
            qty_match = re.search(r'/PC\s+(\d+)', line_clean)
            if qty_match:
                qte = qty_match.group(1)
                
                # Extraire la description (avant /PC)
                pc_pos = line_clean.find('/PC')
                if pc_pos > 0:
                    description_part = line_clean[:pc_pos]
                    description_clean = re.sub(r'\d{13,14}', '', description_part)
                    description_clean = re.sub(r'\d{8}', '', description_clean).strip()
                    
                    if description_clean:
                        designation = normalize_designation_simple(description_clean, "ULYS")
                        
                        articles.append({
                            "Désignation": designation,
                            "Qté": qte
                        })
    
    # Regrouper les consignes si elles apparaissent plusieurs fois
    if articles:
        # Regrouper par désignation
        grouped_articles = {}
        for article in articles:
            designation = article["Désignation"]
            qte = int(article["Qté"]) if article["Qté"].isdigit() else 0
            
            if designation in grouped_articles:
                grouped_articles[designation] += qte
            else:
                grouped_articles[designation] = qte
        
        # Recréer la liste d'articles groupés
        result["articles"] = [{"Désignation": k, "Qté": str(v)} for k, v in grouped_articles.items()]
    else:
        result["articles"] = articles
    
    return result

# ==================== LEADER PRICE ====================
def extract_bdc_leader_price_simple(text: str):
    """Extraction SIMPLIFIÉE pour LEADER PRICE - 2 colonnes seulement"""
    result = {
        "client": "LEADER PRICE",
        "numero": "",
        "date": "",
        "adresse_livraison": "",
        "articles": []  # Liste de dictionnaires: {"Désignation": "", "Qté": ""}
    }
    
    # 1. Extraire numéro BDC
    bdc_match = re.search(r'N[°o]\s+de\s+Commande\s+(BCD\d+)', text, re.IGNORECASE)
    if not bdc_match:
        bdc_match = re.search(r'BCD(\d+)', text, re.IGNORECASE)
        if bdc_match:
            result["numero"] = f"BCD{bdc_match.group(1)}"
    else:
        result["numero"] = bdc_match.group(1)
    
    # 2. Extraire date
    date_match = re.search(r'Date\s+(\d{2}/\d{2}/\d{2,4})', text, re.IGNORECASE)
    if date_match:
        date_str = date_match.group(1)
        if len(date_str.split('/')[-1]) == 2:
            day, month, year = date_str.split('/')
            year = "20" + year
            result["date"] = f"{day}/{month}/{year}"
        else:
            result["date"] = date_str
    
    # 3. Extraire adresse livraison
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if 'A livrer à' in line or 'a livrer a' in line.lower():
            if i + 1 < len(lines):
                result["adresse_livraison"] = lines[i + 1].strip()
                break
    
    # 4. EXTRACTION SIMPLIFIÉE DES ARTICLES - 2 COLONNES
    articles = []
    
    # Chercher les lignes avec motif "nombre.000" (format Leader Price)
    for line in lines:
        line_clean = line.strip()
        
        # Ignorer les lignes d'en-tête
        if not line_clean or 'Réf' in line_clean or 'Désignation' in line_clean:
            continue
        
        # Chercher le motif "nombre.000" (ex: 12.000)
        qty_match = re.search(r'(\d+)\.(\d{3})', line_clean)
        if qty_match:
            qte = qty_match.group(1)  # La partie avant le point est la quantité
            
            # Extraire la désignation (tout avant le motif .000)
            qty_pos = line_clean.find(qty_match.group(0))
            if qty_pos > 0:
                # Enlever les références numériques au début si présentes
                designation_part = line_clean[:qty_pos].strip()
                
                # Enlever les références de 4-5 chiffres au début
                designation_clean = re.sub(r'^\d{4,5}\s+', '', designation_part).strip()
                
                if designation_clean:
                    designation = normalize_designation_simple(designation_clean, "LEADER PRICE")
                    
                    articles.append({
                        "Désignation": designation,
                        "Qté": qte
                    })
    
    # Recherche alternative pour les consignes
    if not articles:
        for line in lines:
            line_clean = line.upper().strip()
            
            if 'CONSIGNE' in line_clean or 'CHAN FOUI' in line_clean:
                # Chercher un nombre (quantité)
                qty_match = re.search(r'\b(\d{2,3})\b', line_clean)
                if qty_match:
                    qte = qty_match.group(1)
                    
                    # Chercher la désignation
                    if 'CONSIGNE' in line_clean:
                        designation = "CONS 2000 CHANFOUI"
                    else:
                        # Extraire les mots significatifs
                        words = line_clean.split()
                        desig_parts = []
                        for word in words:
                            if not re.match(r'^\d+$', word) or word in ['75', 'CL']:
                                desig_parts.append(word)
                        
                        designation = ' '.join(desig_parts) if desig_parts else "CONS 2000 CHANFOUI"
                    
                    articles.append({
                        "Désignation": designation,
                        "Qté": qte
                    })
    
    result["articles"] = articles
    return result

def normalize_designation_simple(designation_raw: str, client_type: str) -> str:
    """Normalisation simple des désignations pour tous les clients"""
    designation = designation_raw.upper().strip()
    
    # Nettoyer les espaces multiples
    designation = re.sub(r'\s+', ' ', designation)
    
    # Correspondances communes pour tous les clients
    common_matches = {
        "COTE DE FIANAR ROUGE 75 CL": "Côte de Fianar Rouge 75 cl",
        "COTE DE FIANAR ROUGE 75CL": "Côte de Fianar Rouge 75 cl",
        "COTE DE FIANAR BLANC 75 CL": "Côte de Fianar Blanc 75 cl",
        "COTE DE FIANAR BLANC 75CL": "Côte de Fianar Blanc 75 cl",
        "COTE DE FIANAR ROSE 75 CL": "Côte de Fianar Rosé 75 cl",
        "COTE DE FIANAR ROSÉ 75 CL": "Côte de Fianar Rosé 75 cl",
        "COTE DE FIANAR GRIS 75 CL": "Côte de Fianar Gris 75 cl",
        "CONS 2000 CHANFOUI": "CONS 2000 CHANFOUI",
        "CONS. CHAN FOUI 75CL": "CONS 2000 CHANFOUI",
        "CONSIGNE BLLE CHAN FOUI 75CL": "CONS 2000 CHANFOUI",
        "MAROPARASY ROUGE 75 CL": "Maroparasy Rouge 75 cl",
        "BLANC DOUX MAROPARASY 75 CL": "Blanc doux Maroparasy 75 cl",
        "VIN ROUGE CUVEE SPEC AMBALAVAO 750ML NU": "Côteau d'Ambalavao Spécial 75 cl",
        "VIN ROUGE COTE DE FIANARA 750ML NU": "Côte de Fianar Rouge 75 cl",
        "VIN BLANC DOUX MAROPARASY 750ML NU": "Blanc doux Maroparasy 75 cl",
        "VIN BLANC COTE DE FIANARA 750ML NU": "Côte de Fianar Blanc 75 cl",
        "VIN GRIS COTE DE FIANARA 750ML NU": "Côte de Fianar Gris 75 cl",
        "VIN ROSE COTE DE FIANARA 750ML NU": "Côte de Fianar Rosé 75 cl",
        "VIN ROUGE DOUX MAROPARASY 750ML NU": "Maroparasy Rouge 75 cl",
    }
    
    # Vérifier les correspondances exactes
    for key, value in common_matches.items():
        if key in designation:
            return value
    
    # Correspondances partielles
    if "COTE DE FIANAR" in designation:
        if "ROUGE" in designation:
            return "Côte de Fianar Rouge 75 cl"
        elif "BLANC" in designation:
            return "Côte de Fianar Blanc 75 cl"
        elif "ROSE" in designation or "ROSÉ" in designation:
            return "Côte de Fianar Rosé 75 cl"
        elif "GRIS" in designation:
            return "Côte de Fianar Gris 75 cl"
        else:
            return "Côte de Fianar Rouge 75 cl"
    
    elif "MAROPARASY" in designation:
        if "ROUGE" in designation:
            return "Maroparasy Rouge 75 cl"
        elif "BLANC" in designation and "DOUX" in designation:
            return "Blanc doux Maroparasy 75 cl"
        else:
            return "Maroparasy Rouge 75 cl"
    
    elif "AMBALAVAO" in designation:
        if "SPEC" in designation or "SPÉCIAL" in designation or "CUVEE" in designation:
            return "Côteau d'Ambalavao Spécial 75 cl"
        else:
            return "Côteau d'Ambalavao Rouge 75 cl"
    
    elif "CONS" in designation and "CHAN" in designation:
        return "CONS 2000 CHANFOUI"
    
    # Pour ULYS spécifiquement, nettoyer les mentions inutiles
    if client_type == "ULYS":
        designation = designation.replace("750ML NU", "").replace("VIN", "").strip()
        designation = re.sub(r'\s+', ' ', designation)
    
    # Pour Leader Price, nettoyer les mentions BTL, etc.
    if client_type == "LEADER PRICE":
        designation = designation.replace("BTL", "").replace("NU", "").replace("LOGE", "").strip()
        designation = re.sub(r'\s+', ' ', designation)
    
    # Capitaliser la première lettre de chaque mot (sauf articles)
    words = designation.split()
    capitalized_words = []
    for word in words:
        if word.lower() in ['de', 'd', 'la', 'le', 'les', 'du', 'des']:
            capitalized_words.append(word.lower())
        else:
            capitalized_words.append(word.capitalize())
    
    return ' '.join(capitalized_words)

# ==================== PIPELINE PRINCIPAL SIMPLIFIÉ ====================
def bdc_pipeline_simple(image_bytes: bytes, client_type: str = "auto"):
    """Pipeline BDC simplifié avec Google Vision AI - 2 colonnes seulement"""
    
    # 1. Prétraitement
    processed_img = advanced_preprocess_image(image_bytes)
    
    # 2. OCR avec Google Vision AI
    with st.spinner("🔍 Analyse avec Google Vision AI..."):
        ocr_result = google_vision_ai_ocr(processed_img)
    
    raw_text = ocr_result["raw_text"]
    raw_text = clean_text(raw_text)
    
    # 3. Détection automatique du client
    if client_type == "auto":
        if "SUPERMAKI" in raw_text or "AMBOHIBAO" in raw_text:
            client_type = "SUPERMAKI"
        elif "LEADER PRICE" in raw_text or "D.L.P.M" in raw_text or "BCD" in raw_text:
            client_type = "LEADER PRICE"
        elif "ULYS" in raw_text or "SUPER U" in raw_text or "BON DE COMMANDE FOURNISSEUR" in raw_text:
            client_type = "ULYS"
        else:
            client_type = "SUPERMAKI"
    
    # 4. Extraction selon le client
    if client_type == "SUPERMAKI":
        result = extract_bdc_supermaki_simple(raw_text)
    elif client_type == "LEADER PRICE":
        result = extract_bdc_leader_price_simple(raw_text)
    elif client_type == "ULYS":
        result = extract_bdc_ulys_simple(raw_text)
    else:
        result = extract_bdc_supermaki_simple(raw_text)
    
    # 5. Nettoyer et valider
    valid_articles = []
    for article in result["articles"]:
        if article.get("Désignation") and article.get("Qté"):
            # Nettoyer la quantité
            qte = str(article["Qté"])
            qte = qte.replace('.', '').replace(',', '').strip()
            if qte.isdigit():
                article["Qté"] = qte
                valid_articles.append(article)
    
    result["articles"] = valid_articles
    
    # 6. Calculer la confiance
    total_articles = len(result["articles"])
    if total_articles > 0:
        result["overall_confidence"] = min(0.95, 0.7 + (total_articles * 0.05))  # Augmente avec le nombre d'articles
        result["article_count"] = total_articles
    else:
        result["overall_confidence"] = 0
        result["article_count"] = 0
    
    # 7. Métadonnées
    result["raw"] = raw_text[:500] + "..." if len(raw_text) > 500 else raw_text  # Limiter pour l'affichage
    result["client_type"] = client_type
    
    return result

def display_simple_table(articles, client_type):
    """Affiche un tableau simplifié 2 colonnes"""
    
    if not articles:
        return "<div class='table-preview'><p style='color: #666; text-align: center; padding: 20px;'>Aucun article détecté dans le document</p></div>"
    
    # Générer le HTML du tableau simplifié
    html = f"""
    <div class='table-preview'>
        <div style='margin-bottom: 15px; font-weight: bold; color: var(--petrol);'>
            📋 {len(articles)} article(s) détecté(s) - Format {client_type}
        </div>
        <table class='simple-table'>
            <thead>
                <tr>
                    <th>Désignation / Article</th>
                    <th>Quantité</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Ajouter les lignes d'articles
    total_qty = 0
    for i, item in enumerate(articles):
        designation = item.get("Désignation", "")
        qte = item.get("Qté", "0")
        
        try:
            qte_num = int(str(qte).replace('.', '').replace(',', ''))
            total_qty += qte_num
            qte_formatted = f"{qte_num:,}".replace(",", " ")
        except:
            qte_formatted = qte
        
        html += f"""
                <tr>
                    <td>{designation}</td>
                    <td style='font-weight: bold; text-align: center;'>{qte_formatted}</td>
                </tr>
        """
    
    html += f"""
            </tbody>
        </table>
        <div style='margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 6px; text-align: center;'>
            <strong>Quantité totale : {total_qty:,} unités</strong>
        </div>
    </div>
    """
    
    return html

# ---------------------------
# Facture Extraction Functions (inchangées)
# ---------------------------
def extract_invoice_number(text: str) -> str:
    patterns = [
        r"FACTURE\s+EN\s+COMPTE.*?N[°o]?\s*([0-9]{3,})",
        r"FACTURE.*?N[°o]\s*([0-9]{3,})",
        r"FACTURE.*?N\s*([0-9]{3,})",
        r"N°\s*([0-9]{3,})"
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return m.group(1).strip()
    return ""

def extract_delivery_address(text: str) -> str:
    patterns = [
        r"Adresse de livraison\s*[:\-]\s*(.+)",
        r"Adresse(?:\s+de\s+livraison)?\s*[:\-]?\s*\n?\s*(.+)"
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            address = m.group(1).strip().rstrip(".")
            return address.split("\n")[0] if "\n" in address else address
    return ""

def extract_doit(text: str) -> str:
    p = r"\bDOIT\s*[:\-]?\s*([A-Z0-9]{2,6})"
    m = re.search(p, text, flags=re.I)
    if m:
        return m.group(1).strip()
    candidates = ["S2M", "ULYS", "DLP"]
    for c in candidates:
        if c in text:
            return c
    return ""

def extract_month(text: str) -> str:
    months = {
        "janvier": "Janvier", "février": "Février", "fevrier": "Février",
        "mars": "Mars", "avril": "Avril", "mai": "Mai",
        "juin": "Juin", "juillet": "Juillet", "août": "Août",
        "aout": "Août", "septembre": "Septembre", "octobre": "Octobre",
        "novembre": "Novembre", "décembre": "Décembre", "decembre": "Décembre"
    }
    for mname in months:
        if re.search(r"\b" + re.escape(mname) + r"\b", text, flags=re.I):
            return months[mname]
    return ""

def extract_bon_commande(text: str) -> str:
    patterns = [
        r"Suivant votre bon de commande\s*[:\-]?\s*([0-9A-Za-z\-\/]+)",
        r"bon de commande\s*[:\-]?\s*(.+)"
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return m.group(1).strip().split()[0]
    return ""

def extract_invoice_items(text: str):
    items = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    pattern = re.compile(r"(.+?(?:75\s*cls?|75\s*cl|75cl|75))\s+\d+\s+\d+\s+(\d+)", flags=re.I)
    
    for line in lines:
        m = pattern.search(line)
        if m:
            name = m.group(1).strip()
            nb_btls = int(m.group(2))
            name = re.sub(r"\s{2,}", " ", name)
            items.append({"article": name, "bouteilles": nb_btls})
    
    if not items:
        for line in lines:
            if "75" in line or "cls" in line.lower():
                nums = re.findall(r"(\d{1,4})", line)
                if nums:
                    nb_btls = int(nums[-1])
                    name = re.sub(r"\d+", "", line).strip()
                    if name:
                        items.append({"article": name, "bouteilles": nb_btls})
    
    return items

def preprocess_image(image_bytes: bytes) -> bytes:
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    max_w = 2600
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
    out = BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()

def google_vision_ocr(img_bytes: bytes) -> str:
    """Utilise document_text_detection pour les factures aussi"""
    client = get_vision_client()
    image = vision.Image(content=img_bytes)
    
    # Utiliser document_text_detection pour une meilleure précision
    response = client.document_text_detection(image=image)
    
    if response.error and response.error.message:
        raise Exception(f"Google Vision Error: {response.error.message}")
    
    raw = ""
    if response.full_text_annotation:
        raw = response.full_text_annotation.text
    
    return raw or ""

def invoice_pipeline(image_bytes: bytes):
    cleaned = preprocess_image(image_bytes)
    raw = google_vision_ocr(cleaned)
    raw = clean_text(raw)
    
    return {
        "raw": raw,
        "facture": extract_invoice_number(raw),
        "adresse": extract_delivery_address(raw),
        "doit": extract_doit(raw),
        "mois": extract_month(raw),
        "bon_commande": extract_bon_commande(raw),
        "articles": extract_invoice_items(raw)
    }

# ---------------------------
# Google Sheets Functions (inchangées)
# ---------------------------
def get_bdc_worksheet():
    if "gcp_sheet" in st.secrets:
        sa_info = dict(st.secrets["gcp_sheet"])
    elif "google_service_account" in st.secrets:
        sa_info = dict(st.secrets["google_service_account"])
    else:
        return None
    
    try:
        client = gspread.service_account_from_dict(sa_info)
        sh = client.open_by_key(BDC_SHEET_ID)
        
        for ws in sh.worksheets():
            if int(ws.id) == BDC_SHEET_GID:
                return ws
        
        return sh.sheet1
    except Exception:
        return None

def get_invoice_worksheet():
    if "gcp_sheet" in st.secrets:
        sa_info = dict(st.secrets["gcp_sheet"])
    elif "google_service_account" in st.secrets:
        sa_info = dict(st.secrets["google_service_account"])
    else:
        return None
    
    try:
        client = gspread.service_account_from_dict(sa_info)
        sh = client.open_by_key(INVOICE_SHEET_ID)
        
        for ws in sh.worksheets():
            if int(ws.id) == INVOICE_SHEET_GID:
                return ws
        
        return sh.sheet1
    except Exception:
        return None

def save_invoice_without_duplicates(ws, invoice_data, user_nom):
    try:
        def clean_value(v):
            try:
                if v is None:
                    return ""
                if isinstance(v, float):
                    if np.isnan(v) or np.isinf(v):
                        return ""
                return v
            except:
                return ""

        all_values = ws.get_all_values()
        
        for row in all_values:
            if len(row) >= 7:
                existing_mois = row[0] if len(row) > 0 else ""
                existing_bdc = row[3] if len(row) > 3 else ""
                existing_article = row[5] if len(row) > 5 else ""

                if (existing_mois == invoice_data["mois"] and 
                    existing_bdc == invoice_data["bon_commande"] and
                    any(item["article"] == existing_article for item in invoice_data["articles"])):
                    return 0, 1

        today_str = datetime.now().strftime("%d/%m/%Y")
        
        rows_to_add = []
        for item in invoice_data["articles"]:
            row = [
                invoice_data["mois"],
                invoice_data["doit"],
                today_str,
                invoice_data["bon_commande"],
                invoice_data["adresse"],
                item["article"],
                item["bouteilles"],
                user_nom
            ]

            row = [clean_value(x) for x in row]
            rows_to_add.append(row)

        if rows_to_add:
            ws.append_rows(rows_to_add)
            return len(rows_to_add), 0

        return 0, 0

    except Exception as e:
        raise Exception(f"Erreur lors de l'enregistrement: {str(e)}")

def save_bdc_simple_to_sheets(ws, bdc_data, user_nom):
    """Enregistre les BDC simplifiés (2 colonnes) dans Google Sheets"""
    try:
        all_values = ws.get_all_values()
        
        # Vérifier les doublons
        for row in all_values:
            if len(row) >= 7:
                existing_bdc = row[2] if len(row) > 2 else ""
                existing_client = row[1] if len(row) > 1 else ""
                existing_article = row[4] if len(row) > 4 else ""
                
                for item in bdc_data["articles"]:
                    if (existing_bdc == bdc_data["numero"] and 
                        existing_client == bdc_data["client"] and
                        existing_article == item.get("Désignation", "")):
                        return 0, 1  # Doublon trouvé
        
        # Préparer les lignes à ajouter
        rows_to_add = []
        for item in bdc_data["articles"]:
            designation = item.get("Désignation", "")
            qte = item.get("Qté", "")
            
            if designation and qte:
                rows_to_add.append([
                    bdc_data.get("date", ""),
                    bdc_data.get("client", ""),
                    bdc_data.get("numero", ""),
                    bdc_data.get("adresse_livraison", bdc_data.get("nom_magasin", "")),
                    str(designation).strip(),
                    str(qte).strip(),
                    user_nom
                ])
        
        # Ajouter les lignes
        if rows_to_add:
            ws.append_rows(rows_to_add)
            return len(rows_to_add), 0
        
        return 0, 0  # Aucune donnée à enregistrer
    
    except Exception as e:
        raise Exception(f"Erreur lors de l'enregistrement: {str(e)}")

# ---------------------------
# Session State
# ---------------------------
if "auth" not in st.session_state:
    st.session_state.auth = False
if "user_nom" not in st.session_state:
    st.session_state.user_nom = ""
if "mode" not in st.session_state:
    st.session_state.mode = None
if "invoice_scans" not in st.session_state:
    st.session_state.invoice_scans = 0
if "bdc_scans" not in st.session_state:
    st.session_state.bdc_scans = 0
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "show_ocr_results" not in st.session_state:
    st.session_state.show_ocr_results = False
if "ocr_result" not in st.session_state:
    st.session_state.ocr_result = None
if "selected_client_type" not in st.session_state:
    st.session_state.selected_client_type = "auto"
if "bdc_client_type" not in st.session_state:
    st.session_state.bdc_client_type = None

# ---------------------------
# Header avec logo et titre
# ---------------------------
col_logo, col_title = st.columns([1, 3])
with col_logo:
    if os.path.exists(LOGO_FILENAME):
        st.image(LOGO_FILENAME, width=100)
    else:
        st.markdown("🍷")

with col_title:
    st.markdown(f"<h1 class='brand-title'>{BRAND_TITLE}</h1>", unsafe_allow_html=True)

st.markdown(f"<p class='brand-sub'>{BRAND_SUB}</p>", unsafe_allow_html=True)

# ---------------------------
# Authentication
# ---------------------------
if not st.session_state.auth:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center'>🔐 Connexion</h3>", unsafe_allow_html=True)
    
    nom = st.text_input("Nom (ex: admin)")
    mat = st.text_input("code", type="password")
    
    if st.button("Se connecter"):
        if nom and nom.upper() in AUTHORIZED_USERS and AUTHORIZED_USERS[nom.upper()] == mat:
            st.session_state.auth = True
            st.session_state.user_nom = nom.upper()
            st.rerun()
        else:
            st.error("❌ Nom ou matricule invalide")
    
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ---------------------------
# Mode Selection
# ---------------------------
if st.session_state.mode is None:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center'>📌 Choisissez un mode de scan</h3>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📄 Scanner Facture", use_container_width=True):
            st.session_state.mode = "facture"
            st.rerun()
    
    with col2:
        if st.button("📝 Scanner BDC (Google Vision AI)", use_container_width=True):
            st.session_state.mode = "bdc"
            st.rerun()
    
    st.markdown("<p style='text-align:center;font-size:0.9em;color:var(--muted)'>"
                "Version BDC avec Google Vision AI pour une extraction ultra-précise</p>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("🚪 Déconnexion"):
        st.session_state.auth = False
        st.session_state.user_nom = ""
        st.rerun()
    
    st.stop()

# ---------------------------
# Facture Mode (inchangé)
# ---------------------------
if st.session_state.mode == "facture":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center'>📄 Scanner une Facture</h3>", unsafe_allow_html=True)
    
    uploaded = st.file_uploader("Téléchargez l'image de la facture", type=["jpg", "jpeg", "png"], 
                                key="facture_uploader")
    
    if uploaded and uploaded != st.session_state.uploaded_file:
        st.session_state.uploaded_file = uploaded
        st.session_state.show_ocr_results = False
        st.session_state.ocr_result = None
    
    if st.session_state.uploaded_file and not st.session_state.show_ocr_results:
        try:
            img = Image.open(st.session_state.uploaded_file)
            st.image(img, caption="Aperçu de la facture", use_column_width=True)
            
            buf = BytesIO()
            img.save(buf, format="JPEG")
            img_bytes = buf.getvalue()
            
            with st.spinner("Traitement OCR avec Google Vision AI..."):
                try:
                    result = invoice_pipeline(img_bytes)
                    st.session_state.ocr_result = result
                    st.session_state.show_ocr_results = True
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erreur OCR: {str(e)}")
        
        except Exception as e:
            st.error(f"❌ Erreur de traitement d'image: {str(e)}")
    
    elif st.session_state.uploaded_file and st.session_state.show_ocr_results and st.session_state.ocr_result:
        result = st.session_state.ocr_result
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h4>📋 Informations détectées</h4>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            mois = st.text_input("Mois", value=result.get("mois", ""), key="facture_mois")
            doit = st.text_input("DOIT", value=result.get("doit", ""), key="facture_doit")
            bon_commande = st.text_input("Bon de commande", value=result.get("bon_commande", ""), key="facture_bdc")
        
        with col2:
            adresse = st.text_input("Adresse de livraison", value=result.get("adresse", ""), key="facture_adresse")
            facture = st.text_input("Numéro de facture (pour référence)", value=result.get("facture", ""), key="facture_num")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h4>🛒 Articles détectés</h4>", unsafe_allow_html=True)
        
        articles = result.get("articles", [])
        if articles:
            df = pd.DataFrame(articles)
            edited_df = st.data_editor(
                df,
                num_rows="dynamic",
                column_config={
                    "article": st.column_config.TextColumn("Article", width="large"),
                    "bouteilles": st.column_config.NumberColumn("Bouteilles", min_value=0, width="small")
                },
                use_container_width=True,
                key="facture_articles"
            )
        else:
            st.warning("Aucun article détecté. Ajoutez-les manuellement.")
            df = pd.DataFrame(columns=["article", "bouteilles"])
            edited_df = st.data_editor(
                df,
                num_rows="dynamic",
                column_config={
                    "article": st.column_config.TextColumn("Article"),
                    "bouteilles": st.column_config.NumberColumn("Bouteilles", min_value=0)
                },
                use_container_width=True,
                key="facture_articles_empty"
            )
        
        if st.button("➕ Ajouter une ligne", key="facture_add_line"):
            new_row = {"article": "", "bouteilles": 0}
            if 'edited_df' in locals():
                edited_df = pd.concat([edited_df, pd.DataFrame([new_row])], ignore_index=True)
            else:
                edited_df = pd.DataFrame([new_row])
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        with st.expander("📄 Voir le texte OCR brut"):
            st.text_area("Texte OCR", value=result.get("raw", ""), height=200, key="facture_raw")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h4>📤 Export vers Google Sheets</h4>", unsafe_allow_html=True)
        
        ws = get_invoice_worksheet()
        
        if ws is None:
            st.warning("⚠️ Google Sheets non configuré. Configurez les credentials dans les secrets.")
        else:
            if st.button("💾 Enregistrer la facture", use_container_width=True, key="facture_save"):
                try:
                    if not hasattr(st.session_state, 'user_nom') or not st.session_state.user_nom:
                        st.error("❌ Erreur de session. Veuillez vous reconnecter.")
                    else:
                        data_to_save = []
                        for _, row in edited_df.iterrows():
                            if str(row["article"]).strip() and str(row["bouteilles"]).strip():
                                data_to_save.append([
                                    mois,
                                    doit,
                                    datetime.now().strftime("%d/%m/%Y"),
                                    bon_commande,
                                    adresse,
                                    str(row["article"]).strip(),
                                    str(row["bouteilles"]).strip(),
                                    st.session_state.user_nom
                                ])
                        
                        if data_to_save:
                            saved_count, duplicate_count = save_invoice_without_duplicates(ws, {
                                "mois": mois,
                                "doit": doit,
                                "bon_commande": bon_commande,
                                "adresse": adresse,
                                "articles": edited_df.to_dict('records')
                            }, st.session_state.user_nom)
                            
                            if saved_count > 0:
                                st.session_state.invoice_scans += 1
                                st.success(f"✅ {saved_count} ligne(s) enregistrée(s) avec succès!")
                                st.info(f"📝 Format enregistré: Mois | Doit | Date | Bon de commande | Adresse | Article | Bouteilles | Editeur")
                                st.info(f"👤 Enregistré par: {st.session_state.user_nom}")
                                
                                if st.button("🗑️ Effacer et recommencer", use_container_width=True, type="secondary"):
                                    st.session_state.uploaded_file = None
                                    st.session_state.show_ocr_results = False
                                    st.session_state.ocr_result = None
                                    st.rerun()
                                    
                            elif duplicate_count > 0:
                                st.warning("⚠️ Cette facture existe déjà dans la base de données.")
                            else:
                                st.warning("⚠️ Aucune donnée valide à enregistrer")
                                
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ Effacer et recommencer", use_container_width=True, type="secondary", key="facture_clear_bottom"):
                st.session_state.uploaded_file = None
                st.session_state.show_ocr_results = False
                st.session_state.ocr_result = None
                st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    else:
        st.info("📤 Veuillez télécharger une image de facture")
        st.markdown("</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Retour"):
            st.session_state.mode = None
            st.session_state.uploaded_file = None
            st.session_state.show_ocr_results = False
            st.session_state.ocr_result = None
            st.rerun()
    
    with col2:
        if st.button("📝 Passer aux BDC"):
            st.session_state.mode = "bdc"
            st.session_state.uploaded_file = None
            st.session_state.show_ocr_results = False
            st.session_state.ocr_result = None
            st.rerun()
    
    with col3:
        if st.button("🚪 Déconnexion"):
            st.session_state.auth = False
            st.session_state.user_nom = ""
            st.session_state.mode = None
            st.session_state.uploaded_file = None
            st.session_state.show_ocr_results = False
            st.session_state.ocr_result = None
            st.rerun()

# ---------------------------
# NOUVEAU MODE BDC AVEC GOOGLE VISION AI
# ---------------------------
elif st.session_state.mode == "bdc":
    if not st.session_state.bdc_client_type:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align:center'>📝 Sélectionnez le type de Bon de Commande</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center'>Choisissez le client correspondant à votre BDC</p>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("<div class='scan-option-card'>", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align:center'>🍷 SUPERMAKI</h4>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center;font-size:0.9em'>Format avec tableau REF/EAN</p>", unsafe_allow_html=True)
            if st.button("Sélectionner SUPERMAKI", key="select_supermaki", use_container_width=True):
                st.session_state.bdc_client_type = "SUPERMAKI"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col2:
            st.markdown("<div class='scan-option-card'>", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align:center'>🏪 LEADER PRICE</h4>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center;font-size:0.9em'>Format avec quantité.000</p>", unsafe_allow_html=True)
            if st.button("Sélectionner LEADER PRICE", key="select_leader", use_container_width=True):
                st.session_state.bdc_client_type = "LEADER PRICE"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col3:
            st.markdown("<div class='scan-option-card'>", unsafe_allow_html=True)
            st.markdown("<h4 style='text-align:center'>🛒 ULYS</h4>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center;font-size:0.9em'>Format avec GTIN et PAQ</p>", unsafe_allow_html=True)
            if st.button("Sélectionner ULYS", key="select_ulys", use_container_width=True):
                st.session_state.bdc_client_type = "ULYS"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='card' style='margin-top:20px'>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align:center'>🔍 Détection Automatique</h4>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center'>Google Vision AI détectera automatiquement le format</p>", unsafe_allow_html=True)
        if st.button("🎯 Détection Automatique", key="select_auto", use_container_width=True):
            st.session_state.bdc_client_type = "auto"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("⬅️ Retour"):
                st.session_state.mode = None
                st.rerun()
        
        st.stop()
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    
    client_badge_class = ""
    if st.session_state.bdc_client_type == "SUPERMAKI":
        client_badge_class = "badge-supermaki"
        client_name = "SUPERMAKI"
    elif st.session_state.bdc_client_type == "LEADER PRICE":
        client_badge_class = "badge-leader"
        client_name = "LEADER PRICE"
    elif st.session_state.bdc_client_type == "ULYS":
        client_badge_class = "badge-ulys"
        client_name = "ULYS"
    else:
        client_badge_class = "badge-supermaki"
        client_name = "Détection Automatique"
    
    st.markdown(f"""
        <div style='display: flex; justify-content: center; align-items: center; gap: 10px; margin-bottom: 20px;'>
            <h3 style='text-align:center; margin:0'>📝 Scanner un Bon de Commande</h3>
            <span class='client-badge {client_badge_class}'>{client_name}</span>
        </div>
        """, unsafe_allow_html=True)
    
    if st.button("🔄 Changer de type de BDC"):
        st.session_state.bdc_client_type = None
        st.session_state.uploaded_file = None
        st.session_state.show_ocr_results = False
        st.session_state.ocr_result = None
        st.rerun()
    
    uploaded = st.file_uploader(f"Téléchargez l'image du BDC {client_name}", type=["jpg", "jpeg", "png"], 
                                key="bdc_uploader")
    
    if uploaded and uploaded != st.session_state.uploaded_file:
        st.session_state.uploaded_file = uploaded
        st.session_state.show_ocr_results = False
        st.session_state.ocr_result = None
    
    if st.session_state.uploaded_file and not st.session_state.show_ocr_results:
        try:
            img = Image.open(st.session_state.uploaded_file)
            st.image(img, caption=f"Aperçu du BDC {client_name}", use_column_width=True)
            
            buf = BytesIO()
            img.save(buf, format="JPEG")
            img_bytes = buf.getvalue()
            
            with st.spinner(f"🔍 Analyse avec Google Vision AI pour {client_name}..."):
                try:
                    result = bdc_pipeline_simple(img_bytes, st.session_state.bdc_client_type)
                    st.session_state.ocr_result = result
                    st.session_state.show_ocr_results = True
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Erreur OCR: {str(e)}")
        
        except Exception as e:
            st.error(f"❌ Erreur de traitement d'image: {str(e)}")
    
    elif st.session_state.uploaded_file and st.session_state.show_ocr_results and st.session_state.ocr_result:
        result = st.session_state.ocr_result
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # APERÇU DU TABLEAU SIMPLIFIÉ (2 COLONNES)
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"<h4>📊 Articles détectés (2 colonnes)</h4>", unsafe_allow_html=True)
        
        # Afficher le tableau formaté
        table_html = display_simple_table(result.get("articles", []), result.get("client_type", ""))
        st.markdown(table_html, unsafe_allow_html=True)
        
        # Indicateur de confiance
        overall_confidence = result.get("overall_confidence", 0)
        article_count = result.get("article_count", 0)
        
        if article_count > 0:
            if overall_confidence > 0.8:
                confidence_class = "confidence-high"
                confidence_text = "Élevée"
                st.balloons()
            elif overall_confidence > 0.6:
                confidence_class = "confidence-medium"
                confidence_text = "Moyenne"
            else:
                confidence_class = "confidence-low"
                confidence_text = "À vérifier"
            
            st.markdown(f"""
                <div class="{confidence_class}" style="margin-top: 15px;">
                    <strong>Confiance d'extraction : {overall_confidence:.0%} ({confidence_text})</strong><br>
                    <small>Basée sur {article_count} article(s) détecté(s) - Format {result.get('client_type', '')}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Aucun article détecté. Vérifiez la qualité de l'image ou essayez un autre type de BDC.")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Section informations détectées
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h4>📋 Informations du BDC</h4>", unsafe_allow_html=True)
        
        if result.get("client_type") == "SUPERMAKI":
            col1, col2 = st.columns(2)
            with col1:
                date = st.text_input("Date diffusion", value=result.get("date", ""), key="bdc_date")
                numero = st.text_input("Numéro BDC", value=result.get("numero", ""), key="bdc_numero")
            
            with col2:
                adresse = st.text_input("Adresse livraison", value=result.get("adresse_livraison", ""), key="bdc_adresse")
            
            client = "SUPERMAKI"
        
        elif result.get("client_type") == "LEADER PRICE":
            col1, col2 = st.columns(2)
            with col1:
                date = st.text_input("Date", value=result.get("date", ""), key="bdc_date")
                numero = st.text_input("Numéro Commande", value=result.get("numero", ""), key="bdc_numero")
            
            with col2:
                adresse = st.text_input("Adresse livraison", value=result.get("adresse_livraison", ""), key="bdc_adresse")
            
            client = "LEADER PRICE"
        
        elif result.get("client_type") == "ULYS":
            col1, col2 = st.columns(2)
            with col1:
                date = st.text_input("Date de la Commande", value=result.get("date", ""), key="bdc_date")
                numero = st.text_input("N°", value=result.get("numero", ""), key="bdc_numero")
            
            with col2:
                adresse = st.text_input("Nom du Magasin", value=result.get("nom_magasin", ""), key="bdc_adresse")
            
            client = "ULYS"
        
        else:
            col1, col2 = st.columns(2)
            with col1:
                date = st.text_input("Date émission", value=result.get("date", ""), key="bdc_date")
                client = st.text_input("Client/Facturation", value=result.get("client", ""), key="bdc_client")
            
            with col2:
                numero = st.text_input("Numéro BDC", value=result.get("numero", ""), key="bdc_numero")
                adresse = st.text_input("Adresse livraison", value=result.get("adresse_livraison", ""), key="bdc_adresse")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Section articles éditable (tableau 2 colonnes)
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h4>🛒 Édition des articles</h4>", unsafe_allow_html=True)
        st.markdown("<p>Tableau simplifié - 2 colonnes seulement</p>", unsafe_allow_html=True)
        
        articles = result.get("articles", [])
        if articles:
            # Créer un DataFrame avec les 2 colonnes
            data = []
            for item in articles:
                data.append({
                    "Désignation": item.get("Désignation", ""),
                    "Quantité": item.get("Qté", "")
                })
            
            df = pd.DataFrame(data)
            
            # Éditeur de données
            edited_df = st.data_editor(
                df,
                num_rows="dynamic",
                column_config={
                    "Désignation": st.column_config.TextColumn(
                        "Désignation / Article",
                        width="large",
                        help="Nom de l'article ou désignation"
                    ),
                    "Quantité": st.column_config.NumberColumn(
                        "Quantité",
                        min_value=0,
                        width="small",
                        help="Quantité commandée"
                    )
                },
                use_container_width=True,
                key="bdc_articles_simple"
            )
        else:
            st.info("💡 Pour ajouter des articles manuellement, utilisez le tableau ci-dessous.")
            df = pd.DataFrame(columns=["Désignation", "Quantité"])
            edited_df = st.data_editor(
                df,
                num_rows="dynamic",
                column_config={
                    "Désignation": st.column_config.TextColumn("Désignation / Article"),
                    "Quantité": st.column_config.NumberColumn("Quantité", min_value=0)
                },
                use_container_width=True,
                key="bdc_articles_empty_simple"
            )
        
        if st.button("➕ Ajouter une ligne manuellement", key="bdc_add_line_simple"):
            new_row = {"Désignation": "", "Quantité": 0}
            if 'edited_df' in locals():
                edited_df = pd.concat([edited_df, pd.DataFrame([new_row])], ignore_index=True)
            else:
                edited_df = pd.DataFrame([new_row])
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Section debug OCR
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        with st.expander("🔍 Voir l'extrait OCR pour vérification"):
            st.text_area("Texte OCR (extrait)", value=result.get("raw", ""), height=150, key="bdc_raw")
        
        # Bouton pour réessayer
        if st.button("🔄 Réanalyser avec Google Vision AI", key="bdc_retry"):
            st.session_state.show_ocr_results = False
            st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Section export Google Sheets
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("<h4>📤 Export vers Google Sheets</h4>", unsafe_allow_html=True)
        
        ws = get_bdc_worksheet()
        
        if ws is None:
            st.warning("⚠️ Google Sheets non configuré. Configurez les credentials dans les secrets.")
        else:
            if st.button("💾 Enregistrer dans Google Sheets", use_container_width=True, key="bdc_save"):
                try:
                    if not hasattr(st.session_state, 'user_nom') or not st.session_state.user_nom:
                        st.error("❌ Erreur de session. Veuillez vous reconnecter.")
                    else:
                        # Préparer les données à partir du dataframe édité
                        articles_to_save = []
                        if 'edited_df' in locals():
                            for _, row in edited_df.iterrows():
                                if str(row["Désignation"]).strip() and str(row["Quantité"]).strip():
                                    articles_to_save.append({
                                        "Désignation": str(row["Désignation"]).strip(),
                                        "Qté": str(row["Quantité"]).strip()
                                    })
                        
                        if articles_to_save:
                            bdc_data = {
                                "date": date,
                                "client": client,
                                "numero": numero,
                                "adresse_livraison": adresse,
                                "nom_magasin": result.get("nom_magasin", ""),
                                "articles": articles_to_save
                            }
                            
                            saved_count, duplicate_count = save_bdc_simple_to_sheets(ws, bdc_data, st.session_state.user_nom)
                            
                            if saved_count > 0:
                                st.session_state.bdc_scans += 1
                                st.success(f"✅ {saved_count} ligne(s) enregistrée(s) avec succès!")
                                st.info(f"📝 Format simplifié: Date | Client | Numéro BDC | Adresse | Article | Quantité | Editeur")
                                st.info(f"👤 Enregistré par: {st.session_state.user_nom}")
                                st.info(f"🏷️ Type détecté: {result.get('client_type', 'Inconnu')}")
                                
                                # Afficher un récapitulatif
                                st.markdown("---")
                                st.markdown("### 📋 Récapitulatif enregistré:")
                                total_qty = 0
                                for i, article in enumerate(articles_to_save[:5]):  # Montrer les 5 premiers
                                    qty = article.get("Qté", "0")
                                    try:
                                        total_qty += int(qty)
                                    except:
                                        pass
                                    st.write(f"**{i+1}.** {article.get('Désignation', '')} - Qté: {qty}")
                                
                                if len(articles_to_save) > 5:
                                    st.write(f"... et {len(articles_to_save) - 5} autres articles")
                                
                                st.write(f"**Total:** {total_qty} unités")
                                
                                if st.button("🗑️ Effacer et scanner un nouveau BDC", use_container_width=True, type="secondary"):
                                    st.session_state.uploaded_file = None
                                    st.session_state.show_ocr_results = False
                                    st.session_state.ocr_result = None
                                    st.rerun()
                                    
                            elif duplicate_count > 0:
                                st.warning("⚠️ Ce BDC existe déjà dans la base de données.")
                            else:
                                st.warning("⚠️ Aucune donnée valide à enregistrer")
                        else:
                            st.error("❌ Aucun article valide à enregistrer. Vérifiez les désignations et quantités.")
                            
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
            
            # Boutons de contrôle
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🗑️ Effacer et recommencer", use_container_width=True, type="secondary", key="bdc_clear"):
                    st.session_state.uploaded_file = None
                    st.session_state.show_ocr_results = False
                    st.session_state.ocr_result = None
                    st.rerun()
            
            with col2:
                if st.button("🔄 Nouveau type de BDC", use_container_width=True, type="secondary", key="bdc_new_type"):
                    st.session_state.bdc_client_type = None
                    st.session_state.uploaded_file = None
                    st.session_state.show_ocr_results = False
                    st.session_state.ocr_result = None
                    st.rerun()
            
            with col3:
                if st.button("📤 Tester avec autre image", use_container_width=True, type="secondary", key="bdc_test_another"):
                    st.session_state.uploaded_file = None
                    st.session_state.show_ocr_results = False
                    st.rerun()
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    else:
        st.info(f"📤 Veuillez télécharger une image de bon de commande {client_name}")
        st.markdown("</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Retour"):
            st.session_state.mode = None
            st.session_state.bdc_client_type = None
            st.session_state.uploaded_file = None
            st.session_state.show_ocr_results = False
            st.session_state.ocr_result = None
            st.rerun()
    
    with col2:
        if st.button("📄 Passer aux factures"):
            st.session_state.mode = "facture"
            st.session_state.bdc_client_type = None
            st.session_state.uploaded_file = None
            st.session_state.show_ocr_results = False
            st.session_state.ocr_result = None
            st.rerun()
    
    with col3:
        if st.button("🚪 Déconnexion"):
            st.session_state.auth = False
            st.session_state.user_nom = ""
            st.session_state.mode = None
            st.session_state.bdc_client_type = None
            st.session_state.uploaded_file = None
            st.session_state.show_ocr_results = False
            st.session_state.ocr_result = None
            st.rerun()

# ---------------------------
# Footer
# ---------------------------
st.markdown("---")
st.markdown(f"<p style='text-align:center;color:{PALETTE['muted']};font-size:0.8em'>"
            f"Session: {st.session_state.user_nom} | Factures: {st.session_state.invoice_scans} | BDC: {st.session_state.bdc_scans}</p>", 
            unsafe_allow_html=True)
