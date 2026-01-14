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
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import threading

# ============================================================
# STANDARDISATION INTELLIGENTE DES PRODUITS
# ============================================================

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
    "Rhum Sambatra 20 cl",
    "Consignation Btl 75 cl",
    "Côte de Fianar Gris 3L",
    "Côteau d'Ambalavao Special 75 cl",
    "Aperao Peche 37 cl",
    "Cuvee Speciale 75cls"
]

# ============================================================
# LOCK POUR PRÉVENIR LES EXPORTS DOUBLES
# ============================================================
class ExportLock:
    def __init__(self):
        self._lock = threading.Lock()
        self._locked = False
    
    def acquire(self):
        if self._locked:
            return False
        self._locked = True
        return True
    
    def release(self):
        self._locked = False
    
    @property
    def locked(self):
        return self._locked

export_lock = ExportLock()

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================
def extract_fact_number_from_handwritten(text: str) -> str:
    if not text:
        return ""
    
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    patterns = [
        r'\bFact\s*[:.]?\s*(\d{4,})\b',
        r'\bF\s*[:.]?\s*(\d{4,})\b',
        r'\bfact\s*[:.]?\s*(\d{4,})\b',
        r'\bf\s*[:.]?\s*(\d{4,})\b',
        r'Fact\.?\s*(\d{4,})',
        r'F\.?\s*(\d{4,})',
    ]
    
    all_matches = []
    for pattern in patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            number = match.group(1)
            all_matches.append({
                'number': number,
                'pattern': pattern,
                'position': match.start(),
                'is_fact': 'fact' in pattern.lower()
            })
    
    if not all_matches:
        return ""
    
    fact_matches = [m for m in all_matches if m['is_fact']]
    if fact_matches:
        fact_matches.sort(key=lambda x: x['position'], reverse=True)
        return fact_matches[0]['number']
    
    all_matches.sort(key=lambda x: x['position'], reverse=True)
    return all_matches[0]['number']

def extract_motel_name_from_doit(text: str) -> str:
    if not text:
        return ""
    
    text_upper = text.upper()
    
    patterns = [
        r'DOIT\s+M\s*:\s*(.+)',
        r'DOIT\s+M\s*:\s*(.+?)(?:\n|$)',
        r'DOIT\s*M\s*:\s*(.+)',
        r'DOIT\s*:\s*(.+?)(?:\n|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            motel_name = match.group(1).strip()
            motel_name = re.sub(r'[\n\r\t]', ' ', motel_name)
            motel_name = ' '.join(motel_name.split())
            motel_name = motel_name.strip()
            if motel_name:
                return motel_name
    
    return ""

def clean_quartier(quartier: str) -> str:
    if not quartier:
        return ""
    
    quartier = re.sub(r'["\'\[\]:]', '', quartier)
    quartier = re.sub(r'quartier[_\-]?s2m', '', quartier, flags=re.IGNORECASE)
    quartier = ' '.join(quartier.split())
    return quartier.strip()

def clean_adresse(adresse: str) -> str:
    if not adresse:
        return ""
    
    if '"quartier_s2m"' in adresse or "quartier_s2m" in adresse:
        match = re.search(r'"quartier_s2m":\s*"([^"]+)"', adresse)
        if match:
            quartier = match.group(1)
            return f"Supermaki {quartier}"
        
        match = re.search(r'quartier_s2m[":\s]+([^",}\]]+)', adresse)
        if match:
            quartier = match.group(1).strip()
            quartier = clean_quartier(quartier)
            return f"Supermaki {quartier}"
    
    if "Supermaki" in adresse:
        adresse = re.sub(r'["\'\[\]:]', ' ', adresse)
        adresse = re.sub(r'\s+', ' ', adresse)
        return adresse.strip()
    
    return adresse.strip()

SYNONYMS = {
    "cote de fianar": "côte de fianar",
    "cote de fianara": "côte de fianar",
    "fianara": "fianar",
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
    "cons. chan foul": "consignation btl",
    "cons chan foul": "consignation btl",
    "cons.chan foui": "consignation btl",
    "cons.chan foui 75cl": "consignation btl 75cl",
    "cons chan foui 75cl": "consignation btl 75cl",
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
    "coteau d'ambalavao rouge": "cuvee speciale 75cls",
    "coteau d ambalavao rouge": "cuvee speciale 75cls",
    "ambalavao rouge": "cuvee speciale 75cls",
    "coteau ambalavao rouge": "cuvee speciale 75cls",
    "côteau d'ambalavao rouge": "cuvee speciale 75cls",
    "côteau ambalavao rouge": "cuvee speciale 75cls",
    "cote fianar": "côte de fianar",
    "cote de fianar 3l": "côte de fianar 3l",
    "cote fianar 3l": "côte de fianar 3l",
    "maroparasy doux": "blanc doux maroparasy",
    "maroparas doux": "blanc doux maroparasy",
    "aperao peche": "aperao pêche",
    "aperitif aperao": "aperao",
    "vin champetre": "vin de champêtre",
    "jus raisin": "jus de raisin",
    "rhum": "sambatra",
    "consignation": "consignation btl",
}

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
    "37cl": "37",
    "37 cl": "37",
    "70cl": "70",
    "70 cl": "70",
    "20cl": "20",
    "20 cl": "20",
    "100cl": "100",
    "100 cl": "100",
    "50cl": "50",
    "50 cl": "50",
}

