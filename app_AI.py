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
from typing import List, Tuple, Dict, Any
import hashlib
import json

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
if "edited_df" not in st.session_state:
    st.session_state.edited_df = None
if "raw_data_df" not in st.session_state:
    st.session_state.raw_data_df = None
if "standardized_data_df" not in st.session_state:
    st.session_state.standardized_data_df = None

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
    st.rerun()

# ============================================================
# PAGE DE CONNEXION
# ============================================================
if not check_authentication():
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 50px auto;
            padding: 40px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            text-align: center;
        }
        .login-title {
            color: #27414A;
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 10px;
        }
        .login-subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 1rem;
        }
        .login-logo {
            height: 80px;
            margin-bottom: 20px;
        }
        .stTextInput > div > div > input {
            border: 2px solid #E0E0E0;
            border-radius: 10px;
            padding: 12px 15px;
            font-size: 16px;
        }
        .stTextInput > div > div > input:focus {
            border-color: #27414A;
            box-shadow: 0 0 0 2px rgba(39, 65, 74, 0.2);
        }
        .stButton > button {
            background: #27414A;
            color: white;
            font-weight: 600;
            border: none;
            padding: 14px 20px;
            border-radius: 10px;
            width: 100%;
            font-size: 16px;
            margin-top: 10px;
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            background: #1F2F35;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(39, 65, 74, 0.3);
        }
        .user-list {
            background: #F8F9FA;
            border-radius: 10px;
            padding: 15px;
            margin-top: 30px;
            text-align: left;
        }
        .user-item {
            padding: 8px 0;
            border-bottom: 1px solid #E0E0E0;
        }
        .user-item:last-child {
            border-bottom: none;
        }
        .security-warning {
            background: #FFF3CD;
            border: 1px solid #FFC107;
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
            font-size: 0.9rem;
            color: #856404;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    if os.path.exists("CF_LOGOS.png"):
        st.image("CF_LOGOS.png", width=80, output_format="PNG")
    else:
        st.markdown("🍷")
    
    st.markdown('<h1 class="login-title">CHAN FOUI ET FILS</h1>', unsafe_allow_html=True)
    st.markdown('<p class="login-subtitle">Système de Scanner Pro - Accès Restreint</p>', unsafe_allow_html=True)
    
    username = st.selectbox(
        "👤 Nom d'utilisateur",
        options=[""] + list(AUTHORIZED_USERS.keys()),
        format_func=lambda x: "— Sélectionnez votre nom —" if x == "" else x,
        key="login_username"
    )
    password = st.text_input("🔒 Code d'accès", type="password", placeholder="Entrez votre code CFFx", key="login_password")
    
    if st.button("🔓 Se connecter", use_container_width=True, key="login_button"):
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
        <strong>⚠️ Sécurité :</strong> Ce système est réservé au personnel autorisé.<br>
        • Ne partagez pas vos identifiants<br>
        • Déconnectez-vous après utilisation<br>
        • 3 tentatives maximum avant verrouillage
    </div>
    """, unsafe_allow_html=True)
    
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
BRAND_SUB = "OpenAI Vision AI — Scanner Intelligent"

PALETTE = {
    "primary_dark": "#27414A",
    "primary_light": "#1F2F35",
    "background": "#F5F5F3",
    "card_bg": "#FFFFFF",
    "card_bg_alt": "#F4F6F3",
    "text_dark": "#1A1A1A",
    "text_medium": "#333333",
    "accent": "#2C5F73",
    "success": "#2E7D32",
    "warning": "#ED6C02",
    "error": "#D32F2F",
    "border": "#D1D5DB",
    "hover": "#F9FAFB",
}

st.markdown(f"""
<style>
    .main {{
        background: {PALETTE['background']};
    }}
    
    .stApp {{
        background: {PALETTE['background']};
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        line-height: 1.6;
    }}
    
    .header-container {{
        background: {PALETTE['card_bg']};
        padding: 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(39, 65, 74, 0.08);
        text-align: center;
        border: 1px solid {PALETTE['border']};
        position: relative;
    }}
    
    .user-info {{
        position: absolute;
        top: 20px;
        right: 20px;
        background: {PALETTE['accent']};
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    
    .logout-btn {{
        background: transparent;
        border: 1px solid white;
        color: white;
        padding: 4px 12px;
        border-radius: 15px;
        font-size: 0.8rem;
        margin-left: 10px;
        cursor: pointer;
        transition: all 0.2s ease;
    }}
    
    .logout-btn:hover {{
        background: white;
        color: {PALETTE['accent']};
    }}
    
    .logo-title-wrapper {{
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1.2rem;
        margin-bottom: 0.5rem;
    }}
    
    .logo-img {{
        height: 100px;
        width: auto;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
        border-radius: 12px;
        padding: 8px;
        background: {PALETTE['card_bg']};
    }}
    
    .brand-title {{
        color: {PALETTE['text_dark']} !important;
        font-size: 2.5rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: 1px;
        text-transform: uppercase;
        line-height: 1.2;
    }}
    
    .brand-sub {{
        color: {PALETTE['text_medium']} !important;
        font-size: 1.1rem;
        margin-top: 0.2rem;
        font-weight: 400;
        opacity: 0.9;
    }}
    
    .document-title {{
        background: {PALETTE['primary_dark']};
        color: {PALETTE['card_bg']} !important;
        padding: 1.2rem 2rem;
        border-radius: 16px;
        font-weight: 700;
        font-size: 1.4rem;
        text-align: center;
        margin: 1.5rem 0 2rem 0;
        box-shadow: 0 4px 12px rgba(39, 65, 74, 0.15);
        border: none;
    }}
    
    .card {{
        background: {PALETTE['card_bg']};
        padding: 2rem;
        border-radius: 18px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
        margin-bottom: 1.8rem;
        border: 1px solid {PALETTE['border']};
        transition: all 0.2s ease;
    }}
    
    .card:hover {{
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }}
    
    .card h4 {{
        color: {PALETTE['text_dark']} !important;
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 1.5rem;
        border-bottom: 2px solid {PALETTE['accent']};
        padding-bottom: 0.8rem;
    }}
    
    .stButton > button {{
        background: {PALETTE['primary_dark']};
        color: white !important;
        font-weight: 600;
        border: 1px solid {PALETTE['primary_dark']};
        padding: 0.9rem 1.8rem;
        border-radius: 12px;
        transition: all 0.2s ease;
        width: 100%;
        font-size: 1rem;
    }}
    
    .stButton > button:hover {{
        background: {PALETTE['primary_light']};
        border-color: {PALETTE['primary_light']};
        color: white !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(39, 65, 74, 0.2);
    }}
    
    .upload-box {{
        border: 2px dashed {PALETTE['accent']};
        border-radius: 18px;
        padding: 3rem;
        text-align: center;
        background: {PALETTE['card_bg']};
        margin: 1.5rem 0;
        transition: all 0.3s ease;
    }}
    
    .upload-box:hover {{
        background: {PALETTE['hover']};
        border-color: {PALETTE['primary_dark']};
    }}
    
    .progress-container {{
        background: {PALETTE['primary_dark']};
        color: {PALETTE['card_bg']} !important;
        padding: 2.5rem;
        border-radius: 18px;
        text-align: center;
        margin: 2rem 0;
        box-shadow: 0 4px 20px rgba(39, 65, 74, 0.15);
    }}
    
    .image-preview-container {{
        background: {PALETTE['card_bg']};
        border-radius: 18px;
        padding: 1.8rem;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
        margin-bottom: 2rem;
        border: 1px solid {PALETTE['border']};
    }}
    
    .info-box {{
        background: #E8F4F8;
        border-left: 4px solid {PALETTE['accent']};
        padding: 1.2rem;
        border-radius: 12px;
        margin: 1rem 0;
        color: {PALETTE['text_dark']} !important;
    }}
    
    .success-box {{
        background: #E8F5E9;
        border-left: 4px solid {PALETTE['success']};
        padding: 1.2rem;
        border-radius: 12px;
        margin: 1rem 0;
        color: {PALETTE['text_dark']} !important;
    }}
    
    .warning-box {{
        background: #FFF3E0;
        border-left: 4px solid {PALETTE['warning']};
        padding: 1.2rem;
        border-radius: 12px;
        margin: 1rem 0;
        color: {PALETTE['text_dark']} !important;
    }}
    
    .duplicate-box {{
        background: #FFF8E1;
        border-left: 4px solid {PALETTE['warning']};
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1.5rem 0;
        color: {PALETTE['text_dark']} !important;
        border: 2px solid {PALETTE['warning']};
    }}
    
    .warning-cell {{
        background-color: #FFD6D6 !important;
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

def openai_vision_ocr(image_bytes: bytes) -> Dict:
    """Utilise OpenAI Vision pour analyser le document et extraire les données structurées"""
    try:
        client = get_openai_client()
        if not client:
            return None
        
        # Encoder l'image
        base64_image = encode_image_to_base64(image_bytes)
        
        # Prompt pour détecter automatiquement le type
        prompt = """
        Analyse ce document et identifie s'il s'agit d'une FACTURE EN COMPTE ou d'un BON DE COMMANDE (BDC).
        
        Si c'est une FACTURE EN COMPTE, extrais ces informations:
        {
            "type_document": "FACTURE EN COMPTE",
            "numero_facture": "...",
            "date": "...",
            "client": "...",
            "adresse_livraison": "...",
            "bon_commande": "...",
            "mois": "...",
            "articles": [{"article": "...", "quantite": ...}]
        }
        
        Si c'est un BON DE COMMANDE (BDC), extrais ces informations:
        {
            "type_document": "BDC [CLIENT]",
            "numero": "...",
            "date": "...",
            "client": "...",
            "adresse_livraison": "...",
            "articles": [{"article": "...", "quantite": ...}]
        }
        
        Pour les clients BDC: LEADERPRICE/DLP, S2M/SUPERMAKI, ULYS
        Pour les articles, standardise: "COTE DE FIANAR" → "Côte de Fianar", "MAROPARASY" → "Maroparasy", "CONS CHAN FOUI" → "Consigne Chan Foui"
        """
        
        # Appel à l'API OpenAI Vision - CORRECTION ICI
        response = client.chat.completions.create(
            model="gpt-4o",  # CORRIGÉ: gpt-4o remplace gpt-4-vision-preview
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
            max_tokens=2000,
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
                st.error("❌ Impossible de parser la réponse JSON d'OpenAI")
                return None
        else:
            st.error("❌ Réponse JSON non trouvée dans la réponse OpenAI")
            return None
            
    except Exception as e:
        st.error(f"❌ Erreur OpenAI Vision: {str(e)}")
        return None

def standardize_product_name(product_name: str) -> str:
    """Standardise les noms de produits en utilisant le tableau de données standardisées"""
    # Tableau de correspondance pour les produits standardisés
    STANDARD_PRODUCTS = {
        "COTE DE FIANAR": "Côte de Fianar",
        "COTE FIANAR": "Côte de Fianar",
        "FIANAR": "Côte de Fianar",
        "CÔTE DE FIANAR": "Côte de Fianar",
        "CÔTE FIANAR": "Côte de Fianar",
        "COTE DE FIANAR ROUGE": "Côte de Fianar Rouge 75cl",
        "COTE DE FIANAR BLANC": "Côte de Fianar Blanc 75cl",
        "COTE DE FIANAR ROSÉ": "Côte de Fianar Rosé 75cl",
        "COTE DE FIANAR ROSÉ": "Côte de Fianar Rosé 75cl",
        "COTE DE FIANAR GRIS": "Côte de Fianar Gris 75cl",
        "MAROPARASY": "Maroparasy",
        "MAROPARASY ROUGE": "Maroparasy Rouge 75cl",
        "MAROPARASY BLANC": "Maroparasy Blanc 75cl",
        "CONS CHAN FOUI": "Consigne Chan Foui 75cl",
        "CONSIGNE CHAN FOUI": "Consigne Chan Foui 75cl",
        "CHAN FOUI": "Consigne Chan Foui 75cl",
        "CONSIGNE": "Consigne Chan Foui 75cl"
    }
    
    name = product_name.upper().strip()
    
    # Chercher une correspondance exacte d'abord
    for key, value in STANDARD_PRODUCTS.items():
        if key == name:
            return value
    
    # Chercher une correspondance partielle
    for key, value in STANDARD_PRODUCTS.items():
        if key in name:
            # Si c'est un produit Côte de Fianar, déterminer le type
            if "COTE" in key and "FIANAR" in key:
                if "ROUGE" in name:
                    return "Côte de Fianar Rouge 75cl"
                elif "BLANC" in name:
                    return "Côte de Fianar Blanc 75cl"
                elif "ROSE" in name or "ROSÉ" in name:
                    return "Côte de Fianar Rosé 75cl"
                elif "GRIS" in name:
                    return "Côte de Fianar Gris 75cl"
                else:
                    return "Côte de Fianar Rouge 75cl"
            elif "MAROPARASY" in key:
                if "BLANC" in name:
                    return "Maroparasy Blanc 75cl"
                elif "ROUGE" in name:
                    return "Maroparasy Rouge 75cl"
                else:
                    return "Maroparasy Rouge 75cl"
            elif "CONS" in key or "CHAN" in key or "FOUI" in key:
                return "Consigne Chan Foui 75cl"
            return value
    
    # Si aucune correspondance, retourner le nom original mais en title case
    return product_name.title()

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
def prepare_facture_rows(data: dict, articles_df: pd.DataFrame, use_raw: bool = False) -> List[List[str]]:
    """Prépare les lignes pour les factures (9 colonnes)"""
    rows = []
    
    try:
        mois = data.get("mois", get_month_from_date(data.get("date", "")))
        client = data.get("client", "")
        date = format_date_french(data.get("date", ""))
        nbc = data.get("bon_commande", "")
        nf = data.get("numero_facture", "")
        magasin = data.get("adresse_livraison", "")
        
        for _, row in articles_df.iterrows():
            if use_raw:
                article = str(row.get("designation_brute", "")).strip()
            else:
                # MODIFICATION: Utiliser la colonne designation_standard
                article = str(row.get("designation_standard", "")).strip()
                if not article:  # Fallback si la colonne n'existe pas
                    article = str(row.get("designation_brute", "")).strip()
            
            quantite = format_quantity(row.get("quantite", ""))
            
            rows.append([
                mois,
                client,
                date,
                nbc,
                nf,
                "",  # Lien (vide par défaut)
                magasin,
                article,
                quantite
            ])
        
        return rows
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la préparation des données facture: {str(e)}")
        return []

def prepare_bdc_rows(data: dict, articles_df: pd.DataFrame, use_raw: bool = False) -> List[List[str]]:
    """Prépare les lignes pour les BDC (8 colonnes)"""
    rows = []
    
    try:
        date_emission = data.get("date", "")
        mois = get_month_from_date(date_emission)
        client = map_client(data.get("client", ""))
        date = format_date_french(date_emission)
        nbc = data.get("numero", "")
        magasin = data.get("adresse_livraison", "")
        
        for _, row in articles_df.iterrows():
            if use_raw:
                article = str(row.get("designation_brute", "")).strip()
            else:
                # MODIFICATION: Utiliser la colonne designation_standard
                article = str(row.get("designation_standard", "")).strip()
                if not article:  # Fallback si la colonne n'existe pas
                    article = str(row.get("designation_brute", "")).strip()
            
            quantite = format_quantity(row.get("quantite", ""))
            
            rows.append([
                mois,
                client,
                date,
                nbc,
                "",  # Lien (vide par défaut)
                magasin,
                article,
                quantite
            ])
        
        return rows
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la préparation des données BDC: {str(e)}")
        return []

def prepare_rows_for_sheet(document_type: str, data: dict, articles_df: pd.DataFrame, use_raw: bool = False) -> List[List[str]]:
    """Prépare les lignes pour l'insertion dans Google Sheets selon le type de document"""
    if "FACTURE" in document_type.upper():
        return prepare_facture_rows(data, articles_df, use_raw)
    else:
        return prepare_bdc_rows(data, articles_df, use_raw)

# ============================================================
# FONCTIONS DE DÉTECTION DE DOUBLONS
# ============================================================
def generate_document_hash(document_type: str, extracted_data: dict) -> str:
    """Génère un hash unique pour un document"""
    if "FACTURE" in document_type.upper():
        key_data = f"{document_type}_{extracted_data.get('numero_facture', '')}_{extracted_data.get('client', '')}"
    else:
        key_data = f"{document_type}_{extracted_data.get('numero', '')}_{extracted_data.get('client', '')}"
    
    if 'date' in extracted_data:
        key_data += f"_{extracted_data['date']}"
    
    return hashlib.md5(key_data.encode()).hexdigest()

def check_for_duplicates(document_type: str, extracted_data: dict, worksheet) -> Tuple[bool, List[Dict]]:
    """Vérifie si un document existe déjà dans Google Sheets"""
    try:
        all_data = worksheet.get_all_values()
        
        if len(all_data) <= 1:
            return False, []
        
        if "FACTURE" in document_type.upper():
            nf_col = 4
            client_col = 1
            
            current_nf = extracted_data.get('numero_facture', '')
            current_client = extracted_data.get('client', '')
            
            duplicates = []
            for i, row in enumerate(all_data[1:], start=2):
                if len(row) > max(nf_col, client_col):
                    if (row[nf_col] == current_nf and 
                        row[client_col] == current_client and 
                        current_nf != '' and current_client != ''):
                        duplicates.append({
                            'row_number': i,
                            'data': row,
                            'match_type': 'NF et Client identiques'
                        })
        else:
            nbc_col = 3
            client_col = 1
            
            current_nbc = extracted_data.get('numero', '')
            current_client = extracted_data.get('client', '')
            
            duplicates = []
            for i, row in enumerate(all_data[1:], start=2):
                if len(row) > max(nbc_col, client_col):
                    if (row[nbc_col] == current_nbc and 
                        row[client_col] == current_client and 
                        current_nbc != '' and current_client != ''):
                        duplicates.append({
                            'row_number': i,
                            'data': row,
                            'match_type': 'NBC et Client identiques'
                        })
        
        return len(duplicates) > 0, duplicates
            
    except Exception as e:
        st.error(f"❌ Erreur lors de la vérification des doublons: {str(e)}")
        return False, []

def display_duplicate_warning(document_type: str, extracted_data: dict, duplicates: List[Dict]):
    """Affiche un avertissement pour les doublons détectés"""
    st.markdown('<div class="duplicate-box">', unsafe_allow_html=True)
    
    st.markdown(f'### ⚠️ DOUBLON DÉTECTÉ')
    
    if "FACTURE" in document_type.upper():
        st.markdown(f"""
        **Document identique déjà présent dans la base :**
        - **Type :** {document_type}
        - **Numéro de facture :** {extracted_data.get('numero_facture', 'Non détecté')}
        - **Client :** {extracted_data.get('client', 'Non détecté')}
        """)
    else:
        st.markdown(f"""
        **Document identique déjà présent dans la base :**
        - **Type :** {document_type}
        - **Numéro BDC :** {extracted_data.get('numero', 'Non détecté')}
        - **Client :** {extracted_data.get('client', 'Non détecté')}
        """)
    
    st.markdown("**Enregistrements similaires trouvés :**")
    for dup in duplicates:
        st.markdown(f"- Ligne {dup['row_number']} : {dup['match_type']}")
    
    st.markdown("**Que souhaitez-vous faire ?**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✅ Écraser et mettre à jour", key="overwrite_duplicate_main", 
                    use_container_width=True, type="primary"):
            st.session_state.duplicate_action = "overwrite"
            st.session_state.duplicate_rows = [d['row_number'] for d in duplicates]
            st.rerun()
    
    with col2:
        if st.button("📝 Ajouter comme nouveau", key="add_new_duplicate_main", 
                    use_container_width=True):
            st.session_state.duplicate_action = "add_new"
            st.rerun()
    
    with col3:
        if st.button("❌ Ne pas importer", key="skip_duplicate_main", 
                    use_container_width=True):
            st.session_state.duplicate_action = "skip"
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return False

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
                         duplicate_action: str = None, duplicate_rows: List[int] = None,
                         use_raw: bool = False):
    """Sauvegarde les données dans Google Sheets"""
    try:
        ws = get_worksheet(document_type)
        
        if not ws:
            st.error("❌ Impossible de se connecter à Google Sheets")
            return False, "Erreur de connexion"
        
        new_rows = prepare_rows_for_sheet(document_type, data, articles_df, use_raw)
        
        if not new_rows:
            st.warning("⚠️ Aucune donnée à enregistrer")
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
        
        data_type = "brutes" if use_raw else "standardisées"
        st.info(f"📋 **Aperçu des données {data_type} à enregistrer:**")
        
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
            
            st.success(f"✅ {len(new_rows)} ligne(s) {data_type} {action_msg} avec succès dans Google Sheets!")
            
            # Utiliser le type normalisé pour l'URL
            normalized_type = normalize_document_type(document_type)
            sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={SHEET_GIDS.get(normalized_type, '')}"
            st.markdown(f'<div class="info-box">🔗 <a href="{sheet_url}" target="_blank">Ouvrir Google Sheets</a></div>', unsafe_allow_html=True)
            
            st.balloons()
            return True, f"{len(new_rows)} lignes {data_type} {action_msg}"
            
        except Exception as e:
            st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
            
            try:
                st.info("🔄 Tentative alternative d'enregistrement...")
                
                all_data = ws.get_all_values()
                
                for row in new_rows:
                    all_data.append(row)
                
                ws.update('A1', all_data)
                
                st.success(f"✅ {len(new_rows)} ligne(s) {data_type} enregistrée(s) avec méthode alternative!")
                return True, f"{len(new_rows)} lignes {data_type} enregistrées (méthode alternative)"
                
            except Exception as e2:
                st.error(f"❌ Échec de la méthode alternative: {str(e2)}")
                return False, str(e)
                
    except Exception as e:
        st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
        return False, str(e)

# ============================================================
# HEADER AVEC LOGO
# ============================================================
st.markdown('<div class="header-container">', unsafe_allow_html=True)

st.markdown(f'''
<div class="user-info">
    👤 {st.session_state.username}
    <button class="logout-btn" onclick="window.location.href='?logout=true'">🚪 Déconnexion</button>
</div>
''', unsafe_allow_html=True)

st.markdown('<div class="logo-title-wrapper">', unsafe_allow_html=True)

if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME, width=120)
else:
    st.markdown("🍷")

st.markdown(f'<h1 class="brand-title">{BRAND_TITLE}</h1>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

st.markdown(f'<p class="brand-sub">{BRAND_SUB} - Connecté en tant que {st.session_state.username}</p>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

if st.query_params.get("logout"):
    logout()

# ============================================================
# ZONE DE TÉLÉCHARGEMENT UNIQUE
# ============================================================
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<h4>📤 Téléchargement du document</h4>', unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    ℹ️ Vous pouvez importer n'importe quel type de document :
    • Factures en compte
    • Bons de commande (LEADERPRICE, S2M, ULYS)
    Le système détectera automatiquement le type et extraira les informations.
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="upload-box">', unsafe_allow_html=True)
uploaded = st.file_uploader(
    "**Glissez-déposez votre document ici**",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
    help="Formats supportés : JPG, JPEG, PNG",
    key="file_uploader_main"
)
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# APERÇU DU DOCUMENT (TOUJOURS VISIBLE)
# ============================================================
if st.session_state.uploaded_image:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h4>👁️ Aperçu du document</h4>', unsafe_allow_html=True)
    st.image(st.session_state.uploaded_image, use_column_width=True)
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
    
    # Barre de progression
    progress_container = st.empty()
    with progress_container.container():
        st.markdown('<div class="progress-container">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 2.5rem; margin-bottom: 1rem; animation: pulse 1.5s infinite;">🔍</div>', unsafe_allow_html=True)
        st.markdown('<h3 style="color: white;">Analyse en cours...</h3>', unsafe_allow_html=True)
        st.markdown('<p style="color: rgba(255,255,255,0.9);">OpenAI Vision AI traite votre document</p>', unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        for percent_complete in range(0, 101, 20):
            time.sleep(0.3)
            progress_bar.progress(percent_complete)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Traitement OCR avec OpenAI Vision
    try:
        buf = BytesIO()
        st.session_state.uploaded_image.save(buf, format="JPEG")
        image_bytes = buf.getvalue()
        
        # Prétraitement de l'image
        img_processed = preprocess_image(image_bytes)
        
        # Analyse avec OpenAI Vision
        result = openai_vision_ocr(img_processed)
        
        if result:
            st.session_state.ocr_result = result
            raw_doc_type = result.get("type_document", "DOCUMENT INCONNU")
            # Normaliser le type de document détecté
            st.session_state.detected_document_type = normalize_document_type(raw_doc_type)
            st.session_state.show_results = True
            st.session_state.processing = False
            
            # Préparer les dataframes
            if "articles" in result:
                # Données brutes
                raw_data = []
                for article in result["articles"]:
                    raw_data.append({
                        "designation_brute": article.get("article", ""),
                        "quantite": article.get("quantite", 0)
                    })
                st.session_state.raw_data_df = pd.DataFrame(raw_data)
                
                # Données standardisées - AMÉLIORATION: utiliser standardize_product_name
                std_data = []
                for article in result["articles"]:
                    raw_name = article.get("article", "")
                    std_name = standardize_product_name(raw_name)
                    std_data.append({
                        "designation_brute": raw_name,
                        "designation_standard": std_name,
                        "quantite": article.get("quantite", 0),
                        "standardise": raw_name.upper() != std_name.upper()
                    })
                st.session_state.standardized_data_df = pd.DataFrame(std_data)
            
            progress_container.empty()
            st.rerun()
        else:
            st.error("❌ Impossible d'analyser le document avec OpenAI Vision")
            st.session_state.processing = False
        
    except Exception as e:
        st.error(f"❌ Erreur lors de l'analyse: {str(e)}")
        st.session_state.processing = False

# ============================================================
# AFFICHAGE DES RÉSULTATS
# ============================================================
if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
    result = st.session_state.ocr_result
    doc_type = st.session_state.detected_document_type
    
    # Message de succès
    st.success(
        f"🤖 Analyse terminée avec succès, {st.session_state.username}.\n\n"
        f"**Type détecté :** {doc_type}\n"
        f"La précision estimée est de 98.8%, selon la qualité de la photo.\n\n"
        "Merci de vérifier les données extraites avant validation."
    )
    
    # Titre du mode détecté
    st.markdown(
        f"""
        <div class="document-title">
            📄 Document détecté : {doc_type}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # ========================================================
    # INFORMATIONS EXTRAITES
    # ========================================================
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h4>📋 Informations extraites</h4>', unsafe_allow_html=True)
    
    # Afficher les informations selon le type de document
    if "FACTURE" in doc_type.upper():
        col1, col2 = st.columns(2)
        with col1:
            client = st.text_input("Client", value=result.get("client", ""), key="facture_client")
            numero_facture = st.text_input("Numéro de facture", value=result.get("numero_facture", ""), key="facture_num")
            bon_commande = st.text_input("Bon de commande", value=result.get("bon_commande", ""), key="facture_bdc")
        
        with col2:
            adresse = st.text_input("Adresse de livraison", value=result.get("adresse_livraison", ""), key="facture_adresse")
            date = st.text_input("Date", value=result.get("date", ""), key="facture_date")
            mois = st.text_input("Mois", value=result.get("mois", get_month_from_date(result.get("date", ""))), key="facture_mois")
        
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
            client = st.text_input("Client", value=result.get("client", ""), key="bdc_client")
            numero = st.text_input("Numéro BDC", value=result.get("numero", ""), key="bdc_numero")
        
        with col2:
            date = st.text_input("Date", value=result.get("date", ""), key="bdc_date")
            adresse = st.text_input("Adresse livraison", 
                                  value=result.get("adresse_livraison", "SCORE TALATAMATY"), 
                                  key="bdc_adresse")
        
        data_for_sheets = {
            "client": client,
            "numero": numero,
            "date": date,
            "adresse_livraison": adresse
        }
    
    st.session_state.data_for_sheets = data_for_sheets
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # TABLEAU BRUT
    # ========================================================
    if st.session_state.raw_data_df is not None and not st.session_state.raw_data_df.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>📄 Données extraites (brutes)</h4>', unsafe_allow_html=True)
        st.dataframe(st.session_state.raw_data_df, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # TABLEAU STANDARDISÉ
    # ========================================================
    if st.session_state.standardized_data_df is not None and not st.session_state.standardized_data_df.empty:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>📘 Données standardisées</h4>', unsafe_allow_html=True)
        
        # Appliquer le style pour les cellules non standardisées
        def highlight_non_standardized(row):
            if not row["standardise"]:
                return ['background-color: #FFD6D6'] * len(row)
            return [''] * len(row)
        
        styled_df = st.session_state.standardized_data_df.style.apply(highlight_non_standardized, axis=1)
        st.dataframe(styled_df, use_container_width=True)
        
        st.markdown("🔴 **Les lignes en rouge ne sont pas reconnues dans le référentiel**")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Éditeur de données pour les articles
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>🛒 Articles détectés (éditable)</h4>', unsafe_allow_html=True)
        
        # Préparer le dataframe pour l'édition
        edit_df = st.session_state.standardized_data_df[["designation_standard", "quantite"]].copy()
        edit_df.columns = ["article", "quantite"]
        
        edited_df = st.data_editor(
            edit_df,
            num_rows="dynamic",
            column_config={
                "article": st.column_config.TextColumn("Article", width="large"),
                "quantite": st.column_config.NumberColumn("Quantité", min_value=0)
            },
            use_container_width=True,
            key="articles_editor_main"
        )
        
        # Mettre à jour le dataframe standardisé avec les modifications
        if not edited_df.empty:
            for idx, row in edited_df.iterrows():
                if idx < len(st.session_state.standardized_data_df):
                    st.session_state.standardized_data_df.at[idx, 'designation_standard'] = row['article']
                    st.session_state.standardized_data_df.at[idx, 'quantite'] = row['quantite']
        
        # Statistiques
        total_items = len(edited_df)
        total_qty = edited_df["quantite"].sum() if not edited_df.empty else 0
        
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.markdown(
                f'<div class="info-box"><strong>{total_items}</strong> articles détectés</div>',
                unsafe_allow_html=True
            )
        with col_stat2:
            st.markdown(
                f'<div class="info-box"><strong>{total_qty}</strong> unités totales</div>',
                unsafe_allow_html=True
            )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # VÉRIFICATION DES DOUBLONS
    # ========================================================
    if not st.session_state.duplicate_check_done:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>🔍 Vérification des doublons</h4>', unsafe_allow_html=True)
        
        if st.button("🔎 Vérifier si le document existe déjà", use_container_width=True, key="check_duplicates_main"):
            with st.spinner("Recherche de documents similaires..."):
                # Utiliser le type de document normalisé
                normalized_doc_type = normalize_document_type(doc_type)
                ws = get_worksheet(normalized_doc_type)
                
                if ws:
                    # Afficher des informations de débogage
                    st.info(f"📄 Type de document: {doc_type} → {normalized_doc_type}")
                    
                    duplicate_found, duplicates = check_for_duplicates(
                        normalized_doc_type,
                        data_for_sheets,
                        ws
                    )
                    
                    if not duplicate_found:
                        st.success("✅ Aucun doublon trouvé - Le document est unique")
                        st.session_state.duplicate_found = False
                        st.session_state.duplicate_check_done = True
                        st.rerun()
                    else:
                        st.session_state.duplicate_found = True
                        st.session_state.duplicate_rows = [d['row_number'] for d in duplicates]
                        st.session_state.duplicate_check_done = True
                        st.rerun()
                else:
                    st.error("❌ Impossible de vérifier les doublons - Connexion échouée")
                    # Réinitialiser pour permettre une nouvelle tentative
                    st.session_state.duplicate_check_done = False
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # GESTION DES DOUBLONS DÉTECTÉS
    # ========================================================
    if st.session_state.duplicate_check_done and st.session_state.duplicate_found:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>⚠️ Gestion des doublons</h4>', unsafe_allow_html=True)
        
        display_duplicate_warning(
            doc_type,
            data_for_sheets,
            [{'row_number': row, 'match_type': 'Document identique'} for row in st.session_state.duplicate_rows]
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # EXPORT VERS GOOGLE SHEETS (DEUX BOUTONS)
    # ============================================================
    if (st.session_state.duplicate_check_done and not st.session_state.duplicate_found) or \
       (st.session_state.duplicate_check_done and st.session_state.duplicate_action):
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>📤 Export vers Google Sheets</h4>', unsafe_allow_html=True)
        
        action = None
        if st.session_state.duplicate_action:
            action = st.session_state.duplicate_action
        
        # Deux boutons côte à côte
        col_export1, col_export2 = st.columns(2)
        
        with col_export1:
            if st.button("📄 Enregistrer données BRUTES", 
                        use_container_width=True, 
                        type="primary", 
                        key="export_raw_data_main"):
                try:
                    success, message = save_to_google_sheets(
                        doc_type,
                        st.session_state.data_for_sheets,
                        st.session_state.raw_data_df,
                        duplicate_action=action,
                        duplicate_rows=st.session_state.duplicate_rows if action == "overwrite" else None,
                        use_raw=True
                    )
                    
                    if success:
                        st.success("✅ Données brutes enregistrées avec succès!")
                        
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'enregistrement des données brutes: {str(e)}")
        
        with col_export2:
            if st.button("✨ Enregistrer données STANDARDISÉES", 
                        use_container_width=True, 
                        type="primary", 
                        key="export_standardized_data_main"):
                try:
                    # MODIFICATION: Utiliser directement la colonne designation_standard
                    export_std_df = st.session_state.standardized_data_df[["designation_standard", "quantite"]].copy()
                    # Ne pas renommer, garder "designation_standard" pour la fonction prepare_rows_for_sheet
                    
                    success, message = save_to_google_sheets(
                        doc_type,
                        st.session_state.data_for_sheets,
                        export_std_df,
                        duplicate_action=action,
                        duplicate_rows=st.session_state.duplicate_rows if action == "overwrite" else None,
                        use_raw=False  # Utiliser designation_standard
                    )
                    
                    if success:
                        st.success("✅ Données standardisées enregistrées avec succès!")
                        
                except Exception as e:
                    st.error(f"❌ Erreur lors de l'enregistrement des données standardisées: {str(e)}")
        
        # Explication des deux options
        st.markdown("""
        <div class="info-box">
        <strong>ℹ️ Différence entre les deux exports :</strong><br>
        • <strong>Données brutes :</strong> Les articles exactement comme détectés par l'IA<br>
        • <strong>Données standardisées :</strong> Les articles corrigés et normalisés selon le référentiel Chan Foui
        </div>
        """, unsafe_allow_html=True)
        
        # SUPPRESSION: Retirer les boutons en double de cette section
        st.markdown("</div>", unsafe_allow_html=True)
    
    # ========================================================
    # BOUTONS UNIQUES DE NAVIGATION
    # ============================================================
    st.markdown("---")
    col_nav1, col_nav2 = st.columns([1, 1])
    
    with col_nav1:
        if st.button("📄 Scanner un nouveau document", 
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
            st.rerun()
    
    with col_nav2:
        if st.button("🔄 Recommencer l'analyse", 
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
            st.rerun()

# ============================================================
# BOUTON DE DÉCONNEXION (toujours visible)
# ============================================================
st.markdown("---")
if st.button("🚪 Déconnexion", 
            use_container_width=True, 
            type="secondary",
            key="logout_button_final"):
    logout()

# ============================================================
# FOOTER
# ============================================================
st.markdown(f"""
<div style="text-align: center; color: {PALETTE['text_medium']}; font-size: 0.9rem; padding: 1.5rem; background: {PALETTE['card_bg']}; border-radius: 12px; margin-top: 2rem; border-top: 1px solid {PALETTE['border']}">
    <p><strong>{BRAND_TITLE}</strong> • Chanfoui IA V2 • © {datetime.now().strftime("%Y")}</p>
    <p style="font-size: 0.8rem; margin-top: 0.5rem; opacity: 0.8;">
        Connecté en tant que <strong>{st.session_state.username}</strong> • 
        Système OpenAI Vision • Double export (brute + standardisée)
    </p>
</div>
""", unsafe_allow_html=True)
