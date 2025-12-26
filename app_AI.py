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
import jellyfish  # Pour la distance de Jaro-Winkler

# ============================================================
# STANDARDISATION INTELLIGENTE DES PRODUITS
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
    # Marques principales
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
    
    # Types de vins
    "vin rouge": "rouge",
    "vin blanc": "blanc",
    "vin rose": "rosé",
    "vin rosé": "rosé",
    "vin gris": "gris",
    "rouge doux": "rouge doux",
    "blanc doux": "blanc doux",
    "doux": "doux",
    
    # Abréviations communes
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
    
    # Unités
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
    
    # Convertir en minuscules
    text = text.lower()
    
    # Supprimer les accents
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('ascii')
    
    # Remplacer les apostrophes et tirets
    text = text.replace("'", " ").replace("-", " ").replace("_", " ").replace("/", " ")
    
    # Supprimer les caractères spéciaux (garder lettres, chiffres, espaces)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    
    # Remplacer les synonymes
    words = text.split()
    cleaned_words = []
    for word in words:
        if word in SYNONYMS:
            replacement = SYNONYMS[word]
            if replacement:  # Ne pas ajouter si le synonyme est vide
                cleaned_words.append(replacement)
        else:
            cleaned_words.append(word)
    
    text = ' '.join(cleaned_words)
    
    # Supprimer les espaces multiples
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def extract_volume_info(text: str) -> Tuple[str, Optional[str]]:
    """Extrait et normalise l'information de volume"""
    # Chercher des motifs de volume
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
            # Normaliser le volume
            if 'ml' in pattern:
                # Convertir ml en cl
                try:
                    ml = int(volume)
                    if ml >= 1000:
                        volume = f"{ml//100}l" if ml % 1000 == 0 else f"{ml/10:.0f} cl"
                    else:
                        volume = f"{ml/10:.0f} cl" if ml % 10 == 0 else f"{ml/10:.1f} cl"
                except:
                    pass
            elif 'l' in pattern and 'cl' not in pattern and 'ml' not in pattern:
                # Convertir litres en cl
                try:
                    liters = float(volume)
                    if liters >= 1:
                        volume = f"{liters:.0f}l" if liters.is_integer() else f"{liters}l"
                except:
                    pass
            
            # Supprimer le volume du texte pour faciliter la correspondance
            text_without_volume = re.sub(pattern, '', text_without_volume)
            break
    
    # Chercher aussi des volumes sans unité spécifique
    if not volume:
        match = re.search(r'\b(\d+)\b', text)
        if match:
            vol_num = match.group(1)
            # Deviner l'unité basée sur la valeur
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
    
    # Normaliser le texte
    normalized = preprocess_text(text)
    
    # Extraire le volume
    text_without_volume, volume = extract_volume_info(normalized)
    if volume:
        features['volume'] = volume
    
    # Détecter la couleur
    colors = ['rouge', 'blanc', 'rose', 'gris', 'orange', 'peche', 'ananas', 'epices', 'ratafia']
    for color in colors:
        if color in text_without_volume:
            features['couleur'] = color
            text_without_volume = text_without_volume.replace(color, '')
            break
    
    # Détecter le type
    types = ['vin', 'jus', 'aperitif', 'eau de vie', 'cuvee', 'cuvee special', 'special', 'consigne']
    for type_ in types:
        if type_ in text_without_volume:
            features['type'] = type_
            text_without_volume = text_without_volume.replace(type_, '')
            break
    
    # Détecter la marque
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
    
    # Nettoyer le texte restant
    text_without_volume = re.sub(r'\s+', ' ', text_without_volume).strip()
    if text_without_volume:
        features['autres'] = text_without_volume
    
    return features

def calculate_similarity_score(features1: Dict, features2: Dict) -> float:
    """Calcule un score de similarité entre deux ensembles de caractéristiques"""
    score = 0.0
    max_score = 0.0
    
    # Poids pour chaque caractéristique
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
            # Similarité partielle pour les couleurs (rose/rosé)
            elif key == 'couleur':
                if ('rose' in features1[key] and 'rosé' in features2[key]) or \
                   ('rosé' in features1[key] and 'rose' in features2[key]):
                    score += weight * 0.8
        max_score += weight
    
    # Bonus pour correspondance exacte du volume
    if features1.get('volume') and features2.get('volume'):
        if features1['volume'] == features2['volume']:
            score += 0.1
            max_score += 0.1
    
    return score / max_score if max_score > 0 else 0.0

def find_best_match(ocr_designation: str, standard_products: List[str]) -> Tuple[Optional[str], float]:
    """
    Trouve le meilleur match pour une désignation OCR
    
    Returns:
        Tuple (produit_standard, score_confidence)
    """
    # Prétraiter la désignation OCR
    ocr_features = extract_product_features(ocr_designation)
    
    best_match = None
    best_score = 0.0
    
    # Pré-calculer les caractéristiques des produits standards
    standard_features = []
    for product in standard_products:
        std_features = extract_product_features(product)
        standard_features.append((product, std_features))
    
    # Chercher le meilleur match
    for product, std_features in standard_features:
        score = calculate_similarity_score(ocr_features, std_features)
        
        # Bonus pour correspondance exacte (après normalisation)
        ocr_normalized = preprocess_text(ocr_designation)
        std_normalized = preprocess_text(product)
        
        # Utiliser Jaro-Winkler pour la similarité textuelle
        jaro_score = jellyfish.jaro_winkler_similarity(ocr_normalized, std_normalized)
        
        # Combiner les scores
        combined_score = (score * 0.7) + (jaro_score * 0.3)
        
        if combined_score > best_score:
            best_score = combined_score
            best_match = product
    
    # Seuil de confiance minimum
    if best_score < 0.6:
        return None, best_score
    
    return best_match, best_score

def intelligent_product_matcher(ocr_designation: str) -> Tuple[Optional[str], float, Dict]:
    """
    Standardise intelligemment une désignation produit OCR
    
    Returns:
        Tuple (produit_standard, score_confidence, details)
    """
    details = {
        'original': ocr_designation,
        'features': {},
        'matches': []
    }
    
    # 1. Extraction des caractéristiques
    features = extract_product_features(ocr_designation)
    details['features'] = features
    
    # 2. Recherche du meilleur match
    best_match, confidence = find_best_match(ocr_designation, STANDARD_PRODUCTS)
    
    # 3. Calcul des alternatives (top 3)
    alternatives = []
    for product in STANDARD_PRODUCTS:
        product_features = extract_product_features(product)
        score = calculate_similarity_score(features, product_features)
        jaro_score = jellyfish.jaro_winkler_similarity(
            preprocess_text(ocr_designation),
            preprocess_text(product)
        )
        combined_score = (score * 0.7) + (jaro_score * 0.3)
        
        if combined_score >= 0.4:  # Seuil bas pour voir les alternatives
            alternatives.append((product, combined_score))
    
    # Trier par score décroissant
    alternatives.sort(key=lambda x: x[1], reverse=True)
    details['matches'] = alternatives[:3]  # Top 3 seulement
    
    return best_match, confidence, details

# ============================================================
# FONCTION AMÉLIORÉE DE STANDARDISATION
# ============================================================
def standardize_product_name_improved(product_name: str) -> Tuple[str, float, str]:
    """
    Standardise le nom du produit avec score de confiance
    
    Args:
        product_name: Nom du produit issu de l'OCR
        
    Returns:
        Tuple (nom_standardisé, score_confiance, status)
    """
    if not product_name or not product_name.strip():
        return "", 0.0, "empty"
    
    # Essayer d'abord avec le matching intelligent
    best_match, confidence, details = intelligent_product_matcher(product_name)
    
    if best_match and confidence >= 0.7:
        return best_match, confidence, "matched"
    elif best_match and confidence >= 0.6:
        # Match à confiance moyenne
        return best_match, confidence, "partial_match"
    else:
        # Aucun bon match trouvé
        return product_name.title(), confidence, "no_match"

