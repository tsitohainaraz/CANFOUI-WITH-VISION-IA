import streamlit as st
import re
import pandas as pd
import numpy as np
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps
import openai
from openai import OpenAI
import base64
import gspread
from datetime import datetime
import os
import time
from dateutil import parser
from typing import List, Tuple, Dict, Any, Optional
import hashlib
import json
import unicodedata
import jellyfish

# ============================================================
# STANDARDISATION INTELLIGENTE DES PRODUITS (gardé du code 1)
# ============================================================

# Liste officielle des produits
STANDARD_PRODUCTS = [
    "Côte de Fianar Rouge 75 cl",
    "Côte de Fianar Rouge 37 cl",
    "Côte de Fianar Rouge 3L",
    "Côte de Fianar Blanc 3L",
    "Côte de Fianar Rosé 3L",
    "Blanc doux Maroparasy 3L",
    "Côte de Fianar Blanc 75 cl",
    "Côte de Fianar Blanc 37 cl",
    "Côte de Fianar Rosé 75 cl",
    "Côte de Fianar Rosé 37 cl",
    "Côte de Fianar Gris 75 cl",
    "Côte de Fianar Gris 37 cl",
    "Maroparasy Rouge 75 cl",
    "Maroparasy Rouge 37 cl",
    "Blanc doux Maroparasy 75 cl",
    "Blanc doux Maroparasy 37 cl",
    "Côteau d'Ambalavao Rouge 75 cl",
    "Côteau d'Ambalavao Blanc 75 cl",
    "Côteau d'Ambalavao Rosé 75 cl",
    "Côteau d'Ambalavao Spécial 75 cl",
    "Aperao Orange 75 cl",
    "Aperao Pêche 75 cl",
    "Aperao Ananas 75 cl",
    "Aperao Epices 75 cl",
    "Aperao Ratafia 75 cl",
    "Aperao Eau de vie 75 cl",
    "Aperao Eau de vie 37 cl",
    "Vin de Champêtre 100 cl",
    "Vin de Champêtre 50 cl",
    "Jus de raisin Rouge 70 cl",
    "Jus de raisin Rouge 20 cl",
    "Jus de raisin Blanc 70 cl",
    "Jus de raisin Blanc 20 cl",
    "Sambatra 20 cl"
]

# Dictionnaire de synonymes et normalisations
SYNONYMS = {
    "cote de fianar": "côte de fianar",
    "cote de fianara": "côte de fianar",
    "fianara": "fianar",
    "fianar": "fianar",
    "flanar": "fianar",
    "côte de flanar": "côte de fianar",
    "cote de flanar": "côte de fianar",
    "coteau": "côteau",
    "ambalavao": "ambalavao",
    "coteau d'amb": "côteau d'ambalavao",
    "coteau d'amb/vao": "côteau d'ambalavao",
    "maroparasy": "maroparasy",
    "maroparas": "maroparasy",
    "aperao": "aperao",
    "aperitif": "aperitif",
    "sambatra": "sambatra",
    "champetre": "champêtre",
    "vin rouge": "rouge",
    "vin blanc": "blanc",
    "vin rose": "rosé",
    "vin rosé": "rosé",
    "vin gris": "gris",
    "rouge doux": "rouge doux",
    "blanc doux": "blanc doux",
    "doux": "doux",
    "btl": "",
    "bouteille": "",
    "nu": "",
    "lp7": "",
    "cl": "cl",
    "ml": "ml",
    "l": "l",
    "cons": "",
    "cons.": "",
    "foul": "foui",
    "chan foul": "chan foui",
    "cons. chan foul": "chan foui",
    "cons chan foul": "chan foui",
    "750ml": "75 cl",
    "750 ml": "75 cl",
    "700ml": "70 cl",
    "700 ml": "70 cl",
    "370ml": "37 cl",
    "370 ml": "37 cl",
    "3000ml": "3l",
    "3000 ml": "3l",
    "3 l": "3l",
    "3l": "3l",
    "1000ml": "100 cl",
    "1000 ml": "100 cl",
    "500ml": "50 cl",
    "500 ml": "50 cl",
    "200ml": "20 cl",
    "200 ml": "20 cl",
}

# Mapping des équivalences de volume
VOLUME_EQUIVALENTS = {
    "750": "75",
    "750ml": "75",
    "750 ml": "75",
    "700": "70",
    "700ml": "70",
    "700 ml": "70",
    "370": "37",
    "370ml": "37",
    "370 ml": "37",
    "300": "3",
    "3000": "3",
    "3000ml": "3",
    "3000 ml": "3",
    "1000": "100",
    "1000ml": "100",
    "1000 ml": "100",
    "500": "50",
    "500ml": "50",
    "500 ml": "50",
    "200": "20",
    "200ml": "20",
    "200 ml": "20",
    "75cl": "75",
    "75 cl": "75",
}

def preprocess_text(text: str) -> str:
    """Prétraitement avancé du texte"""
    if not text:
        return ""
    
    text = text.lower()
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('ascii')
    text = text.replace("'", " ").replace("-", " ").replace("_", " ").replace("/", " ")
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    
    words = text.split()
    cleaned_words = []
    for word in words:
        if word in SYNONYMS:
            replacement = SYNONYMS[word]
            if replacement:
                cleaned_words.append(replacement)
        else:
            cleaned_words.append(word)
    
    text = ' '.join(cleaned_words)
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def extract_volume_info(text: str) -> Tuple[str, Optional[str]]:
    """Extrait et normalise l'information de volume"""
    volume_patterns = [
        r'(\d+)\s*cl',
        r'(\d+)\s*ml',
        r'(\d+)\s*l',
        r'(\d+)\s*litre',
        r'(\d+)\s*litres',
    ]
    
    volume = None
    text_without_volume = text
    
    for pattern in volume_patterns:
        matches = re.findall(pattern, text)
        if matches:
            volume = matches[0]
            if 'ml' in pattern:
                try:
                    ml = int(volume)
                    if ml >= 1000:
                        volume = f"{ml//100}l" if ml % 1000 == 0 else f"{ml/10:.0f} cl"
                    else:
                        volume = f"{ml/10:.0f} cl" if ml % 10 == 0 else f"{ml/10:.1f} cl"
                except:
                    pass
            elif 'l' in pattern and 'cl' not in pattern and 'ml' not in pattern:
                try:
                    liters = float(volume)
                    if liters >= 1:
                        volume = f"{liters:.0f}l" if liters.is_integer() else f"{liters}l"
                except:
                    pass
            
            text_without_volume = re.sub(pattern, '', text_without_volume)
            break
    
    if not volume:
        match = re.search(r'\b(\d+)\b', text)
        if match:
            vol_num = match.group(1)
            if vol_num in VOLUME_EQUIVALENTS:
                volume = f"{VOLUME_EQUIVALENTS[vol_num]} cl"
                text_without_volume = re.sub(r'\b' + vol_num + r'\b', '', text_without_volume)
    
    return text_without_volume.strip(), volume

