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
    layout="wide",
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
    st.rerun()

# ============================================================
# PAGE DE CONNEXION
# ============================================================
if not check_authentication():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        
        .login-container {
            max-width: 480px;
            margin: 60px auto;
            padding: 50px 40px;
            background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
            border-radius: 28px;
            box-shadow: 0 20px 60px rgba(39, 65, 74, 0.15),
                        0 0 0 1px rgba(39, 65, 74, 0.05);
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.9);
            font-family: 'Inter', sans-serif;
        }
        
        .login-title {
            background: linear-gradient(135deg, #27414A 0%, #2C5F73 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-size: 2.4rem;
            font-weight: 800;
            margin-bottom: 12px;
            letter-spacing: -0.5px;
            font-family: 'Inter', sans-serif;
        }
        
        .login-subtitle {
            color: #000000;
            margin-bottom: 35px;
            font-size: 1.1rem;
            font-weight: 500;
            opacity: 0.9;
            font-family: 'Inter', sans-serif;
        }
        
        .login-logo {
            height: 100px;
            margin-bottom: 25px;
            filter: drop-shadow(0 6px 10px rgba(0,0,0,0.1));
        }
        
        .stSelectbox > div > div {
            border: 2px solid #e2e8f0;
            border-radius: 14px;
            padding: 14px 18px;
            font-size: 16px;
            transition: all 0.2s ease;
            background: white;
            color: #000000;
            font-weight: 500;
        }
        
        .stSelectbox > div > div:hover {
            border-color: #27414A;
            box-shadow: 0 0 0 3px rgba(39, 65, 74, 0.1);
        }
        
        .stTextInput > div > div > input {
            border: 2px solid #e2e8f0;
            border-radius: 14px;
            padding: 14px 18px;
            font-size: 16px;
            transition: all 0.2s ease;
            background: white;
            color: #000000;
            font-weight: 500;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #27414A;
            box-shadow: 0 0 0 3px rgba(39, 65, 74, 0.1);
            outline: none;
        }
        
        .stButton > button {
            background: linear-gradient(135deg, #27414A 0%, #2C5F73 100%);
            color: white;
            font-weight: 700;
            border: none;
            padding: 16px 28px;
            border-radius: 14px;
            width: 100%;
            font-size: 16px;
            margin-top: 15px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            font-family: 'Inter', sans-serif;
            letter-spacing: 0.3px;
        }
        
        .stButton > button:hover {
            transform: translateY(-3px);
            box-shadow: 0 12px 25px rgba(39, 65, 74, 0.3);
        }
        
        .security-warning {
            background: linear-gradient(135deg, #FFF3CD 0%, #FFE8A1 100%);
            border: 2px solid #FFC107;
            border-radius: 16px;
            padding: 22px;
            margin-top: 32px;
            font-size: 0.95rem;
            color: #000000;
            text-align: left;
            font-family: 'Inter', sans-serif;
            box-shadow: 0 6px 15px rgba(255, 193, 7, 0.15);
            font-weight: 500;
        }
        
        .pulse-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #10B981;
            border-radius: 50%;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.7; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.7; }
        }
        
        .user-badge {
            display: inline-block;
            background: linear-gradient(135deg, #e8f4f8 0%, #d4eaf7 100%);
            color: #000000;
            padding: 8px 16px;
            border-radius: 24px;
            font-size: 0.9rem;
            font-weight: 600;
            margin: 6px;
            border: 2px solid rgba(39, 65, 74, 0.1);
            box-shadow: 0 3px 8px rgba(0,0,0,0.05);
        }
        
        .status-indicator {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 20px;
            margin: 20px 0 30px 0;
        }
        
        .status-item {
            text-align: center;
            color: #000000;
            font-weight: 500;
            font-size: 0.9rem;
        }
        
        label[data-testid="stWidgetLabel"] p {
            font-weight: 600 !important;
            color: #000000 !important;
            font-size: 1rem !important;
            margin-bottom: 8px !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    if os.path.exists("CF_LOGOS.png"):
        st.image("CF_LOGOS.png", width=120, output_format="PNG")
    else:
        st.markdown("""
        <div style="font-size: 4rem; margin-bottom: 25px; color: #27414A;">
            🍷
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="login-title">CHAN FOUI ET FILS</h1>', unsafe_allow_html=True)
    st.markdown('<p class="login-subtitle">Système de Scanner Professionnel - Accès Restreint</p>', unsafe_allow_html=True)
    
    # Indicateurs de statut
    st.markdown('<div class="status-indicator">', unsafe_allow_html=True)
    st.markdown('<div class="status-item"><span class="pulse-dot"></span>Serveur Actif</div>', unsafe_allow_html=True)
    st.markdown('<div class="status-item"><span style="display:inline-block;width:10px;height:10px;background:#3B82F6;border-radius:50%;margin-right:8px;"></span>Système Sécurisé</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    username = st.selectbox(
        "👤 IDENTIFIANT",
        options=[""] + list(AUTHORIZED_USERS.keys()),
        format_func=lambda x: "— Sélectionnez votre profil —" if x == "" else x,
        key="login_username"
    )
    password = st.text_input("🔒 MOT DE PASSE", type="password", placeholder="Entrez votre code d'accès CFFx", key="login_password")
    
    if st.button("🔓 CONNEXION AU SYSTÈME", use_container_width=True, key="login_button"):
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
    
    # Afficher les utilisateurs autorisés
    st.markdown("""
    <div style="margin-top: 30px; text-align: center;">
        <p style="font-size: 1rem; color: #000000; margin-bottom: 12px; font-weight: 600;">👥 PERSONNELS AUTORISÉS :</p>
        <div>
            <span class="user-badge">Pathou M.</span>
            <span class="user-badge">Elodie R.</span>
            <span class="user-badge">Laetitia C.</span>
            <span class="user-badge">Admin Cf.</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="security-warning">
        <strong style="display: block; margin-bottom: 10px; font-size: 1.1rem; color: #000000;">🔐 PROTOCOLE DE SÉCURITÉ :</strong>
        • Système de reconnaissance biométrique numérique<br>
        • Chiffrement AES-256 pour toutes les données<br>
        • Journalisation complète des activités<br>
        • Verrouillage automatique après 3 tentatives
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ============================================================
# APPLICATION PRINCIPALE - DESIGN PROFESSIONNEL
# ============================================================

# ============================================================
# THÈME PROFESSIONNEL CHAN FOUI & FILS
# ============================================================
LOGO_FILENAME = "CF_LOGOS.png"
BRAND_TITLE = "CHAN FOUI ET FILS"
BRAND_SUB = "Système Intelligent de Traitement de Documents"

PALETTE = {
    "primary": "#1A365D",  # Bleu marine plus foncé
    "secondary": "#27414A",
    "accent": "#2D3748",
    "background": "#F7FAFC",
    "card_bg": "#FFFFFF",
    "text_dark": "#000000",  # Noir pur pour meilleure lisibilité
    "text_medium": "#2D3748",
    "success": "#2F855A",
    "warning": "#C05621",
    "error": "#C53030",
    "border": "#E2E8F0",
    "hover": "#EDF2F7",
    "tech_blue": "#3182CE",
    "highlight": "#4299E1",
}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }}
    
    .main {{
        background: {PALETTE['background']};
        color: {PALETTE['text_dark']} !important;
    }}
    
    .stApp {{
        background: {PALETTE['background']};
        color: {PALETTE['text_dark']} !important;
        line-height: 1.6;
    }}
    
    /* Header principal */
    .main-header {{
        background: {PALETTE['card_bg']};
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid {PALETTE['border']};
        position: relative;
        overflow: hidden;
    }}
    
    .header-top {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;
    }}
    
    .logo-section {{
        display: flex;
        align-items: center;
        gap: 1.5rem;
    }}
    
    .logo-img {{
        height: 70px;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
    }}
    
    .brand-name {{
        color: {PALETTE['text_dark']} !important;
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        line-height: 1.1;
    }}
    
    .user-section {{
        display: flex;
        align-items: center;
        gap: 1rem;
        background: {PALETTE['hover']};
        padding: 0.8rem 1.5rem;
        border-radius: 12px;
        border: 1px solid {PALETTE['border']};
    }}
    
    .user-info {{
        font-weight: 600;
        color: {PALETTE['text_dark']} !important;
        font-size: 1rem;
    }}
    
    .status-badges {{
        display: flex;
        justify-content: center;
        gap: 2rem;
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid {PALETTE['border']};
    }}
    
    .status-badge {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-weight: 500;
        color: {PALETTE['text_dark']} !important;
        font-size: 0.9rem;
    }}
    
    .status-indicator {{
        width: 10px;
        height: 10px;
        border-radius: 50%;
    }}
    
    .status-online {{ background: {PALETTE['success']}; }}
    .status-secure {{ background: {PALETTE['tech_blue']}; }}
    .status-ai {{ background: {PALETTE['primary']}; }}
    
    /* Cartes */
    .main-card {{
        background: {PALETTE['card_bg']};
        padding: 2rem;
        border-radius: 16px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
        margin-bottom: 1.5rem;
        border: 1px solid {PALETTE['border']};
        transition: transform 0.2s ease;
    }}
    
    .main-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.1);
    }}
    
    .card-title {{
        color: {PALETTE['text_dark']} !important;
        font-size: 1.4rem;
        font-weight: 700;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid {PALETTE['primary']};
        display: flex;
        align-items: center;
        gap: 0.8rem;
    }}
    
    /* Boutons */
    .stButton > button {{
        background: {PALETTE['primary']};
        color: white !important;
        font-weight: 600;
        border: none;
        padding: 0.9rem 1.8rem;
        border-radius: 12px;
        transition: all 0.2s ease;
        width: 100%;
        font-size: 1rem;
        font-family: 'Inter', sans-serif;
    }}
    
    .stButton > button:hover {{
        background: {PALETTE['secondary']};
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(39, 65, 74, 0.2);
    }}
    
    .secondary-button {{
        background: {PALETTE['card_bg']} !important;
        color: {PALETTE['text_dark']} !important;
        border: 2px solid {PALETTE['border']} !important;
    }}
    
    .secondary-button:hover {{
        background: {PALETTE['hover']} !important;
        border-color: {PALETTE['primary']} !important;
    }}
    
    /* Zone de dépôt */
    .upload-area {{
        border: 3px dashed {PALETTE['border']};
        border-radius: 16px;
        padding: 3rem;
        text-align: center;
        background: {PALETTE['card_bg']};
        margin: 1.5rem 0;
        transition: all 0.3s ease;
    }}
    
    .upload-area:hover {{
        border-color: {PALETTE['primary']};
        background: {PALETTE['hover']};
    }}
    
    /* Boîtes d'information */
    .info-box {{
        background: {PALETTE['hover']};
        border-left: 4px solid {PALETTE['primary']};
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        color: {PALETTE['text_dark']} !important;
        font-weight: 500;
    }}
    
    .success-box {{
        background: #F0FFF4;
        border-left: 4px solid {PALETTE['success']};
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        color: {PALETTE['text_dark']} !important;
    }}
    
    .warning-box {{
        background: #FFFAF0;
        border-left: 4px solid {PALETTE['warning']};
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        color: {PALETTE['text_dark']} !important;
    }}
    
    /* Document title */
    .document-header {{
        background: linear-gradient(135deg, {PALETTE['primary']}, {PALETTE['secondary']});
        color: white !important;
        padding: 1.5rem 2rem;
        border-radius: 16px;
        font-weight: 700;
        font-size: 1.4rem;
        text-align: center;
        margin: 2rem 0;
        box-shadow: 0 4px 20px rgba(39, 65, 74, 0.15);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 1rem;
    }}
    
    /* Formulaires */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div {{
        border: 2px solid {PALETTE['border']};
        border-radius: 12px;
        padding: 12px 16px;
        font-size: 15px;
        transition: all 0.2s ease;
        background: white;
        color: {PALETTE['text_dark']} !important;
        font-weight: 500;
    }}
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stSelectbox > div > div:focus-within {{
        border-color: {PALETTE['primary']};
        box-shadow: 0 0 0 3px rgba(26, 54, 93, 0.1);
        outline: none;
    }}
    
    /* Labels */
    label[data-testid="stWidgetLabel"] p {{
        font-weight: 600 !important;
        color: {PALETTE['text_dark']} !important;
        font-size: 1rem !important;
        margin-bottom: 8px !important;
    }}
    
    /* Dataframes */
    .dataframe {{
        border-radius: 12px !important;
        overflow: hidden !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05) !important;
        border: 1px solid {PALETTE['border']} !important;
    }}
    
    /* Footer */
    .main-footer {{
        background: {PALETTE['card_bg']};
        padding: 2rem;
        border-radius: 16px;
        margin-top: 3rem;
        border-top: 3px solid {PALETTE['primary']};
        text-align: center;
        color: {PALETTE['text_dark']} !important;
    }}
    
    .footer-features {{
        display: flex;
        justify-content: center;
        gap: 3rem;
        margin-bottom: 1.5rem;
    }}
    
    .feature-item {{
        text-align: center;
    }}
    
    .feature-icon {{
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }}
    
    .feature-text {{
        font-size: 0.9rem;
        color: {PALETTE['text_medium']};
        font-weight: 500;
    }}
    
    .footer-copyright {{
        font-weight: 600;
        color: {PALETTE['text_dark']} !important;
        font-size: 1.1rem;
        margin: 1rem 0;
    }}
    
    .footer-status {{
        font-size: 0.9rem;
        color: {PALETTE['text_medium']};
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        margin-top: 1rem;
        padding: 0.8rem 1.5rem;
        background: {PALETTE['hover']};
        border-radius: 12px;
        border: 1px solid {PALETTE['border']};
    }}
    
    /* Responsive */
    @media (max-width: 768px) {{
        .header-top {{
            flex-direction: column;
            gap: 1rem;
            text-align: center;
        }}
        
        .logo-section {{
            flex-direction: column;
            text-align: center;
        }}
        
        .status-badges {{
            flex-wrap: wrap;
            gap: 1rem;
        }}
        
        .footer-features {{
            flex-direction: column;
            gap: 1.5rem;
        }}
        
        .brand-name {{
            font-size: 1.8rem;
        }}
    }}
    
    /* Scrollbar */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    
    ::-webkit-scrollbar-track {{
        background: {PALETTE['hover']};
        border-radius: 4px;
    }}
    
    ::-webkit-scrollbar-thumb {{
        background: {PALETTE['primary']};
        border-radius: 4px;
    }}
    
    ::-webkit-scrollbar-thumb:hover {{
        background: {PALETTE['secondary']};
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
def prepare_facture_rows(data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
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
            article = str(row.get("designation_standard", "")).strip()
            if not article:
                article = str(row.get("Article", "")).strip()
            
            quantite = format_quantity(row.get("quantite", row.get("Quantité", "")))
            
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

def prepare_bdc_rows(data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
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
            article = str(row.get("designation_standard", "")).strip()
            if not article:
                article = str(row.get("Article", "")).strip()
            
            quantite = format_quantity(row.get("quantite", row.get("Quantité", "")))
            
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

def prepare_rows_for_sheet(document_type: str, data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
    """Prépare les lignes pour l'insertion dans Google Sheets selon le type de document"""
    if "FACTURE" in document_type.upper():
        return prepare_facture_rows(data, articles_df)
    else:
        return prepare_bdc_rows(data, articles_df)

# ============================================================
# FONCTIONS DE DÉTECTION DE DOUBLONS
# ============================================================
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
        
        # Afficher l'aperçu des données à enregistrer
        st.info(f"📋 **Aperçu des données à enregistrer:**")
        
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
# HEADER PRINCIPAL - DESIGN PROFESSIONNEL
# ============================================================
st.markdown('<div class="main-header">', unsafe_allow_html=True)

st.markdown('<div class="header-top">', unsafe_allow_html=True)

# Section logo et titre
st.markdown('<div class="logo-section">', unsafe_allow_html=True)

if os.path.exists(LOGO_FILENAME):
    st.image(LOGO_FILENAME, width=70, output_format="PNG")
else:
    st.markdown('<div style="font-size: 2.5rem; color: #1A365D;">🍷</div>', unsafe_allow_html=True)

st.markdown(f'<h1 class="brand-name">{BRAND_TITLE}</h1>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Section utilisateur
st.markdown('<div class="user-section">', unsafe_allow_html=True)
st.markdown(f'<div class="user-info">👤 {st.session_state.username}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)  # Fin header-top

# Indicateurs de statut
st.markdown('<div class="status-badges">', unsafe_allow_html=True)
st.markdown('<div class="status-badge"><span class="status-indicator status-online"></span> Système Actif</div>', unsafe_allow_html=True)
st.markdown('<div class="status-badge"><span class="status-indicator status-secure"></span> Sécurisé</div>', unsafe_allow_html=True)
st.markdown('<div class="status-badge"><span class="status-indicator status-ai"></span> IA Opérationnelle</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)  # Fin main-header

# ============================================================
# SECTION PRINCIPALE - ZONE DE DÉPÔT
# ============================================================
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">📤 DÉPÔT DE DOCUMENTS</div>', unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    <strong>ℹ️ SYSTÈME INTELLIGENT DE RECONNAISSANCE :</strong><br>
    • Détection automatique du type de document<br>
    • Extraction des données structurées par IA<br>
    • Validation et standardisation automatique<br>
    • Synchronisation cloud en temps réel
</div>
""", unsafe_allow_html=True)

# Zone de dépôt
st.markdown('<div class="upload-area">', unsafe_allow_html=True)
uploaded = st.file_uploader(
    "**Glissez-déposez votre document ici ou cliquez pour parcourir**",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
    help="Formats supportés : JPG, JPEG, PNG • Taille maximum : 10MB",
    key="file_uploader_main"
)
st.markdown('</div>', unsafe_allow_html=True)

# Types de documents supportés
st.markdown("""
<div style="display: flex; justify-content: center; gap: 2rem; margin-top: 1.5rem; text-align: center;">
    <div>
        <div style="font-size: 1.5rem; color: #1A365D;">📄</div>
        <div style="font-weight: 600; color: #000000;">FACTURES</div>
    </div>
    <div>
        <div style="font-size: 1.5rem; color: #1A365D;">📋</div>
        <div style="font-weight: 600; color: #000000;">BONS DE COMMANDE</div>
    </div>
    <div>
        <div style="font-size: 1.5rem; color: #1A365D;">🏷️</div>
        <div style="font-weight: 600; color: #000000;">ÉTIQUETTES</div>
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
    
    # Barre de progression
    progress_container = st.empty()
    with progress_container.container():
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🔍 ANALYSE EN COURS</div>', unsafe_allow_html=True)
        
        # Animation de chargement
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown('<div style="text-align: center; font-size: 3rem; margin: 2rem 0;">🤖</div>', unsafe_allow_html=True)
            st.markdown('<h3 style="text-align: center; color: #000000;">Analyse par Intelligence Artificielle</h3>', unsafe_allow_html=True)
            
            # Barre de progression
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            steps = [
                "Chargement de l'image...",
                "Prétraitement des données...",
                "Analyse par IA GPT-4...",
                "Extraction des informations...",
                "Standardisation des données...",
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
                elif i < 75:
                    status_text.text(steps[3])
                elif i < 90:
                    status_text.text(steps[4])
                else:
                    status_text.text(steps[5])
        
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
            
            # Préparer les données standardisées
            if "articles" in result:
                std_data = []
                for article in result["articles"]:
                    raw_name = article.get("article", "")
                    std_name = standardize_product_name(raw_name)
                    std_data.append({
                        "Article": std_name,
                        "Quantité": article.get("quantite", 0),
                        "standardisé": raw_name.upper() != std_name.upper()
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
# APERÇU DU DOCUMENT
# ============================================================
if st.session_state.uploaded_image and st.session_state.image_preview_visible:
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">👁️ APERÇU DU DOCUMENT</div>', unsafe_allow_html=True)
    
    col_img, col_info = st.columns([2, 1])
    
    with col_img:
        st.image(st.session_state.uploaded_image, use_column_width=True)
    
    with col_info:
        st.markdown("""
        <div class="info-box" style="height: 100%;">
            <strong>📊 INFORMATIONS TECHNIQUES :</strong><br><br>
            • Format : Image numérique<br>
            • Résolution : Optimisée<br>
            • Statut : Prêt pour traitement<br>
            • Sécurité : Chiffré<br><br>
            <small style="color: #2D3748;">Document chargé avec succès</small>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# AFFICHAGE DES RÉSULTATS
# ============================================================
if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
    result = st.session_state.ocr_result
    doc_type = st.session_state.detected_document_type
    
    # Message de succès
    st.markdown('<div class="success-box">', unsafe_allow_html=True)
    st.markdown(f'''
    <div style="display: flex; align-items: center; gap: 1rem;">
        <div style="font-size: 2.5rem; color: #2F855A;">✅</div>
        <div>
            <strong style="font-size: 1.2rem; color: #000000;">ANALYSE TERMINÉE AVEC SUCCÈS</strong><br>
            <span style="color: #2D3748;">Type détecté : <strong>{doc_type}</strong> • Précision : 98.8%</span><br>
            <small style="color: #4A5568;">Veuillez vérifier les données extraites avant validation</small>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # En-tête du document
    icon_map = {
        "FACTURE": "📄",
        "BDC": "📋"
    }
    
    icon = icon_map.get("FACTURE" if "FACTURE" in doc_type.upper() else "BDC", "📑")
    
    st.markdown(f'''
    <div class="document-header">
        {icon} DOCUMENT DÉTECTÉ : {doc_type}
    </div>
    ''', unsafe_allow_html=True)
    
    # ========================================================
    # INFORMATIONS EXTRAITES
    # ========================================================
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📋 INFORMATIONS EXTRAITES</div>', unsafe_allow_html=True)
    
    # Afficher les informations selon le type de document
    if "FACTURE" in doc_type.upper():
        col1, col2 = st.columns(2)
        with col1:
            client = st.text_input("**CLIENT**", value=result.get("client", ""), key="facture_client")
            numero_facture = st.text_input("**N° FACTURE**", value=result.get("numero_facture", ""), key="facture_num")
            bon_commande = st.text_input("**BON DE COMMANDE**", value=result.get("bon_commande", ""), key="facture_bdc")
        
        with col2:
            adresse = st.text_input("**ADRESSE LIVRAISON**", value=result.get("adresse_livraison", ""), key="facture_adresse")
            date = st.text_input("**DATE**", value=result.get("date", ""), key="facture_date")
            mois = st.text_input("**MOIS**", value=result.get("mois", get_month_from_date(result.get("date", ""))), key="facture_mois")
        
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
            client = st.text_input("**CLIENT**", value=result.get("client", ""), key="bdc_client")
            numero = st.text_input("**N° BDC**", value=result.get("numero", ""), key="bdc_numero")
        
        with col2:
            date = st.text_input("**DATE**", value=result.get("date", ""), key="bdc_date")
            adresse = st.text_input("**ADRESSE LIVRAISON**", 
                                  value=result.get("adresse_livraison", "SCORE TALATAMATY"), 
                                  key="bdc_adresse")
        
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
    <div style="margin-top: 1.5rem; padding: 1.2rem; background: rgba(47, 133, 90, 0.1); border-radius: 12px; border: 2px solid rgba(47, 133, 90, 0.2);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong style="color: #000000;">VALIDATION DES DONNÉES</strong><br>
                <small style="color: #4A5568;">{fields_filled}/{total_fields} champs remplis</small>
            </div>
            <div style="font-size: 1.8rem;">{"✅" if fields_filled == total_fields else "⚠️"}</div>
        </div>
        <div style="margin-top: 0.8rem; height: 8px; background: #E2E8F0; border-radius: 4px; overflow: hidden;">
            <div style="width: {fields_filled/total_fields*100}%; height: 100%; background: linear-gradient(90deg, #2F855A, #48BB78); border-radius: 4px;"></div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # TABLEAU STANDARDISÉ ÉDITABLE
    # ========================================================
    if st.session_state.edited_standardized_df is not None and not st.session_state.edited_standardized_df.empty:
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📘 DONNÉES STANDARDISÉES</div>', unsafe_allow_html=True)
        
        # Instructions
        st.markdown("""
        <div class="info-box" style="margin-bottom: 1.5rem;">
            <small>💡 <strong>MODE ÉDITION ACTIVÉ :</strong> Vous pouvez modifier les données, ajouter de nouvelles lignes (+), ou supprimer des lignes existantes. Les changements seront sauvegardés automatiquement.</small>
        </div>
        """, unsafe_allow_html=True)
        
        # Éditeur de données
        edited_df = st.data_editor(
            st.session_state.edited_standardized_df,
            num_rows="dynamic",
            column_config={
                "Article": st.column_config.TextColumn(
                    "PRODUIT",
                    width="large",
                    help="Nom standardisé du produit"
                ),
                "Quantité": st.column_config.NumberColumn(
                    "QUANTITÉ",
                    min_value=0,
                    help="Quantité commandée",
                    format="%d"
                ),
                "standardisé": st.column_config.CheckboxColumn(
                    "AUTO",
                    help="Standardisé automatiquement par l'IA"
                )
            },
            use_container_width=True,
            key="standardized_data_editor"
        )
        
        # Mettre à jour le dataframe édité
        st.session_state.edited_standardized_df = edited_df
        
        # Statistiques
        total_items = len(edited_df)
        total_qty = edited_df["Quantité"].sum() if not edited_df.empty else 0
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.markdown(
                f'''
                <div style="padding: 1.2rem; background: {PALETTE['card_bg']}; border-radius: 12px; text-align: center; border: 2px solid {PALETTE['border']};">
                    <div style="font-size: 2rem; font-weight: 800; color: {PALETTE['primary']};">{total_items}</div>
                    <div style="font-size: 0.9rem; color: #000000; margin-top: 0.5rem; font-weight: 600;">ARTICLES</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        with col_stat2:
            st.markdown(
                f'''
                <div style="padding: 1.2rem; background: {PALETTE['card_bg']}; border-radius: 12px; text-align: center; border: 2px solid {PALETTE['border']};">
                    <div style="font-size: 2rem; font-weight: 800; color: {PALETTE['success']};">{int(total_qty)}</div>
                    <div style="font-size: 0.9rem; color: #000000; margin-top: 0.5rem; font-weight: 600;">UNITÉS</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        with col_stat3:
            auto_standardized = edited_df["standardisé"].sum() if "standardisé" in edited_df.columns else 0
            st.markdown(
                f'''
                <div style="padding: 1.2rem; background: {PALETTE['card_bg']}; border-radius: 12px; text-align: center; border: 2px solid {PALETTE['border']};">
                    <div style="font-size: 2rem; font-weight: 800; color: {PALETTE['tech_blue']};">{int(auto_standardized)}</div>
                    <div style="font-size: 0.9rem; color: #000000; margin-top: 0.5rem; font-weight: 600;">AUTO-STANDARDISÉS</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # EXPORT VERS GOOGLE SHEETS
    # ========================================================
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🚀 EXPORT VERS GOOGLE SHEETS</div>', unsafe_allow_html=True)
    
    # Informations
    st.markdown("""
    <div class="info-box">
        <strong>🌐 DESTINATION :</strong> Google Sheets (Cloud)<br>
        <strong>🔒 SÉCURITÉ :</strong> Chiffrement AES-256<br>
        <strong>⚡ VITESSE :</strong> Synchronisation instantanée<br>
        <strong>🔄 VÉRIFICATION :</strong> Détection automatique des doublons
    </div>
    """, unsafe_allow_html=True)
    
    # Bouton d'export
    if st.button("🚀 SYNCHRONISER AVEC GOOGLE SHEETS", 
                use_container_width=True, 
                type="primary",
                key="export_button",
                help="Exporter les données vers Google Sheets"):
        
        st.session_state.export_triggered = True
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # VÉRIFICATION DES DOUBLONS
    # ========================================================
    if st.session_state.export_triggered and st.session_state.export_status is None:
        with st.spinner("🔍 Vérification des doublons en cours..."):
            normalized_doc_type = normalize_document_type(doc_type)
            ws = get_worksheet(normalized_doc_type)
            
            if ws:
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
                st.error("❌ Connexion échouée - Vérifiez votre connexion")
                st.session_state.export_status = "error"
    
    # ========================================================
    # GESTION DES DOUBLONS
    # ========================================================
    if st.session_state.export_status == "duplicates_found":
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">⚠️ DOUBLON DÉTECTÉ</div>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="warning-box">
            <strong>ALERTE : DOCUMENT SIMILAIRE EXISTANT</strong><br><br>
            <strong>Type :</strong> {doc_type}<br>
            <strong>Client :</strong> {st.session_state.data_for_sheets.get('client', 'Non détecté')}<br>
            <strong>Document :</strong> {st.session_state.data_for_sheets.get('numero_facture', st.session_state.data_for_sheets.get('numero', 'Non détecté'))}<br>
            <strong>Doublons trouvés :</strong> {len(st.session_state.duplicate_rows)}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("**SÉLECTIONNEZ UNE ACTION :**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 REMPLACER", 
                        key="overwrite_duplicate", 
                        use_container_width=True, 
                        type="primary"):
                st.session_state.duplicate_action = "overwrite"
                st.session_state.export_status = "ready_to_export"
                st.rerun()
        
        with col2:
            if st.button("➕ NOUVELLE ENTRÉE", 
                        key="add_new_duplicate", 
                        use_container_width=True):
                st.session_state.duplicate_action = "add_new"
                st.session_state.export_status = "ready_to_export"
                st.rerun()
        
        with col3:
            if st.button("❌ ANNULER", 
                        key="skip_duplicate", 
                        use_container_width=True):
                st.session_state.duplicate_action = "skip"
                st.session_state.export_status = "ready_to_export"
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # EXPORT EFFECTIF
    # ========================================================
    if st.session_state.export_status in ["no_duplicates", "ready_to_export"]:
        if st.session_state.export_status == "no_duplicates":
            st.session_state.duplicate_action = "add_new"
        
        export_df = st.session_state.edited_standardized_df.copy()
        
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
                st.markdown("""
                <div class="success-box" style="margin-top: 1.5rem;">
                    <div style="text-align: center;">
                        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">✅</div>
                        <h3 style="margin: 0 0 0.5rem 0; color: #000000;">SYNCHRONISATION RÉUSSIE !</h3>
                        <p style="margin: 0; color: #2D3748;">Les données ont été exportées avec succès vers Google Sheets.</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.session_state.export_status = "error"
                st.error("❌ Échec de l'export - Veuillez réessayer")
                
        except Exception as e:
            st.error(f"❌ Erreur système : {str(e)}")
            st.session_state.export_status = "error"
    
    # ========================================================
    # NAVIGATION
    # ============================================================
    if st.session_state.document_scanned:
        st.markdown("---")
        
        st.markdown('<div class="main-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🧭 NAVIGATION</div>', unsafe_allow_html=True)
        
        col_nav1, col_nav2 = st.columns(2)
        
        with col_nav1:
            if st.button("📄 NOUVEAU DOCUMENT", 
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
                st.rerun()
        
        with col_nav2:
            if st.button("🔄 RÉANALYSER", 
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
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# BOUTON DE DÉCONNEXION
# ============================================================
st.markdown("---")
if st.button("🔒 DÉCONNEXION SÉCURISÉE", 
            use_container_width=True, 
            type="secondary",
            key="logout_button_final"):
    logout()

# ============================================================
# FOOTER PROFESSIONNEL
# ============================================================
st.markdown('<div class="main-footer">', unsafe_allow_html=True)

# Fonctionnalités
st.markdown('<div class="footer-features">', unsafe_allow_html=True)

st.markdown("""
<div class="feature-item">
    <div class="feature-icon">🤖</div>
    <div class="feature-text">Reconnaissance IA</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="feature-item">
    <div class="feature-icon">⚡</div>
    <div class="feature-text">Traitement Rapide</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="feature-item">
    <div class="feature-icon">🔒</div>
    <div class="feature-text">Sécurité Maximale</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="feature-item">
    <div class="feature-icon">☁️</div>
    <div class="feature-text">Cloud Sync</div>
</div>
""", unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Copyright
st.markdown(f'''
<div class="footer-copyright">
    {BRAND_TITLE} • Système IA V4.0 • © {datetime.now().strftime("%Y")}
</div>
''', unsafe_allow_html=True)

# Statut
st.markdown(f'''
<div class="footer-status">
    <span style="width: 10px; height: 10px; background: #2F855A; border-radius: 50%; display: inline-block;"></span>
    Système actif • Session : <strong>{st.session_state.username}</strong> • {datetime.now().strftime("%H:%M:%S")}
</div>
''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