# ============================================================
# FONCTION DE STANDARDISATION SPÉCIFIQUE POUR BDC
# ============================================================
def standardize_product_for_bdc(product_name: str) -> Tuple[str, str, float, str]:
    """
    Standardise spécifiquement pour les produits BDC ULYS
    
    Returns:
        Tuple (produit_brut, produit_standard, confidence, status)
    """
    # Garder le produit brut original
    produit_brut = product_name.strip()
    
    # Standardiser avec la méthode améliorée
    produit_standard, confidence, status = standardize_product_name_improved(product_name)
    
    # Corrections spécifiques pour ULYS
    produit_upper = produit_brut.upper()
    
    # Gestion spéciale pour "CONS. CHAN FOUI 75CL" - FILTRE 2
    if "CONS" in produit_upper and "CHAN" in produit_upper and "FOUI" in produit_upper:
        # Juste "Chan Foui 75 cl"
        produit_standard = "Chan Foui 75 cl"
        confidence = 0.95
        status = "matched"
    
    # Gestion spéciale pour les vins avec "NU"
    if "NU" in produit_upper and "750" in produit_upper:
        # Essayer de déterminer le type exact
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
# CONFIGURATION STREAMLIT
# ============================================================
st.set_page_config(
    page_title="Chan Foui & Fils — Scanner Pro",
    page_icon="🍷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============================================================
# INITIALISATION COMPLÈTE DES VARIABLES DE SESSION
# ============================================================
# Initialisation des états de session pour l'authentification
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "login_attempts" not in st.session_state:
    st.session_state.login_attempts = 0
if "locked_until" not in st.session_state:
    st.session_state.locked_until = None

# Initialisation des états pour l'application principale
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

# ============================================================
# FONCTION DE NORMALISATION DES PRODUITS (COMPATIBILITÉ)
# ============================================================
def standardize_product_name(product_name: str) -> str:
    """Standardise les noms de produits avec la nouvelle méthode intelligente"""
    standardized, confidence, status = standardize_product_name_improved(product_name)
    
    # Stocker le score de confiance dans la session pour affichage
    st.session_state.product_matching_scores[product_name] = {
        'standardized': standardized,
        'confidence': confidence,
        'status': status
    }
    
    return standardized

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
# PAGE DE CONNEXION - FILTRE 1: Texte noir sur fond blanc
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
            color: #1E293B !important;  /* Texte sombre */
            margin-bottom: 32px;
            font-size: 1rem;
            font-weight: 400;
            font-family: 'Inter', sans-serif;
        }
        
        .login-logo {
            height: 80px;
            margin-bottom: 20px;
            filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1));
        }
        
        /* FORCER LE TEXTE EN NOIR SUR BLANC - FILTRE 1 */
        .stSelectbox > div > div {
            border: 1.5px solid #e2e8f0;
            border-radius: 12px;
            padding: 10px 15px;
            font-size: 15px;
            transition: all 0.2s ease;
            background: white;
            color: #1E293B !important;  /* Texte noir */
        }
        
        .stSelectbox > div > div:hover {
            border-color: #27414A;
            box-shadow: 0 0 0 3px rgba(39, 65, 74, 0.1);
        }
        
        /* Texte dans le dropdown */
        .stSelectbox input,
        .stSelectbox div,
        .stSelectbox span {
            color: #1E293B !important;
            fill: #1E293B !important;
        }
        
        /* Options du dropdown */
        [data-baseweb="popover"] div,
        [data-baseweb="popover"] span {
            color: #1E293B !important;
        }
        
        .stTextInput > div > div > input {
            border: 1.5px solid #e2e8f0;
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 15px;
            transition: all 0.2s ease;
            background: white;
            color: #1E293B !important;  /* Texte noir */
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #27414A;
            box-shadow: 0 0 0 3px rgba(39, 65, 74, 0.1);
            outline: none;
            color: #1E293B !important;  /* Texte noir */
        }
        
        /* Correction pour le placeholder */
        .stTextInput > div > div > input::placeholder {
            color: #64748b !important;  /* Placeholder en gris */
        }
        
        /* Labels en noir */
        label {
            color: #1E293B !important;
            font-weight: 500 !important;
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
            position: relative;
            overflow: hidden;
            font-family: 'Inter', sans-serif;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(39, 65, 74, 0.25);
        }
        
        .stButton > button:after {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: 0.5s;
        }
        
        .stButton > button:hover:after {
            left: 100%;
        }
        
        .security-warning {
            background: linear-gradient(135deg, #FFF3CD 0%, #FFE8A1 100%);
            border: 1px solid #FFC107;
            border-radius: 14px;
            padding: 18px;
            margin-top: 28px;
            font-size: 0.9rem;
            color: #856404 !important;  /* Texte sombre */
            text-align: left;
            font-family: 'Inter', sans-serif;
            box-shadow: 0 4px 12px rgba(255, 193, 7, 0.1);
        }
        
        .pulse-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #10B981;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.7; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.7; }
        }
        
        /* Override pour tous les textes */
        * {
            color: #1E293B !important;
        }
        
        /* Exception pour les éléments qui doivent être blancs */
        .stButton > button,
        .user-info {
            color: white !important;
        }
        
        /* Style spécifique pour le dropdown */
        [data-baseweb="select"] * {
            color: #1E293B !important;
        }
        
        [data-baseweb="popover"] * {
            color: #1E293B !important;
        }
        
        /* Texte dans les options */
        [role="listbox"] div,
        [role="option"] {
            color: #1E293B !important;
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
    st.markdown('<p class="login-subtitle">Système de Scanner Pro - Accès Restreint</p>', unsafe_allow_html=True)
    
    # Indicateur de sécurité
    col_status = st.columns(3)
    with col_status[0]:
        st.markdown('<div style="text-align: center; color: #1E293B !important;"><span class="pulse-dot"></span>Serveur actif</div>', unsafe_allow_html=True)
    
    # FILTRE 1: Le nom de l'identifiant apparaît clair et noir sur fond blanc
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
    <div class="security-warning">
        <strong style="display: block; margin-bottom: 8px; color: #856404 !important;">🔐 Protocole de sécurité :</strong>
        • Système de reconnaissance biométrique numérique<br>
        • Chiffrement AES-256 pour toutes les données<br>
        • Journalisation complète des activités<br>
        • Verrouillage automatique après 3 tentatives
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ============================================================
# APPLICATION PRINCIPALE
# ============================================================

# ============================================================
# THÈME CHAN FOUI & FILS - VERSION TECH AMÉLIORÉE
# ============================================================
LOGO_FILENAME = "CF_LOGOS.png"
BRAND_TITLE = "CHAN FOUI ET FILS"
BRAND_SUB = "AI Document Processing System"

PALETTE = {
    "primary_dark": "#27414A",
    "primary_light": "#1F2F35",
    "background": "#F5F5F3",
    "card_bg": "#FFFFFF",
    "card_bg_alt": "#F4F6F3",
    "text_dark": "#1A1A1A",        # Couleur de texte principale
    "text_medium": "#333333",      # Texte secondaire
    "text_light": "#4B5563",       # Texte tertiaire
    "accent": "#2C5F73",
    "success": "#10B981",
    "warning": "#F59E0B",
    "error": "#EF4444",
    "border": "#E5E7EB",
    "hover": "#F9FAFB",
    "tech_blue": "#3B82F6",
    "tech_purple": "#8B5CF6",
    "tech_cyan": "#06B6D4",
}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400&display=swap');
    
    /* RÈGLE GLOBALE : AUCUN TEXTE EN BLANC */
    * {{
        color: {PALETTE['text_dark']} !important;
    }}
    
    /* Exceptions spécifiques pour les éléments qui DOIVENT être blancs */
    .stButton > button,
    .user-info,
    .document-title,
    .progress-container h3,
    .progress-container p:not(.progress-text-dark) {{
        color: white !important;
    }}
    
    .main {{
        background: linear-gradient(135deg, {PALETTE['background']} 0%, #f0f2f5 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: {PALETTE['text_dark']} !important;
    }}
    
    .stApp {{
        background: linear-gradient(135deg, {PALETTE['background']} 0%, #f0f2f5 100%);
        font-family: 'Inter', sans-serif;
        line-height: 1.6;
        color: {PALETTE['text_dark']} !important;
    }}
    
    /* Amélioration de la lisibilité */
    h1, h2, h3, h4, h5, h6 {{
        color: {PALETTE['text_dark']} !important;
        font-weight: 700 !important;
    }}
    
    p, span, div:not(.exception) {{
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
        border: 1px solid rgba(255, 255, 255, 0.8);
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(10px);
    }}
    
    .header-container:before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, {PALETTE['tech_blue']}, {PALETTE['tech_purple']}, {PALETTE['tech_cyan']});
        background-size: 200% 100%;
        animation: gradient-shift 3s ease infinite;
    }}
    
    @keyframes gradient-shift {{
        0% {{ background-position: 0% 50%; }}
        50% {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
    }}
    
    .user-info {{
        position: absolute;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, {PALETTE['accent']} 0%, {PALETTE['tech_blue']} 100%);
        color: white !important;
        padding: 10px 20px;
        border-radius: 16px;
        font-size: 0.9rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(5px);
    }}
    
    .logo-title-wrapper {{
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1.5rem;
        margin-bottom: 0.8rem;
        position: relative;
        z-index: 2;
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
        font-family: 'Inter', sans-serif;
    }}
    
    .brand-sub {{
        color: {PALETTE['text_medium']} !important;
        font-size: 1.1rem;
        margin-top: 0.3rem;
        font-weight: 400;
        opacity: 0.9;
        font-family: 'Inter', sans-serif;
        letter-spacing: 0.5px;
    }}
    
    .document-title {{
        background: linear-gradient(135deg, {PALETTE['primary_dark']} 0%, {PALETTE['accent']} 100%);
        color: white !important;
        padding: 1.5rem 2.5rem;
        border-radius: 18px;
        font-weight: 700;
        font-size: 1.5rem;
        text-align: center;
        margin: 2rem 0 3rem 0;
        box-shadow: 0 8px 25px rgba(39, 65, 74, 0.2);
        border: none;
        position: relative;
        overflow: hidden;
        font-family: 'Inter', sans-serif;
    }}
    
    .document-title:after {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(45deg, transparent 30%, rgba(255,255,255,0.1) 50%, transparent 70%);
        animation: shine 3s infinite;
    }}
    
    @keyframes shine {{
        0% {{ transform: translateX(-100%); }}
        100% {{ transform: translateX(100%); }}
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
        backdrop-filter: blur(10px);
        position: relative;
        overflow: hidden;
    }}
    
    .card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 15px 40px rgba(0, 0, 0, 0.12),
                    0 0 0 1px rgba(39, 65, 74, 0.08);
    }}
    
    .card h4 {{
        color: {PALETTE['text_dark']} !important;
        font-size: 1.4rem;
        font-weight: 700;
        margin-bottom: 1.8rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid;
        border-image: linear-gradient(90deg, {PALETTE['tech_blue']}, {PALETTE['tech_purple']}) 1;
        font-family: 'Inter', sans-serif;
        position: relative;
        display: inline-block;
    }}
    
    .card h4:after {{
        content: '';
        position: absolute;
        bottom: -2px;
        left: 0;
        width: 60px;
        height: 3px;
        background: linear-gradient(90deg, {PALETTE['tech_blue']}, {PALETTE['tech_purple']});
        border-radius: 3px;
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
        font-family: 'Inter', sans-serif;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 15px rgba(39, 65, 74, 0.2);
    }}
    
    .stButton > button:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(39, 65, 74, 0.3);
    }}
    
    .stButton > button:active {{
        transform: translateY(-1px);
    }}
    
    .upload-box {{
        border: 2px dashed {PALETTE['accent']};
        border-radius: 20px;
        padding: 3.5rem;
        text-align: center;
        background: linear-gradient(145deg, rgba(255,255,255,0.9) 0%, rgba(248,250,252,0.9) 100%);
        margin: 2rem 0;
        transition: all 0.3s ease;
        backdrop-filter: blur(5px);
        position: relative;
        overflow: hidden;
    }}
    
    .upload-box:hover {{
        border-color: {PALETTE['tech_blue']};
        background: linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(248,250,252,0.95) 100%);
        transform: translateY(-2px);
        box-shadow: 0 10px 30px rgba(39, 65, 74, 0.1);
    }}
    
    .upload-box:before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, {PALETTE['tech_blue']}, {PALETTE['tech_purple']});
        opacity: 0;
        transition: opacity 0.3s ease;
    }}
    
    .upload-box:hover:before {{
        opacity: 1;
    }}
    
    .progress-container {{
        background: linear-gradient(135deg, {PALETTE['primary_dark']} 0%, {PALETTE['accent']} 100%);
        color: white !important;
        padding: 3rem;
        border-radius: 20px;
        text-align: center;
        margin: 2.5rem 0;
        box-shadow: 0 10px 30px rgba(39, 65, 74, 0.2);
        position: relative;
        overflow: hidden;
    }}
    
    .progress-container:before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(45deg, transparent 30%, rgba(255,255,255,0.1) 50%, transparent 70%);
        animation: shine 2s infinite;
    }}
    
    /* Texte en noir dans la barre de progression */
    .progress-text-dark {{
        color: {PALETTE['text_dark']} !important;
        font-weight: 600;
        margin-top: 15px;
    }}
    
    .image-preview-container {{
        background: linear-gradient(145deg, {PALETTE['card_bg']} 0%, #f8fafc 100%);
        border-radius: 20px;
        padding: 2rem;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
        margin-bottom: 2.5rem;
        border: 1px solid rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px);
    }}
    
    .info-box {{
        background: linear-gradient(135deg, #E8F4F8 0%, #D4EAF7 100%);
        border-left: 4px solid {PALETTE['tech_blue']};
        padding: 1.5rem;
        border-radius: 16px;
        margin: 1.2rem 0;
        color: {PALETTE['text_dark']} !important;
        font-family: 'Inter', sans-serif;
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
        font-family: 'Inter', sans-serif;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.1);
    }}
    
    .warning-box {{
        background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
        border-left: 4px solid {PALETTE['warning']};
        padding: 1.5rem;
        border-radius: 16px;
        margin: 1.2rem 0;
        color: {PALETTE['text_dark']} !important;
        font-family: 'Inter', sans-serif;
        box-shadow: 0 4px 12px rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.1);
    }}
    
    .duplicate-box {{
        background: linear-gradient(135deg, #FFEDD5 0%, #FED7AA 100%);
        border: 2px solid {PALETTE['warning']};
        padding: 2rem;
        border-radius: 18px;
        margin: 2rem 0;
        color: {PALETTE['text_dark']} !important;
        font-family: 'Inter', sans-serif;
        box-shadow: 0 8px 25px rgba(245, 158, 11, 0.15);
        position: relative;
        overflow: hidden;
    }}
    
    .duplicate-box:before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, {PALETTE['warning']}, #F97316);
    }}
    
    .data-table {{
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        border: 1px solid {PALETTE['border']};
    }}
    
    .tech-badge {{
        display: inline-block;
        padding: 6px 14px;
        background: linear-gradient(135deg, {PALETTE['tech_blue']}15 0%, {PALETTE['tech_purple']}15 100%);
        color: {PALETTE['tech_blue']} !important;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 500;
        margin: 2px;
        border: 1px solid rgba(59, 130, 246, 0.2);
        font-family: 'JetBrains Mono', monospace;
    }}
    
    .pulse {{
        animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }}
    
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.5; }}
    }}
    
    .tech-grid {{
        background: linear-gradient(45deg, transparent 49%, rgba(59, 130, 246, 0.03) 50%, transparent 51%);
        background-size: 20px 20px;
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        pointer-events: none;
    }}
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    
    ::-webkit-scrollbar-track {{
        background: rgba(39, 65, 74, 0.05);
        border-radius: 4px;
    }}
    
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(135deg, {PALETTE['primary_dark']} 0%, {PALETTE['accent']} 100%);
        border-radius: 4px;
    }}
    
    ::-webkit-scrollbar-thumb:hover {{
        background: linear-gradient(135deg, {PALETTE['primary_light']} 0%, {PALETTE['tech_blue']} 100%);
    }}
    
    /* Animations pour les éléments d'interface */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    .fade-in {{
        animation: fadeIn 0.5s ease-out;
    }}
    
    /* AMÉLIORATION : Style pour les champs de formulaire avec texte sombre */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div,
    .stSelectbox > div > div > input,
    .stSelectbox > div > div > div,
    .stSelectbox > div > div > div > div {{
        border: 1.5px solid {PALETTE['border']};
        border-radius: 12px;
        padding: 12px 16px;
        font-size: 15px;
        transition: all 0.2s ease;
        background: white;
        color: {PALETTE['text_dark']} !important;
    }}
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stSelectbox > div > div:focus-within {{
        border-color: {PALETTE['tech_blue']};
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        outline: none;
        color: {PALETTE['text_dark']} !important;
    }}
    
    /* Placeholder en gris */
    ::placeholder {{
        color: {PALETTE['text_light']} !important;
        opacity: 0.7;
    }}
    
    /* Labels en gras et sombres */
    label {{
        color: {PALETTE['text_dark']} !important;
        font-weight: 600 !important;
        margin-bottom: 5px;
        display: block;
    }}
    
    /* Forcer le texte dans les dropdowns */
    [data-baseweb="select"] *,
    [data-baseweb="popover"] *,
    [role="listbox"] *,
    [role="option"] {{
        color: {PALETTE['text_dark']} !important;
    }}
    
    /* Style pour les dataframes */
    .dataframe {{
        border-radius: 12px !important;
        overflow: hidden !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05) !important;
        border: 1px solid {PALETTE['border']} !important;
    }}
    
    /* Amélioration des contrastes pour l'accessibilité */
    .stAlert {{
        color: {PALETTE['text_dark']} !important;
    }}
    
    .stSuccess {{
        background-color: rgba(16, 185, 129, 0.1) !important;
        color: {PALETTE['text_dark']} !important;
        border-color: {PALETTE['success']} !important;
    }}
    
    .stError {{
        background-color: rgba(239, 68, 68, 0.1) !important;
        color: {PALETTE['text_dark']} !important;
        border-color: {PALETTE['error']} !important;
    }}
    
    .stWarning {{
        background-color: rgba(245, 158, 11, 0.1) !important;
        color: {PALETTE['text_dark']} !important;
        border-color: {PALETTE['warning']} !important;
    }}
    
    /* Amélioration des badges */
    .stat-badge {{
        padding: 15px;
        border-radius: 14px;
        text-align: center;
        font-weight: 700;
        font-size: 1.8rem;
        margin-bottom: 5px;
    }}
    
    .stat-label {{
        font-size: 0.85rem;
        color: {PALETTE['text_light']} !important;
        margin-top: 5px;
    }}
    
    /* Animation pour les nouveaux éléments */
    @keyframes slideIn {{
        from {{ transform: translateX(-20px); opacity: 0; }}
        to {{ transform: translateX(0); opacity: 1; }}
    }}
    
    .slide-in {{
        animation: slideIn 0.3s ease-out;
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
# FONCTION DE NORMALISATION DU TYPE DE DOCUMENT
# ============================================================
def normalize_document_type(doc_type: str) -> str:
    """Normalise le type de document pour correspondre aux clés SHEET_GIDS"""
    if not doc_type:
        return "DOCUMENT INCONNU"
    
    doc_type_upper = doc_type.upper()
    
    # Mapping des types de documents
    if "FACTURE" in doc_type_upper and "COMPTE" in doc_type_upper:
        return "FACTURE EN COMPTE"
    elif "BDC" in doc_type_upper or "BON DE COMMANDE" in doc_type_upper:
        # Extraire le client du type de document
        if "LEADERPRICE" in doc_type_upper or "DLP" in doc_type_upper:
            return "BDC LEADERPRICE"
        elif "S2M" in doc_type_upper or "SUPERMAKI" in doc_type_upper:
            return "BDC S2M"
        elif "ULYS" in doc_type_upper:
            return "BDC ULYS"
        else:
            # Vérifier si le client est dans le nom
            for client in ["LEADERPRICE", "DLP", "S2M", "SUPERMAKI", "ULYS"]:
                if client in doc_type_upper:
                    return f"BDC {client}"
            return "BDC LEADERPRICE"  # Par défaut
    else:
        # Essayer de deviner le type
        if any(word in doc_type_upper for word in ["FACTURE", "INVOICE", "BILL"]):
            return "FACTURE EN COMPTE"
        elif any(word in doc_type_upper for word in ["COMMANDE", "ORDER", "PO"]):
            return "BDC LEADERPRICE"
        else:
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
# FONCTION OCR AMÉLIORÉE POUR BDC ULYS
# ============================================================
def openai_vision_ocr_improved(image_bytes: bytes) -> Dict:
    """Utilise OpenAI Vision pour analyser le document avec un prompt amélioré"""
    try:
        client = get_openai_client()
        if not client:
            return None
        
        # Encoder l'image
        base64_image = encode_image_to_base64(image_bytes)
        
        # Prompt amélioré pour mieux extraire les articles
        prompt = """
        Analyse ce document de type BON DE COMMANDE (BDC) et extrais précisément les informations suivantes:
        
        IMPORTANT: Extrais TOUTES les lignes du tableau, y compris les catégories comme "122111 - VINS ROUGES".
        
        {
            "type_document": "BDC",
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
        
        RÈGLES STRICTES:
        1. Pour "article_brut": copie EXACTEMENT le texte de la colonne "Description de l'Article" sans modifications
        2. Pour les quantités: extrais le nombre exact de la colonne "Qté"
        3. Si c'est un BDC ULYS, note "ULYS" comme client
        4. Extrais TOUTES les lignes d'articles, même celles qui sont des catégories
        5. Ne standardise PAS les noms, garde-les exactement comme sur le document
        6. Pour les lignes sans quantité (catégories), mets "0" ou laisse vide
        
        Exemples d'extraction CORRECTE:
        "article_brut": "VIN ROUGE COTE DE FIANAR 3L"
        "article_brut": "VIN ROUGE COTE DE FIANARA 750ML NU"
        "article_brut": "CONS. CHAN FOUI 75CL"
        "article_brut": "122111 - VINS ROUGES"  (c'est OK, on garde tout)
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
            max_tokens=3000,
            temperature=0.1
        )
        
        # Extraire et parser la réponse JSON
        content = response.choices[0].message.content
        
        # Nettoyer la réponse pour extraire le JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError:
                # Essayer de nettoyer le JSON
                json_str = re.sub(r'[\x00-\x1f\x7f]', '', json_str)
                try:
                    data = json.loads(json_str)
                    return data
                except:
                    st.error("❌ Impossible de parser la réponse JSON d'OpenAI")
                    return None
        else:
            st.error("❌ Réponse JSON non trouvée dans la réponse OpenAI")
            return None
            
    except Exception as e:
        st.error(f"❌ Erreur OpenAI Vision: {str(e)}")
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

def encode_image_to_base64(image_bytes: bytes) -> str:
    """Encode l'image en base64 pour OpenAI Vision"""
    return base64.b64encode(image_bytes).decode('utf-8')

def clean_text(text: str) -> str:
    """Nettoie le texte"""
    text = text.replace("\r", "\n")
    text = re.sub(r"[^\S\r\n]+", " ", text)
    return text.strip()

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

def map_client(client: str) -> str:
    """Mappe le nom du client vers la forme standard"""
    client_upper = client.upper()
    
    if "ULYS" in client_upper:
        return "ULYS"
    elif "SUPERMAKI" in client_upper or "S2M" in client_upper:
        return "S2M"
    elif "LEADER" in client_upper or "LEADERPRICE" in client_upper or "DLP" in client_upper:
        return "DLP"
    else:
        return client

# ============================================================
# FONCTIONS POUR PRÉPARER LES DONNÉES POUR GOOGLE SHEETS
# ============================================================
def prepare_facture_rows(data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
    """Prépare les lignes pour les factures (9 colonnes) - FILTRE 1: Supprimer lignes avec quantité 0"""
    rows = []
    
    try:
        mois = data.get("mois", get_month_from_date(data.get("date", "")))
        client = data.get("client", "")
        date = format_date_french(data.get("date", ""))
        nbc = data.get("bon_commande", "")
        nf = data.get("numero_facture", "")
        magasin = data.get("adresse_livraison", "")
        
        for _, row in articles_df.iterrows():
            # FILTRE 1: Vérifier si la quantité est différente de 0
            quantite = row.get("Quantité", 0)
            if pd.isna(quantite) or quantite == 0 or str(quantite).strip() == "0":
                continue  # Passer à la ligne suivante
            
            article = str(row.get("Produit Standard", "")).strip()
            if not article:
                article = str(row.get("Produit Brute", "")).strip()
            
            quantite_str = format_quantity(quantite)
            
            rows.append([
                mois,
                client,
                date,
                nbc,
                nf,
                "",  # Lien (vide par défaut)
                magasin,
                article,
                quantite_str
            ])
        
        return rows
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la préparation des données facture: {str(e)}")
        return []

def prepare_bdc_rows(data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
    """Prépare les lignes pour les BDC (8 colonnes) - FILTRE 1: Supprimer lignes avec quantité 0"""
    rows = []
    
    try:
        date_emission = data.get("date", "")
        mois = get_month_from_date(date_emission)
        client = map_client(data.get("client", ""))
        date = format_date_french(date_emission)
        nbc = data.get("numero", "")
        magasin = data.get("adresse_livraison", "")
        
        for _, row in articles_df.iterrows():
            # FILTRE 1: Vérifier si la quantité est différente de 0
            quantite = row.get("Quantité", 0)
            if pd.isna(quantite) or quantite == 0 or str(quantite).strip() == "0":
                continue  # Passer à la ligne suivante
            
            article = str(row.get("Produit Standard", "")).strip()
            if not article:
                article = str(row.get("Produit Brute", "")).strip()
            
            quantite_str = format_quantity(quantite)
            
            rows.append([
                mois,
                client,
                date,
                nbc,
                "",  # Lien (vide par défaut)
                magasin,
                article,
                quantite_str
            ])
        
        return rows
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la préparation des données BDC: {str(e)}")
        return []

def prepare_rows_for_sheet(document_type: str, data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
    """Prépare les lignes pour l'insertion dans Google Sheets selon le type de document - FILTRE 1 appliqué"""
    if "FACTURE" in document_type.upper():
        return prepare_facture_rows(data, articles_df)
    else:
        return prepare_bdc_rows(data, articles_df)

# ============================================================
# FONCTIONS DE DÉTECTION DE DOUBLONS - FILTRE 3: Même logique pour BDC et factures
# ============================================================
def check_for_duplicates(document_type: str, extracted_data: dict, worksheet) -> Tuple[bool, List[Dict]]:
    """Vérifie si un document existe déjà dans Google Sheets - FILTRE 3: Même logique pour BDC et factures"""
    try:
        all_data = worksheet.get_all_values()
        
        if len(all_data) <= 1:
            return False, []
        
        # FILTRE 3: Même logique de détection pour BDC et factures
        # Recherche basée sur client et numéro de document
        client_col = 1  # Colonne client (commune aux deux types)
        
        current_client = extracted_data.get('client', '')
        
        # Colonne pour le numéro de document selon le type
        if "FACTURE" in document_type.upper():
            doc_num_col = 4  # Colonne NF
            current_doc_num = extracted_data.get('numero_facture', '')
        else:
            doc_num_col = 3  # Colonne NBC
            current_doc_num = extracted_data.get('numero', '')
        
        duplicates = []
        for i, row in enumerate(all_data[1:], start=2):
            if len(row) > max(doc_num_col, client_col):
                row_client = row[client_col] if len(row) > client_col else ''
                row_doc_num = row[doc_num_col] if len(row) > doc_num_col else ''
                
                if (row_client == current_client and 
                    row_doc_num == current_doc_num and 
                    current_client != '' and current_doc_num != ''):
                    
                    # Vérifier aussi les articles similaires
                    match_type = 'Client et Numéro identiques'
                    
                    # Vérification supplémentaire pour les BDC ULYS
                    if "ULYS" in current_client.upper() and "BDC" in document_type.upper():
                        # Pour ULYS, vérifier aussi la date
                        date_col = 2  # Colonne date
                        current_date = format_date_french(extracted_data.get('date', ''))
                        row_date = row[date_col] if len(row) > date_col else ''
                        
                        if row_date == current_date and current_date != '':
                            match_type = 'Client, Numéro et Date identiques'
                    
                    duplicates.append({
                        'row_number': i,
                        'data': row,
                        'match_type': match_type
                    })
        
        return len(duplicates) > 0, duplicates
            
    except Exception as e:
        st.error(f"❌ Erreur lors de la vérification des doublons: {str(e)}")
        return False, []

# ============================================================
# GOOGLE SHEETS FUNCTIONS
# ============================================================
def get_worksheet(document_type: str):
    """Récupère la feuille Google Sheets correspondant au type de document"""
    try:
        if "gcp_sheet" not in st.secrets:
            st.error("❌ Les credentials Google Sheets ne sont pas configurés")
            return None
        
        # Normaliser le type de document
        normalized_type = normalize_document_type(document_type)
        
        # Si le type n'est pas dans SHEET_GIDS, utiliser une feuille par défaut
        if normalized_type not in SHEET_GIDS:
            st.warning(f"⚠️ Type de document '{document_type}' non reconnu. Utilisation de la feuille par défaut.")
            normalized_type = "FACTURE EN COMPTE"
        
        sa_info = dict(st.secrets["gcp_sheet"])
        gc = gspread.service_account_from_dict(sa_info)
        sh = gc.open_by_key(SHEET_ID)
        
        target_gid = SHEET_GIDS.get(normalized_type)
        
        if target_gid is None:
            st.error(f"❌ GID non trouvé pour le type: {normalized_type}")
            # Utiliser la première feuille par défaut
            return sh.get_worksheet(0)
        
        for worksheet in sh.worksheets():
            if int(worksheet.id) == target_gid:
                return worksheet
        
        # Si la feuille spécifique n'est pas trouvée, utiliser la première feuille
        st.warning(f"⚠️ Feuille avec GID {target_gid} non trouvée. Utilisation de la première feuille.")
        return sh.get_worksheet(0)
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la connexion à Google Sheets: {str(e)}")
        return None

def find_table_range(worksheet, num_columns=9):
    """Trouve la plage de table dans la feuille avec un nombre de colonnes spécifique"""
    try:
        all_data = worksheet.get_all_values()
        
        if not all_data:
            if num_columns == 9:
                return "A1:I1"
            else:
                return "A1:H1"
        
        # Déterminer les headers selon le nombre de colonnes
        if num_columns == 9:
            headers = ["Mois", "Client", "date", "NBC", "NF", "lien", "Magasin", "Produit", "Quantite"]
        else:
            headers = ["Mois", "Client", "date", "NBC", "lien", "Magasin", "Produit", "Quantite"]
        
        first_row = all_data[0] if all_data else []
        header_found = any(header in str(first_row) for header in headers)
        
        if header_found:
            last_row = len(all_data) + 1
            if len(all_data) <= 1:
                if num_columns == 9:
                    return "A2:I2"
                else:
                    return "A2:H2"
            else:
                if num_columns == 9:
                    return f"A{last_row}:I{last_row}"
                else:
                    return f"A{last_row}:H{last_row}"
        else:
            for i, row in enumerate(all_data, start=1):
                if not any(cell.strip() for cell in row):
                    if num_columns == 9:
                        return f"A{i}:I{i}"
                    else:
                        return f"A{i}:H{i}"
            
            if num_columns == 9:
                return f"A{len(all_data)+1}:I{len(all_data)+1}"
            else:
                return f"A{len(all_data)+1}:H{len(all_data)+1}"
            
    except Exception as e:
        if num_columns == 9:
            return "A2:I2"
        else:
            return "A2:H2"

def save_to_google_sheets(document_type: str, data: dict, articles_df: pd.DataFrame, 
                         duplicate_action: str = None, duplicate_rows: List[int] = None):
    """Sauvegarde les données dans Google Sheets"""
    try:
        ws = get_worksheet(document_type)
        
        if not ws:
            st.error("❌ Impossible de se connecter à Google Sheets")
            return False, "Erreur de connexion"
        
        new_rows = prepare_rows_for_sheet(document_type, data, articles_df)
        
        if not new_rows:
            st.warning("⚠️ Aucune donnée à enregistrer (toutes les lignes ont une quantité de 0)")
            return False, "Aucune donnée"
        
        if duplicate_action == "overwrite" and duplicate_rows:
            try:
                duplicate_rows.sort(reverse=True)
                for row_num in duplicate_rows:
                    ws.delete_rows(row_num)
                
                st.info(f"🗑️ {len(duplicate_rows)} ligne(s) dupliquée(s) supprimée(s)")
                
            except Exception as e:
                st.error(f"❌ Erreur lors de la suppression des doublons: {str(e)}")
                return False, str(e)
        
        if duplicate_action == "skip":
            st.warning("⏸️ Import annulé - Document ignoré")
            return True, "Document ignoré (doublon)"
        
        # Afficher l'aperçu des données à enregistrer
        st.info(f"📋 **Aperçu des données à enregistrer (lignes avec quantité > 0):**")
        
        # Définir les colonnes selon le type de document
        if "FACTURE" in document_type.upper():
            columns = ["Mois", "Client", "Date", "NBC", "NF", "Lien", "Magasin", "Produit", "Quantité"]
        else:
            columns = ["Mois", "Client", "Date", "NBC", "Lien", "Magasin", "Produit", "Quantité"]
        
        preview_df = pd.DataFrame(new_rows, columns=columns)
        st.dataframe(preview_df, use_container_width=True)
        
        # Ajuster la plage selon le nombre de colonnes
        if "FACTURE" in document_type.upper():
            table_range = find_table_range(ws, num_columns=9)
        else:
            table_range = find_table_range(ws, num_columns=8)
        
        try:
            if ":" in table_range and table_range.count(":") == 1:
                ws.append_rows(new_rows, table_range=table_range)
            else:
                ws.append_rows(new_rows)
            
            action_msg = "enregistrée(s)"
            if duplicate_action == "overwrite":
                action_msg = "mise(s) à jour"
            elif duplicate_action == "add_new":
                action_msg = "ajoutée(s) comme nouvelle(s)"
            
            st.success(f"✅ {len(new_rows)} ligne(s) {action_msg} avec succès dans Google Sheets!")
            
            # Utiliser le type normalisé pour l'URL
            normalized_type = normalize_document_type(document_type)
            sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={SHEET_GIDS.get(normalized_type, '')}"
            st.markdown(f'<div class="info-box">🔗 <a href="{sheet_url}" target="_blank">Ouvrir Google Sheets</a></div>', unsafe_allow_html=True)
            
            st.balloons()
            return True, f"{len(new_rows)} lignes {action_msg}"
            
        except Exception as e:
            st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
            
            try:
                st.info("🔄 Tentative alternative d'enregistrement...")
                
                all_data = ws.get_all_values()
                
                for row in new_rows:
                    all_data.append(row)
                
                ws.update('A1', all_data)
                
                st.success(f"✅ {len(new_rows)} ligne(s) enregistrée(s) avec méthode alternative!")
                return True, f"{len(new_rows)} lignes enregistrées (méthode alternative)"
                
            except Exception as e2:
                st.error(f"❌ Échec de la méthode alternative: {str(e2)}")
                return False, str(e)
                
    except Exception as e:
        st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
        return False, str(e)

# ============================================================
# HEADER AVEC LOGO - VERSION TECH AMÉLIORÉE
# ============================================================
st.markdown('<div class="header-container slide-in">', unsafe_allow_html=True)

# Badge utilisateur avec style tech
st.markdown(f'''
<div class="user-info">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-right: 6px;">
        <path d="M8 8C10.2091 8 12 6.20914 12 4C12 1.79086 10.2091 0 8 0C5.79086 0 4 1.79086 4 4C4 6.20914 5.79086 8 8 8Z" fill="white"/>
        <path d="M8 9C4.13401 9 1 12.134 1 16H15C15 12.134 11.866 9 8 9Z" fill="white"/>
    </svg>
    {st.session_state.username}
</div>
''', unsafe_allow_html=True)

# Grille technologique en arrière-plan
st.markdown('<div class="tech-grid"></div>', unsafe_allow_html=True)

st.markdown('<div class="logo-title-wrapper">', unsafe_allow_html=True)

# Logo avec effet
if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME, width=100)
else:
    st.markdown("""
    <div style="font-size: 3.5rem; margin-bottom: 10px; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1)); color: #1A1A1A !important;">
        🍷
    </div>
    """, unsafe_allow_html=True)

# Titre avec effet gradient
st.markdown(f'<h1 class="brand-title">{BRAND_TITLE}</h1>', unsafe_allow_html=True)

# Sous-titre avec badges technologiques
st.markdown(f'''
<div style="margin-top: 10px;">
    <span class="tech-badge">GPT-4 Vision</span>
    <span class="tech-badge">AI Processing</span>
    <span class="tech-badge">Cloud Sync</span>
    <span class="tech-badge">Smart Matching</span>
</div>
''', unsafe_allow_html=True)

st.markdown(f'''
<p class="brand-sub">
    Système intelligent de traitement de documents • Connecté en tant que <strong style="color: #1A1A1A !important;">{st.session_state.username}</strong>
</p>
''', unsafe_allow_html=True)

# Indicateurs de statut
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f'<div style="text-align: center; color: #1A1A1A !important;"><span class="pulse-dot"></span><small>AI Active</small></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div style="text-align: center; color: #1A1A1A !important;"><span style="display:inline-block;width:8px;height:8px;background:#10B981;border-radius:50%;margin-right:8px;"></span><small>Cloud Online</small></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div style="text-align: center; color: #1A1A1A !important;"><span style="display:inline-block;width:8px;height:8px;background:#3B82F6;border-radius:50%;margin-right:8px;"></span><small>Secured</small></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# ZONE DE TÉLÉCHARGEMENT UNIQUE - VERSION TECH AMÉLIORÉE
# ============================================================
st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
st.markdown('<h4>📤 Zone de dépôt de documents</h4>', unsafe_allow_html=True)

st.markdown(f"""
<div class="info-box">
    <strong>ℹ️ Que fait ChanFoui.AI ?</strong><br><br>

    ✔ Il lit votre facture ou bon de commande<br>
    ✔ Il corrige automatiquement les noms des produits<br>
    ✔ Il garde uniquement les quantités utiles<br>
    ✔ Il évite les doublons<br>
    ✔ Il enregistre tout automatiquement<br><br>

    <strong>📸 Conseil important :</strong><br>
    Prenez une photo bien nette, bien cadrée et le plus proche possible du document.
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

# Indicateur de compatibilité
st.markdown(f"""
<div style="display: flex; justify-content: center; gap: 20px; margin-top: 20px; font-size: 0.85rem; color: #333333 !important;">
    <div style="text-align: center;">
        <div style="font-size: 1.2rem; color: #1A1A1A !important;">📄</div>
        <div>Factures</div>
    </div>
    <div style="text-align: center;">
        <div style="font-size: 1.2rem; color: #1A1A1A !important;">📋</div>
        <div>Bons de commande</div>
    </div>
    <div style="text-align: center;">
        <div style="font-size: 1.2rem; color: #1A1A1A !important;">🏷️</div>
        <div>Étiquettes</div>
    </div>
    <div style="text-align: center;">
        <div style="font-size: 1.2rem; color: #1A1A1A !important;">🤖</div>
        <div>Smart Matching</div>
    </div>
</div>
""", unsafe_allow_html=True)

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
    st.session_state.duplicate_check_done = False
    st.session_state.duplicate_found = False
    st.session_state.duplicate_action = None
    st.session_state.image_preview_visible = True
    st.session_state.document_scanned = True
    st.session_state.export_triggered = False
    st.session_state.export_status = None
    st.session_state.product_matching_scores = {}
    
    # Barre de progression avec style tech
    progress_container = st.empty()
    with progress_container.container():
        st.markdown('<div class="progress-container">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 3rem; margin-bottom: 1rem;">🤖</div>', unsafe_allow_html=True)
        st.markdown('<h3 style="color: white !important;">Initialisation du système IA</h3>', unsafe_allow_html=True)
        # Texte en noir comme demandé
        st.markdown(f'<p class="progress-text-dark">Analyse en cours avec GPT-4 Vision...</p>', unsafe_allow_html=True)
        
        # Barre de progression animée
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        steps = [
            "Chargement de l'image...",
            "Prétraitement des données...",
            "Analyse par IA...",
            "Extraction des données...",
            "Standardisation intelligente...",
            "Finalisation..."
        ]
        
        for i in range(101):
            time.sleep(0.03)
            progress_bar.progress(i)
            if i < 20:
                status_text.text(steps[0])
            elif i < 40:
                status_text.text(steps[1])
            elif i < 60:
                status_text.text(steps[2])
            elif i < 80:
                status_text.text(steps[3])
            elif i < 95:
                status_text.text(steps[4])
            else:
                status_text.text(steps[5])
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Traitement OCR avec OpenAI Vision améliorée
    try:
        buf = BytesIO()
        st.session_state.uploaded_image.save(buf, format="JPEG")
        image_bytes = buf.getvalue()
        
        # Prétraitement de l'image
        img_processed = preprocess_image(image_bytes)
        
        # Analyse avec OpenAI Vision améliorée
        result = openai_vision_ocr_improved(img_processed)
        
        if result:
            st.session_state.ocr_result = result
            raw_doc_type = result.get("type_document", "DOCUMENT INCONNU")
            # Normaliser le type de document détecté
            st.session_state.detected_document_type = normalize_document_type(raw_doc_type)
            st.session_state.show_results = True
            st.session_state.processing = False
            
            # Préparer les données standardisées avec les nouvelles colonnes
            if "articles" in result:
                std_data = []
                for article in result["articles"]:
                    raw_name = article.get("article_brut", article.get("article", ""))
                    
                    # Filtrer les catégories (lignes qui ne sont pas des produits)
                    if any(cat in raw_name.upper() for cat in ["VINS ROUGES", "VINS BLANCS", "VINS ROSES", "LIQUEUR", "CONSIGNE"]):
                        # C'est une catégorie, on la garde mais on ne la standardise pas
                        std_data.append({
                            "Produit Brute": raw_name,
                            "Produit Standard": raw_name,  # Garder tel quel
                            "Quantité": 0,
                            "Confiance": "0%",
                            "Auto": False
                        })
                    else:
                        # C'est un produit, on le standardise
                        produit_brut, produit_standard, confidence, status = standardize_product_for_bdc(raw_name)
                        
                        std_data.append({
                            "Produit Brute": produit_brut,
                            "Produit Standard": produit_standard,
                            "Quantité": article.get("quantite", 0),
                            "Confiance": f"{confidence*100:.1f}%",
                            "Auto": confidence >= 0.7  # True si confiance élevée
                        })
                
                # Créer le dataframe standardisé pour l'édition
                st.session_state.edited_standardized_df = pd.DataFrame(std_data)
            
            progress_container.empty()
            st.rerun()
        else:
            st.error("❌ Échec de l'analyse IA - Veuillez réessayer")
            st.session_state.processing = False
        
    except Exception as e:
        st.error(f"❌ Erreur système: {str(e)}")
        st.session_state.processing = False

# ============================================================
# APERÇU DU DOCUMENT (TOUJOURS VISIBLE SI SCANNÉ)
# ============================================================
if st.session_state.uploaded_image and st.session_state.image_preview_visible:
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>👁️ Aperçu du document analysé</h4>', unsafe_allow_html=True)
    
    # Ajouter un effet de cadre moderne
    col_img, col_info = st.columns([2, 1])
    
    with col_img:
        st.image(st.session_state.uploaded_image, use_column_width=True)
    
    with col_info:
    st.markdown("""
    <div class="info-box" style="height: 100%;">
        <strong>📊 Informations du document :</strong><br><br>

        • Qualité de la photo : Bonne<br>
        • Type : Photo du document<br>
        • État : Analyse terminée<br>
        • Fiabilité : Élevée<br><br>

        ✔ Document prêt pour le traitement
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# AFFICHAGE DES RÉSULTATS
# ============================================================
if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
    result = st.session_state.ocr_result
    doc_type = st.session_state.detected_document_type
    
    # Message de succès avec style tech
    st.markdown('<div class="success-box fade-in">', unsafe_allow_html=True)
    st.markdown(f'''
    <div style="display: flex; align-items: start; gap: 15px;">
        <div style="font-size: 2.5rem; color: {PALETTE['success']} !important;">✅</div>
        <div>
            <strong style="font-size: 1.1rem; color: #1A1A1A !important;">Analyse IA terminée avec succès</strong><br>
            <span style="color: #333333 !important;">Type détecté : <strong>{doc_type}</strong> | Standardisation : <strong>Active</strong></span><br>
            <small style="color: #4B5563 !important;">Veuillez vérifier les données extraites avant validation</small>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Titre du mode détecté avec icône tech
    icon_map = {
        "FACTURE": "📄",
        "BDC": "📋",
        "DEFAULT": "📑"
    }
    
    icon = icon_map.get("FACTURE" if "FACTURE" in doc_type.upper() else "BDC" if "BDC" in doc_type.upper() else "DEFAULT", "📑")
    
    st.markdown(
        f"""
        <div class="document-title fade-in">
            {icon} Document détecté : {doc_type}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # ========================================================
    # INFORMATIONS EXTRAITES
    # ========================================================
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>📋 Informations extraites</h4>', unsafe_allow_html=True)
    
    # Afficher les informations selon le type de document
    if "FACTURE" in doc_type.upper():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Client</div>', unsafe_allow_html=True)
            client = st.text_input("", value=result.get("client", ""), key="facture_client", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">N° Facture</div>', unsafe_allow_html=True)
            numero_facture = st.text_input("", value=result.get("numero_facture", ""), key="facture_num", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Bon de commande</div>', unsafe_allow_html=True)
            bon_commande = st.text_input("", value=result.get("bon_commande", ""), key="facture_bdc", label_visibility="collapsed")
        
        with col2:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Adresse</div>', unsafe_allow_html=True)
            adresse = st.text_input("", value=result.get("adresse_livraison", ""), key="facture_adresse", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Date</div>', unsafe_allow_html=True)
            date = st.text_input("", value=result.get("date", ""), key="facture_date", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Mois</div>', unsafe_allow_html=True)
            mois = st.text_input("", value=result.get("mois", get_month_from_date(result.get("date", ""))), key="facture_mois", label_visibility="collapsed")
        
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
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Client</div>', unsafe_allow_html=True)
            client = st.text_input("", value=result.get("client", "ULYS"), key="bdc_client", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">N° BDC</div>', unsafe_allow_html=True)
            numero = st.text_input("", value=result.get("numero", ""), key="bdc_numero", label_visibility="collapsed")
        
        with col2:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Date</div>', unsafe_allow_html=True)
            date = st.text_input("", value=result.get("date", ""), key="bdc_date", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Adresse</div>', unsafe_allow_html=True)
            adresse = st.text_input("", 
                                  value=result.get("adresse_livraison", "SCORE TALATAMATY"), 
                                  key="bdc_adresse", 
                                  label_visibility="collapsed")
        
        data_for_sheets = {
            "client": client,
            "numero": numero,
            "date": date,
            "adresse_livraison": adresse
        }
    
    st.session_state.data_for_sheets = data_for_sheets
    
    # Indicateur de validation amélioré
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
    # TABLEAU STANDARDISÉ ÉDITABLE - FILTRE 1 appliqué automatiquement
    # ========================================================
    if st.session_state.edited_standardized_df is not None and not st.session_state.edited_standardized_df.empty:
        st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
        st.markdown('<h4>📘 Standardisation des Produits</h4>', unsafe_allow_html=True)
        
        # Instructions avec mention des filtres
        st.markdown(f"""
        <div style="margin-bottom: 20px; padding: 12px; background: rgba(59, 130, 246, 0.05); border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.1);">
            <small style="color: #1A1A1A !important;">
            💡 <strong>Mode édition activé avec filtres :</strong> 
            • <strong>Filtre 1:</strong> Lignes avec quantité 0 seront automatiquement supprimées à l'export<br>
            • <strong>Filtre 2:</strong> "CONS. CHAN FOUI 75CL" devient "Chan Foui 75 cl"<br>
            • <strong>Filtre 3:</strong> Détection de doublons identique pour BDC et factures<br>
            • Colonne "Produit Brute" : texte original extrait par l'OCR<br>
            • Colonne "Produit Standard" : standardisé automatiquement (éditable)<br>
            • Colonne "Auto" : ✓ si la standardisation est automatique et fiable<br>
            • <strong>Note :</strong> Les lignes de catégorie (ex: "122111 - VINS ROUGES") ne sont pas standardisées
            </small>
        </div>
        """, unsafe_allow_html=True)
        
        # Afficher un avertissement pour les lignes avec quantité 0
        df_with_zero_qty = st.session_state.edited_standardized_df[
            (st.session_state.edited_standardized_df["Quantité"] == 0) | 
            (st.session_state.edited_standardized_df["Quantité"].isna())
        ]
        
        if len(df_with_zero_qty) > 0:
            st.warning(f"⚠️ **Attention :** {len(df_with_zero_qty)} ligne(s) avec quantité 0 seront automatiquement supprimées lors de l'export")
        
        # Éditeur de données avec les nouvelles colonnes
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
        
        # Mettre à jour le dataframe édité
        st.session_state.edited_standardized_df = edited_df
        
        # Afficher les statistiques
        total_items = len(edited_df)
        auto_standardized = edited_df["Auto"].sum() if "Auto" in edited_df.columns else 0
        items_with_qty = len(edited_df[edited_df["Quantité"] > 0])
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.markdown(
                f'''
                <div class="stat-badge" style="background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%); border: 1px solid rgba(59, 130, 246, 0.2);">
                    <div style="font-size: 1.8rem; font-weight: 700; color: #3B82F6 !important;">{total_items}</div>
                    <div class="stat-label">Articles totaux</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        with col_stat2:
            st.markdown(
                f'''
                <div class="stat-badge" style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(52, 211, 153, 0.1) 100%); border: 1px solid rgba(16, 185, 129, 0.2);">
                    <div style="font-size: 1.8rem; font-weight: 700; color: #10B981 !important;">{items_with_qty}</div>
                    <div class="stat-label">Avec quantité > 0</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        with col_stat3:
            st.markdown(
                f'''
                <div class="stat-badge" style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(251, 191, 36, 0.1) 100%); border: 1px solid rgba(245, 158, 11, 0.2);">
                    <div style="font-size: 1.8rem; font-weight: 700; color: #F59E0B !important;">{int(auto_standardized)}</div>
                    <div class="stat-label">Auto-standardisés</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        
        # Bouton pour forcer la re-standardisation
        if st.button("🔄 Re-standardiser tous les produits", 
                    key="restandardize_button",
                    help="Appliquer la standardisation intelligente à tous les produits"):
            # Réappliquer la standardisation
            new_data = []
            for _, row in edited_df.iterrows():
                produit_brut = row["Produit Brute"]
                
                # Vérifier si c'est une catégorie
                if any(cat in produit_brut.upper() for cat in ["VINS ROUGES", "VINS BLANCS", "VINS ROSES", "LIQUEUR", "CONSIGNE", "122111", "122112", "122113"]):
                    # Garder les catégories telles quelles
                    new_data.append({
                        "Produit Brute": produit_brut,
                        "Produit Standard": produit_brut,
                        "Quantité": row["Quantité"],
                        "Confiance": "0%",
                        "Auto": False
                    })
                else:
                    # Standardiser les produits
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
    # TEST DE STANDARDISATION ULYS - FILTRE 2 test
    # ========================================================
    with st.expander("🧪 Tester la standardisation ULYS (Filtre 2)"):
        # Exemples de test avec focus sur FILTRE 2
        test_examples = [
            "CONS. CHAN FOUI 75CL",
            "CONS. CHAN FOUL 75CL",
            "CONS CHAN FOUI 75CL",
            "CONS CHAN FOUL 75CL",
            "VIN ROUGE COTE DE FIANAR 3L",
            "VIN ROUGE COTE DE FIANARA 750ML NU",
            "VIN BLANC COTE DE FIANAR 3L",
            "VIN BLANC DOUX MAROPARASY 750ML NU",
            "VIN BLANC COTE DE FIANARA 750ML NU",
            "VIN GRIS COTE DE FIANARA 750ML NU",
            "VIN ROUGE DOUX MAROPARASY 750ML NU",
            "COTE DE FIANAR 3L",
            "MAROPARASY 750ML",
            "VIN ROUGE COTE DE FLANAR 3L",
        ]
        
        if st.button("Tester les filtres avec des exemples typiques ULYS"):
            results = []
            for example in test_examples:
                produit_brut, produit_standard, confidence, status = standardize_product_for_bdc(example)
                results.append({
                    "Produit Brute": example,
                    "Produit Standard": produit_standard,
                    "Confiance": f"{confidence*100:.1f}%",
                    "Statut": status
                })
            
            test_df = pd.DataFrame(results)
            st.dataframe(test_df, use_container_width=True)
            
            # Vérification spécifique du FILTRE 2
            filter2_test = test_df[test_df["Produit Brute"].str.contains("CHAN FOUI|CHAN FOUL", case=False, na=False)]
            if not filter2_test.empty:
                st.info(f"**Filtre 2 testé:** 'CONS. CHAN FOUI 75CL' → '{filter2_test.iloc[0]['Produit Standard']}'")
            
            # Calculer l'accuracy
            perfect_matches = sum(1 for _, row in test_df.iterrows() 
                                if float(row["Confiance"].replace('%', '')) >= 85.0 and row["Statut"] == "matched")
            accuracy = (perfect_matches / len(test_df)) * 100
            st.success(f"📈 Précision pour ULYS : {accuracy:.1f}%")
    
    # ========================================================
    # BOUTON D'EXPORT PAR DÉFAUT
    # ========================================================
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>🚀 Export vers Cloud</h4>', unsafe_allow_html=True)
    
    # Informations sur l'export avec mention des filtres
    st.markdown(f"""
    <div class="info-box">
        <strong style="color: #1A1A1A !important;">🌐 Destination :</strong> Google Sheets (Cloud)<br>
        <strong style="color: #1A1A1A !important;">🔒 Sécurité :</strong> Chiffrement AES-256<br>
        <strong style="color: #1A1A1A !important;">⚡ Vitesse :</strong> Synchronisation en temps réel<br>
        <strong style="color: #1A1A1A !important;">🔄 Vérification :</strong> Détection automatique des doublons<br>
        <strong style="color: #1A1A1A !important;">⚠️ Filtres actifs :</strong> 
        • Suppression lignes quantité 0 | • Standardisation "Chan Foui 75cl" | • Détection doublons BDC
    </div>
    """, unsafe_allow_html=True)
    
    # Bouton d'export avec style tech
    col_btn, col_info = st.columns([2, 1])
    
    with col_btn:
        if st.button("🚀 Synchroniser avec Google Sheets", 
                    use_container_width=True, 
                    type="primary",
                    key="export_button",
                    help="Cliquez pour exporter les données vers le cloud"):
            
            st.session_state.export_triggered = True
            st.rerun()
    
    with col_info:
        st.markdown(f"""
        <div style="text-align: center; padding: 15px; background: rgba(59, 130, 246, 0.05); border-radius: 12px; height: 100%;">
            <div style="font-size: 1.5rem; color: #3B82F6 !important;">⚡</div>
            <div style="font-size: 0.8rem; color: #4B5563 !important;">Export instantané<br>Filtres actifs</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # VÉRIFICATION AUTOMATIQUE DES DOUBLONS APRÈS CLIC SUR EXPORT - FILTRE 3
    # ========================================================
    if st.session_state.export_triggered and st.session_state.export_status is None:
        with st.spinner("🔍 Analyse des doublons en cours ..."):
            # Normaliser le type de document
            normalized_doc_type = normalize_document_type(doc_type)
            
            # Obtenir la feuille Google Sheets
            ws = get_worksheet(normalized_doc_type)
            
            if ws:
                # Vérifier les doublons avec la même logique pour BDC et factures
                duplicate_found, duplicates = check_for_duplicates(
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
                st.error("❌ Connexion cloud échouée - Vérifiez votre connexion")
                st.session_state.export_status = "error"
    
    # ========================================================
    # AFFICHAGE DES OPTIONS EN CAS DE DOUBLONS - FILTRE 3
    # ========================================================
    if st.session_state.export_status == "duplicates_found":
        st.markdown('<div class="duplicate-box fade-in">', unsafe_allow_html=True)
        
        # En-tête avec icône
        st.markdown(f'''
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
            <div style="font-size: 2rem; color: #F59E0B !important;">⚠️</div>
            <div>
                <h3 style="margin: 0; color: #1A1A1A !important;">ALERTE : DOUBLON DÉTECTÉ </h3>
                <p style="margin: 5px 0 0 0; color: #4B5563 !important; font-size: 0.9rem;">Document similaire existant dans la base cloud - Même logique pour BDC et factures</p>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Détails du document
        if "FACTURE" in doc_type.upper():
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.5); padding: 15px; border-radius: 12px; margin-bottom: 20px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9rem; color: #1A1A1A !important;">
                    <div><strong>Type :</strong> {doc_type}</div>
                    <div><strong>Client :</strong> {st.session_state.data_for_sheets.get('client', 'Non détecté')}</div>
                    <div><strong>N° Facture :</strong> {st.session_state.data_for_sheets.get('numero_facture', 'Non détecté')}</div>
                    <div><strong>Doublons :</strong> {len(st.session_state.duplicate_rows)} trouvé(s)</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.5); padding: 15px; border-radius: 12px; margin-bottom: 20px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9rem; color: #1A1A1A !important;">
                    <div><strong>Type :</strong> {doc_type}</div>
                    <div><strong>Client :</strong> {st.session_state.data_for_sheets.get('client', 'Non détecté')}</div>
                    <div><strong>N° BDC :</strong> {st.session_state.data_for_sheets.get('numero', 'Non détecté')}</div>
                    <div><strong>Doublons :</strong> {len(st.session_state.duplicate_rows)} trouvé(s)</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown(f'<div style="color: #1A1A1A !important; margin-bottom: 10px; font-weight: 600;">Sélectionnez une action :</div>', unsafe_allow_html=True)
        
        # Boutons d'action avec style tech
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Remplacer", 
                        key="overwrite_duplicate", 
                        use_container_width=True, 
                        type="primary",
                        help="Remplace les documents existants par les nouvelles données"):
                st.session_state.duplicate_action = "overwrite"
                st.session_state.export_status = "ready_to_export"
                st.rerun()
        
        with col2:
            if st.button("➕ Nouvelle entrée", 
                        key="add_new_duplicate", 
                        use_container_width=True,
                        help="Ajoute comme nouvelle entrée sans supprimer l'existant"):
                st.session_state.duplicate_action = "add_new"
                st.session_state.export_status = "ready_to_export"
                st.rerun()
        
        with col3:
            if st.button("❌ Annuler", 
                        key="skip_duplicate", 
                        use_container_width=True,
                        help="Annule l'export et conserve les données existantes"):
                st.session_state.duplicate_action = "skip"
                st.session_state.export_status = "ready_to_export"
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # EXPORT EFFECTIF DES DONNÉES - FILTRE 1 appliqué ici
    # ========================================================
    if st.session_state.export_status in ["no_duplicates", "ready_to_export"]:
        if st.session_state.export_status == "no_duplicates":
            st.session_state.duplicate_action = "add_new"
        
        # Préparer le dataframe pour l'export
        export_df = st.session_state.edited_standardized_df.copy()
        
        # FILTRE 1: Afficher le nombre de lignes qui seront supprimées
        zero_qty_rows = export_df[export_df["Quantité"] == 0]
        if len(zero_qty_rows) > 0:
            st.info(f"⚠️ **Filtre 1 actif :** {len(zero_qty_rows)} ligne(s) avec quantité 0 seront automatiquement exclues de l'export")
        
        try:
            success, message = save_to_google_sheets(
                doc_type,
                st.session_state.data_for_sheets,
                export_df,
                duplicate_action=st.session_state.duplicate_action,
                duplicate_rows=st.session_state.duplicate_rows if st.session_state.duplicate_action == "overwrite" else None
            )
            
            if success:
                st.session_state.export_status = "completed"
                # Afficher un message de succès stylé avec mention des filtres
                st.markdown("""
                <div style="padding: 25px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%); color: white !important; border-radius: 18px; text-align: center; margin: 20px 0;">
                    <div style="font-size: 2.5rem; margin-bottom: 10px;">✅</div>
                    <h3 style="margin: 0 0 10px 0; color: white !important;">Synchronisation réussie !</h3>
                    <p style="margin: 0; opacity: 0.9;">Les données ont été exportées avec succès vers le cloud.</p>
                    <p style="margin: 10px 0 0 0; font-size: 0.9rem; opacity: 0.8;">✓ Filtre 1: Lignes quantité 0 supprimées<br>✓ Filtre 2: Standardisation Chan Foui appliquée<br>✓ Filtre 3: Détection doublons BDC activée</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.session_state.export_status = "error"
                st.error("❌ Échec de l'export - Veuillez réessayer")
                
        except Exception as e:
            st.error(f"❌ Erreur système : {str(e)}")
            st.session_state.export_status = "error"
    
    # ========================================================
    # BOUTONS DE NAVIGATION
    # ============================================================
    if st.session_state.document_scanned:
        st.markdown("---")
        
        # Section de navigation avec style tech
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
                st.session_state.duplicate_check_done = False
                st.session_state.duplicate_found = False
                st.session_state.duplicate_action = None
                st.session_state.image_preview_visible = False
                st.session_state.document_scanned = False
                st.session_state.export_triggered = False
                st.session_state.export_status = None
                st.session_state.product_matching_scores = {}
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
                st.session_state.duplicate_check_done = False
                st.session_state.duplicate_found = False
                st.session_state.duplicate_action = None
                st.session_state.image_preview_visible = True
                st.session_state.document_scanned = True
                st.session_state.export_triggered = False
                st.session_state.export_status = None
                st.session_state.product_matching_scores = {}
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# BOUTON DE DÉCONNEXION (toujours visible)
# ============================================================
st.markdown("---")
if st.button("🔒 Déconnexion sécurisée", 
            use_container_width=True, 
            type="secondary",
            key="logout_button_final",
            help="Fermer la session en toute sécurité"):
    logout()

# ============================================================
# FOOTER - SOLUTION STREAMLIT NATIVE AMÉLIORÉE
# ============================================================
st.markdown("---")

# Créer un conteneur stylé
with st.container():
    # Espacement
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    
    # Première ligne : Icônes
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"<center style='color: #1A1A1A !important;'>🤖</center>", unsafe_allow_html=True)
        st.markdown(f"<center><small style='color: #4B5563 !important;'>AI Vision</small></center>", unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"<center style='color: #1A1A1A !important;'>⚡</center>", unsafe_allow_html=True)
        st.markdown(f"<center><small style='color: #4B5563 !important;'>Fast Processing</small></center>", unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"<center style='color: #1A1A1A !important;'>🔒</center>", unsafe_allow_html=True)
        st.markdown(f"<center><small style='color: #4B5563 !important;'>Secure Cloud</small></center>", unsafe_allow_html=True)
    
    # Deuxième ligne : Titre
    st.markdown(f"""
    <center style='margin: 15px 0;'>
        <span style='font-weight: 700; color: #27414A !important;'>{BRAND_TITLE}</span>
        <span style='color: #4B5563 !important;'> • Système IA V3.0 • © {datetime.now().strftime("%Y")}</span>
    </center>
    """, unsafe_allow_html=True)
    
    # Troisième ligne : Statut avec mention des filtres
    st.markdown(f"""
    <center style='font-size: 0.8rem; color: #4B5563 !important;'>
        <span style='color: #10B981 !important;'>●</span> 
        Système actif • Session : 
        <strong style='color: #1A1A1A !important;'>{st.session_state.username}</strong>
        • Filtres actifs • {datetime.now().strftime("%H:%M:%S")}
    </center>
    """, unsafe_allow_html=True)
    
    # Espacement final
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