def extract_product_features(text: str) -> Dict[str, str]:
    """Extrait les caractéristiques clés du produit"""
    features = {
        'type': '',
        'marque': '',
        'couleur': '',
        'volume': '',
        'original': text
    }
    
    normalized = preprocess_text(text)
    text_without_volume, volume = extract_volume_info(normalized)
    if volume:
        features['volume'] = volume
    
    colors = ['rouge', 'blanc', 'rose', 'gris', 'orange', 'peche', 'ananas', 'epices', 'ratafia']
    for color in colors:
        if color in text_without_volume:
            features['couleur'] = color
            text_without_volume = text_without_volume.replace(color, '')
            break
    
    types = ['vin', 'jus', 'aperitif', 'eau de vie', 'cuvee', 'cuvee special', 'special', 'consigne']
    for type_ in types:
        if type_ in text_without_volume:
            features['type'] = type_
            text_without_volume = text_without_volume.replace(type_, '')
            break
    
    marques = [
        ('cote de fianar', 'côte de fianar'),
        ('maroparasy', 'maroparasy'),
        ('coteau d ambalavao', 'côteau d\'ambalavao'),
        ('ambalavao', 'côteau d\'ambalavao'),
        ('aperao', 'aperao'),
        ('champetre', 'vin de champêtre'),
        ('sambatra', 'sambatra'),
        ('chan foui', 'chan foui'),
    ]
    
    for marque_pattern, marque_std in marques:
        if marque_pattern in text_without_volume:
            features['marque'] = marque_std
            text_without_volume = text_without_volume.replace(marque_pattern, '')
            break
    
    text_without_volume = re.sub(r'\s+', ' ', text_without_volume).strip()
    if text_without_volume:
        features['autres'] = text_without_volume
    
    return features

def calculate_similarity_score(features1: Dict, features2: Dict) -> float:
    """Calcule un score de similarité entre deux ensembles de caractéristiques"""
    score = 0.0
    max_score = 0.0
    
    weights = {
        'marque': 0.4,
        'couleur': 0.3,
        'volume': 0.2,
        'type': 0.1,
    }
    
    for key, weight in weights.items():
        if features1.get(key) and features2.get(key):
            if features1[key] == features2[key]:
                score += weight
            elif key == 'couleur':
                if ('rose' in features1[key] and 'rosé' in features2[key]) or \
                   ('rosé' in features1[key] and 'rose' in features2[key]):
                    score += weight * 0.8
        max_score += weight
    
    if features1.get('volume') and features2.get('volume'):
        if features1['volume'] == features2['volume']:
            score += 0.1
            max_score += 0.1
    
    return score / max_score if max_score > 0 else 0.0

def find_best_match(ocr_designation: str, standard_products: List[str]) -> Tuple[Optional[str], float]:
    """Trouve le meilleur match pour une désignation OCR"""
    ocr_features = extract_product_features(ocr_designation)
    
    best_match = None
    best_score = 0.0
    
    standard_features = []
    for product in standard_products:
        std_features = extract_product_features(product)
        standard_features.append((product, std_features))
    
    for product, std_features in standard_features:
        score = calculate_similarity_score(ocr_features, std_features)
        
        ocr_normalized = preprocess_text(ocr_designation)
        std_normalized = preprocess_text(product)
        
        jaro_score = jellyfish.jaro_winkler_similarity(ocr_normalized, std_normalized)
        combined_score = (score * 0.7) + (jaro_score * 0.3)
        
        if combined_score > best_score:
            best_score = combined_score
            best_match = product
    
    if best_score < 0.6:
        return None, best_score
    
    return best_match, best_score

def intelligent_product_matcher(ocr_designation: str) -> Tuple[Optional[str], float, Dict]:
    """Standardise intelligemment une désignation produit OCR"""
    details = {
        'original': ocr_designation,
        'features': {},
        'matches': []
    }
    
    features = extract_product_features(ocr_designation)
    details['features'] = features
    
    best_match, confidence = find_best_match(ocr_designation, STANDARD_PRODUCTS)
    
    alternatives = []
    for product in STANDARD_PRODUCTS:
        product_features = extract_product_features(product)
        score = calculate_similarity_score(features, product_features)
        jaro_score = jellyfish.jaro_winkler_similarity(
            preprocess_text(ocr_designation),
            preprocess_text(product)
        )
        combined_score = (score * 0.7) + (jaro_score * 0.3)
        
        if combined_score >= 0.4:
            alternatives.append((product, combined_score))
    
    alternatives.sort(key=lambda x: x[1], reverse=True)
    details['matches'] = alternatives[:3]
    
    return best_match, confidence, details

def standardize_product_name_improved(product_name: str) -> Tuple[str, float, str]:
    """Standardise le nom du produit avec score de confiance"""
    if not product_name or not product_name.strip():
        return "", 0.0, "empty"
    
    best_match, confidence, details = intelligent_product_matcher(product_name)
    
    if best_match and confidence >= 0.7:
        return best_match, confidence, "matched"
    elif best_match and confidence >= 0.6:
        return best_match, confidence, "partial_match"
    else:
        return product_name.title(), confidence, "no_match"

def standardize_product_for_bdc(product_name: str) -> Tuple[str, str, float, str]:
    """Standardise spécifiquement pour les produits BDC ULYS"""
    produit_brut = product_name.strip()
    produit_standard, confidence, status = standardize_product_name_improved(product_name)
    
    produit_upper = produit_brut.upper()
    
    # Gestion spéciale pour "CONS. CHAN FOUI 75CL" - FILTRE 2
    if "CONS" in produit_upper and "CHAN" in produit_upper and "FOUI" in produit_upper:
        produit_standard = "Chan Foui 75 cl"
        confidence = 0.95
        status = "matched"
    
    # Gestion spéciale pour les vins avec "NU"
    if "NU" in produit_upper and "750" in produit_upper:
        if "ROUGE" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Rouge 75 cl"
            confidence = 0.9
            status = "matched"
        elif "BLANC" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Blanc 75 cl"
            confidence = 0.9
            status = "matched"
        elif "GRIS" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Gris 75 cl"
            confidence = 0.9
            status = "matched"
        elif "ROUGE" in produit_upper and "MAROPARASY" in produit_upper:
            produit_standard = "Maroparasy Rouge 75 cl"
            confidence = 0.9
            status = "matched"
        elif "BLANC" in produit_upper and "MAROPARASY" in produit_upper:
            produit_standard = "Blanc doux Maroparasy 75 cl"
            confidence = 0.9
            status = "matched"
    
    # Gestion spéciale pour les 3L
    if "3L" in produit_upper or "3 L" in produit_upper:
        if "ROUGE" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Rouge 3L"
            confidence = 0.9
            status = "matched"
        elif "BLANC" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Blanc 3L"
            confidence = 0.9
            status = "matched"
    
    return produit_brut, produit_standard, confidence, status

# ============================================================
# DÉTECTION DE TYPE DE DOCUMENT AMÉLIORÉE (du code 2)
# ============================================================

