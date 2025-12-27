import streamlit as st
import pandas as pd
import json
import re
from PIL import Image
from io import BytesIO
import base64
from typing import Dict, List, Tuple
from datetime import datetime

# ============================================================
# CONFIGURATION GLOBALE
# ============================================================
SHEET_ID = "1FooEwQBwLjvyjAsvHu4eDes0o-eEm92fbEWv6maBNyE"

SHEET_GIDS = {
    "FACTURE EN COMPTE": 16102465,
    "BDC LEADERPRICE": 954728911,
    "BDC S2M": 954728911,
    "BDC ULYS": 954728911
}

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================
def encode_image_to_base64(image_bytes):
    """Encode une image en base64"""
    return base64.b64encode(image_bytes).decode('utf-8')

def preprocess_image(image_bytes):
    """Prétraite l'image pour améliorer l'OCR"""
    image = Image.open(BytesIO(image_bytes))
    if image.mode != 'L':
        image = image.convert('L')
    return image

def get_openai_client():
    """Initialise et retourne le client OpenAI"""
    # À implémenter selon votre configuration
    # Exemple:
    # from openai import OpenAI
    # return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    return None

def format_date_french(date_str):
    """Formate une date en français"""
    try:
        if not date_str:
            return ""
        # Essaye de parser la date
        date_formats = ["%d %B %Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y"]
        for fmt in date_formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime("%d/%m/%Y")
            except:
                continue
        return date_str
    except:
        return date_str

def get_month_from_date(date_str):
    """Extrait le mois d'une date"""
    try:
        if not date_str:
            return ""
        date_formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y"]
        for fmt in date_formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                # Retourne le mois en français
                months_fr = {
                    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
                    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
                    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
                }
                month_name = months_fr[date_obj.month]
                return f"{month_name} {date_obj.year}"
            except:
                continue
        return date_str
    except:
        return date_str

def format_quantity(quantity):
    """Formate une quantité"""
    try:
        if pd.isna(quantity):
            return "0"
        # Essaye de convertir en entier
        qty = float(quantity)
        if qty.is_integer():
            return str(int(qty))
        return str(qty)
    except:
        return str(quantity)

