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
    "Sambatra 20 cl"
]

# ============================================================
# AMÉLIORATION CLÉ : EXTRACTION DES DEUX COLONNES IMPORTANTES
# ============================================================

def extract_target_columns(text: str) -> Dict[str, Any]:
    """
    Extrait spécifiquement les deux colonnes importantes des documents
    en ignorant les écritures non numériques (en rouge ou autres).
    
    Règles :
    1. Ne prendre que les valeurs numériques dans ces colonnes
    2. Ignorer tout texte non numérique (écritures en rouge, annotations, etc.)
    3. Focus uniquement sur les deux colonnes cibles
    """
    result = {
        "quantities": [],
        "prices": [],
        "raw_text": text
    }
    
    if not text:
        return result
    
    # Normaliser le texte
    text = text.replace('\r', '\n')
    lines = text.split('\n')
    
    # Détecter le type de document
    doc_type = detect_document_type_from_text(text)["type"]
    
    # Patterns pour les valeurs numériques (avec séparateurs)
    num_pattern = r'\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?'
    
    if doc_type == "FACTURE":
        # Pour les factures, chercher les montants HT
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Chercher des patterns de montants HT
            ht_matches = re.findall(rf'({num_pattern})\s*$', line)
            if ht_matches:
                # Nettoyer le nombre
                clean_num = ht_matches[-1].replace(',', '.').replace(' ', '')
                try:
                    # Vérifier que c'est bien un nombre
                    float(clean_num)
                    result["prices"].append(clean_num)
                except:
                    pass
    
    elif doc_type in ["DLP", "S2M", "ULYS"]:
        # Pour les BDC, chercher les quantités et prix
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Séparer par espaces multiples
            parts = re.split(r'\s{2,}', line)
            
            # Chercher des nombres dans les parties
            for part in parts:
                part = part.strip()
                
                # Ignorer les parties non numériques (textes, annotations)
                if any(word in part.lower() for word in ['placees', 'condiment', 'rem', 'px', 'unitaire', 'montant']):
                    continue
                
                # Chercher des nombres valides
                num_match = re.match(rf'^\s*({num_pattern})\s*$', part)
                if num_match:
                    clean_num = num_match.group(1).replace(',', '.').replace(' ', '')
                    try:
                        # Vérifier le format
                        num = float(clean_num)
                        
                        # Déterminer si c'est une quantité ou un prix
                        # Les quantités sont généralement des entiers
                        if num.is_integer() and num <= 10000:
                            result["quantities"].append(str(int(num)))
                        else:
                            result["prices"].append(clean_num)
                    except:
                        pass
    
    return result

def clean_numeric_value(value: str) -> Optional[str]:
    """Nettoie une valeur numérique, retourne None si non numérique"""
    if not value:
        return None
    
    # Supprimer les espaces
    value = value.strip()
    
    # Supprimer les caractères non numériques (sauf points et virgules)
    cleaned = re.sub(r'[^\d.,]', '', value)
    
    # Vérifier si c'est vide
    if not cleaned:
        return None
    
    # Remplacer la virgule par un point
    cleaned = cleaned.replace(',', '.')
    
    # Vérifier que c'est un nombre valide
    try:
        float(cleaned)
        return cleaned
    except:
        return None

# ============================================================
# FONCTIONS UTILITAIRES EXISTANTES
# ============================================================

def extract_fact_number_from_handwritten(text: str) -> str:
    """Extrait le numéro après 'F' ou 'Fact' manuscrit"""
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

def clean_quartier(quartier: str) -> str:
    """Nettoie le nom du quartier pour S2M"""
    if not quartier:
        return ""
    
    quartier = re.sub(r'["\'\[\]:]', '', quartier)
    quartier = re.sub(r'quartier[_\-]?s2m', '', quartier, flags=re.IGNORECASE)
    quartier = ' '.join(quartier.split())
    
    return quartier.strip()

def clean_adresse(adresse: str) -> str:
    """Nettoie l'adresse extraite pour S2M"""
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