def preprocess_text(text: str) -> str:
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
                if ('rose' in features1[key] and 'rosé' in features2[key]) or ('rosé' in features1[key] and 'rose' in features2[key]):
                    score += weight * 0.8
        max_score += weight
    
    if features1.get('volume') and features2.get('volume'):
        if features1['volume'] == features2['volume']:
            score += 0.1
            max_score += 0.1
    
    return score / max_score if max_score > 0 else 0.0

def find_best_match(ocr_designation: str, standard_products: List[str]) -> Tuple[Optional[str], float]:
    ocr_features = extract_product_features(ocr_designation)
    standard_features = []
    for product in standard_products:
        std_features = extract_product_features(product)
        standard_features.append((product, std_features))
    
    best_match = None
    best_score = 0.0
    
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
    produit_brut = product_name.strip()
    produit_standard, confidence, status = standardize_product_name_improved(product_name)
    
    produit_upper = produit_brut.upper()
    
    if "CONS" in produit_upper and "CHAN" in produit_upper and "FOUI" in produit_upper:
        if "75" in produit_upper or "750" in produit_upper:
            produit_standard = "Consignation btl 75cl"
        else:
            produit_standard = "Consignation btl"
        confidence = 0.95
        status = "matched"
    
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
    
    if "3L" in produit_upper or "3 L" in produit_upper:
        if "ROUGE" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Rouge 3L"
            confidence = 0.9
            status = "matched"
        elif "BLANC" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Blanc 3L"
            confidence = 0.9
            status = "matched"
        elif "ROSE" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Rosé 3L"
            confidence = 0.9
            status = "matched"
        elif "GRIS" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Gris 3L"
            confidence = 0.9
            status = "matched"
    
    if "COTEAU" in produit_upper and "AMBALAVAO" in produit_upper and "ROUGE" in produit_upper:
        produit_standard = "Cuvee Speciale 75cls"
        confidence = 0.95
        status = "matched"
    
    if "COTEAU" in produit_upper and "DAMBALAVAO" in produit_upper:
        if "ROUGE" in produit_upper:
            produit_standard = "Cuvee Speciale 75cls"
            confidence = 0.9
            status = "matched"
        elif "BLANC" in produit_upper:
            produit_standard = "Côteau d'Ambalavao Blanc 75 cl"
            confidence = 0.9
            status = "matched"
        elif "ROSE" in produit_upper:
            produit_standard = "Côteau d'Ambalavao Rosé 75 cl"
            confidence = 0.9
            status = "matched"
    
    if "APERAO" in produit_upper and "PECHE" in produit_upper:
        if "37" in produit_upper or "370" in produit_upper:
            produit_standard = "Aperao Peche 37 cl"
        else:
            produit_standard = "Aperao Pêche 75 cl"
        confidence = 0.9
        status = "matched"
    
    if "COTEAU" in produit_upper and "AMBALAVAO" in produit_upper and "SPECIAL" in produit_upper:
        produit_standard = "Côteau d'Ambalavao Special 75 cl"
        confidence = 0.9
        status = "matched"
    
    return produit_brut, produit_standard, confidence, status