def extract_document_type_from_text(text: str) -> Dict[str, Any]:
    """Détecte le type de document à partir du texte OCR (méthode du code 2)"""
    text_upper = text.upper()
    result = {
        "type_document": "DOCUMENT INCONNU",
        "numero": "",
        "date": "",
        "client": "",
        "adresse_livraison": "",
        "bon_commande": "",
        "doit": "",
        "mois": "",
        "is_facture": False,
        "is_bdc": False
    }
    
    # Détection FACTURE
    facture_patterns = [
        r"FACTURE\s+EN\s+COMPTE.*?N[°o]?\s*([0-9]{3,})",
        r"FACTURE.*?N[°o]\s*([0-9]{3,})",
        r"FACTURE.*?N\s*([0-9]{3,})",
        r"N°\s*([0-9]{3,})"
    ]
    
    for p in facture_patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            result["type_document"] = "FACTURE EN COMPTE"
            result["numero"] = m.group(1).strip()
            result["is_facture"] = True
            break
    
    # Si facture trouvée, extraire autres infos
    if result["is_facture"]:
        # Adresse de livraison
        addr_patterns = [
            r"Adresse de livraison\s*[:\-]\s*(.+)",
            r"Adresse(?:\s+de\s+livraison)?\s*[:\-]?\s*\n?\s*(.+)"
        ]
        for p in addr_patterns:
            m = re.search(p, text, flags=re.I)
            if m:
                address = m.group(1).strip().rstrip(".")
                result["adresse_livraison"] = address.split("\n")[0] if "\n" in address else address
                break
        
        # DOIT (client)
        doit_pattern = r"\bDOIT\s*[:\-]?\s*([A-Z0-9]{2,6})"
        m = re.search(doit_pattern, text, flags=re.I)
        if m:
            result["doit"] = m.group(1).strip()
            result["client"] = result["doit"]
        
        # Mois
        months = {
            "janvier": "Janvier", "février": "Février", "fevrier": "Février",
            "mars": "Mars", "avril": "Avril", "mai": "Mai",
            "juin": "Juin", "juillet": "Juillet", "août": "Août",
            "aout": "Août", "septembre": "Septembre", "octobre": "Octobre",
            "novembre": "Novembre", "décembre": "Décembre", "decembre": "Décembre"
        }
        for mname in months:
            if re.search(r"\b" + re.escape(mname) + r"\b", text, flags=re.I):
                result["mois"] = months[mname]
                break
        
        # Bon de commande
        bdc_patterns = [
            r"Suivant votre bon de commande\s*[:\-]?\s*([0-9A-Za-z\-\/]+)",
            r"bon de commande\s*[:\-]?\s*(.+)"
        ]
        for p in bdc_patterns:
            m = re.search(p, text, flags=re.I)
            if m:
                result["bon_commande"] = m.group(1).strip().split()[0]
                break
        
        return result
    
    # Détection BDC
    bdc_patterns = [
        r"Bon\s*de\s*commande\s*n[°o]?\s*([0-9]{7,8})",
        r"BDC\s*n[°o]?\s*([0-9]{7,8})",
        r"n[°o]\s*([0-9]{7,8})",
    ]
    
    for p in bdc_patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            result["type_document"] = "BDC"
            result["numero"] = m.group(1).strip()
            result["is_bdc"] = True
            break
    
    # Si BDC trouvé, extraire autres infos
    if result["is_bdc"]:
        # Date d'émission
        date_pattern = r"date\s*émission\s*(\d{1,2}\s*[/\-]\s*\d{1,2}\s*[/\-]\s*\d{2,4})"
        m = re.search(date_pattern, text, flags=re.I)
        if m:
            date_str = re.sub(r"\s+", "", m.group(1))
            parts = re.split(r"[/\-]", date_str)
            if len(parts) == 3:
                day = parts[0].zfill(2)
                mon = parts[1].zfill(2)
                year = parts[2] if len(parts[2]) == 4 else "20" + parts[2]
                result["date"] = f"{day}/{mon}/{year}"
        
        # Client
        client_pattern = r"Adresse\s*facturation\s*(S2M|SZM|2M|ULYS|LEADERPRICE|DLP|SUPERMAKI)"
        m = re.search(client_pattern, text, flags=re.I)
        if m:
            result["client"] = m.group(1).strip()
        
        # Adresse livraison
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if "adresse livraison" in line.lower():
                address_lines = []
                for j in range(1, 4):
                    if i + j < len(lines) and lines[i + j].strip():
                        address_lines.append(lines[i + j].strip())
                if address_lines:
                    result["adresse_livraison"] = " ".join(address_lines[:2])
                break
        
        # Recherche d'adresses connues
        known_addresses = ["SCORE TALATAMATY", "SCORE TALATAJATY", "SCORE TANJOMBATO"]
        for addr in known_addresses:
            if addr in text_upper:
                result["adresse_livraison"] = addr
                break
        
        # Détection du client spécifique
        if "ULYS" in text_upper:
            result["client"] = "ULYS"
            result["type_document"] = "BDC ULYS"
        elif "LEADERPRICE" in text_upper or "DLP" in text_upper:
            result["client"] = "LEADERPRICE"
            result["type_document"] = "BDC LEADERPRICE"
        elif "S2M" in text_upper or "SUPERMAKI" in text_upper:
            result["client"] = "S2M"
            result["type_document"] = "BDC S2M"
    
    return result

# ============================================================
# CONFIGURATION STREAMLIT
# ============================================================

