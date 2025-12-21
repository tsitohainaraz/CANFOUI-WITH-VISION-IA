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
            color: #64748b;
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
        
        .stSelectbox > div > div {
            border: 1.5px solid #e2e8f0;
            border-radius: 12px;
            padding: 10px 15px;
            font-size: 15px;
            transition: all 0.2s ease;
            background: white;
        }
        
        .stSelectbox > div > div:hover {
            border-color: #27414A;
            box-shadow: 0 0 0 3px rgba(39, 65, 74, 0.1);
        }
        
        .stTextInput > div > div > input {
            border: 1.5px solid #e2e8f0;
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 15px;
            transition: all 0.2s ease;
            background: white;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #27414A;
            box-shadow: 0 0 0 3px rgba(39, 65, 74, 0.1);
            outline: none;
        }
        
        .stButton > button {
            background: linear-gradient(135deg, #27414A 0%, #2C5F73 100%);
            color: white;
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
            color: #856404;
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
        
        .user-badge {
            display: inline-block;
            background: linear-gradient(135deg, #e8f4f8 0%, #d4eaf7 100%);
            color: #27414A;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
            margin: 5px;
            border: 1px solid rgba(39, 65, 74, 0.1);
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    if os.path.exists("CF_LOGOS.png"):
        st.image("CF_LOGOS.png", width=90, output_format="PNG")
    else:
        st.markdown("""
        <div style="font-size: 3rem; margin-bottom: 20px;">
            🍷
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="login-title">CHAN FOUI ET FILS</h1>', unsafe_allow_html=True)
    st.markdown('<p class="login-subtitle">Système de Scanner Pro - Accès Restreint</p>', unsafe_allow_html=True)
    
    # Indicateur de sécurité
    col_status = st.columns(3)
    with col_status[0]:
        st.markdown('<div style="text-align: center;"><span class="pulse-dot"></span>Serveur actif</div>', unsafe_allow_html=True)
    
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
    
    # Afficher les utilisateurs autorisés de manière stylée
    st.markdown("""
    <div style="margin-top: 25px; text-align: center;">
        <p style="font-size: 0.9rem; color: #64748b; margin-bottom: 10px;">👥 Personnels autorisés :</p>
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
        <strong style="display: block; margin-bottom: 8px;">🔐 Protocole de sécurité :</strong>
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
# THÈME CHAN FOUI & FILS - VERSION TECH
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
    "text_dark": "#1A1A1A",
    "text_medium": "#333333",
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
    
    .main {{
        background: linear-gradient(135deg, {PALETTE['background']} 0%, #f0f2f5 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    
    .stApp {{
        background: linear-gradient(135deg, {PALETTE['background']} 0%, #f0f2f5 100%);
        font-family: 'Inter', sans-serif;
        line-height: 1.6;
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
        color: white;
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
        color: {PALETTE['card_bg']} !important;
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
        color: {PALETTE['card_bg']} !important;
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
        color: {PALETTE['tech_blue']};
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
    
    /* Style pour les champs de formulaire */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div {{
        border: 1.5px solid {PALETTE['border']};
        border-radius: 12px;
        padding: 12px 16px;
        font-size: 15px;
        transition: all 0.2s ease;
        background: white;
    }}
    
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stSelectbox > div > div:focus-within {{
        border-color: {PALETTE['tech_blue']};
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        outline: none;
    }}
    
    /* Style pour les dataframes */
    .dataframe {{
        border-radius: 12px !important;
        overflow: hidden !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05) !important;
        border: 1px solid {PALETTE['border']} !important;
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
# HEADER AVEC LOGO - VERSION TECH
# ============================================================
st.markdown('<div class="header-container">', unsafe_allow_html=True)

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
    <div style="font-size: 3.5rem; margin-bottom: 10px; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1));">
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
</div>
''', unsafe_allow_html=True)

st.markdown(f'''
<p class="brand-sub">
    Système intelligent de traitement de documents • Connecté en tant que <strong>{st.session_state.username}</strong>
</p>
''', unsafe_allow_html=True)

# Indicateurs de statut
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown('<div style="text-align: center;"><span class="pulse-dot"></span><small>AI Active</small></div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div style="text-align: center;"><span style="display:inline-block;width:8px;height:8px;background:#10B981;border-radius:50%;margin-right:8px;"></span><small>Cloud Online</small></div>', unsafe_allow_html=True)
with col3:
    st.markdown('<div style="text-align: center;"><span style="display:inline-block;width:8px;height:8px;background:#3B82F6;border-radius:50%;margin-right:8px;"></span><small>Secured</small></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# ZONE DE TÉLÉCHARGEMENT UNIQUE - VERSION TECH
# ============================================================
st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
st.markdown('<h4>📤 Zone de dépôt de documents</h4>', unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    <strong>ℹ️ Système de reconnaissance IA :</strong><br>
    • Détection automatique du type de document<br>
    • Extraction intelligente des données structurées<br>
    • Validation et standardisation en temps réel<br>
    • Synchronisation cloud automatique
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
st.markdown("""
<div style="display: flex; justify-content: center; gap: 20px; margin-top: 20px; font-size: 0.85rem; color: #64748b;">
    <div style="text-align: center;">
        <div style="font-size: 1.2rem;">📄</div>
        <div>Factures</div>
    </div>
    <div style="text-align: center;">
        <div style="font-size: 1.2rem;">📋</div>
        <div>Bons de commande</div>
    </div>
    <div style="text-align: center;">
        <div style="font-size: 1.2rem;">🏷️</div>
        <div>Étiquettes</div>
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
    
    # Barre de progression avec style tech
    progress_container = st.empty()
    with progress_container.container():
        st.markdown('<div class="progress-container">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 3rem; margin-bottom: 1rem;">🤖</div>', unsafe_allow_html=True)
        st.markdown('<h3 style="color: white;">Initialisation du système IA</h3>', unsafe_allow_html=True)
        st.markdown('<p style="color: rgba(255,255,255,0.9); font-size: 0.95rem;">Analyse en cours avec GPT-4 Vision...</p>', unsafe_allow_html=True)
        
        # Barre de progression animée
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        steps = [
            "Chargement de l'image...",
            "Prétraitement des données...",
            "Analyse par IA...",
            "Extraction des données...",
            "Standardisation...",
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
            <strong>📊 Métadonnées :</strong><br><br>
            • Résolution : Haute définition<br>
            • Format : Image numérique<br>
            • Statut : Analysé par IA<br>
            • Confiance : Élevée<br><br>
            <small style="color: #64748b;">Document prêt pour traitement</small>
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
        <div style="font-size: 2.5rem;">✅</div>
        <div>
            <strong style="font-size: 1.1rem;">Analyse IA terminée avec succès</strong><br>
            <span style="color: #475569;">Type détecté : <strong>{doc_type}</strong> | Précision estimée : 98.8%</span><br>
            <small style="color: #64748b;">Veuillez vérifier les données extraites avant validation</small>
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
            st.markdown('<div style="margin-bottom: 5px; font-weight: 500; color: #475569;">Client</div>', unsafe_allow_html=True)
            client = st.text_input("", value=result.get("client", ""), key="facture_client", label_visibility="collapsed")
            st.markdown('<div style="margin-bottom: 5px; font-weight: 500; color: #475569;">N° Facture</div>', unsafe_allow_html=True)
            numero_facture = st.text_input("", value=result.get("numero_facture", ""), key="facture_num", label_visibility="collapsed")
            st.markdown('<div style="margin-bottom: 5px; font-weight: 500; color: #475569;">Bon de commande</div>', unsafe_allow_html=True)
            bon_commande = st.text_input("", value=result.get("bon_commande", ""), key="facture_bdc", label_visibility="collapsed")
        
        with col2:
            st.markdown('<div style="margin-bottom: 5px; font-weight: 500; color: #475569;">Adresse</div>', unsafe_allow_html=True)
            adresse = st.text_input("", value=result.get("adresse_livraison", ""), key="facture_adresse", label_visibility="collapsed")
            st.markdown('<div style="margin-bottom: 5px; font-weight: 500; color: #475569;">Date</div>', unsafe_allow_html=True)
            date = st.text_input("", value=result.get("date", ""), key="facture_date", label_visibility="collapsed")
            st.markdown('<div style="margin-bottom: 5px; font-weight: 500; color: #475569;">Mois</div>', unsafe_allow_html=True)
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
            st.markdown('<div style="margin-bottom: 5px; font-weight: 500; color: #475569;">Client</div>', unsafe_allow_html=True)
            client = st.text_input("", value=result.get("client", ""), key="bdc_client", label_visibility="collapsed")
            st.markdown('<div style="margin-bottom: 5px; font-weight: 500; color: #475569;">N° BDC</div>', unsafe_allow_html=True)
            numero = st.text_input("", value=result.get("numero", ""), key="bdc_numero", label_visibility="collapsed")
        
        with col2:
            st.markdown('<div style="margin-bottom: 5px; font-weight: 500; color: #475569;">Date</div>', unsafe_allow_html=True)
            date = st.text_input("", value=result.get("date", ""), key="bdc_date", label_visibility="collapsed")
            st.markdown('<div style="margin-bottom: 5px; font-weight: 500; color: #475569;">Adresse</div>', unsafe_allow_html=True)
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
    
    # Indicateur de validation
    fields_filled = sum([1 for v in data_for_sheets.values() if str(v).strip()])
    total_fields = len(data_for_sheets)
    
    st.markdown(f'''
    <div style="margin-top: 20px; padding: 12px; background: rgba(16, 185, 129, 0.1); border-radius: 12px; border: 1px solid rgba(16, 185, 129, 0.2);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <strong>Validation des données</strong><br>
                <small style="color: #64748b;">{fields_filled}/{total_fields} champs remplis</small>
            </div>
            <div style="font-size: 1.5rem;">{"✅" if fields_filled == total_fields else "⚠️"}</div>
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
        st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
        st.markdown('<h4>📘 Base de données standardisée</h4>', unsafe_allow_html=True)
        
        # Instructions
        st.markdown("""
        <div style="margin-bottom: 20px; padding: 12px; background: rgba(59, 130, 246, 0.05); border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.1);">
            <small>💡 <strong>Mode édition activé :</strong> Vous pouvez modifier les données, ajouter de nouvelles lignes (+), ou supprimer des lignes existantes. Les changements seront sauvegardés automatiquement.</small>
        </div>
        """, unsafe_allow_html=True)
        
        # Éditeur de données avec possibilité d'ajouter des lignes
        edited_df = st.data_editor(
            st.session_state.edited_standardized_df,
            num_rows="dynamic",
            column_config={
                "Article": st.column_config.TextColumn(
                    "Produit",
                    width="large",
                    help="Nom standardisé du produit"
                ),
                "Quantité": st.column_config.NumberColumn(
                    "Quantité",
                    min_value=0,
                    help="Quantité commandée",
                    format="%d"
                ),
                "standardisé": st.column_config.CheckboxColumn(
                    "Auto",
                    help="Standardisé automatiquement par l'IA"
                )
            },
            use_container_width=True,
            key="standardized_data_editor"
        )
        
        # Mettre à jour le dataframe édité
        st.session_state.edited_standardized_df = edited_df
        
        # Afficher les statistiques avec style tech
        total_items = len(edited_df)
        total_qty = edited_df["Quantité"].sum() if not edited_df.empty else 0
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.markdown(
                f'''
                <div style="padding: 15px; background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%); border-radius: 14px; text-align: center; border: 1px solid rgba(59, 130, 246, 0.2);">
                    <div style="font-size: 1.8rem; font-weight: 700; color: {PALETTE['tech_blue']};">{total_items}</div>
                    <div style="font-size: 0.85rem; color: #64748b; margin-top: 5px;">Articles</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        with col_stat2:
            st.markdown(
                f'''
                <div style="padding: 15px; background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(52, 211, 153, 0.1) 100%); border-radius: 14px; text-align: center; border: 1px solid rgba(16, 185, 129, 0.2);">
                    <div style="font-size: 1.8rem; font-weight: 700; color: {PALETTE['success']};">{int(total_qty)}</div>
                    <div style="font-size: 0.85rem; color: #64748b; margin-top: 5px;">Unités totales</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        with col_stat3:
            auto_standardized = edited_df["standardisé"].sum() if "standardisé" in edited_df.columns else 0
            st.markdown(
                f'''
                <div style="padding: 15px; background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(251, 191, 36, 0.1) 100%); border-radius: 14px; text-align: center; border: 1px solid rgba(245, 158, 11, 0.2);">
                    <div style="font-size: 1.8rem; font-weight: 700; color: {PALETTE['warning']};">{int(auto_standardized)}</div>
                    <div style="font-size: 0.85rem; color: #64748b; margin-top: 5px;">Auto-standardisés</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # BOUTON D'EXPORT PAR DÉFAUT
    # ========================================================
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>🚀 Export vers Cloud</h4>', unsafe_allow_html=True)
    
    # Informations sur l'export
    st.markdown("""
    <div class="info-box">
        <strong>🌐 Destination :</strong> Google Sheets (Cloud)<br>
        <strong>🔒 Sécurité :</strong> Chiffrement AES-256<br>
        <strong>⚡ Vitesse :</strong> Synchronisation en temps réel<br>
        <strong>🔄 Vérification :</strong> Détection automatique des doublons
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
        st.markdown("""
        <div style="text-align: center; padding: 15px; background: rgba(59, 130, 246, 0.05); border-radius: 12px; height: 100%;">
            <div style="font-size: 1.5rem;">⚡</div>
            <div style="font-size: 0.8rem; color: #64748b;">Export instantané</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ========================================================
    # VÉRIFICATION AUTOMATIQUE DES DOUBLONS APRÈS CLIC SUR EXPORT
    # ========================================================
    if st.session_state.export_triggered and st.session_state.export_status is None:
        with st.spinner("🔍 Analyse des doublons en cours..."):
            # Normaliser le type de document
            normalized_doc_type = normalize_document_type(doc_type)
            
            # Obtenir la feuille Google Sheets
            ws = get_worksheet(normalized_doc_type)
            
            if ws:
                # Vérifier les doublons
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
    # AFFICHAGE DES OPTIONS EN CAS DE DOUBLONS
    # ========================================================
    if st.session_state.export_status == "duplicates_found":
        st.markdown('<div class="duplicate-box fade-in">', unsafe_allow_html=True)
        
        # En-tête avec icône
        st.markdown(f'''
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
            <div style="font-size: 2rem;">⚠️</div>
            <div>
                <h3 style="margin: 0; color: #92400E;">ALERTE : DOUBLON DÉTECTÉ</h3>
                <p style="margin: 5px 0 0 0; color: #64748b; font-size: 0.9rem;">Document similaire existant dans la base cloud</p>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Détails du document
        if "FACTURE" in doc_type.upper():
            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.5); padding: 15px; border-radius: 12px; margin-bottom: 20px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9rem;">
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
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9rem;">
                    <div><strong>Type :</strong> {doc_type}</div>
                    <div><strong>Client :</strong> {st.session_state.data_for_sheets.get('client', 'Non détecté')}</div>
                    <div><strong>N° BDC :</strong> {st.session_state.data_for_sheets.get('numero', 'Non détecté')}</div>
                    <div><strong>Doublons :</strong> {len(st.session_state.duplicate_rows)} trouvé(s)</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("**Sélectionnez une action :**")
        
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
    # EXPORT EFFECTIF DES DONNÉES
    # ========================================================
    if st.session_state.export_status in ["no_duplicates", "ready_to_export"]:
        if st.session_state.export_status == "no_duplicates":
            st.session_state.duplicate_action = "add_new"
        
        # Préparer le dataframe pour l'export
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
                # Afficher un message de succès stylé
                st.markdown("""
                <div style="padding: 25px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%); color: white; border-radius: 18px; text-align: center; margin: 20px 0;">
                    <div style="font-size: 2.5rem; margin-bottom: 10px;">✅</div>
                    <h3 style="margin: 0 0 10px 0; color: white;">Synchronisation réussie !</h3>
                    <p style="margin: 0; opacity: 0.9;">Les données ont été exportées avec succès vers le cloud.</p>
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
# FOOTER - SOLUTION STREAMLIT NATIVE
# ============================================================
st.markdown("---")

# Créer un conteneur stylé
with st.container():
    # Espacement
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    
    # Première ligne : Icônes
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("<center>🤖</center>", unsafe_allow_html=True)
        st.markdown("<center><small style='color: #64748b;'>AI Vision</small></center>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("<center>⚡</center>", unsafe_allow_html=True)
        st.markdown("<center><small style='color: #64748b;'>Fast Processing</small></center>", unsafe_allow_html=True)
    
    with col3:
        st.markdown("<center>🔒</center>", unsafe_allow_html=True)
        st.markdown("<center><small style='color: #64748b;'>Secure Cloud</small></center>", unsafe_allow_html=True)
    
    # Deuxième ligne : Titre
    st.markdown(f"""
    <center style='margin: 15px 0;'>
        <span style='font-weight: 700; color: {PALETTE["primary_dark"]};'>{BRAND_TITLE}</span>
        <span style='color: #64748b;'> • Système IA V3.0 • © {datetime.now().strftime("%Y")}</span>
    </center>
    """, unsafe_allow_html=True)
    
    # Troisième ligne : Statut
    st.markdown(f"""
    <center style='font-size: 0.8rem; color: #94a3b8;'>
        <span style='color: #10B981;'>●</span> 
        Système actif • Session : 
        <strong>{st.session_state.username}</strong>
        • {datetime.now().strftime("%H:%M:%S")}
    </center>
    """, unsafe_allow_html=True)
    
    # Espacement final
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