# ============================================================
# FONCTIONS OCR
# ============================================================
def openai_vision_ocr_bdc(image_bytes: bytes) -> Dict:
    """Utilise OpenAI Vision pour analyser un BON DE COMMANDE"""
    try:
        client = get_openai_client()
        if not client:
            # Mode démo - retourne des données fictives
            return {
                "type_document": "BON DE COMMANDE",
                "numero": "24007505",
                "date": "16 Septembre 2024",
                "client": "S2M",
                "adresse_livraison": "SCORE FI-Fianarantsoa - Fianarantsoa",
                "articles": [
                    {"article_brut": "Côte de Fanar Rouge 75 cls", "quantite": 24},
                    {"article_brut": "Côteau d'Ambalavao Rouge 75 cls", "quantite": 12},
                    {"article_brut": "Coteau d'Ambalavao Rosé 75 cls", "quantite": 12},
                    {"article_brut": "Coteau d'Ambalavao Blanc 75 cls", "quantite": 12},
                    {"article_brut": "Blanc dont de Marcparasy 75 cls", "quantite": 60}
                ]
            }
        
        base64_image = encode_image_to_base64(image_bytes)
        
        prompt = """
        Analyse ce document de type BON DE COMMANDE et extrais précisément les informations suivantes:
        
        IMPORTANT: Extrais TOUTES les lignes du tableau, y compris les produits.
        
        {
            "type_document": "BON DE COMMANDE",
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
        1. Pour "article_brut": copie EXACTEMENT le texte de la colonne "Description" ou "Désignation" sans modifications
        2. Pour les quantités: extrais le nombre exact de la colonne "Qté" ou "Quantité"
        3. Pour "numero": cherche "N° Commande", "Bon de commande N°", "BC" ou similaire
        4. Extrais TOUTES les lignes d'articles
        5. Ne standardise PAS les noms, garde-les exactement comme sur le document
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
            max_tokens=3000,
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError:
                json_str = re.sub(r'[\x00-\x1f\x7f]', '', json_str)
                try:
                    data = json.loads(json_str)
                    return data
                except:
                    st.error("❌ Impossible de parser la réponse JSON")
                    return None
        return None
            
    except Exception as e:
        st.error(f"❌ Erreur OpenAI Vision: {str(e)}")
        return None

def openai_vision_ocr_facture(image_bytes: bytes) -> Dict:
    """Utilise OpenAI Vision pour analyser une FACTURE"""
    try:
        client = get_openai_client()
        if not client:
            # Mode démo - retourne des données fictives basées sur l'exemple
            return {
                "type_document": "FACTURE EN COMPTE",
                "numero_facture": "240933",
                "date": "16 Septembre 2024",
                "client": "S2M",
                "adresse_livraison": "SCORE FI-Fianarantsoa - Fianarantsoa",
                "bon_commande": "24007505",
                "articles": [
                    {"article_brut": "Côte de Fanar Rouge 75 cls", "quantite": 24},
                    {"article_brut": "Côteau d'Ambalavao Rouge 75 cls", "quantite": 12},
                    {"article_brut": "Coteau d'Ambalavao Rosé 75 cls", "quantite": 12},
                    {"article_brut": "Coteau d'Ambalavao Blanc 75 cls", "quantite": 12},
                    {"article_brut": "Blanc dont de Marcparasy 75 cls", "quantite": 60}
                ]
            }
        
        base64_image = encode_image_to_base64(image_bytes)
        
        prompt = """
        Analyse ce document de type FACTURE et extrais précisément les informations suivantes:
        
        IMPORTANT: Extrais TOUTES les lignes du tableau, y compris les produits.
        
        {
            "type_document": "FACTURE EN COMPTE",
            "numero_facture": "...",
            "date": "...",
            "client": "...",
            "adresse_livraison": "...",
            "bon_commande": "...",
            "articles": [
                {
                    "article_brut": "TEXT EXACT COMME SUR LE DOCUMENT",
                    "quantite": nombre
                }
            ]
        }
        
        RÈGLES STRICTES:
        1. Pour "article_brut": copie EXACTEMENT le texte de la colonne "Description" ou "Désignation" sans modifications
        2. Pour les quantités: extrais le nombre exact de la colonne "Qté" ou "Quantité"
        3. Pour "numero_facture": cherche "N° Facture", "Facture N°", "No." ou similaire
        4. Pour "bon_commande": cherche "Bon de commande", "N° Commande", "BC" ou similaire
        5. Extrais TOUTES les lignes d'articles
        6. Ne standardise PAS les noms, garde-les exactement comme sur le document
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
            max_tokens=3000,
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            try:
                data = json.loads(json_str)
                return data
            except json.JSONDecodeError:
                json_str = re.sub(r'[\x00-\x1f\x7f]', '', json_str)
                try:
                    data = json.loads(json_str)
                    return data
                except:
                    st.error("❌ Impossible de parser la réponse JSON")
                    return None
        return None
            
    except Exception as e:
        st.error(f"❌ Erreur OpenAI Vision: {str(e)}")
        return None

# ============================================================
# FONCTIONS DE STANDARDISATION
# ============================================================
def standardize_product_name_improved(product_name):
    """Standardise le nom du produit pour les factures et BDC"""
    # Votre logique de standardisation existante
    # Pour l'exemple, on retourne le même nom
    return product_name, 1.0, "SUCCESS"

def standardize_product_for_bdc(product_name):
    """Standardise le nom du produit pour les BDC"""
    # Votre logique de standardisation spécifique BDC
    # Pour l'exemple, on retourne le même nom
    return product_name, product_name, 1.0, "SUCCESS"