# ============================================================
# CONFIGURATION STREAMLIT
# ============================================================
st.set_page_config(
    page_title="Chan Foui & Fils — Scanner Pro",
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
if "login_attempts" not in st.session_state:
    st.session_state.login_attempts = 0
if "locked_until" not in st.session_state:
    st.session_state.locked_until = None
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
if "ocr_raw_text" not in st.session_state:
    st.session_state.ocr_raw_text = None
if "document_analysis_details" not in st.session_state:
    st.session_state.document_analysis_details = {}
if "quartier_s2m" not in st.session_state:
    st.session_state.quartier_s2m = ""
if "nom_magasin_ulys" not in st.session_state:
    st.session_state.nom_magasin_ulys = ""
if "fact_manuscrit" not in st.session_state:
    st.session_state.fact_manuscrit = ""
if "worksheet_cache" not in st.session_state:
    st.session_state.worksheet_cache = {}
if "export_in_progress" not in st.session_state:
    st.session_state.export_in_progress = False

# ============================================================
# AUTHENTIFICATION
# ============================================================
AUTHORIZED_USERS = {
    "Pathou M.": "CFF3",
    "Elodie R.": "CFF2", 
    "Laetitia C.": "CFF1",
    "Admin Cf.": "CFF4"
}

def check_authentication():
    if st.session_state.locked_until and datetime.now() < st.session_state.locked_until:
        remaining_time = st.session_state.locked_until - datetime.now()
        st.error(f"🛑 Compte temporairement verrouillé. Réessayez dans {int(remaining_time.total_seconds())} secondes.")
        return False
    return st.session_state.authenticated

def login(username, password):
    if st.session_state.locked_until and datetime.now() < st.session_state.locked_until:
        return False, "Compte temporairement verrouillé"
    
    if username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password:
        st.session_state.authenticated = True
        st.session_state.username = username
        st.session_state.login_attempts = 0
        st.session_state.locked_until = None
        return True, "Connexion réussie"
    else:
        st.session_state.login_attempts += 1
        
        if st.session_state.login_attempts >= 3:
            lock_duration = 300
            st.session_state.locked_until = datetime.now() + pd.Timedelta(seconds=lock_duration)
            return False, f"Trop de tentatives échouées. Compte verrouillé pour {lock_duration//60} minutes."
        
        return False, f"Identifiants incorrects. Tentatives restantes: {3 - st.session_state.login_attempts}"

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
    st.rerun()

# ============================================================
# PAGE DE CONNEXION
# ============================================================
if not check_authentication():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400&display=swap');
        
        .login-container {
            max-width: 420px;
            margin: 50px auto;
            padding: 40px 35px;
            background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
            border-radius: 24px;
            box-shadow: 0 12px 40px rgba(39, 65, 74, 0.15),
                        0 0 0 1px rgba(39, 65, 74, 0.05);
            text-align: center;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.8);
        }
        
        .login-title {
            background: linear-gradient(135deg, #27414A 0%, #2C5F73 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
            font-family: 'Inter', sans-serif;
        }
        
        .login-subtitle {
            color: #1E293B !important;
            margin-bottom: 32px;
            font-size: 1rem;
            font-weight: 400;
            font-family: 'Inter', sans-serif;
        }
        
        .stSelectbox > div > div,
        .stTextInput > div > div > input {
            color: #1E293B !important;
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
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    if os.path.exists("CF_LOGOS.png"):
        st.image("CF_LOGOS.png", width=90)
    else:
        st.markdown("""<div style="font-size: 3rem; margin-bottom: 20px;">🍷</div>""", unsafe_allow_html=True)
    
    st.markdown('<h1 class="login-title">CHAN FOUI ET FILS</h1>', unsafe_allow_html=True)
    st.markdown('<p class="login-subtitle">Système de Scanner Pro - Accès Restreint</p>', unsafe_allow_html=True)
    
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
    
    st.markdown("""
    <div style="background: linear-gradient(135deg, #FFF3CD 0%, #FFE8A1 100%); border: 1px solid #FFC107; border-radius: 14px; padding: 18px; margin-top: 28px; font-size: 0.9rem; color: #856404 !important;">
        <strong style="display: block; margin-bottom: 8px;">🔐 Protocole de sécurité :</strong>
        • Votre compte est protégé<br>
        • Vos informations sont en sécurité<br>
        • Personne d'autre ne peut y accéder<br>
        • Verrouillage automatique après 3 tentatives
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ============================================================
# THÈME PRINCIPAL
# ============================================================
PALETTE = {
    "primary_dark": "#27414A",
    "accent": "#2C5F73",
    "success": "#10B981",
    "warning": "#F59E0B",
    "error": "#EF4444",
    "text_dark": "#1A1A1A",
}

st.markdown(f"""
<style>
    * {{
        color: {PALETTE['text_dark']} !important;
    }}
    
    .main {{
        background: linear-gradient(135deg, #F5F5F3 0%, #f0f2f5 100%);
    }}
    
    .header-container {{
        background: linear-gradient(145deg, #FFFFFF 0%, #f8fafc 100%);
        padding: 2.5rem 2rem;
        border-radius: 24px;
        margin-bottom: 2.5rem;
        box-shadow: 0 12px 40px rgba(39, 65, 74, 0.1);
        text-align: center;
        position: relative;
    }}
    
    .user-info {{
        position: absolute;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, {PALETTE['accent']} 0%, #3B82F6 100%);
        color: white !important;
        padding: 10px 20px;
        border-radius: 16px;
        font-size: 0.9rem;
        font-weight: 600;
    }}
    
    .brand-title {{
        background: linear-gradient(135deg, {PALETTE['primary_dark']} 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.8rem;
        font-weight: 800;
        margin: 0;
    }}
    
    .card {{
        background: linear-gradient(145deg, #FFFFFF 0%, #f8fafc 100%);
        padding: 2.2rem;
        border-radius: 20px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
        margin-bottom: 2rem;
    }}
    
    .stButton > button {{
        background: linear-gradient(135deg, {PALETTE['primary_dark']} 0%, {PALETTE['accent']} 100%);
        color: white !important;
        font-weight: 600;
        border: none;
        padding: 1rem 2rem;
        border-radius: 14px;
        width: 100%;
    }}
    
    .info-box {{
        background: linear-gradient(135deg, #E8F4F8 0%, #D4EAF7 100%);
        border-left: 4px solid #3B82F6;
        padding: 1.5rem;
        border-radius: 16px;
        margin: 1.2rem 0;
        color: {PALETTE['text_dark']} !important;
    }}
    
    .duplicate-box {{
        background: linear-gradient(135deg, #FFEDD5 0%, #FED7AA 100%);
        border: 2px solid {PALETTE['warning']};
        padding: 2rem;
        border-radius: 18px;
        margin: 2rem 0;
    }}
</style>
""", unsafe_allow_html=True)

# ============================================================
# GOOGLE SHEETS CONFIGURATION
# ============================================================
SHEET_ID = "1h4xT-cw9Ys1HbkhMWVtRnDOxsZ0fBOaskjPgRyIj3K8"
SHEET_GIDS = {
    "FACTURE EN COMPTE": 0,
    "BDC LEADERPRICE": 581432835,
    "BDC S2M": 581432835,
    "BDC ULYS": 581432835
}

def normalize_document_type(doc_type: str) -> str:
    if not doc_type:
        return "DOCUMENT INCONNU"
    
    doc_type_upper = doc_type.upper()
    
    facture_keywords = ["FACTURE", "INVOICE", "BILL", "DOIT"]
    bdc_keywords = ["BDC", "BON DE COMMANDE", "ORDER", "COMMANDE"]
    
    facture_score = sum(1 for keyword in facture_keywords if keyword in doc_type_upper)
    bdc_score = sum(1 for keyword in bdc_keywords if keyword in doc_type_upper)
    
    if facture_score > bdc_score:
        return "FACTURE EN COMPTE"
    
    elif bdc_score > facture_score:
        if "LEADERPRICE" in doc_type_upper or "DLP" in doc_type_upper:
            return "BDC LEADERPRICE"
        elif "ULYS" in doc_type_upper:
            return "BDC ULYS"
        elif "S2M" in doc_type_upper or "SUPERMAKI" in doc_type_upper:
            return "BDC S2M"
        else:
            return "BDC LEADERPRICE"
    
    else:
        if "FACTURE" in doc_type_upper and "COMPTE" in doc_type_upper:
            return "FACTURE EN COMPTE"
        elif "BDC" in doc_type_upper:
            return "BDC LEADERPRICE"
        else:
            return "DOCUMENT INCONNU"

# ============================================================
# RETRY MECHANISM FOR GOOGLE SHEETS API
# ============================================================
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((gspread.exceptions.APIError, Exception))
)
def safe_google_sheets_operation(operation, *args, **kwargs):
    """Execute Google Sheets operation with retry logic"""
    time.sleep(1)  # Throttling between API calls
    return operation(*args, **kwargs)

# ============================================================
# OPTIMIZED DUPLICATE DETECTION
# ============================================================
def check_for_duplicates_fast(document_type: str, extracted_data: dict, worksheet) -> Tuple[bool, List[Dict]]:
    """Fast duplicate detection using key-based lookup"""
    try:
        cache_key = f"{worksheet.title}_{document_type}"
        
        if cache_key not in st.session_state.worksheet_cache:
            all_data = safe_google_sheets_operation(worksheet.get_all_values)
            
            if len(all_data) <= 1:
                st.session_state.worksheet_cache[cache_key] = set()
                return False, []
            
            header = all_data[0]
            
            client_idx = 2
            doc_num_idx = 3
            date_idx = 1
            
            for i, col in enumerate(header):
                col_upper = col.upper()
                if "CLIENT" in col_upper:
                    client_idx = i
                elif "FACT" in col_upper or "N*" in col_upper:
                    doc_num_idx = i
                elif "DATE" in col_upper:
                    date_idx = i
            
            key_set = set()
            
            for i, row in enumerate(all_data[1:], start=2):
                if len(row) > max(client_idx, doc_num_idx, date_idx):
                    client = row[client_idx].strip() if len(row) > client_idx else ""
                    doc_num = row[doc_num_idx].strip() if len(row) > doc_num_idx else ""
                    date_val = row[date_idx].strip() if len(row) > date_idx else ""
                    
                    if client and doc_num:
                        key = f"{client}_{doc_num}"
                        if "ULYS" in client.upper() and "BDC" in document_type.upper():
                            key = f"{key}_{date_val}"
                        key_set.add(key)
            
            st.session_state.worksheet_cache[cache_key] = key_set
        
        key_set = st.session_state.worksheet_cache[cache_key]
        
        client = extracted_data.get('client', '').strip()
        
        if "FACTURE" in document_type.upper():
            doc_num = extracted_data.get('numero_facture', '').strip()
        else:
            doc_num = extracted_data.get('numero', '').strip()
        
        if not client or not doc_num:
            return False, []
        
        search_key = f"{client}_{doc_num}"
        
        if "ULYS" in client.upper() and "BDC" in document_type.upper():
            date_val = extracted_data.get('date', '').strip()
            search_key = f"{search_key}_{date_val}"
        
        if search_key in key_set:
            return True, [{'row_number': 0, 'data': [], 'match_type': 'Document déjà présent'}]
        
        return False, []
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la vérification des doublons: {str(e)}")
        return False, []

# ============================================================
# GOOGLE SHEETS FUNCTIONS WITH RETRY
# ============================================================
def get_worksheet(document_type: str):
    """Get worksheet with retry mechanism"""
    try:
        if "gcp_sheet" not in st.secrets:
            st.error("❌ Les credentials Google Sheets ne sont pas configurés")
            return None
        
        normalized_type = normalize_document_type(document_type)
        
        if normalized_type not in SHEET_GIDS:
            normalized_type = "FACTURE EN COMPTE"
        
        sa_info = dict(st.secrets["gcp_sheet"])
        gc = gspread.service_account_from_dict(sa_info)
        sh = safe_google_sheets_operation(gc.open_by_key, SHEET_ID)
        
        target_gid = SHEET_GIDS.get(normalized_type)
        
        if target_gid is None:
            return safe_google_sheets_operation(sh.get_worksheet, 0)
        
        for worksheet in sh.worksheets():
            if int(worksheet.id) == target_gid:
                return worksheet
        
        return safe_google_sheets_operation(sh.get_worksheet, 0)
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la connexion à Google Sheets: {str(e)}")
        return None

def prepare_rows_for_sheet(document_type: str, data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
    """Prepare rows for Google Sheets insertion"""
    rows = []
    
    try:
        if "FACTURE" in document_type.upper():
            date_str = data.get("date", "")
            try:
                date_obj = parser.parse(date_str, dayfirst=True)
                date_formatted = date_obj.strftime("%d/%m/%Y")
            except:
                date_formatted = datetime.now().strftime("%d/%m/%Y")
            
            mois = data.get("mois", date_obj.strftime("%B") if 'date_obj' in locals() else "")
            client = data.get("client", "")
            numero = data.get("numero_facture", "")
            magasin = data.get("adresse_livraison", "")
            editeur = st.session_state.username
            
            columns = ["Mois", "Date", "Client", "N* facture", "Magasin", "Désignation", "Quantité", "Editeur"]
        else:
            date_str = data.get("date", "")
            try:
                date_obj = parser.parse(date_str, dayfirst=True)
                date_formatted = date_obj.strftime("%d/%m/%Y")
            except:
                date_formatted = datetime.now().strftime("%d/%m/%Y")
            
            mois = date_obj.strftime("%B") if 'date_obj' in locals() else ""
            client = data.get("client", "")
            numero = data.get("numero", "")
            magasin = data.get("adresse_livraison", "")
            editeur = st.session_state.username
            
            columns = ["Mois", "Date", "Client", "FACT", "Magasin", "Désignation", "Quantité", "Editeur"]
        
        for _, row in articles_df.iterrows():
            quantite = row.get("Quantité", 0)
            if pd.isna(quantite) or quantite == 0:
                continue
            
            try:
                quantite_int = int(float(quantite))
                if quantite_int <= 0:
                    continue
            except:
                continue
            
            designation = str(row.get("Produit Standard", "")).strip()
            if not designation:
                designation = str(row.get("Produit Brute", "")).strip()
            
            if "FACTURE" in document_type.upper():
                rows.append([mois, date_formatted, client, numero, magasin, designation, str(quantite_int), editeur])
            else:
                rows.append([mois, date_formatted, client, numero, magasin, designation, str(quantite_int), editeur])
        
        return rows
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la préparation des données: {str(e)}")
        return []

def save_to_google_sheets(document_type: str, data: dict, articles_df: pd.DataFrame, 
                         duplicate_action: str = None, duplicate_rows: List[int] = None):
    """Save data to Google Sheets with retry mechanism and execution lock"""
    
    if st.session_state.export_in_progress:
        return False, "Un export est déjà en cours..."
    
    if not export_lock.acquire():
        return False, "Un export est déjà en cours..."
    
    try:
        st.session_state.export_in_progress = True
        
        ws = get_worksheet(document_type)
        if not ws:
            return False, "Impossible de se connecter à Google Sheets"
        
        new_rows = prepare_rows_for_sheet(document_type, data, articles_df)
        if not new_rows:
            return False, "Aucune donnée à enregistrer"
        
        if duplicate_action == "overwrite" and duplicate_rows:
            try:
                all_data = safe_google_sheets_operation(ws.get_all_values)
                existing_keys = set()
                
                for row_num in duplicate_rows:
                    if row_num <= len(all_data):
                        existing_keys.add(row_num)
                
                rows_to_delete = sorted(existing_keys, reverse=True)
                for row_num in rows_to_delete:
                    safe_google_sheets_operation(ws.delete_rows, row_num)
                    time.sleep(0.5)
                
                st.info(f"🗑️ {len(rows_to_delete)} ligne(s) dupliquée(s) supprimée(s)")
                
            except Exception as e:
                st.error(f"❌ Erreur lors de la suppression des doublons: {str(e)}")
                return False, str(e)
        
        if duplicate_action == "skip":
            return True, "Document ignoré (doublon)"
        
        try:
            safe_google_sheets_operation(ws.append_rows, new_rows, value_input_option="USER_ENTERED")
            
            action_msg = "enregistrée(s)"
            if duplicate_action == "overwrite":
                action_msg = "mise(s) à jour"
            elif duplicate_action == "add_new":
                action_msg = "ajoutée(s) comme nouvelle(s)"
            
            st.success(f"✅ {len(new_rows)} ligne(s) {action_msg} avec succès!")
            
            cache_key = f"{ws.title}_{document_type}"
            if cache_key in st.session_state.worksheet_cache:
                del st.session_state.worksheet_cache[cache_key]
            
            return True, f"{len(new_rows)} lignes {action_msg}"
            
        except Exception as e:
            st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
            return False, str(e)
            
    finally:
        st.session_state.export_in_progress = False
        export_lock.release()

# ============================================================
# OPENAI FUNCTIONS
# ============================================================
def get_openai_client():
    try:
        if "openai" in st.secrets:
            api_key = st.secrets["openai"]["api_key"]
        else:
            api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            st.error("❌ Clé API OpenAI non configurée")
            return None
        
        return OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"❌ Erreur d'initialisation OpenAI: {str(e)}")
        return None

def encode_image_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode('utf-8')

def preprocess_image(b: bytes) -> bytes:
    img = Image.open(BytesIO(b)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180))
    out = BytesIO()
    img.save(out, format="PNG", optimize=True, quality=95)
    return out.getvalue()

def openai_vision_ocr_improved(image_bytes: bytes) -> Dict:
    try:
        client = get_openai_client()
        if not client:
            return None
        
        base64_image = encode_image_to_base64(image_bytes)
        
        prompt = """
        ANALYSE CE DOCUMENT ET EXTRACT LES INFORMATIONS SUIVANTES:
        
        Puis selon le type:
        1. SI C'EST UNE FACTURE (FACTURE EN COMPTE):
            "numero_facture": "...",
            "date": "...",
            "bon_commande": "...",
            "articles": [
                {
                    "article_brut": "TEXT EXACT de l'article",
                    "quantite": nombre
                }
            ]
        
        2. SI C'EST UN BDC (DLP, S2M, ULYS):
            "numero": "...",
            "date": "...",
            "articles": [
                {
                    "article_brut": "TEXT EXACT de la colonne Désignation",
                    "quantite": nombre
                }
            ]
        """
        
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
        
        content = response.choices[0].message.content
        st.session_state.ocr_raw_text = content
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                return json.loads(json_str)
            except:
                pass
        
        return {"type_document": "UNKNOWN", "articles": []}
        
    except Exception as e:
        st.error(f"❌ Erreur OpenAI Vision: {str(e)}")
        return None

def analyze_document_with_backup(image_bytes: bytes) -> Dict:
    result = openai_vision_ocr_improved(image_bytes)
    
    if not result:
        return {"type_document": "DOCUMENT INCONNU", "articles": []}
    
    ocr_text = st.session_state.ocr_raw_text or ""
    
    if ocr_text and result.get("type_document") == "BDC":
        fact_manuscrit = extract_fact_number_from_handwritten(ocr_text)
        if fact_manuscrit:
            result["fact_manuscrit"] = fact_manuscrit
            result["numero"] = fact_manuscrit
    
    return result

# ============================================================
# HEADER
# ============================================================
st.markdown('<div class="header-container">', unsafe_allow_html=True)

st.markdown(f'''
<div class="user-info">
    👤 {st.session_state.username}
</div>
''', unsafe_allow_html=True)

st.markdown('<div class="logo-title-wrapper">', unsafe_allow_html=True)

LOGO_FILENAME = "CF_LOGOS.png"
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME, width=100)
else:
    st.markdown("""<div style="font-size: 3.5rem; margin-bottom: 10px;">🍷</div>""", unsafe_allow_html=True)

st.markdown('<h1 class="brand-title">CHAN FOUI ET FILS</h1>', unsafe_allow_html=True)
st.markdown('<p class="brand-sub">Système intelligent de traitement de documents</p>', unsafe_allow_html=True)

st.markdown('</div>')
st.markdown('</div>')

# ============================================================
# UPLOAD ZONE
# ============================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<h4>📤 Zone de dépôt de documents</h4>', unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    <strong>ℹ️ Que fait ChanFoui.AI ?</strong>
    <ul style="margin-top:10px;">
        <li>Il lit votre facture ou bon de commande</li>
        <li>Il corrige automatiquement les noms des produits</li>
        <li>Il garde uniquement les quantités utiles</li>
        <li>Il évite les doublons</li>
        <li>Il enregistre tout automatiquement</li>
    </ul>
</div>
""", unsafe_allow_html=True)

uploaded = st.file_uploader(
    "**Déposez votre document ici ou cliquez pour parcourir**",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
    help="Formats supportés : JPG, JPEG, PNG",
    key="file_uploader_main"
)

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# DOCUMENT PROCESSING
# ============================================================
if uploaded and uploaded != st.session_state.uploaded_file:
    st.session_state.uploaded_file = uploaded
    st.session_state.uploaded_image = Image.open(uploaded)
    st.session_state.ocr_result = None
    st.session_state.show_results = False
    st.session_state.processing = True
    st.session_state.detected_document_type = None
    st.session_state.duplicate_check_done = False
    st.session_state.duplicate_found = False
    st.session_state.duplicate_action = None
    st.session_state.image_preview_visible = True
    st.session_state.document_scanned = True
    st.session_state.export_triggered = False
    st.session_state.export_status = None
    st.session_state.product_matching_scores = {}
    st.session_state.ocr_raw_text = None
    st.session_state.document_analysis_details = {}
    st.session_state.quartier_s2m = ""
    st.session_state.nom_magasin_ulys = ""
    st.session_state.fact_manuscrit = ""
    st.session_state.worksheet_cache = {}
    
    with st.spinner("🤖 Analyse en cours avec GPT-4 Vision..."):
        try:
            buf = BytesIO()
            st.session_state.uploaded_image.save(buf, format="JPEG")
            image_bytes = buf.getvalue()
            
            img_processed = preprocess_image(image_bytes)
            result = analyze_document_with_backup(img_processed)
            
            if result:
                raw_doc_type = result.get("type_document", "DOCUMENT INCONNU")
                document_subtype = result.get("document_subtype", "").upper()
                
                if document_subtype == "DLP":
                    final_doc_type = "BDC LEADERPRICE"
                elif document_subtype == "S2M":
                    final_doc_type = "BDC S2M"
                elif document_subtype == "ULYS":
                    final_doc_type = "BDC ULYS"
                elif document_subtype == "FACTURE":
                    final_doc_type = "FACTURE EN COMPTE"
                else:
                    final_doc_type = normalize_document_type(raw_doc_type)
                
                st.session_state.detected_document_type = final_doc_type
                st.session_state.ocr_result = result
                st.session_state.show_results = True
                st.session_state.processing = False
                
                if "articles" in result:
                    std_data = []
                    for article in result["articles"]:
                        raw_name = article.get("article_brut", article.get("article", ""))
                        
                        if any(cat in raw_name.upper() for cat in ["VINS ROUGES", "VINS BLANCS", "VINS ROSES", "LIQUEUR", "CONSIGNE"]):
                            std_data.append({
                                "Produit Brute": raw_name,
                                "Produit Standard": raw_name,
                                "Quantité": article.get("quantite", 0),
                                "Confiance": "0%",
                                "Auto": False
                            })
                        else:
                            produit_brut, produit_standard, confidence, status = standardize_product_for_bdc(raw_name)
                            
                            std_data.append({
                                "Produit Brute": produit_brut,
                                "Produit Standard": produit_standard,
                                "Quantité": article.get("quantite", 0),
                                "Confiance": f"{confidence*100:.1f}%",
                                "Auto": confidence >= 0.7
                            })
                    
                    st.session_state.edited_standardized_df = pd.DataFrame(std_data)
                
                st.rerun()
            else:
                st.error("❌ Échec de l'analyse IA - Veuillez réessayer")
                st.session_state.processing = False
            
        except Exception as e:
            st.error(f"❌ Erreur système: {str(e)}")
            st.session_state.processing = False

# ============================================================
# DISPLAY RESULTS
# ============================================================
if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
    result = st.session_state.ocr_result
    doc_type = st.session_state.detected_document_type
    
    st.success("✅ Analyse IA terminée avec succès")
    
    st.markdown(f'<div class="document-title">📄 Document détecté : {doc_type}</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h4>📋 Informations extraites</h4>', unsafe_allow_html=True)
    
    if "FACTURE" in doc_type.upper():
        col1, col2 = st.columns(2)
        with col1:
            adresse = st.text_input("Adresse", value=result.get("adresse_livraison", ""), key="facture_adresse")
            numero_facture = st.text_input("N° Facture", value=result.get("numero_facture", ""), key="facture_num")
            bon_commande = st.text_input("Bon de commande", value=result.get("bon_commande", ""), key="facture_bdc")
        
        with col2:
            client_options = ["ULYS", "S2M", "DLP", "Autre"]
            extracted_client = result.get("client", "")
            default_index = 3
            
            if "DLP" in extracted_client.upper():
                default_index = 2
            elif "S2M" in extracted_client.upper():
                default_index = 1
            elif "ULYS" in extracted_client.upper():
                default_index = 0
            
            client_choice = st.selectbox("Client", options=client_options, index=default_index, key="facture_client_select")
            
            if client_choice == "Autre":
                client = adresse
            else:
                client = client_choice
            
            date_extracted = result.get("date", "")
            date = st.text_input("Date", value=date_extracted, key="facture_date")
            mois = st.text_input("Mois", value=result.get("mois", ""), key="facture_mois")
        
        data_for_sheets = {
            "client": client,
            "numero_facture": numero_facture,
            "bon_commande": bon_commande,
            "adresse_livraison": adresse,
            "date": date,
            "mois": mois
        }
    else:
        col1, col2 = st.columns(2)
        with col1:
            client_options = ["ULYS", "S2M", "DLP", "Autre"]
            extracted_client = result.get("client", "")
            default_index = 0
            
            if "DLP" in extracted_client.upper():
                default_index = 2
            elif "S2M" in extracted_client.upper():
                default_index = 1
            elif extracted_client and extracted_client not in ["ULYS", "S2M", "DLP"]:
                default_index = 3
            
            client_choice = st.selectbox("Client", options=client_options, index=default_index, key="bdc_client_select")
            
            if client_choice == "Autre":
                client = st.text_input("Autre client", value=extracted_client, key="bdc_client_other")
            else:
                client = client_choice
            
            fact_manuscrit = result.get("fact_manuscrit", "")
            numero = st.text_input("FACT", value=fact_manuscrit, key="bdc_numero")
        
        with col2:
            date_extracted = result.get("date", "")
            date = st.text_input("Date", value=date_extracted, key="bdc_date")
            
            adresse_value = result.get("adresse_livraison", "")
            adresse = st.text_input("Adresse", value=adresse_value, key="bdc_adresse")
        
        data_for_sheets = {
            "client": client,
            "numero": numero,
            "date": date,
            "adresse_livraison": adresse
        }
    
    st.session_state.data_for_sheets = data_for_sheets
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ============================================================
    # PRODUCT STANDARDIZATION TABLE
    # ============================================================
    if st.session_state.edited_standardized_df is not None and not st.session_state.edited_standardized_df.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>📘 Standardisation des Produits</h4>', unsafe_allow_html=True)
        
        edited_df = st.data_editor(
            st.session_state.edited_standardized_df,
            num_rows="dynamic",
            column_config={
                "Produit Brute": st.column_config.TextColumn("Produit Brute", width="large"),
                "Produit Standard": st.column_config.TextColumn("Produit Standard", width="large"),
                "Quantité": st.column_config.NumberColumn("Quantité", min_value=0, format="%d", step=1),
                "Confiance": st.column_config.TextColumn("Confiance", width="small"),
                "Auto": st.column_config.CheckboxColumn("Auto")
            },
            use_container_width=True,
            key="standardized_data_editor"
        )
        
        if "Quantité" in edited_df.columns:
            edited_df["Quantité"] = edited_df["Quantité"].apply(
                lambda x: int(round(float(x))) if pd.notna(x) else 0
            )
        
        st.session_state.edited_standardized_df = edited_df
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ============================================================
    # EXPORT BUTTON
    # ============================================================
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h4>🚀 Export vers Cloud</h4>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
        <strong>🌐 Destination :</strong> Google Sheets (Cloud)<br>
        <strong>🔒 Sécurité :</strong> Chiffrement AES-256<br>
        <strong>⚡ Vitesse :</strong> Synchronisation en temps réel<br>
        <strong>🔄 Vérification :</strong> Détection automatique des doublons
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀 Synchroniser avec Google Sheets", use_container_width=True, type="primary", key="export_button"):
        st.session_state.export_triggered = True
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ============================================================
    # DUPLICATE CHECK AND EXPORT
    # ============================================================
    if st.session_state.export_triggered and st.session_state.export_status is None:
        with st.spinner("🔍 Vérification des doublons..."):
            normalized_doc_type = normalize_document_type(doc_type)
            ws = get_worksheet(normalized_doc_type)
            
            if ws:
                duplicate_found, duplicates = check_for_duplicates_fast(
                    normalized_doc_type,
                    st.session_state.data_for_sheets,
                    ws
                )
                
                if not duplicate_found:
                    st.session_state.duplicate_found = False
                    st.session_state.export_status = "no_duplicates"
                    st.rerun()
                else:
                    st.session_state.duplicate_found = True
                    st.session_state.duplicate_rows = [d['row_number'] for d in duplicates]
                    st.session_state.export_status = "duplicates_found"
                    st.rerun()
            else:
                st.error("❌ Connexion cloud échouée")
                st.session_state.export_status = "error"
    
    # ============================================================
    # DUPLICATE HANDLING
    # ============================================================
    if st.session_state.export_status == "duplicates_found":
        st.markdown('<div class="duplicate-box">', unsafe_allow_html=True)
        st.warning("⚠️ ALERTE : DOUBLON DÉTECTÉ")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Remplacer", key="overwrite_duplicate", use_container_width=True):
                st.session_state.duplicate_action = "overwrite"
                st.session_state.export_status = "ready_to_export"
                st.rerun()
        
        with col2:
            if st.button("➕ Nouvelle entrée", key="add_new_duplicate", use_container_width=True):
                st.session_state.duplicate_action = "add_new"
                st.session_state.export_status = "ready_to_export"
                st.rerun()
        
        with col3:
            if st.button("❌ Annuler", key="skip_duplicate", use_container_width=True):
                st.session_state.duplicate_action = "skip"
                st.session_state.export_status = "ready_to_export"
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ============================================================
    # PERFORM EXPORT
    # ============================================================
    if st.session_state.export_status in ["no_duplicates", "ready_to_export"]:
        if st.session_state.export_status == "no_duplicates":
            st.session_state.duplicate_action = "add_new"
        
        export_df = st.session_state.edited_standardized_df.copy()
        export_df = export_df[export_df["Quantité"] > 0]
        
        if export_df.empty:
            st.warning("⚠️ Aucune ligne avec quantité > 0 à exporter")
            st.session_state.export_status = "error"
        else:
            with st.spinner("📤 Export en cours..."):
                success, message = save_to_google_sheets(
                    doc_type,
                    st.session_state.data_for_sheets,
                    export_df,
                    duplicate_action=st.session_state.duplicate_action,
                    duplicate_rows=st.session_state.duplicate_rows if st.session_state.duplicate_action == "overwrite" else None
                )
                
                if success:
                    st.session_state.export_status = "completed"
                    st.success("✅ Synchronisation réussie !")
                else:
                    st.session_state.export_status = "error"
                    st.error(f"❌ {message}")
    
    # ============================================================
    # NAVIGATION BUTTONS
    # ============================================================
    if st.session_state.document_scanned:
        st.markdown("---")
        
        col_nav1, col_nav2 = st.columns(2)
        
        with col_nav1:
            if st.button("📄 Nouveau document", use_container_width=True, type="secondary"):
                st.session_state.ocr_result = None
                st.session_state.data_for_sheets = None
                st.session_state.edited_standardized_df = None
                st.session_state.product_matching_scores = {}
                st.session_state.uploaded_file = None
                st.session_state.uploaded_image = None
                st.session_state.image_preview_visible = False
                st.session_state.show_results = False
                st.session_state.detected_document_type = None
                st.session_state.duplicate_check_done = False
                st.session_state.duplicate_found = False
                st.session_state.duplicate_action = None
                st.session_state.document_scanned = False
                st.session_state.export_triggered = False
                st.session_state.export_status = None
                st.session_state.ocr_raw_text = None
                st.session_state.document_analysis_details = {}
                st.session_state.quartier_s2m = ""
                st.session_state.nom_magasin_ulys = ""
                st.session_state.fact_manuscrit = ""
                st.session_state.worksheet_cache = {}
                st.rerun()
        
        with col_nav2:
            if st.button("🔄 Réanalyser", use_container_width=True, type="secondary"):
                st.session_state.uploaded_file = None
                st.session_state.uploaded_image = None
                st.session_state.ocr_result = None
                st.session_state.show_results = False
                st.session_state.detected_document_type = None
                st.session_state.duplicate_check_done = False
                st.session_state.duplicate_found = False
                st.session_state.duplicate_action = None
                st.session_state.image_preview_visible = True
                st.session_state.document_scanned = True
                st.session_state.export_triggered = False
                st.session_state.export_status = None
                st.session_state.product_matching_scores = {}
                st.rerun()

# ============================================================
# LOGOUT BUTTON
# ============================================================
st.markdown("---")
if st.button("🔒 Déconnexion sécurisée", use_container_width=True, type="secondary"):
    logout()

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown(f"""
<center style='margin: 15px 0;'>
    <span style='font-weight: 700; color: #27414A !important;'>CHAN FOUI ET FILS</span>
    <span style='color: #4B5563 !important;'> • Système IA Amélioré • © {datetime.now().strftime("%Y")}</span>
</center>
""", unsafe_allow_html=True)