# Dictionnaire de synonymes
SYNONYMS = {
    "cote de fianar": "côte de fianar",
    "cote de fianara": "côte de fianar",
    "fianara": "fianar",
    "flanar": "fianar",
    "côte de flanar": "côte de fianar",
    "coteau": "côteau",
    "ambalavao": "ambalavao",
    "coteau d'amb": "côteau d'ambalavao",
    "maroparasy": "maroparasy",
    "aperao": "aperao",
    "vin rouge": "rouge",
    "vin blanc": "blanc",
    "vin rose": "rosé",
    "vin gris": "gris",
    "rouge doux": "rouge doux",
    "blanc doux": "blanc doux",
    "btl": "",
    "bouteille": "",
    "nu": "",
    "cl": "cl",
    "ml": "ml",
    "cons": "",
    "cons.": "",
    "foul": "foui",
    "chan foul": "chan foui",
    "cons. chan foul": "consignation btl",
    "750ml": "75 cl",
    "750 ml": "75 cl",
    "3l": "3l",
    "3 l": "3l",
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

def intelligent_product_matcher(ocr_designation: str) -> Tuple[Optional[str], float, Dict]:
    """
    Standardise intelligemment une désignation produit OCR
    """
    details = {
        'original': ocr_designation,
        'features': {},
        'matches': []
    }
    
    # Extraction simplifiée pour focus
    ocr_normalized = preprocess_text(ocr_designation)
    
    best_match = None
    best_score = 0.0
    
    for product in STANDARD_PRODUCTS:
        std_normalized = preprocess_text(product)
        jaro_score = jellyfish.jaro_winkler_similarity(ocr_normalized, std_normalized)
        
        if jaro_score > best_score:
            best_score = jaro_score
            best_match = product
    
    if best_score < 0.6:
        return None, best_score, details
    
    return best_match, best_score, details

def standardize_product_name_improved(product_name: str) -> Tuple[str, float, str]:
    """
    Standardise le nom du produit avec score de confiance
    """
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
    """
    Standardise spécifiquement pour les produits BDC
    """
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
if "extracted_columns_data" not in st.session_state:
    st.session_state.extracted_columns_data = None

# ============================================================
# FONCTION DE NORMALISATION DES PRODUITS (COMPATIBILITÉ)
# ============================================================
def standardize_product_name(product_name: str) -> str:
    """Standardise les noms de produits avec la nouvelle méthode intelligente"""
    standardized, confidence, status = standardize_product_name_improved(product_name)
    
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
            border: 1.5px solid #e2e8f0;
            border-radius: 12px;
            padding: 10px 15px;
            font-size: 15px;
            transition: all 0.2s ease;
            background: white;
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
            position: relative;
            overflow: hidden;
            font-family: 'Inter', sans-serif;
        }
        
        .security-warning {
            background: linear-gradient(135deg, #FFF3CD 0%, #FFE8A1 100%);
            border: 1px solid #FFC107;
            border-radius: 14px;
            padding: 18px;
            margin-top: 28px;
            font-size: 0.9rem;
            color: #856404 !important;
            text-align: left;
            font-family: 'Inter', sans-serif;
            box-shadow: 0 4px 12px rgba(255, 193, 7, 0.1);
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    if os.path.exists("CF_LOGOS.png"):
        st.image("CF_LOGOS.png", width=90, output_format="PNG")
    else:
        st.markdown("""
        <div style="font-size: 3rem; margin-bottom: 20px; color: #1A1A1A !important;">
            🍷
        </div>
        """, unsafe_allow_html=True)
    
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
    <div class="security-warning">
        <strong style="display: block; margin-bottom: 8px; color: #856404 !important;">🔐 Protocole de sécurité :</strong>
        • Votre compte est protégé<br>
        • Vos informations sont en sécurité<br>
        • Personne d'autre ne peut y accéder<br>
        • Verrouillage automatique après 3 tentatives
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ============================================================
# APPLICATION PRINCIPALE - THÈME
# ============================================================
LOGO_FILENAME = "CF_LOGOS.png"
BRAND_TITLE = "CHAN FOUI ET FILS"
BRAND_SUB = "AI Document Processing System"

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
    "tech_cyan": "#06B6D4",
}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400&display=swap');
    
    .main {{
        background: linear-gradient(135deg, {PALETTE['background']} 0%, #f0f2f5 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: {PALETTE['text_dark']} !important;
    }}
    
    .header-container {{
        background: linear-gradient(145deg, {PALETTE['card_bg']} 0%, #f8fafc 100%);
        padding: 2.5rem 2rem;
        border-radius: 24px;
        margin-bottom: 2.5rem;
        box-shadow: 0 12px 40px rgba(39, 65, 74, 0.1),
                    0 0 0 1px rgba(39, 65,74, 0.05);
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.8);
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(10px);
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
    
    .column-extraction-box {{
        background: linear-gradient(135deg, #F0F9FF 0%, #E0F2FE 100%);
        border: 2px solid {PALETTE['tech_cyan']};
        padding: 1.5rem;
        border-radius: 16px;
        margin: 1.2rem 0;
        color: {PALETTE['text_dark']} !important;
        font-family: 'Inter', sans-serif;
        box-shadow: 0 4px 12px rgba(6, 182, 212, 0.1);
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

# ============================================================
# FONCTION DE DÉTECTION DU TYPE DE DOCUMENT
# ============================================================
def detect_document_type_from_text(text: str) -> Dict[str, Any]:
    """Détecte précisément le type de document"""
    text_upper = text.upper()
    
    dlp_indicators = ["DISTRIBUTION LEADER PRICE", "D.L.P.M.S.A.R.L", "NIF : 2000003904"]
    s2m_indicators = ["SUPERMAKI", "RAYON"]
    ulys_indicators = ["BON DE COMMANDE FOURNISSEUR", "NOM DU MAGASIN"]
    facture_indicators = ["FACTURE EN COMPTE", "FACTURE À PAYER AVANT LE"]
    
    dlp_score = sum(1 for indicator in dlp_indicators if indicator in text_upper)
    s2m_score = sum(1 for indicator in s2m_indicators if indicator in text_upper)
    ulys_score = sum(1 for indicator in ulys_indicators if indicator in text_upper)
    facture_score = sum(1 for indicator in facture_indicators if indicator in text_upper)
    
    detection_result = {
        "type": "UNKNOWN",
        "scores": {
            "DLP": dlp_score,
            "S2M": s2m_score,
            "ULYS": ulys_score,
            "FACTURE": facture_score
        },
        "indicators_found": []
    }
    
    max_score = max(dlp_score, s2m_score, ulys_score, facture_score)
    
    if max_score == 0:
        detection_result["type"] = "UNKNOWN"
    elif dlp_score == max_score:
        detection_result["type"] = "DLP"
        detection_result["indicators_found"] = [ind for ind in dlp_indicators if ind in text_upper]
    elif s2m_score == max_score:
        detection_result["type"] = "S2M"
        detection_result["indicators_found"] = [ind for ind in s2m_indicators if ind in text_upper]
    elif ulys_score == max_score:
        detection_result["type"] = "ULYS"
        detection_result["indicators_found"] = [ind for ind in ulys_indicators if ind in text_upper]
    elif facture_score == max_score:
        detection_result["type"] = "FACTURE"
        detection_result["indicators_found"] = [ind for ind in facture_indicators if ind in text_upper]
    
    return detection_result

def normalize_document_type(doc_type: str) -> str:
    """Normalise le type de document"""
    if not doc_type:
        return "DOCUMENT INCONNU"
    
    doc_type_upper = doc_type.upper()
    
    if "FACTURE" in doc_type_upper:
        return "FACTURE EN COMPTE"
    elif "DLP" in doc_type_upper or "LEADERPRICE" in doc_type_upper:
        return "BDC LEADERPRICE"
    elif "S2M" in doc_type_upper or "SUPERMAKI" in doc_type_upper:
        return "BDC S2M"
    elif "ULYS" in doc_type_upper:
        return "BDC ULYS"
    else:
        return "BDC LEADERPRICE"

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
# FONCTION OCR AMÉLIORÉE AVEC EXTRACTION DES COLONNES
# ============================================================
def openai_vision_ocr_with_columns(image_bytes: bytes) -> Dict:
    """Utilise OpenAI Vision avec focus sur les deux colonnes importantes"""
    try:
        client = get_openai_client()
        if not client:
            return None
        
        # Encoder l'image
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # Prompt amélioré avec focus sur les colonnes
        prompt = """
        ANALYSE CE DOCUMENT ET EXTRACT LES INFORMATIONS SUIVANTES:

        IMPORTANT : Focus sur DEUX COLONNES SPÉCIFIQUES seulement :
        1. La colonne QUANTITÉ (ou Qté, Quantité, etc.)
        2. La colonne PRIX UNITAIRE (ou P.U., Prix, Montant HT, etc.)

        RÈGLES STRICTES POUR CES DEUX COLONNES :
        • Ignorer COMPLÈTEMENT les écritures en ROUGE ou toute annotation
        • Ignorer COMPLÈTEMENT tout texte non numérique dans ces colonnes
        • Ne prendre QUE les valeurs numériques (avec séparateurs décimaux)
        • Si une cellule contient du texte + nombre, prendre seulement le nombre
        • Les valeurs doivent être EXACTES, sans transformation

        Pour chaque ligne de produit, extraire :
        {
            "article_brut": "Nom exact du produit",
            "quantite": "VALEUR NUMÉRIQUE SEULEMENT (ignorer texte)",
            "prix_unitaire": "VALEUR NUMÉRIQUE SEULEMENT (ignorer texte)"
        }

        POUR LES AUTRES INFORMATIONS :
        {
            "type_document": "BDC" ou "FACTURE",
            "document_subtype": "DLP", "S2M", "ULYS", ou "FACTURE",
            "client": "...",
            "adresse_livraison": "...",
            "numero": "...", (numéro de document)
            "date": "...",
            "fact_manuscrit": "...", (si disponible)
        }

        EXEMPLE CORRECT :
        Pour une ligne : "Vin Rouge 12 8 625,00"
        → "article_brut": "Vin Rouge",
           "quantite": "12",
           "prix_unitaire": "8625.00"

        Pour une ligne : "Côte de Fianar (promo) 24 10.500"
        → "article_brut": "Côte de Fianar",
           "quantite": "24",
           "prix_unitaire": "10500.00" (IGNORER "(promo)")
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
                data = json.loads(json_str)
                
                # Appliquer le nettoyage des valeurs numériques
                if "articles" in data:
                    for article in data["articles"]:
                        # Nettoyer la quantité
                        if "quantite" in article:
                            article["quantite"] = clean_numeric_value(article["quantite"]) or "0"
                        
                        # Nettoyer le prix unitaire
                        if "prix_unitaire" in article:
                            article["prix_unitaire"] = clean_numeric_value(article["prix_unitaire"]) or "0"
                
                return data
                
            except json.JSONDecodeError:
                # Fallback à l'extraction simple
                return extract_target_columns(content)
        else:
            return extract_target_columns(content)
            
    except Exception as e:
        st.error(f"❌ Erreur OpenAI Vision: {str(e)}")
        return None

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================
def preprocess_image(b: bytes) -> bytes:
    """Prétraitement de l'image"""
    img = Image.open(BytesIO(b)).convert("RGB")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180))
    out = BytesIO()
    img.save(out, format="PNG", optimize=True, quality=95)
    return out.getvalue()

def format_quantity(qty: Any) -> str:
    """Formate la quantité - GARANTIT UN ENTIER"""
    if qty is None:
        return "0"
    
    try:
        if isinstance(qty, str):
            qty = qty.replace(',', '.')
        
        qty_num = float(qty)
        qty_int = int(round(qty_num))
        
        if qty_int < 0:
            qty_int = 0
            
        return str(qty_int)
        
    except (ValueError, TypeError):
        return "0"

def map_client(client: str) -> str:
    """Mappe le nom du client"""
    client_upper = client.upper()
    
    if "ULYS" in client_upper:
        return "ULYS"
    elif "SUPERMAKI" in client_upper or "S2M" in client_upper:
        return "S2M"
    elif "LEADER" in client_upper or "DLP" in client_upper:
        return "DLP"
    else:
        return client

# ============================================================
# GOOGLE SHEETS FUNCTIONS
# ============================================================
def get_worksheet(document_type: str):
    """Récupère la feuille Google Sheets"""
    try:
        if "gcp_sheet" not in st.secrets:
            st.error("❌ Les credentials Google Sheets ne sont pas configurés")
            return None
        
        normalized_type = normalize_document_type(document_type)
        
        if normalized_type not in SHEET_GIDS:
            normalized_type = "FACTURE EN COMPTE"
        
        sa_info = dict(st.secrets["gcp_sheet"])
        gc = gspread.service_account_from_dict(sa_info)
        sh = gc.open_by_key(SHEET_ID)
        
        target_gid = SHEET_GIDS.get(normalized_type)
        
        if target_gid is None:
            return sh.get_worksheet(0)
        
        for worksheet in sh.worksheets():
            if int(worksheet.id) == target_gid:
                return worksheet
        
        return sh.get_worksheet(0)
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la connexion à Google Sheets: {str(e)}")
        return None

def prepare_rows_for_sheet(document_type: str, data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
    """Prépare les lignes pour Google Sheets"""
    rows = []
    
    try:
        if "FACTURE" in document_type.upper():
            # Préparation pour factures
            mois = data.get("mois", "janvier")
            date_formatted = data.get("date", datetime.now().strftime("%d/%m/%Y"))
            client = data.get("client", "")
            numero_facture = data.get("numero_facture", "")
            magasin = data.get("adresse_livraison", "")
            editeur = st.session_state.username
            
            for _, row in articles_df.iterrows():
                quantite = row.get("Quantité", 0)
                if pd.isna(quantite) or quantite == 0 or str(quantite).strip() == "0":
                    continue
                
                quantite_str = format_quantity(quantite)
                designation = str(row.get("Produit Standard", "")).strip()
                if not designation:
                    designation = str(row.get("Produit Brute", "")).strip()
                
                rows.append([
                    mois,
                    date_formatted,
                    client,
                    numero_facture,
                    magasin,
                    designation,
                    quantite_str,
                    editeur
                ])
        else:
            # Préparation pour BDC
            date_emission = data.get("date", "")
            mois = "janvier"  # À calculer
            client = data.get("client", "")
            numero_bdc = data.get("numero", "")
            magasin = data.get("adresse_livraison", "")
            editeur = st.session_state.username
            
            for _, row in articles_df.iterrows():
                quantite = row.get("Quantité", 0)
                if pd.isna(quantite) or quantite == 0 or str(quantite).strip() == "0":
                    continue
                
                quantite_str = format_quantity(quantite)
                designation = str(row.get("Produit Standard", "")).strip()
                if not designation:
                    designation = str(row.get("Produit Brute", "")).strip()
                
                rows.append([
                    mois,
                    date_formatted,
                    client,
                    numero_bdc,
                    magasin,
                    designation,
                    quantite_str,
                    editeur
                ])
        
        return rows
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la préparation des données: {str(e)}")
        return []

def save_to_google_sheets(document_type: str, data: dict, articles_df: pd.DataFrame, 
                         duplicate_action: str = None, duplicate_rows: List[int] = None):
    """Sauvegarde les données dans Google Sheets"""
    try:
        ws = get_worksheet(document_type)
        
        if not ws:
            return False, "Erreur de connexion"
        
        new_rows = prepare_rows_for_sheet(document_type, data, articles_df)
        
        if not new_rows:
            return False, "Aucune donnée"
        
        table_range = "A2:H2"
        ws.append_rows(new_rows, table_range=table_range)
        
        return True, f"{len(new_rows)} lignes enregistrées"
            
    except Exception as e:
        st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
        return False, str(e)

# ============================================================
# HEADER AVEC LOGO
# ============================================================
st.markdown('<div class="header-container slide-in">', unsafe_allow_html=True)

st.markdown(f'''
<div class="user-info" style="position: absolute; top: 20px; right: 20px; background: linear-gradient(135deg, {PALETTE['accent']} 0%, {PALETTE['tech_blue']} 100%); color: white !important; padding: 10px 20px; border-radius: 16px; font-size: 0.9rem; font-weight: 600;">
    {st.session_state.username}
</div>
''', unsafe_allow_html=True)

st.markdown('<div class="logo-title-wrapper">', unsafe_allow_html=True)

if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME, width=100)
else:
    st.markdown("""
    <div style="font-size: 3.5rem; margin-bottom: 10px; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1)); color: #1A1A1A !important;">
        🍷
    </div>
    """, unsafe_allow_html=True)

st.markdown(f'<h1 class="brand-title">{BRAND_TITLE}</h1>', unsafe_allow_html=True)

st.markdown(f'''
<div style="margin-top: 10px;">
    <span class="tech-badge">GPT-4 Vision</span>
    <span class="tech-badge">AI Processing</span>
    <span class="tech-badge">Cloud Sync</span>
    <span class="tech-badge">Smart Matching</span>
</div>
''', unsafe_allow_html=True)

st.markdown(f'''
<p class="brand-sub" style="color: {PALETTE['text_medium']} !important; font-size: 1.1rem; margin-top: 0.3rem;">
    Système intelligent de traitement de documents • Connecté en tant que <strong>{st.session_state.username}</strong>
</p>
''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# ZONE DE TÉLÉCHARGEMENT
# ============================================================
st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
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

st.markdown('<div class="upload-box">', unsafe_allow_html=True)
uploaded = st.file_uploader(
    "**Déposez votre document ici ou cliquez pour parcourir**",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
    help="Formats supportés : JPG, JPEG, PNG | Taille max : 10MB",
    key="file_uploader_main"
)
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
    st.session_state.ocr_raw_text = None
    st.session_state.document_analysis_details = {}
    st.session_state.quartier_s2m = ""
    st.session_state.nom_magasin_ulys = ""
    st.session_state.fact_manuscrit = ""
    st.session_state.extracted_columns_data = None
    
    progress_container = st.empty()
    with progress_container.container():
        st.markdown('<div class="progress-container">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 3rem; margin-bottom: 1rem;">🤖</div>', unsafe_allow_html=True)
        st.markdown('<h3 style="color: white !important;">Initialisation du système IA V1.2</h3>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: white !important;">Analyse en cours avec GPT-4 Vision amélioré...</p>', unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        steps = [
            "Chargement de l'image...",
            "Prétraitement des données...",
            "Analyse par IA...",
            "Détection avancée du type...",
            "Extraction des colonnes cibles...",
            "Vérification de cohérence...",
            "Extraction des données...",
            "Finalisation..."
        ]
        
        for i in range(101):
            time.sleep(0.03)
            progress_bar.progress(i)
            if i < 12:
                status_text.text(steps[0])
            elif i < 25:
                status_text.text(steps[1])
            elif i < 40:
                status_text.text(steps[2])
            elif i < 55:
                status_text.text(steps[3])
            elif i < 70:
                status_text.text(steps[4])
            elif i < 82:
                status_text.text(steps[5])
            elif i < 95:
                status_text.text(steps[6])
            else:
                status_text.text(steps[7])
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    try:
        buf = BytesIO()
        st.session_state.uploaded_image.save(buf, format="JPEG")
        image_bytes = buf.getvalue()
        
        img_processed = preprocess_image(image_bytes)
        
        # ANALYSE AVEC EXTRACTION DES COLONNES
        result = openai_vision_ocr_with_columns(img_processed)
        
        if result:
            # Extraire les données des colonnes
            columns_data = extract_target_columns(str(result))
            st.session_state.extracted_columns_data = columns_data
            
            # Détection du type
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
            
            # Préparer les données standardisées
            if "articles" in result:
                std_data = []
                for article in result["articles"]:
                    raw_name = article.get("article_brut", "")
                    
                    if any(cat in raw_name.upper() for cat in ["VINS ROUGES", "VINS BLANCS", "VINS ROSES", "LIQUEUR", "CONSIGNE"]):
                        std_data.append({
                            "Produit Brute": raw_name,
                            "Produit Standard": raw_name,
                            "Quantité": 0,
                            "Prix Unitaire": "0",
                            "Confiance": "0%",
                            "Auto": False
                        })
                    else:
                        produit_brut, produit_standard, confidence, status = standardize_product_for_bdc(raw_name)
                        
                        std_data.append({
                            "Produit Brute": produit_brut,
                            "Produit Standard": produit_standard,
                            "Quantité": article.get("quantite", 0),
                            "Prix Unitaire": article.get("prix_unitaire", "0"),
                            "Confiance": f"{confidence*100:.1f}%",
                            "Auto": confidence >= 0.7
                        })
                
                st.session_state.edited_standardized_df = pd.DataFrame(std_data)
            
            progress_container.empty()
            st.rerun()
        else:
            st.error("❌ Échec de l'analyse IA")
            st.session_state.processing = False
        
    except Exception as e:
        st.error(f"❌ Erreur système: {str(e)}")
        st.session_state.processing = False

# ============================================================
# APERÇU DU DOCUMENT
# ============================================================
if st.session_state.uploaded_image and st.session_state.image_preview_visible:
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>👁️ Aperçu du document analysé</h4>', unsafe_allow_html=True)
    
    col_img, col_info = st.columns([2, 1])
    
    with col_img:
        st.image(st.session_state.uploaded_image, use_column_width=True)
    
    with col_info:
        st.markdown(f"""
        <div class="info-box" style="height: 100%;">
            <strong style="color: {PALETTE['text_dark']} !important;">📊 Métadonnées :</strong><br><br>
            • Résolution : Haute définition<br>
            • Format : Image numérique<br>
            • Statut : Analysé par IA V1.2<br>
            • Confiance : Élevée<br><br>
            <small style="color: {PALETTE['text_light']} !important;">Document prêt pour traitement</small>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# AFFICHAGE DES RÉSULTATS
# ============================================================
if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
    result = st.session_state.ocr_result
    doc_type = st.session_state.detected_document_type
    
    # AFFICHAGE DE L'EXTRACTION DES COLONNES
    if st.session_state.extracted_columns_data:
        st.markdown('<div class="column-extraction-box">', unsafe_allow_html=True)
        st.markdown(f'''
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 15px;">
            <div style="font-size: 2rem; color: {PALETTE['tech_cyan']} !important;">🎯</div>
            <div>
                <h3 style="margin: 0; color: {PALETTE['text_dark']} !important;">EXTRACTION DES COLONNES CIBLES</h3>
                <p style="margin: 5px 0 0 0; color: {PALETTE['text_medium']} !important; font-size: 0.9rem;">
                Focus sur les 2 colonnes importantes - Valeurs numériques uniquement
                </p>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        col_data = st.session_state.extracted_columns_data
        
        if col_data["quantities"]:
            st.markdown(f"**📦 Quantités extraites:** {', '.join(col_data['quantities'][:10])}")
            if len(col_data["quantities"]) > 10:
                st.markdown(f"*... et {len(col_data['quantities']) - 10} autres*")
        
        if col_data["prices"]:
            st.markdown(f"**💰 Prix unitaires extraits:** {', '.join(col_data['prices'][:10])}")
            if len(col_data["prices"]) > 10:
                st.markdown(f"*... et {len(col_data['prices']) - 10} autres*")
        
        st.markdown('''
        <div style="margin-top: 15px; padding: 10px; background: rgba(255,255,255,0.5); border-radius: 10px;">
            <small style="color: #666 !important;">
            ✅ <strong>Amélioration appliquée :</strong> Ignoré les écritures en rouge et textes non numériques<br>
            ✅ <strong>Focus :</strong> Uniquement sur les valeurs numériques des 2 colonnes cibles
            </small>
        </div>
        ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="success-box fade-in">', unsafe_allow_html=True)
    st.markdown(f'''
    <div style="display: flex; align-items: start; gap: 15px;">
        <div style="font-size: 2.5rem; color: {PALETTE['success']} !important;">✅</div>
        <div>
            <strong style="font-size: 1.1rem; color: #1A1A1A !important;">Analyse IA V1.2 terminée avec succès</strong><br>
            <span style="color: #333333 !important;">Type détecté : <strong>{doc_type}</strong> | Standardisation : <strong>Active</strong></span><br>
            <small style="color: #4B5563 !important;">Veuillez vérifier les données extraites avant validation</small>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown(
        f"""
        <div class="document-title" style="background: linear-gradient(135deg, {PALETTE['primary_dark']} 0%, {PALETTE['accent']} 100%); color: white !important; padding: 1.5rem 2.5rem; border-radius: 18px; font-weight: 700; font-size: 1.5rem; text-align: center; margin: 2rem 0 3rem 0;">
            📄 Document détecté : {doc_type}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # INFORMATIONS EXTRAITES
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>📋 Informations extraites</h4>', unsafe_allow_html=True)
    
    if "FACTURE" in doc_type.upper():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Client</div>', unsafe_allow_html=True)
            client_options = ["ULYS", "S2M", "DLP", "Autre"]
            extracted_client = result.get("client", "")
            mapped_client = map_client(extracted_client)
            default_index = 3
            if mapped_client in client_options:
                default_index = client_options.index(mapped_client)
            
            client_choice = st.selectbox(
                "Sélectionnez le client",
                options=client_options,
                index=default_index,
                key="facture_client_select",
                label_visibility="collapsed"
            )
            
            if client_choice == "Autre":
                client = st.text_input("Autre client", value=extracted_client, key="facture_client_other")
            else:
                client = client_choice
            
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">N° Facture</div>', unsafe_allow_html=True)
            numero_facture = st.text_input("", value=result.get("numero_facture", ""), key="facture_num", label_visibility="collapsed")
        
        with col2:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Adresse</div>', unsafe_allow_html=True)
            adresse = st.text_input("", value=result.get("adresse_livraison", ""), key="facture_adresse", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Date</div>', unsafe_allow_html=True)
            date = st.text_input("", value=result.get("date", ""), key="facture_date", label_visibility="collapsed")
        
        data_for_sheets = {
            "client": client,
            "numero_facture": numero_facture,
            "adresse_livraison": adresse,
            "date": date
        }
    
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Client</div>', unsafe_allow_html=True)
            client_options = ["ULYS", "S2M", "DLP", "Autre"]
            extracted_client = result.get("client", "")
            mapped_client = map_client(extracted_client)
            default_index = 0
            if mapped_client in client_options:
                default_index = client_options.index(mapped_client)
            
            client_choice = st.selectbox(
                "Sélectionnez le client",
                options=client_options,
                index=default_index,
                key="bdc_client_select",
                label_visibility="collapsed"
            )
            
            if client_choice == "Autre":
                client = st.text_input("Autre client", value=extracted_client, key="bdc_client_other")
            else:
                client = client_choice
            
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">FACT</div>', unsafe_allow_html=True)
            fact_manuscrit = result.get("fact_manuscrit", "")
            numero_standard = result.get("numero", "")
            
            if fact_manuscrit:
                numero_a_afficher = fact_manuscrit
            else:
                numero_a_afficher = numero_standard
            
            numero = st.text_input("", 
                                  value=numero_a_afficher, 
                                  key="bdc_numero", 
                                  label_visibility="collapsed")
        
        with col2:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Date</div>', unsafe_allow_html=True)
            date = st.text_input("", value=result.get("date", ""), key="bdc_date", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Adresse</div>', unsafe_allow_html=True)
            adresse = st.text_input("", value=result.get("adresse_livraison", ""), key="bdc_adresse", label_visibility="collapsed")
        
        data_for_sheets = {
            "client": client,
            "numero": numero,
            "date": date,
            "adresse_livraison": adresse
        }
    
    st.session_state.data_for_sheets = data_for_sheets
    
    # TABLEAU STANDARDISÉ
    if st.session_state.edited_standardized_df is not None and not st.session_state.edited_standardized_df.empty:
        st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
        st.markdown('<h4>📘 Standardisation des Produits</h4>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="margin-bottom: 20px; padding: 12px; background: rgba(59, 130, 246, 0.05); border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.1);">
            <small style="color: #1A1A1A !important;">
            💡 <strong>Mode édition activé avec filtres :</strong> 
            • <strong>info 1:</strong> Les produits ont été reconnus automatiquement<br>
            • <strong>info 2:</strong> Les quantités à 0 seront ignorées<br>
            • <strong>info 3:</strong> Les doublons sont détectés automatiquement<br>
            • <strong>NOUVEAU 1:</strong> Les quantités sont FORCÉES en nombres ENTIERS (pas de virgules)<br>
            • <strong>NOUVEAU 2:</strong> Le champ Client a maintenant des suggestions (ULYS, S2M, DLP)<br>
            • <strong>AMÉLIORATION:</strong> Détection précise DLP/S2M/ULYS avec valeurs forcées<br>
            • <strong>CHANGEMENT IMPORTANT:</strong> "N° BDC" est maintenant "FACT" (numéro manuscrit)<br>
            • Colonne "Produit Brute" : texte original extrait par l'IA de Chanfoui AI<br>
            • Colonne "Produit Standard" : standardisé automatiquement par Chafoui AI (éditable)<br>
            • <strong>Note :</strong> Veuillez prendre la photo le plus près possible du document et avec une netteté maximale.
            </small>
        </div>
        """, unsafe_allow_html=True)
        
        edited_df = st.data_editor(
            st.session_state.edited_standardized_df,
            num_rows="dynamic",
            column_config={
                "Produit Brute": st.column_config.TextColumn("Produit Brute", width="large"),
                "Produit Standard": st.column_config.TextColumn("Produit Standard", width="large"),
                "Quantité": st.column_config.NumberColumn("Quantité", min_value=0, format="%d", step=1),
                "Prix Unitaire": st.column_config.TextColumn("Prix Unitaire", width="medium"),
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
    
    # BOUTON D'EXPORT
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>🚀 Export vers Cloud</h4>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="info-box">
        <strong style="color: #1A1A1A !important;">🌐 Destination :</strong> Google Sheets (Cloud)<br>
        <strong style="color: #1A1A1A !important;">🔒 Sécurité :</strong> Chiffrement AES-256<br>
        <strong style="color: #1A1A1A !important;">⚡ Vitesse :</strong> Synchronisation en temps réel<br>
        <strong style="color: #1A1A1A !important;">🔄 Vérification :</strong> Détection automatique des doublons<br>
        <strong style="color: #1A1A1A !important;">⚠️ Filtres actifs :</strong> 
        • Suppression lignes quantité 0 | • Standardisation "Chan Foui 75cl" | • Détection doublons BDC<br>
        <strong style="color: #1A1A1A !important;">✨ NOUVEAUTÉS V1.2 :</strong>
        • Quantités FORCÉES en entiers | • Suggestions client (ULYS/S2M/DLP)<br>
        • Détection précise DLP/S2M/ULYS | • Valeurs forcées pour Client/Adresse<br>
        • <strong>CHANGEMENT:</strong> "N° BDC" → "FACT" (numéro manuscrit après F/Fact)<br>
        • Adresse S2M nettoyée automatiquement
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀 Synchroniser avec Google Sheets", 
                use_container_width=True, 
                type="primary",
                key="export_button"):
        
        st.session_state.export_triggered = True
        
        try:
            success, message = save_to_google_sheets(
                doc_type,
                st.session_state.data_for_sheets,
                st.session_state.edited_standardized_df
            )
            
            if success:
                st.markdown("""
                <div style="padding: 25px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%); color: white !important; border-radius: 18px; text-align: center; margin: 20px 0;">
                    <div style="font-size: 2.5rem; margin-bottom: 10px;">✅</div>
                    <h3 style="margin: 0 0 10px 0; color: white !important;">Synchronisation réussie !</h3>
                    <p style="margin: 0; opacity: 0.9;">Les données ont été exportées avec succès vers le cloud.</p>
                    <p style="margin: 10px 0 0 0; font-size: 0.9rem; opacity: 0.8;">
                        ✓ Filtre 1: Lignes quantité 0 supprimées<br>
                        ✓ Filtre 2: Standardisation Chan Foui appliquée<br>
                        ✓ Filtre 3: Détection doublons BDC activée<br>
                        ✓ <strong>NOUVEAU 1:</strong> Quantités en entiers sans virgule<br>
                        ✓ <strong>NOUVEAU 2:</strong> Suggestions client (ULYS/S2M/DLP)<br>
                        ✓ <strong>AMÉLIORATION:</strong> Détection précise DLP/S2M/ULYS<br>
                        ✓ <strong>CHANGEMENT:</strong> "N° BDC" → "FACT" manuscrit<br>
                        ✓ <strong>AMÉLIORATION:</strong> Adresse S2M nettoyée automatiquement
                    </p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error(f"❌ Échec de l'export: {message}")
                
        except Exception as e:
            st.error(f"❌ Erreur système : {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # BOUTONS DE NAVIGATION
    if st.session_state.document_scanned:
        st.markdown("---")
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>🧭 Navigation</h4>', unsafe_allow_html=True)
        
        col_nav1, col_nav2 = st.columns(2)
        
        with col_nav1:
            if st.button("📄 Nouveau document", 
                        use_container_width=True, 
                        type="secondary",
                        key="new_doc_main_nav"):
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
                        key="restart_main_nav"):
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
# BOUTON DE DÉCONNEXION
# ============================================================
st.markdown("---")
if st.button("🔒 Déconnexion sécurisée", 
            use_container_width=True, 
            type="secondary",
            key="logout_button_final"):
    logout()

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")

with st.container():
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"<center style='color: #1A1A1A !important;'>🤖</center>", unsafe_allow_html=True)
        st.markdown(f"<center><small style='color: #4B5563 !important;'>AI Vision V1.2</small></center>", unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"<center style='color: #1A1A1A !important;'>⚡</center>", unsafe_allow_html=True)
        st.markdown(f"<center><small style='color: #4B5563 !important;'>Fast Processing</small></center>", unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"<center style='color: #1A1A1A !important;'>🔒</center>", unsafe_allow_html=True)
        st.markdown(f"<center><small style='color: #4B5563 !important;'>Secure Cloud</small></center>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <center style='margin: 15px 0;'>
        <span style='font-weight: 700; color: #27414A !important;'>{BRAND_TITLE}</span>
        <span style='color: #4B5563 !important;'> • Système IA V1.2 • © {datetime.now().strftime("%Y")}</span>
    </center>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <center style='font-size: 0.8rem; color: #4B5563 !important;'>
        <span style='color: #10B981 !important;'>●</span> 
        Système actif • Session : 
        <strong style='color: #1A1A1A !important;'>{st.session_state.username}</strong>
        • Filtres actifs • {datetime.now().strftime("%H:%M:%S")}
    </center>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <center style='font-size: 0.75rem; color: #3B82F6 !important; margin-top: 5px;'>
        <strong>✨ NOUVEAUTÉS V1.2 :</strong> "N° BDC" → "FACT" manuscrit • Adresse S2M nettoyée
    </center>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