# ============================================================
# FONCTIONS DE DÉTECTION DE DOUBLONS
# ============================================================
def check_for_duplicates(document_type: str, extracted_data: dict, worksheet) -> Tuple[bool, List[Dict]]:
    """Vérifie si un document existe déjà dans Google Sheets"""
    try:
        all_data = worksheet.get_all_values()
        
        if len(all_data) <= 1:
            return False, []
        
        # Pour les FACTURES
        if "FACTURE" in document_type.upper():
            client_col = 1
            doc_num_col = 4  # NF
            nbc_col = 3      # NBC
            
            current_client = extracted_data.get('client', '')
            current_doc_num = extracted_data.get('numero_facture', '')
            current_nbc = extracted_data.get('bon_commande', '')
            
            duplicates = []
            for i, row in enumerate(all_data[1:], start=2):
                if len(row) > max(doc_num_col, client_col):
                    row_client = row[client_col] if len(row) > client_col else ''
                    row_doc_num = row[doc_num_col] if len(row) > doc_num_col else ''
                    row_nbc = row[nbc_col] if len(row) > nbc_col else ''
                    
                    if (row_client == current_client and 
                        row_doc_num == current_doc_num and 
                        current_client != '' and current_doc_num != ''):
                        
                        duplicates.append({
                            'row_number': i,
                            'data': row,
                            'match_type': 'Client et N° Facture identiques'
                        })
                    
                    elif (row_client == current_client and 
                          row_nbc == current_nbc and 
                          current_client != '' and current_nbc != ''):
                        
                        duplicates.append({
                            'row_number': i,
                            'data': row,
                            'match_type': 'Client et N° Bon de Commande identiques'
                        })
        
        else:  # Pour les BDC
            client_col = 1
            doc_num_col = 3  # NBC
            
            current_client = extracted_data.get('client', '')
            current_doc_num = extracted_data.get('numero', '')
            
            duplicates = []
            for i, row in enumerate(all_data[1:], start=2):
                if len(row) > max(doc_num_col, client_col):
                    row_client = row[client_col] if len(row) > client_col else ''
                    row_doc_num = row[doc_num_col] if len(row) > doc_num_col else ''
                    
                    if (row_client == current_client and 
                        row_doc_num == current_doc_num and 
                        current_client != '' and current_doc_num != ''):
                        
                        match_type = 'Client et Numéro identiques'
                        
                        if "ULYS" in current_client.upper() and "BDC" in document_type.upper():
                            date_col = 2
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
# FONCTIONS DE PRÉPARATION DES DONNÉES
# ============================================================
def prepare_bdc_rows(data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
    """Prépare les lignes pour les BDC (8 colonnes)"""
    rows = []
    
    try:
        mois = data.get("mois", get_month_from_date(data.get("date", "")))
        client = data.get("client", "")
        date = format_date_french(data.get("date", ""))
        nbc = data.get("numero", data.get("bon_commande", ""))
        magasin = data.get("adresse_livraison", "")
        
        for _, row in articles_df.iterrows():
            quantite = row.get("Quantité", 0)
            if pd.isna(quantite) or quantite == 0 or str(quantite).strip() == "0":
                continue
            
            article = str(row.get("Produit Standard", "")).strip()
            if not article:
                article = str(row.get("Produit Brute", "")).strip()
            
            quantite_str = format_quantity(quantite)
            
            rows.append([
                mois,
                client,
                date,
                nbc,      # NBC
                "",       # Lien
                magasin,
                article,
                quantite_str
            ])
        
        return rows
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la préparation des données BDC: {str(e)}")
        return []

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
            quantite = row.get("Quantité", 0)
            if pd.isna(quantite) or quantite == 0 or str(quantite).strip() == "0":
                continue
            
            article = str(row.get("Produit Standard", "")).strip()
            if not article:
                article = str(row.get("Produit Brute", "")).strip()
            
            quantite_str = format_quantity(quantite)
            
            rows.append([
                mois,
                client,
                date,
                nbc,      # NBC
                nf,       # NF
                "",       # Lien
                magasin,
                article,
                quantite_str
            ])
        
        return rows
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la préparation des données facture: {str(e)}")
        return []

# ============================================================
# PAGE DE CHOIX
# ============================================================
def page_choix():
    """Page de sélection du type de document à importer"""
    st.set_page_config(page_title="Choix du Document", page_icon="📄", layout="centered")
    
    st.markdown("""
    <style>
        .main {
            padding: 2rem;
        }
        .stButton > button {
            width: 100%;
            padding: 1.5rem;
            font-size: 1.2rem;
            margin: 1rem 0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.title("📄 Système d'Importation de Documents")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 Factures")
        st.markdown("""
        <div style='padding: 1rem; background-color: #f8f9fa; border-radius: 10px; margin: 1rem 0;'>
            <p><strong>Enregistrement dans:</strong> GID 16102465</p>
            <p><strong>Colonnes:</strong> 9 colonnes</p>
            <p><strong>Extraction:</strong> N° Facture + N° Commande</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("📄 IMPORTER FACTURE", use_container_width=True):
            st.session_state.page = "facture"
            st.rerun()
    
    with col2:
        st.markdown("### 📦 Bons de Commande")
        st.markdown("""
        <div style='padding: 1rem; background-color: #f8f9fa; border-radius: 10px; margin: 1rem 0;'>
            <p><strong>Enregistrement dans:</strong> GID 954728911</p>
            <p><strong>Colonnes:</strong> 8 colonnes</p>
            <p><strong>Clients:</strong> LEADERPRICE, S2M, ULYS</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("📦 IMPORTER BON DE COMMANDE", use_container_width=True):
            st.session_state.page = "bdc"
            st.rerun()
    
    st.markdown("---")
    st.info("👈 Sélectionnez le type de document que vous souhaitez importer")

# ============================================================
# PAGE FACTURE
# ============================================================
def page_facture():
    """Page de traitement des factures"""
    st.set_page_config(page_title="Importation Facture", page_icon="📄", layout="wide")
    
    # Initialisation session state
    if 'uploaded_file' not in st.session_state:
        st.session_state.uploaded_file = None
    if 'uploaded_image' not in st.session_state:
        st.session_state.uploaded_image = None
    if 'ocr_result' not in st.session_state:
        st.session_state.ocr_result = None
    if 'show_results' not in st.session_state:
        st.session_state.show_results = False
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'edited_standardized_df' not in st.session_state:
        st.session_state.edited_standardized_df = None
    
    # Header avec bouton retour
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("📄 Importation de Facture")
    with col2:
        if st.button("🔙 Retour au choix", use_container_width=True):
            st.session_state.page = "choix"
            st.rerun()
    
    st.markdown("""
    <div style="margin: 20px 0; padding: 15px; background: linear-gradient(135deg, #E8F4F8 0%, #D4EAF7 100%); 
                border-radius: 12px; border-left: 4px solid #3B82F6;">
        <strong style="color: #1A1A1A !important;">📄 FACTURE :</strong><br>
        <small style="color: #4B5563 !important;">
        • Enregistrement dans le tableau Factures (GID: 16102465)<br>
        • 9 colonnes: Mois, Client, Date, NBC, NF, Lien, Magasin, Produit, Quantité<br>
        • Extraction automatique du N° Facture et N° Bon de Commande
        </small>
    </div>
    """, unsafe_allow_html=True)
    
    # Section téléchargement
    st.header("1. Téléchargement du Document")
    uploaded = st.file_uploader("Choisissez un fichier image de FACTURE", type=['png', 'jpg', 'jpeg', 'pdf'])
    
    # Traitement
    if uploaded and uploaded != st.session_state.uploaded_file:
        st.session_state.uploaded_file = uploaded
        st.session_state.uploaded_image = Image.open(uploaded)
        st.session_state.processing = True
        st.session_state.show_results = False
        
        with st.spinner("🔍 Analyse de la facture en cours..."):
            try:
                buf = BytesIO()
                st.session_state.uploaded_image.save(buf, format="JPEG")
                image_bytes = buf.getvalue()
                
                img_processed = preprocess_image(image_bytes)
                
                # Analyse spécifique facture
                result = openai_vision_ocr_facture(image_bytes)
                
                if result:
                    st.session_state.ocr_result = result
                    st.session_state.show_results = True
                    st.session_state.processing = False
                    
                    # Préparer les données standardisées
                    if "articles" in result:
                        std_data = []
                        for article in result["articles"]:
                            raw_name = article.get("article_brut", "")
                            
                            produit_brut = raw_name
                            produit_standard, confidence, status = standardize_product_name_improved(raw_name)
                            
                            std_data.append({
                                "Produit Brute": produit_brut,
                                "Produit Standard": produit_standard,
                                "Quantité": article.get("quantite", 0),
                                "Confiance": f"{confidence*100:.1f}%",
                                "Auto": confidence >= 0.7
                            })
                        
                        st.session_state.edited_standardized_df = pd.DataFrame(std_data)
                    
                    st.success("✅ Analyse terminée avec succès!")
                else:
                    st.error("❌ Échec de l'analyse IA - Veuillez réessayer")
                    st.session_state.processing = False
                
            except Exception as e:
                st.error(f"❌ Erreur système: {str(e)}")
                st.session_state.processing = False
    
    # Affichage résultats
    if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
        st.header("2. Informations Extraites")
        
        # Informations de base
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📋 Informations Facture")
            
            # Création du dictionnaire d'informations
            infos = {
                "Client": st.session_state.ocr_result.get('client', 'Non trouvé'),
                "Date": st.session_state.ocr_result.get('date', 'Non trouvée'),
                "N° Facture (NF)": st.session_state.ocr_result.get('numero_facture', 'Non trouvé'),
                "N° Bon de Commande (NBC)": st.session_state.ocr_result.get('bon_commande', 'Non trouvé'),
                "Adresse Livraison": st.session_state.ocr_result.get('adresse_livraison', 'Non trouvée')
            }
            
            # Affichage
            for key, value in infos.items():
                st.info(f"**{key}:** {value}")
        
        with col2:
            st.subheader("🎯 Structure d'Enregistrement")
            st.markdown("""
            <div style="padding: 15px; background-color: #f0f9ff; border-radius: 10px; border: 1px solid #bae6fd;">
                <p><strong>Feuille Google Sheets:</strong> FACTURE EN COMPTE</p>
                <p><strong>GID:</strong> 16102465</p>
                <p><strong>Colonnes:</strong></p>
                <ol style="margin: 10px 0; padding-left: 20px; font-size: 14px;">
                    <li>Mois</li>
                    <li>Client</li>
                    <li>Date</li>
                    <li>NBC (N° Bon de Commande)</li>
                    <li>NF (N° Facture)</li>
                    <li>Lien</li>
                    <li>Magasin</li>
                    <li>Produit</li>
                    <li>Quantité</li>
                </ol>
            </div>
            """, unsafe_allow_html=True)
        
        # Articles
        if 'articles' in st.session_state.ocr_result and st.session_state.ocr_result['articles']:
            st.subheader("📦 Articles Détectés")
            articles_df = pd.DataFrame(st.session_state.ocr_result['articles'])
            st.dataframe(articles_df, use_container_width=True)
        
        # Données standardisées
        if st.session_state.edited_standardized_df is not None:
            st.header("3. Données Standardisées")
            st.dataframe(st.session_state.edited_standardized_df, use_container_width=True)
            
            # Bouton enregistrement
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Enregistrer dans Google Sheets", type="primary", use_container_width=True):
                    # Préparer les données pour l'enregistrement
                    prepared_rows = prepare_facture_rows(
                        st.session_state.ocr_result, 
                        st.session_state.edited_standardized_df
                    )
                    
                    if prepared_rows:
                        # Ici vous ajouteriez le code pour envoyer à Google Sheets
                        st.success(f"✅ Prêt à enregistrer {len(prepared_rows)} lignes dans GID 16102465")
                        
                        # Afficher un aperçu
                        preview_df = pd.DataFrame(prepared_rows, columns=[
                            "Mois", "Client", "Date", "NBC", "NF", "Lien", "Magasin", "Produit", "Quantité"
                        ])
                        st.subheader("Aperçu des données à enregistrer")
                        st.dataframe(preview_df, use_container_width=True)
                    else:
                        st.warning("Aucune donnée à enregistrer")
            
            with col2:
                if st.button("🔄 Analyser un autre document", use_container_width=True):
                    # Réinitialiser
                    for key in ['uploaded_file', 'uploaded_image', 'ocr_result', 
                              'show_results', 'processing', 'edited_standardized_df']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()

# ============================================================
# PAGE BON DE COMMANDE
# ============================================================
def page_bdc():
    """Page de traitement des bons de commande"""
    st.set_page_config(page_title="Importation Bon de Commande", page_icon="📦", layout="wide")
    
    # Initialisation session state
    if 'uploaded_file' not in st.session_state:
        st.session_state.uploaded_file = None
    if 'uploaded_image' not in st.session_state:
        st.session_state.uploaded_image = None
    if 'ocr_result' not in st.session_state:
        st.session_state.ocr_result = None
    if 'show_results' not in st.session_state:
        st.session_state.show_results = False
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'edited_standardized_df' not in st.session_state:
        st.session_state.edited_standardized_df = None
    
    # Header avec bouton retour
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("📦 Importation de Bon de Commande")
    with col2:
        if st.button("🔙 Retour au choix", use_container_width=True):
            st.session_state.page = "choix"
            st.rerun()
    
    st.markdown("""
    <div style="margin: 20px 0; padding: 15px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); 
                border-radius: 12px; border-left: 4px solid #22c55e;">
        <strong style="color: #1A1A1A !important;">📦 BON DE COMMANDE :</strong><br>
        <small style="color: #4B5563 !important;">
        • Enregistrement dans le tableau BDC (GID: 954728911)<br>
        • 8 colonnes: Mois, Client, Date, NBC, Lien, Magasin, Produit, Quantité<br>
        • Clients: LEADERPRICE, S2M, ULYS
        </small>
    </div>
    """, unsafe_allow_html=True)
    
    # Section téléchargement
    st.header("1. Téléchargement du Document")
    uploaded = st.file_uploader("Choisissez un fichier image de BON DE COMMANDE", type=['png', 'jpg', 'jpeg', 'pdf'])
    
    # Traitement
    if uploaded and uploaded != st.session_state.uploaded_file:
        st.session_state.uploaded_file = uploaded
        st.session_state.uploaded_image = Image.open(uploaded)
        st.session_state.processing = True
        st.session_state.show_results = False
        
        with st.spinner("🔍 Analyse du bon de commande en cours..."):
            try:
                buf = BytesIO()
                st.session_state.uploaded_image.save(buf, format="JPEG")
                image_bytes = buf.getvalue()
                
                img_processed = preprocess_image(image_bytes)
                
                # Analyse spécifique BDC
                result = openai_vision_ocr_bdc(image_bytes)
                
                if result:
                    st.session_state.ocr_result = result
                    st.session_state.show_results = True
                    st.session_state.processing = False
                    
                    # Préparer les données standardisées
                    if "articles" in result:
                        std_data = []
                        for article in result["articles"]:
                            raw_name = article.get("article_brut", "")
                            
                            # Vérification des catégories spéciales
                            if any(cat in raw_name.upper() for cat in ["VINS ROUGES", "VINS BLANCS", "VINS ROSES", "LIQUEUR", "CONSIGNE"]):
                                std_data.append({
                                    "Produit Brute": raw_name,
                                    "Produit Standard": raw_name,
                                    "Quantité": 0,
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
                    
                    st.success("✅ Analyse terminée avec succès!")
                else:
                    st.error("❌ Échec de l'analyse IA - Veuillez réessayer")
                    st.session_state.processing = False
                
            except Exception as e:
                st.error(f"❌ Erreur système: {str(e)}")
                st.session_state.processing = False
    
    # Affichage résultats
    if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
        st.header("2. Informations Extraites")
        
        # Informations de base
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📋 Informations Bon de Commande")
            
            infos = {
                "Client": st.session_state.ocr_result.get('client', 'Non trouvé'),
                "Date": st.session_state.ocr_result.get('date', 'Non trouvée'),
                "N° Commande (NBC)": st.session_state.ocr_result.get('numero', 'Non trouvé'),
                "Adresse Livraison": st.session_state.ocr_result.get('adresse_livraison', 'Non trouvée')
            }
            
            for key, value in infos.items():
                st.info(f"**{key}:** {value}")
        
        with col2:
            st.subheader("🎯 Structure d'Enregistrement")
            st.markdown("""
            <div style="padding: 15px; background-color: #f0fdf4; border-radius: 10px; border: 1px solid #bbf7d0;">
                <p><strong>Feuille Google Sheets:</strong> BON DE COMMANDE</p>
                <p><strong>GID:</strong> 954728911</p>
                <p><strong>Colonnes:</strong></p>
                <ol style="margin: 10px 0; padding-left: 20px; font-size: 14px;">
                    <li>Mois</li>
                    <li>Client</li>
                    <li>Date</li>
                    <li>NBC (N° Bon de Commande)</li>
                    <li>Lien</li>
                    <li>Magasin</li>
                    <li>Produit</li>
                    <li>Quantité</li>
                </ol>
            </div>
            """, unsafe_allow_html=True)
        
        # Articles
        if 'articles' in st.session_state.ocr_result and st.session_state.ocr_result['articles']:
            st.subheader("📦 Articles Détectés")
            articles_df = pd.DataFrame(st.session_state.ocr_result['articles'])
            st.dataframe(articles_df, use_container_width=True)
        
        # Données standardisées
        if st.session_state.edited_standardized_df is not None:
            st.header("3. Données Standardisées")
            st.dataframe(st.session_state.edited_standardized_df, use_container_width=True)
            
            # Bouton enregistrement
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚀 Enregistrer dans Google Sheets", type="primary", use_container_width=True):
                    # Préparer les données pour l'enregistrement
                    prepared_rows = prepare_bdc_rows(
                        st.session_state.ocr_result, 
                        st.session_state.edited_standardized_df
                    )
                    
                    if prepared_rows:
                        # Ici vous ajouteriez le code pour envoyer à Google Sheets
                        st.success(f"✅ Prêt à enregistrer {len(prepared_rows)} lignes dans GID 954728911")
                        
                        # Afficher un aperçu
                        preview_df = pd.DataFrame(prepared_rows, columns=[
                            "Mois", "Client", "Date", "NBC", "Lien", "Magasin", "Produit", "Quantité"
                        ])
                        st.subheader("Aperçu des données à enregistrer")
                        st.dataframe(preview_df, use_container_width=True)
                    else:
                        st.warning("Aucune donnée à enregistrer")
            
            with col2:
                if st.button("🔄 Analyser un autre document", use_container_width=True):
                    # Réinitialiser
                    for key in ['uploaded_file', 'uploaded_image', 'ocr_result', 
                              'show_results', 'processing', 'edited_standardized_df']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()

# ============================================================
# APPLICATION PRINCIPALE
# ============================================================
def main():
    # Initialisation de la page
    if 'page' not in st.session_state:
        st.session_state.page = "choix"
    
    # Navigation entre pages
    if st.session_state.page == "choix":
        page_choix()
    elif st.session_state.page == "facture":
        page_facture()
    elif st.session_state.page == "bdc":
        page_bdc()

if __name__ == "__main__":
    main()