st.set_page_config(
    page_title="Chan Foui & Fils — Scanner Pro V3",
    page_icon="🍷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============================================================
# INITIALISATION DES VARIABLES DE SESSION
# ============================================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "uploaded_image" not in st.session_state:
    st.session_state.uploaded_image = None
if "ocr_result" not in st.session_state:
    st.session_state.ocr_result = None
if "show_results" not in st.session_state:
    st.session_state.show_results = False
if "processing" not in st.session_state:
    st.session_state.processing = False
if "detected_document_type" not in st.session_state:
    st.session_state.detected_document_type = None
if "duplicate_check_done" not in st.session_state:
    st.session_state.duplicate_check_done = False
if "duplicate_found" not in st.session_state:
    st.session_state.duplicate_found = False
if "duplicate_action" not in st.session_state:
    st.session_state.duplicate_action = None
if "duplicate_rows" not in st.session_state:
    st.session_state.duplicate_rows = []
if "data_for_sheets" not in st.session_state:
    st.session_state.data_for_sheets = None
if "edited_standardized_df" not in st.session_state:
    st.session_state.edited_standardized_df = None
if "export_triggered" not in st.session_state:
    st.session_state.export_triggered = False
if "export_status" not in st.session_state:
    st.session_state.export_status = None
if "image_preview_visible" not in st.session_state:
    st.session_state.image_preview_visible = False
if "document_scanned" not in st.session_state:
    st.session_state.document_scanned = False
if "product_matching_scores" not in st.session_state:
    st.session_state.product_matching_scores = {}
if "raw_ocr_text" not in st.session_state:
    st.session_state.raw_ocr_text = ""
if "document_detection_info" not in st.session_state:
    st.session_state.document_detection_info = {}

# ============================================================
# SYSTÈME D'AUTHENTIFICATION
# ============================================================

AUTHORIZED_USERS = {
    "Pathou M.": "CFF3",
    "Elodie R.": "CFF2", 
    "Laetitia C.": "CFF1",
    "Admin Cf.": "CFF4"
}

def check_authentication():
    return st.session_state.authenticated

def login(username, password):
    if username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password:
        st.session_state.authenticated = True
        st.session_state.username = username
        return True, "Connexion réussie"
    else:
        return False, "Identifiants incorrects"

def logout():
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.uploaded_file = None
    st.session_state.uploaded_image = None
    st.session_state.ocr_result = None
    st.session_state.show_results = False
    st.session_state.detected_document_type = None
    st.session_state.image_preview_visible = False
    st.session_state.document_scanned = False
    st.session_state.export_triggered = False
    st.session_state.product_matching_scores = {}
    st.session_state.raw_ocr_text = ""
    st.session_state.document_detection_info = {}
    st.rerun()

# ============================================================
# PAGE DE CONNEXION
# ============================================================

if not check_authentication():
    st.markdown("""
    <style>
        .login-container {
            max-width: 420px;
            margin: 50px auto;
            padding: 40px 35px;
            background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
            border-radius: 24px;
            box-shadow: 0 12px 40px rgba(39, 65, 74, 0.15),
                        0 0 0 1px rgba(39, 65, 74, 0.05);
            text-align: center;
        }
        
        .login-title {
            background: linear-gradient(135deg, #27414A 0%, #2C5F73 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 8px;
        }
        
        .login-subtitle {
            color: #1E293B !important;
            margin-bottom: 32px;
            font-size: 1rem;
            font-weight: 400;
        }
        
        .stButton > button {
            background: linear-gradient(135deg, #27414A 0%, #2C5F73 100%);
            color: white !important;
            font-weight: 600;
            border: none;
            padding: 14px 24px;
            border-radius: 12px;
            width: 100%;
            font-size: 15px;
            margin-top: 12px;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(39, 65, 74, 0.25);
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    if os.path.exists("CF_LOGOS.png"):
        st.image("CF_LOGOS.png", width=90, output_format="PNG")
    else:
        st.markdown("""
        <div style="font-size: 3rem; margin-bottom: 20px; color: #1E293B !important;">
            🍷
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="login-title">CHAN FOUI ET FILS</h1>', unsafe_allow_html=True)
    st.markdown('<p class="login-subtitle">Système de Scanner Pro V3 - Accès Restreint</p>', unsafe_allow_html=True)
    
    username = st.selectbox(
        "👤 Identifiant",
        options=[""] + list(AUTHORIZED_USERS.keys()),
        format_func=lambda x: "— Sélectionnez votre profil —" if x == "" else x,
        key="login_username"
    )
    password = st.text_input("🔒 Mot de passe", type="password", placeholder="Entrez votre code CFFx", key="login_password")
    
    if st.button("🔓 Accéder au système", use_container_width=True, key="login_button"):
        if username and password:
            success, message = login(username, password)
            if success:
                st.success(f"✅ {message}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ {message}")
        else:
            st.warning("⚠️ Veuillez remplir tous les champs")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ============================================================
# APPLICATION PRINCIPALE
# ============================================================

# ============================================================
# THÈME CHAN FOUI & FILS
# ============================================================

LOGO_FILENAME = "CF_LOGOS.png"
BRAND_TITLE = "CHAN FOUI ET FILS"
BRAND_SUB = "AI Document Processing System V3"

PALETTE = {
    "primary_dark": "#27414A",
    "primary_light": "#1F2F35",
    "background": "#F5F5F3",
    "card_bg": "#FFFFFF",
    "text_dark": "#1A1A1A",
    "text_medium": "#333333",
    "text_light": "#4B5563",
    "accent": "#2C5F73",
    "success": "#10B981",
    "warning": "#F59E0B",
    "error": "#EF4444",
    "border": "#E5E7EB",
    "tech_blue": "#3B82F6",
    "tech_purple": "#8B5CF6",
}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400&display=swap');
    
    .main {{
        background: linear-gradient(135deg, {PALETTE['background']} 0%, #f0f2f5 100%);
        font-family: 'Inter', sans-serif;
        color: {PALETTE['text_dark']} !important;
    }}
    
    .header-container {{
        background: linear-gradient(145deg, {PALETTE['card_bg']} 0%, #f8fafc 100%);
        padding: 2.5rem 2rem;
        border-radius: 24px;
        margin-bottom: 2.5rem;
        box-shadow: 0 12px 40px rgba(39, 65, 74, 0.1),
                    0 0 0 1px rgba(39, 65, 74, 0.05);
        text-align: center;
        position: relative;
        overflow: hidden;
    }}
    
    .brand-title {{
        background: linear-gradient(135deg, {PALETTE['primary_dark']} 0%, {PALETTE['tech_blue']} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.8rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
        line-height: 1.1;
        text-transform: uppercase;
    }}
    
    .brand-sub {{
        color: {PALETTE['text_medium']} !important;
        font-size: 1.1rem;
        margin-top: 0.3rem;
        font-weight: 400;
        opacity: 0.9;
    }}
    
    .card {{
        background: linear-gradient(145deg, {PALETTE['card_bg']} 0%, #f8fafc 100%);
        padding: 2.2rem;
        border-radius: 20px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08),
                    0 0 0 1px rgba(39, 65, 74, 0.05);
        margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.8);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    
    .card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 15px 40px rgba(0, 0, 0, 0.12),
                    0 0 0 1px rgba(39, 65, 74, 0.08);
    }}
    
    .stButton > button {{
        background: linear-gradient(135deg, {PALETTE['primary_dark']} 0%, {PALETTE['accent']} 100%);
        color: white !important;
        font-weight: 600;
        border: none;
        padding: 1rem 2rem;
        border-radius: 14px;
        transition: all 0.3s ease;
        width: 100%;
        font-size: 1rem;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(39, 65, 74, 0.3);
    }}
    
    .upload-box {{
        border: 2px dashed {PALETTE['accent']};
        border-radius: 20px;
        padding: 3.5rem;
        text-align: center;
        background: linear-gradient(145deg, rgba(255,255,255,0.9) 0%, rgba(248,250,252,0.9) 100%);
        margin: 2rem 0;
        transition: all 0.3s ease;
    }}
    
    .upload-box:hover {{
        border-color: {PALETTE['tech_blue']};
        background: linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(248,250,252,0.95) 100%);
        transform: translateY(-2px);
        box-shadow: 0 10px 30px rgba(39, 65, 74, 0.1);
    }}
    
    .info-box {{
        background: linear-gradient(135deg, #E8F4F8 0%, #D4EAF7 100%);
        border-left: 4px solid {PALETTE['tech_blue']};
        padding: 1.5rem;
        border-radius: 16px;
        margin: 1.2rem 0;
        color: {PALETTE['text_dark']} !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.1);
    }}
    
    .success-box {{
        background: linear-gradient(135deg, #D1FAE5 0%, #A7F3D0 100%);
        border-left: 4px solid {PALETTE['success']};
        padding: 1.5rem;
        border-radius: 16px;
        margin: 1.2rem 0;
        color: {PALETTE['text_dark']} !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.1);
    }}
    
    .document-type-badge {{
        display: inline-block;
        padding: 8px 16px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.9rem;
        margin: 5px;
    }}
    
    .facture-badge {{
        background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%);
        color: white !important;
    }}
    
    .bdc-badge {{
        background: linear-gradient(135deg, #10B981 0%, #047857 100%);
        color: white !important;
    }}
    
    .unknown-badge {{
        background: linear-gradient(135deg, #6B7280 0%, #4B5563 100%);
        color: white !important;
    }}
</style>
""", unsafe_allow_html=True)

# ============================================================
# GOOGLE SHEETS CONFIGURATION
# ============================================================

SHEET_ID = "1FooEwQBwLjvyjAsvHu4eDes0o-eEm92fbEWv6maBNyE"

SHEET_GIDS = {
    "FACTURE EN COMPTE": 16102465,
    "BDC LEADERPRICE": 954728911,
    "BDC S2M": 954728911,
    "BDC ULYS": 954728911
}

# ============================================================
# FONCTION DE NORMALISATION DU TYPE DE DOCUMENT AMÉLIORÉE
# ============================================================

def normalize_document_type_from_detection(detection_info: Dict) -> str:
    """Normalise le type de document basé sur la détection améliorée"""
    if not detection_info:
        return "DOCUMENT INCONNU"
    
    doc_type = detection_info.get("type_document", "")
    
    # Si c'est une facture
    if detection_info.get("is_facture", False):
        return "FACTURE EN COMPTE"
    
    # Si c'est un BDC
    if detection_info.get("is_bdc", False):
        client = detection_info.get("client", "").upper()
        
        if "ULYS" in client or "ULYS" in doc_type.upper():
            return "BDC ULYS"
        elif "LEADERPRICE" in client or "DLP" in client or "LEADERPRICE" in doc_type.upper():
            return "BDC LEADERPRICE"
        elif "S2M" in client or "SUPERMAKI" in client or "S2M" in doc_type.upper():
            return "BDC S2M"
        else:
            # Par défaut pour BDC non spécifié
            return "BDC LEADERPRICE"
    
    # Essayer de deviner à partir du texte
    if any(word in doc_type.upper() for word in ["FACTURE", "INVOICE", "BILL"]):
        return "FACTURE EN COMPTE"
    elif any(word in doc_type.upper() for word in ["BDC", "BON DE COMMANDE", "COMMANDE", "ORDER"]):
        return "BDC LEADERPRICE"
    
    return "DOCUMENT INCONNU"

# ============================================================
# OPENAI CONFIGURATION
# ============================================================

def get_openai_client():
    """Initialise et retourne le client OpenAI"""
    try:
        if "openai" in st.secrets:
            api_key = st.secrets["openai"]["api_key"]
        else:
            api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            st.error("❌ Clé API OpenAI non configurée")
            return None
        
        client = OpenAI(api_key=api_key)
        return client
    except Exception as e:
        st.error(f"❌ Erreur d'initialisation OpenAI: {str(e)}")
        return None

# ============================================================
# OCR AVEC DÉTECTION DE TYPE AMÉLIORÉE
# ============================================================

def hybrid_document_analysis(image_bytes: bytes) -> Dict:
    """
    Analyse hybride du document :
    1. Utilise OpenAI Vision pour l'extraction structurée
    2. Utilise la détection regex pour identifier le type de document
    """
    try:
        client = get_openai_client()
        if not client:
            return None
        
        # Encoder l'image
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # Prompt pour l'extraction structurée
        prompt = """
        Analyse ce document et extrais précisément les informations suivantes:
        
        IMPORTANT: Extrais TOUTES les lignes du tableau, y compris les catégories.
        
        {
            "raw_text": "TEXTE COMPLET DU DOCUMENT",
            "type_document": "TYPE DE DOCUMENT",
            "numero": "...",
            "date": "...",
            "client": "...",
            "adresse_livraison": "...",
            "articles": [
                {
                    "article_brut": "TEXT EXACT COMME SUR LE DOCUMENT",
                    "quantite": nombre
                }
            ]
        }
        
        RÈGLES:
        1. Pour "raw_text": copie TOUT le texte du document exactement comme il apparaît
        2. Pour "article_brut": copie EXACTEMENT le texte de la colonne "Description" ou "Article"
        3. Pour les quantités: extrais le nombre exact
        4. Garde les articles exactement comme sur le document, ne standardise pas
        """
        
        # Appel à l'API OpenAI Vision
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4000,
            temperature=0.1
        )
        
        # Extraire et parser la réponse JSON
        content = response.choices[0].message.content
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                data = json.loads(json_str)
                
                # Appliquer la détection améliorée du type de document
                raw_text = data.get("raw_text", "")
                detection_info = extract_document_type_from_text(raw_text)
                
                # Mettre à jour les données avec la détection améliorée
                if detection_info["type_document"] != "DOCUMENT INCONNU":
                    data["type_document"] = detection_info["type_document"]
                    data["numero"] = detection_info.get("numero", data.get("numero", ""))
                    data["client"] = detection_info.get("client", data.get("client", ""))
                    data["adresse_livraison"] = detection_info.get("adresse_livraison", data.get("adresse_livraison", ""))
                    data["date"] = detection_info.get("date", data.get("date", ""))
                
                # Stocker les informations de détection
                data["detection_info"] = detection_info
                
                return data
                
            except json.JSONDecodeError:
                # Essayer de nettoyer le JSON
                json_str = re.sub(r'[\x00-\x1f\x7f]', '', json_str)
                try:
                    data = json.loads(json_str)
                    return data
                except:
                    st.error("❌ Impossible de parser la réponse JSON")
                    return None
        else:
            st.error("❌ Réponse JSON non trouvée")
            return None
            
    except Exception as e:
        st.error(f"❌ Erreur d'analyse: {str(e)}")
        return None

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def preprocess_image(b: bytes) -> bytes:
    """Prétraitement de l'image pour améliorer la qualité"""
    img = Image.open(BytesIO(b)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180))
    out = BytesIO()
    img.save(out, format="PNG", optimize=True, quality=95)
    return out.getvalue()

def format_date_french(date_str: str) -> str:
    """Formate la date au format français"""
    try:
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%d %m %Y",
            "%d/%m/%y", "%d-%m-%y", "%d %m %y",
            "%d %B %Y", "%d %b %Y"
        ]
        
        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime("%Y-%m-%d")
            except:
                continue
        
        try:
            date_obj = parser.parse(date_str, dayfirst=True)
            return date_obj.strftime("%Y-%m-%d")
        except:
            return datetime.now().strftime("%Y-%m-%d")
    except:
        return datetime.now().strftime("%Y-%m-%d")

def get_month_from_date(date_str: str) -> str:
    """Extrait le mois français d'une date"""
    months_fr = {
        1: "janvier", 2: "février", 3: "mars", 4: "avril",
        5: "mai", 6: "juin", 7: "juillet", 8: "août",
        9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
    }
    
    try:
        date_obj = parser.parse(date_str, dayfirst=True)
        return months_fr[date_obj.month]
    except:
        return months_fr[datetime.now().month]

def format_quantity(qty: Any) -> str:
    """Formate la quantité"""
    if qty is None:
        return "0"
    
    qty_str = str(qty)
    qty_str = qty_str.replace(".", ",")
    
    if "," in qty_str:
        parts = qty_str.split(",")
        if len(parts) == 2 and parts[1] == "000":
            qty_str = parts[0]
    
    return qty_str

# ============================================================
# GOOGLE SHEETS FUNCTIONS
# ============================================================

def get_worksheet(document_type: str):
    """Récupère la feuille Google Sheets correspondant au type de document"""
    try:
        if "gcp_sheet" not in st.secrets:
            st.error("❌ Les credentials Google Sheets ne sont pas configurés")
            return None
        
        sa_info = dict(st.secrets["gcp_sheet"])
        gc = gspread.service_account_from_dict(sa_info)
        sh = gc.open_by_key(SHEET_ID)
        
        target_gid = SHEET_GIDS.get(document_type)
        
        if target_gid is None:
            # Utiliser la première feuille par défaut
            return sh.get_worksheet(0)
        
        for worksheet in sh.worksheets():
            if int(worksheet.id) == target_gid:
                return worksheet
        
        # Si la feuille spécifique n'est pas trouvée, utiliser la première feuille
        return sh.get_worksheet(0)
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la connexion à Google Sheets: {str(e)}")
        return None

def save_to_google_sheets(document_type: str, data: dict, articles_df: pd.DataFrame):
    """Sauvegarde les données dans Google Sheets"""
    try:
        ws = get_worksheet(document_type)
        
        if not ws:
            st.error("❌ Impossible de se connecter à Google Sheets")
            return False, "Erreur de connexion"
        
        # Préparer les lignes selon le type de document
        rows = []
        
        if "FACTURE" in document_type.upper():
            # Format facture
            for _, row in articles_df.iterrows():
                if row["Quantité"] > 0:  # FILTRE 1: Ignorer les lignes avec quantité 0
                    rows.append([
                        data.get("mois", get_month_from_date(data.get("date", ""))),
                        data.get("client", ""),
                        format_date_french(data.get("date", "")),
                        data.get("bon_commande", ""),
                        data.get("numero", ""),
                        "",  # Lien
                        data.get("adresse_livraison", ""),
                        row["Produit Standard"],
                        format_quantity(row["Quantité"])
                    ])
        else:
            # Format BDC
            for _, row in articles_df.iterrows():
                if row["Quantité"] > 0:  # FILTRE 1: Ignorer les lignes avec quantité 0
                    rows.append([
                        get_month_from_date(data.get("date", "")),
                        data.get("client", ""),
                        format_date_french(data.get("date", "")),
                        data.get("numero", ""),
                        "",  # Lien
                        data.get("adresse_livraison", ""),
                        row["Produit Standard"],
                        format_quantity(row["Quantité"])
                    ])
        
        if not rows:
            st.warning("⚠️ Aucune donnée à enregistrer (toutes les lignes ont une quantité de 0)")
            return False, "Aucune donnée"
        
        # Afficher l'aperçu
        st.info(f"📋 **Aperçu des données à enregistrer ({len(rows)} lignes):**")
        
        if "FACTURE" in document_type.upper():
            columns = ["Mois", "Client", "Date", "NBC", "NF", "Lien", "Magasin", "Produit", "Quantité"]
        else:
            columns = ["Mois", "Client", "Date", "NBC", "Lien", "Magasin", "Produit", "Quantité"]
        
        preview_df = pd.DataFrame(rows, columns=columns)
        st.dataframe(preview_df, use_container_width=True)
        
        # Enregistrer
        try:
            ws.append_rows(rows)
            st.success(f"✅ {len(rows)} ligne(s) enregistrée(s) avec succès dans Google Sheets!")
            
            # Lien vers Google Sheets
            sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
            st.markdown(f'<div class="info-box">🔗 <a href="{sheet_url}" target="_blank">Ouvrir Google Sheets</a></div>', unsafe_allow_html=True)
            
            st.balloons()
            return True, f"{len(rows)} lignes enregistrées"
            
        except Exception as e:
            st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
            return False, str(e)
                
    except Exception as e:
        st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
        return False, str(e)

# ============================================================
# HEADER AVEC LOGO
# ============================================================

st.markdown('<div class="header-container">', unsafe_allow_html=True)

# Badge utilisateur
st.markdown(f'''
<div style="position: absolute; top: 20px; right: 20px; background: linear-gradient(135deg, {PALETTE['accent']} 0%, {PALETTE['tech_blue']} 100%); color: white !important; padding: 10px 20px; border-radius: 16px; font-size: 0.9rem; font-weight: 600; display: flex; align-items: center; gap: 10px;">
    👤 {st.session_state.username}
</div>
''', unsafe_allow_html=True)

st.markdown('<div class="logo-title-wrapper">', unsafe_allow_html=True)

# Logo
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME, width=100)
else:
    st.markdown("""
    <div style="font-size: 3.5rem; margin-bottom: 10px; color: #1A1A1A !important;">
        🍷
    </div>
    """, unsafe_allow_html=True)

# Titre
st.markdown(f'<h1 class="brand-title">{BRAND_TITLE}</h1>', unsafe_allow_html=True)

# Sous-titre
st.markdown(f'''
<p class="brand-sub">
    Système V3 - Détection intelligente des documents • Connecté en tant que <strong>{st.session_state.username}</strong>
</p>
''', unsafe_allow_html=True)

st.markdown('</div>')
st.markdown('</div>')

# ============================================================
# ZONE DE TÉLÉCHARGEMENT
# ============================================================

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<h4>📤 Zone de dépôt de documents</h4>', unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    <strong>ℹ️ Système V3 - Améliorations :</strong>
    <ul style="margin-top:10px;">
        <li>Détection intelligente des types de documents (Facture/BDC)</li>
        <li>Reconnaissance précise des clients (ULYS, S2M, LeaderPrice)</li>
        <li>Standardisation automatique des produits</li>
        <li>Filtre automatique des lignes quantité 0</li>
        <li>Export vers Google Sheets</li>
    </ul>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="upload-box">', unsafe_allow_html=True)
uploaded = st.file_uploader(
    "**Déposez votre document ici ou cliquez pour parcourir**",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
    help="Formats supportés : JPG, JPEG, PNG | Taille max : 10MB",
    key="file_uploader_main"
)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TRAITEMENT AUTOMATIQUE DE L'IMAGE
# ============================================================

if uploaded and uploaded != st.session_state.uploaded_file:
    st.session_state.uploaded_file = uploaded
    st.session_state.uploaded_image = Image.open(uploaded)
    st.session_state.ocr_result = None
    st.session_state.show_results = False
    st.session_state.processing = True
    st.session_state.detected_document_type = None
    st.session_state.image_preview_visible = True
    st.session_state.document_scanned = True
    st.session_state.export_triggered = False
    st.session_state.product_matching_scores = {}
    st.session_state.raw_ocr_text = ""
    st.session_state.document_detection_info = {}
    
    # Barre de progression
    progress_container = st.empty()
    with progress_container.container():
        st.markdown('<div style="background: linear-gradient(135deg, #27414A 0%, #2C5F73 100%); color: white !important; padding: 3rem; border-radius: 20px; text-align: center; margin: 2.5rem 0;">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 3rem; margin-bottom: 1rem;">🤖</div>', unsafe_allow_html=True)
        st.markdown('<h3 style="color: white !important;">Analyse intelligente V3</h3>', unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        steps = [
            "Chargement de l'image...",
            "Prétraitement...",
            "Analyse par IA...",
            "Détection du type de document...",
            "Extraction des articles...",
            "Standardisation des produits...",
            "Finalisation..."
        ]
        
        for i in range(101):
            time.sleep(0.03)
            progress_bar.progress(i)
            if i < 15:
                status_text.text(steps[0])
            elif i < 30:
                status_text.text(steps[1])
            elif i < 50:
                status_text.text(steps[2])
            elif i < 65:
                status_text.text(steps[3])
            elif i < 80:
                status_text.text(steps[4])
            elif i < 95:
                status_text.text(steps[5])
            else:
                status_text.text(steps[6])
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Traitement OCR avec analyse hybride
    try:
        buf = BytesIO()
        st.session_state.uploaded_image.save(buf, format="JPEG")
        image_bytes = buf.getvalue()
        
        # Prétraitement de l'image
        img_processed = preprocess_image(image_bytes)
        
        # Analyse hybride
        result = hybrid_document_analysis(img_processed)
        
        if result:
            st.session_state.ocr_result = result
            st.session_state.raw_ocr_text = result.get("raw_text", "")
            
            # Récupérer les informations de détection
            detection_info = result.get("detection_info", {})
            st.session_state.document_detection_info = detection_info
            
            # Normaliser le type de document détecté
            raw_doc_type = detection_info.get("type_document", "DOCUMENT INCONNU")
            st.session_state.detected_document_type = normalize_document_type_from_detection(detection_info)
            
            st.session_state.show_results = True
            st.session_state.processing = False
            
            # Préparer les données standardisées
            if "articles" in result:
                std_data = []
                for article in result["articles"]:
                    raw_name = article.get("article_brut", article.get("article", ""))
                    
                    # Filtrer les catégories
                    if any(cat in raw_name.upper() for cat in ["VINS ROUGES", "VINS BLANCS", "VINS ROSES", "LIQUEUR", "CONSIGNE"]):
                        std_data.append({
                            "Produit Brute": raw_name,
                            "Produit Standard": raw_name,
                            "Quantité": 0,
                            "Confiance": "0%",
                            "Auto": False
                        })
                    else:
                        # Standardiser les produits
                        produit_brut, produit_standard, confidence, status = standardize_product_for_bdc(raw_name)
                        
                        std_data.append({
                            "Produit Brute": produit_brut,
                            "Produit Standard": produit_standard,
                            "Quantité": article.get("quantite", 0),
                            "Confiance": f"{confidence*100:.1f}%",
                            "Auto": confidence >= 0.7
                        })
                
                # Créer le dataframe standardisé pour l'édition
                st.session_state.edited_standardized_df = pd.DataFrame(std_data)
            
            progress_container.empty()
            st.rerun()
        else:
            st.error("❌ Échec de l'analyse - Veuillez réessayer")
            st.session_state.processing = False
        
    except Exception as e:
        st.error(f"❌ Erreur système: {str(e)}")
        st.session_state.processing = False

# ============================================================
# APERÇU DU DOCUMENT
# ============================================================

if st.session_state.uploaded_image and st.session_state.image_preview_visible:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h4>👁️ Aperçu du document analysé</h4>', unsafe_allow_html=True)
    
    col_img, col_info = st.columns([2, 1])
    
    with col_img:
        st.image(st.session_state.uploaded_image, use_column_width=True)
    
    with col_info:
        # Badge du type de document détecté
        doc_type = st.session_state.detected_document_type or "EN ANALYSE"
        badge_class = "unknown-badge"
        
        if "FACTURE" in doc_type:
            badge_class = "facture-badge"
        elif "BDC" in doc_type:
            badge_class = "bdc-badge"
        
        st.markdown(f'''
        <div class="info-box">
            <strong>📊 Détection V3 :</strong><br><br>
            <span class="document-type-badge {badge_class}">{doc_type}</span><br><br>
            • Résolution : Haute définition<br>
            • Statut : Analysé par IA<br>
            • Détection : Intelligente<br>
            • Client : {st.session_state.document_detection_info.get('client', 'Non détecté')}
        </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# AFFICHAGE DES RÉSULTATS
# ============================================================

if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
    result = st.session_state.ocr_result
    doc_type = st.session_state.detected_document_type
    detection_info = st.session_state.document_detection_info
    
    # Message de succès
    st.markdown('<div class="success-box">', unsafe_allow_html=True)
    
    badge_class = "unknown-badge"
    if "FACTURE" in doc_type:
        badge_class = "facture-badge"
    elif "BDC" in doc_type:
        badge_class = "bdc-badge"
    
    st.markdown(f'''
    <div style="display: flex; align-items: start; gap: 15px;">
        <div style="font-size: 2.5rem; color: {PALETTE['success']} !important;">✅</div>
        <div>
            <strong style="font-size: 1.1rem; color: #1A1A1A !important;">Analyse V3 terminée avec succès</strong><br>
            <span class="document-type-badge {badge_class}">{doc_type}</span><br>
            <small style="color: #4B5563 !important;">Détection intelligente activée • Vérifiez les données</small>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # INFORMATIONS EXTRAITES
    # ========================================================
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h4>📋 Informations extraites</h4>', unsafe_allow_html=True)
    
    # Afficher les informations selon le type de document détecté
    if "FACTURE" in doc_type.upper():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Client (DOIT)</div>', unsafe_allow_html=True)
            client = st.text_input("", value=detection_info.get("doit", detection_info.get("client", "")), key="facture_client", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">N° Facture</div>', unsafe_allow_html=True)
            numero_facture = st.text_input("", value=detection_info.get("numero", result.get("numero", "")), key="facture_num", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Bon de commande</div>', unsafe_allow_html=True)
            bon_commande = st.text_input("", value=detection_info.get("bon_commande", result.get("bon_commande", "")), key="facture_bdc", label_visibility="collapsed")
        
        with col2:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Adresse de livraison</div>', unsafe_allow_html=True)
            adresse = st.text_input("", value=detection_info.get("adresse_livraison", result.get("adresse_livraison", "")), key="facture_adresse", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Date</div>', unsafe_allow_html=True)
            date = st.text_input("", value=result.get("date", ""), key="facture_date", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Mois</div>', unsafe_allow_html=True)
            mois = st.text_input("", value=detection_info.get("mois", get_month_from_date(result.get("date", ""))), key="facture_mois", label_visibility="collapsed")
        
        data_for_sheets = {
            "client": client,
            "numero": numero_facture,
            "bon_commande": bon_commande,
            "adresse_livraison": adresse,
            "date": date,
            "mois": mois
        }
    
    else:
        # BDC
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Client</div>', unsafe_allow_html=True)
            client = st.text_input("", value=detection_info.get("client", "ULYS"), key="bdc_client", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">N° BDC</div>', unsafe_allow_html=True)
            numero = st.text_input("", value=detection_info.get("numero", result.get("numero", "")), key="bdc_numero", label_visibility="collapsed")
        
        with col2:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Date</div>', unsafe_allow_html=True)
            date = st.text_input("", value=detection_info.get("date", result.get("date", "")), key="bdc_date", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Adresse de livraison</div>', unsafe_allow_html=True)
            adresse = st.text_input("", 
                                  value=detection_info.get("adresse_livraison", "SCORE TALATAMATY"), 
                                  key="bdc_adresse", 
                                  label_visibility="collapsed")
        
        data_for_sheets = {
            "client": client,
            "numero": numero,
            "date": date,
            "adresse_livraison": adresse
        }
    
    st.session_state.data_for_sheets = data_for_sheets
    
    # Indicateur de validation
    fields_filled = sum([1 for v in data_for_sheets.values() if str(v).strip()])
    total_fields = len(data_for_sheets)
    
    st.markdown(f'''
    <div style="margin-top: 20px; padding: 12px; background: rgba(16, 185, 129, 0.1); border-radius: 12px; border: 1px solid rgba(16, 185, 129, 0.2);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong style="color: #1A1A1A !important;">Validation des données</strong><br>
                <small style="color: #4B5563 !important;">{fields_filled}/{total_fields} champs remplis</small>
            </div>
            <div style="font-size: 1.5rem; color: #10B981 !important;">{"✅" if fields_filled == total_fields else "⚠️"}</div>
        </div>
        <div style="margin-top: 10px; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;">
            <div style="width: {fields_filled/total_fields*100}%; height: 100%; background: linear-gradient(90deg, #10B981, #34D399); border-radius: 3px;"></div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # TABLEAU STANDARDISÉ ÉDITABLE
    # ========================================================
    if st.session_state.edited_standardized_df is not None and not st.session_state.edited_standardized_df.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>📘 Standardisation des Produits</h4>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="margin-bottom: 20px; padding: 12px; background: rgba(59, 130, 246, 0.05); border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.1);">
            <small style="color: #1A1A1A !important;">
            💡 <strong>Mode édition activé avec filtres :</strong> 
            • <strong>Filtre 1:</strong> Les quantités à 0 seront ignorées à l'export<br>
            • <strong>Filtre 2:</strong> "CONS. CHAN FOUI 75CL" → "Chan Foui 75 cl"<br>
            • <strong>Filtre 3:</strong> Détection intelligente des doublons
            </small>
        </div>
        """, unsafe_allow_html=True)
        
        # Avertissement pour les lignes avec quantité 0
        df_with_zero_qty = st.session_state.edited_standardized_df[
            (st.session_state.edited_standardized_df["Quantité"] == 0) | 
            (st.session_state.edited_standardized_df["Quantité"].isna())
        ]
        
        if len(df_with_zero_qty) > 0:
            st.warning(f"⚠️ **Filtre 1 actif :** {len(df_with_zero_qty)} ligne(s) avec quantité 0 seront automatiquement exclues de l'export")
        
        # Éditeur de données
        edited_df = st.data_editor(
            st.session_state.edited_standardized_df,
            num_rows="dynamic",
            column_config={
                "Produit Brute": st.column_config.TextColumn(
                    "Produit Brute",
                    width="large",
                    help="Texte original extrait par l'OCR"
                ),
                "Produit Standard": st.column_config.TextColumn(
                    "Produit Standard",
                    width="large",
                    help="Nom standardisé du produit (éditable)"
                ),
                "Quantité": st.column_config.NumberColumn(
                    "Quantité",
                    min_value=0,
                    help="Quantité commandée (lignes avec 0 seront supprimées à l'export)",
                    format="%d"
                ),
                "Confiance": st.column_config.TextColumn(
                    "Confiance",
                    width="small",
                    help="Score de confiance de la standardisation"
                ),
                "Auto": st.column_config.CheckboxColumn(
                    "Auto",
                    help="Standardisé automatiquement par l'IA"
                )
            },
            use_container_width=True,
            key="standardized_data_editor"
        )
        
        st.session_state.edited_standardized_df = edited_df
        
        # Statistiques
        total_items = len(edited_df)
        auto_standardized = edited_df["Auto"].sum() if "Auto" in edited_df.columns else 0
        items_with_qty = len(edited_df[edited_df["Quantité"] > 0])
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.markdown(
                f'''
                <div style="padding: 15px; border-radius: 14px; text-align: center; background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%); border: 1px solid rgba(59, 130, 246, 0.2);">
                    <div style="font-size: 1.8rem; font-weight: 700; color: #3B82F6 !important;">{total_items}</div>
                    <div style="font-size: 0.85rem; color: #4B5563 !important; margin-top: 5px;">Articles totaux</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        with col_stat2:
            st.markdown(
                f'''
                <div style="padding: 15px; border-radius: 14px; text-align: center; background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(52, 211, 153, 0.1) 100%); border: 1px solid rgba(16, 185, 129, 0.2);">
                    <div style="font-size: 1.8rem; font-weight: 700; color: #10B981 !important;">{items_with_qty}</div>
                    <div style="font-size: 0.85rem; color: #4B5563 !important; margin-top: 5px;">Avec quantité > 0</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        with col_stat3:
            st.markdown(
                f'''
                <div style="padding: 15px; border-radius: 14px; text-align: center; background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(251, 191, 36, 0.1) 100%); border: 1px solid rgba(245, 158, 11, 0.2);">
                    <div style="font-size: 1.8rem; font-weight: 700; color: #F59E0B !important;">{int(auto_standardized)}</div>
                    <div style="font-size: 0.85rem; color: #4B5563 !important; margin-top: 5px;">Auto-standardisés</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        
        # Bouton pour forcer la re-standardisation
        if st.button("🔄 Re-standardiser tous les produits", 
                    key="restandardize_button",
                    help="Appliquer la standardisation intelligente à tous les produits"):
            new_data = []
            for _, row in edited_df.iterrows():
                produit_brut = row["Produit Brute"]
                
                if any(cat in produit_brut.upper() for cat in ["VINS ROUGES", "VINS BLANCS", "VINS ROSES", "LIQUEUR", "CONSIGNE", "122111", "122112", "122113"]):
                    new_data.append({
                        "Produit Brute": produit_brut,
                        "Produit Standard": produit_brut,
                        "Quantité": row["Quantité"],
                        "Confiance": "0%",
                        "Auto": False
                    })
                else:
                    produit_brut, produit_standard, confidence, status = standardize_product_for_bdc(produit_brut)
                    
                    new_data.append({
                        "Produit Brute": produit_brut,
                        "Produit Standard": produit_standard,
                        "Quantité": row["Quantité"],
                        "Confiance": f"{confidence*100:.1f}%",
                        "Auto": confidence >= 0.7
                    })
            
            st.session_state.edited_standardized_df = pd.DataFrame(new_data)
            st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # BOUTON D'EXPORT
    # ========================================================
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h4>🚀 Export vers Cloud</h4>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="info-box">
        <strong style="color: #1A1A1A !important;">🌐 Destination :</strong> Google Sheets (Cloud)<br>
        <strong style="color: #1A1A1A !important;">📄 Type détecté :</strong> {doc_type}<br>
        <strong style="color: #1A1A1A !important;">⚡ Fonctionnalités :</strong> Détection V3 + Standardisation intelligente<br>
        <strong style="color: #1A1A1A !important;">⚠️ Filtres actifs :</strong> 
        • Suppression lignes quantité 0 | • Standardisation Chan Foui | • Détection intelligente
    </div>
    """, unsafe_allow_html=True)
    
    col_btn, col_info = st.columns([2, 1])
    
    with col_btn:
        if st.button("🚀 Synchroniser avec Google Sheets", 
                    use_container_width=True, 
                    type="primary",
                    key="export_button",
                    help="Cliquez pour exporter les données vers le cloud"):
            
            try:
                success, message = save_to_google_sheets(
                    doc_type,
                    st.session_state.data_for_sheets,
                    st.session_state.edited_standardized_df
                )
                
                if success:
                    st.success("✅ Données exportées avec succès!")
                    st.balloons()
                else:
                    st.error(f"❌ Erreur lors de l'export: {message}")
                    
            except Exception as e:
                st.error(f"❌ Erreur système: {str(e)}")
    
    with col_info:
        st.markdown(f"""
        <div style="text-align: center; padding: 15px; background: rgba(59, 130, 246, 0.05); border-radius: 12px; height: 100%;">
            <div style="font-size: 1.5rem; color: #3B82F6 !important;">⚡</div>
            <div style="font-size: 0.8rem; color: #4B5563 !important;">Export instantané<br>Détection V3</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # SECTION DÉTECTION V3
    # ========================================================
    with st.expander("🔍 Détails de la détection V3"):
        st.markdown(f"""
        <div class="info-box">
            <strong>Informations de détection :</strong><br><br>
            • Type détecté : {detection_info.get('type_document', 'Non détecté')}<br>
            • Client : {detection_info.get('client', 'Non détecté')}<br>
            • N° Document : {detection_info.get('numero', 'Non détecté')}<br>
            • Adresse : {detection_info.get('adresse_livraison', 'Non détecté')}<br>
            • Date : {detection_info.get('date', 'Non détecté')}<br>
            • Méthode : Détection regex + IA
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🧪 Tester la détection sur des exemples"):
            test_examples = [
                "FACTURE EN COMPTE N° 123456",
                "Bon de commande n° 25011956",
                "BDC ULYS N° 78901234",
                "FACTURE DOIT S2M",
                "Bon de commande LeaderPrice"
            ]
            
            results = []
            for example in test_examples:
                detection = extract_document_type_from_text(example)
                results.append({
                    "Texte": example,
                    "Type détecté": detection["type_document"],
                    "Client": detection.get("client", ""),
                    "N°": detection.get("numero", "")
                })
            
            test_df = pd.DataFrame(results)
            st.dataframe(test_df, use_container_width=True)
    
    # ========================================================
    # BOUTONS DE NAVIGATION
    # ========================================================
    if st.session_state.document_scanned:
        st.markdown("---")
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>🧭 Navigation</h4>', unsafe_allow_html=True)
        
        col_nav1, col_nav2 = st.columns(2)
        
        with col_nav1:
            if st.button("📄 Nouveau document", 
                        use_container_width=True, 
                        type="secondary",
                        key="new_doc_main_nav",
                        help="Scanner un nouveau document"):
                st.session_state.uploaded_file = None
                st.session_state.uploaded_image = None
                st.session_state.ocr_result = None
                st.session_state.show_results = False
                st.session_state.detected_document_type = None
                st.session_state.image_preview_visible = False
                st.session_state.document_scanned = False
                st.session_state.export_triggered = False
                st.session_state.product_matching_scores = {}
                st.session_state.raw_ocr_text = ""
                st.session_state.document_detection_info = {}
                st.rerun()
        
        with col_nav2:
            if st.button("🔄 Réanalyser", 
                        use_container_width=True, 
                        type="secondary",
                        key="restart_main_nav",
                        help="Recommencer l'analyse du document actuel"):
                st.session_state.uploaded_file = None
                st.session_state.uploaded_image = None
                st.session_state.ocr_result = None
                st.session_state.show_results = False
                st.session_state.detected_document_type = None
                st.session_state.image_preview_visible = True
                st.session_state.document_scanned = True
                st.session_state.export_triggered = False
                st.session_state.product_matching_scores = {}
                st.session_state.raw_ocr_text = ""
                st.session_state.document_detection_info = {}
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# BOUTON DE DÉCONNEXION
# ============================================================

st.markdown("---")
if st.button("🔒 Déconnexion sécurisée", 
            use_container_width=True, 
            type="secondary",
            key="logout_button_final",
            help="Fermer la session en toute sécurité"):
    logout()

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.markdown(f"""
<center style='margin: 15px 0;'>
    <span style='font-weight: 700; color: #27414A !important;'>{BRAND_TITLE}</span>
    <span style='color: #4B5563 !important;'> • Système V3 - Détection Intelligente • © {datetime.now().strftime("%Y")}</span>
</center>
""", unsafe_allow_html=True)

st.markdown(f"""
<center style='font-size: 0.8rem; color: #4B5563 !important;'>
    <span style='color: #10B981 !important;'>●</span> 
    Système actif • Session : 
    <strong style='color: #1A1A1A !important;'>{st.session_state.username}</strong>
    • Détection V3 • {datetime.now().strftime("%H:%M:%S")}
</center>
""", unsafe_allow_html=True)
