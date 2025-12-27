# ============================================================
# IMPORTS ET CONFIGURATION
# ============================================================
import streamlit as st
import pandas as pd
import json
import re
from PIL import Image
from io import BytesIO
import base64
from typing import Dict, List, Tuple
import pytesseract

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
# FONCTION DE DÉTECTION DE TYPE DE DOCUMENT PAR TITRE
# ============================================================
def detect_document_type_by_title(ocr_result: dict) -> str:
    """
    Détecte le type de document basé sur les titres spécifiques dans le texte OCR.
    """
    if not ocr_result or not isinstance(ocr_result, dict):
        return "INCONNU"
    
    # Récupérer tout le texte OCR combiné pour la détection
    full_text = ""
    
    # Combiner différents champs de texte possibles
    if 'client' in ocr_result:
        full_text += ocr_result.get('client', '') + " "
    if 'adresse_livraison' in ocr_result:
        full_text += ocr_result.get('adresse_livraison', '') + " "
    if 'type_document' in ocr_result:
        full_text += ocr_result.get('type_document', '') + " "
    
    # Ajouter le texte des articles si présent
    if 'articles' in ocr_result:
        for article in ocr_result['articles']:
            full_text += article.get('article_brut', '') + " "
    
    # Vérifier la présence des titres spécifiques
    full_text_upper = full_text.upper()
    
    if "FACTURE EN COMPTE" in full_text_upper:
        return "FACTURE EN COMPTE"
    elif "BON DE COMMANDE FOURNISSEUR" in full_text_upper:
        return "BDC ULYS"
    elif "BON DE COMMANDE /RECEPTION" in full_text_upper or "BON DE COMMANDE/RECEPTION" in full_text_upper:
        return "BDC LEADERPRICE"
    elif "SUPERMAKI" in full_text_upper or "S2M" in full_text_upper:
        return "BDC S2M"
    
    return "INCONNU"

# ============================================================
# FONCTIONS DE DÉTECTION DE DOUBLONS - MIS À JOUR POUR FACTURES
# ============================================================
def check_for_duplicates(document_type: str, extracted_data: dict, worksheet) -> Tuple[bool, List[Dict]]:
    """Vérifie si un document existe déjà dans Google Sheets - MIS À JOUR POUR FACTURES"""
    try:
        all_data = worksheet.get_all_values()
        
        if len(all_data) <= 1:
            return False, []
        
        # Pour les FACTURES : recherche basée sur client et numéro de facture
        if "FACTURE" in document_type.upper():
            # Colonnes pour les factures (9 colonnes)
            # Mois, Client, date, NBC, NF, lien, Magasin, Produit, Quantite
            client_col = 1  # Colonne Client
            doc_num_col = 4  # Colonne NF (numéro de facture)
            current_client = extracted_data.get('client', '')
            current_doc_num = extracted_data.get('numero_facture', '')
            
            # Pour les factures, vérifier aussi le numéro de bon de commande (NBC)
            nbc_col = 3  # Colonne NBC
            current_nbc = extracted_data.get('bon_commande', '')
            
            duplicates = []
            for i, row in enumerate(all_data[1:], start=2):
                if len(row) > max(doc_num_col, client_col):
                    row_client = row[client_col] if len(row) > client_col else ''
                    row_doc_num = row[doc_num_col] if len(row) > doc_num_col else ''
                    row_nbc = row[nbc_col] if len(row) > nbc_col else ''
                    
                    # Vérification 1: Même client et même numéro de facture
                    if (row_client == current_client and 
                        row_doc_num == current_doc_num and 
                        current_client != '' and current_doc_num != ''):
                        
                        match_type = 'Client et N° Facture identiques'
                        duplicates.append({
                            'row_number': i,
                            'data': row,
                            'match_type': match_type
                        })
                    
                    # Vérification 2: Même client et même numéro de bon de commande
                    elif (row_client == current_client and 
                          row_nbc == current_nbc and 
                          current_client != '' and current_nbc != ''):
                        
                        match_type = 'Client et N° Bon de Commande identiques'
                        duplicates.append({
                            'row_number': i,
                            'data': row,
                            'match_type': match_type
                        })
        
        else:
            # Pour les BDC : recherche basée sur client et numéro de BDC
            client_col = 1  # Colonne client
            doc_num_col = 3  # Colonne NBC
            
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
                        
                        # Vérification supplémentaire pour les BDC ULYS
                        if "ULYS" in current_client.upper() and "BDC" in document_type.upper():
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
# MISE À JOUR DE LA FONCTION DE NORMALISATION DU TYPE DE DOCUMENT
# ============================================================
def normalize_document_type(doc_type: str, ocr_result: dict = None) -> str:
    """Normalise le type de document pour correspondre aux clés SHEET_GIDS"""
    if not doc_type:
        return "DOCUMENT INCONNU"
    
    doc_type_upper = doc_type.upper()
    
    # D'abord, essayer de détecter par titre si un résultat OCR est fourni
    if ocr_result:
        title_detected = detect_document_type_by_title(ocr_result)
        if title_detected != "INCONNU":
            return title_detected
    
    # Mapping des types de documents
    if "FACTURE" in doc_type_upper and "COMPTE" in doc_type_upper:
        return "FACTURE EN COMPTE"
    elif "FACTURE" in doc_type_upper:
        return "FACTURE EN COMPTE"  # Toutes les factures vont dans la même feuille
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
# FONCTION DE CONFIRMATION AVANT IMPORTATION
# ============================================================
def show_confirmation_before_import(detected_type: str):
    """
    Affiche une boîte de dialogue de confirmation avant l'importation
    Retourne le type de document confirmé par l'utilisateur
    """
    st.markdown(f"""
    <div style="margin: 20px 0; padding: 20px; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); 
                border-radius: 12px; border: 2px solid #dee2e6; text-align: center;">
        <h4 style="color: #1A1A1A !important; margin-bottom: 15px;">⚠️ CONFIRMATION AVANT IMPORTATION</h4>
        <p style="color: #495057 !important; font-size: 16px;">
        Le document détecté est de type : <strong style="color: #3B82F6 !important;">{detected_type}</strong>
        </p>
        <p style="color: #6c757d !important; font-size: 14px;">
        Souhaitez-vous l'enregistrer ?
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Créer deux colonnes pour les boutons
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button("✅ Enregistrer comme **FACTURE**", 
                    use_container_width=True,
                    type="primary",
                    help="Enregistrer le document dans la feuille Factures",
                    key="confirm_facture"):
            return "FACTURE EN COMPTE"
    
    with col2:
        if st.button("📋 Enregistrer comme **BON DE COMMANDE**", 
                    use_container_width=True,
                    type="secondary",
                    help="Enregistrer le document dans la feuille BDC",
                    key="confirm_bdc"):
            # Déterminer le type de BDC
            if "ULYS" in detected_type:
                return "BDC ULYS"
            elif "S2M" in detected_type or "SUPERMAKI" in detected_type:
                return "BDC S2M"
            else:
                return "BDC LEADERPRICE"
    
    with col3:
        if st.button("❌ Annuler l'importation", 
                    use_container_width=True,
                    type="secondary",
                    key="cancel_import"):
            return "CANCEL"
    
    return None

# ============================================================
# FONCTIONS OCR ET TRAITEMENT D'IMAGES
# ============================================================
def encode_image_to_base64(image_bytes):
    """Encode une image en base64"""
    return base64.b64encode(image_bytes).decode('utf-8')

def preprocess_image(image_bytes):
    """Prétraite l'image pour améliorer l'OCR"""
    image = Image.open(BytesIO(image_bytes))
    # Convertir en niveaux de gris
    if image.mode != 'L':
        image = image.convert('L')
    return image

def get_openai_client():
    """Initialise et retourne le client OpenAI"""
    # Implémentez votre propre logique d'initialisation OpenAI
    return None

def openai_vision_ocr_improved(image_bytes):
    """Utilise OpenAI Vision pour analyser un document"""
    try:
        client = get_openai_client()
        if not client:
            return None
        
        base64_image = encode_image_to_base64(image_bytes)
        
        prompt = """
        Analyse ce document et extrais précisément les informations suivantes:
        
        {
            "type_document": "...",
            "numero": "...",
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
                    return None
        return None
            
    except Exception as e:
        st.error(f"❌ Erreur OpenAI Vision: {str(e)}")
        return None

def openai_vision_ocr_facture(image_bytes):
    """Utilise OpenAI Vision pour analyser une FACTURE"""
    try:
        client = get_openai_client()
        if not client:
            return None
        
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
                    return None
        return None
            
    except Exception as e:
        st.error(f"❌ Erreur OpenAI Vision: {str(e)}")
        return None

# ============================================================
# FONCTIONS DE STANDARDISATION
# ============================================================
def standardize_product_name_improved(product_name):
    """Standardise le nom du produit"""
    # Implémentez votre logique de standardisation
    return product_name, 1.0, "SUCCESS"

def standardize_product_for_bdc(product_name):
    """Standardise le nom du produit pour les BDC"""
    # Implémentez votre logique de standardisation pour BDC
    return product_name, product_name, 1.0, "SUCCESS"

# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================
def format_date_french(date_str):
    """Formate une date en français"""
    return date_str

def get_month_from_date(date_str):
    """Extrait le mois d'une date"""
    return ""

def format_quantity(quantity):
    """Formate une quantité"""
    return str(quantity)

# ============================================================
# FONCTION DE PRÉPARATION DES DONNÉES
# ============================================================
def prepare_facture_rows(data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
    """Prépare les lignes pour les factures (9 colonnes) - MIS À JOUR"""
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
                nbc,      # NBC (Bon de commande)
                nf,       # NF (Numéro de facture)
                "",       # Lien (vide par défaut)
                magasin,
                article,
                quantite_str
            ])
        
        return rows
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la préparation des données facture: {str(e)}")
        return []

# ============================================================
# FONCTION DE SYNCHRONISATION AVEC GOOGLE SHEETS
# ============================================================
def sync_to_google_sheets(document_type: str = None):
    """
    Synchronise les données avec Google Sheets en utilisant le type de document spécifié
    """
    try:
        # Utiliser le type confirmé si disponible, sinon le type détecté
        if hasattr(st.session_state, 'confirmed_document_type') and st.session_state.confirmed_document_type:
            doc_type = st.session_state.confirmed_document_type
        elif document_type:
            doc_type = document_type
        elif hasattr(st.session_state, 'detected_document_type') and st.session_state.detected_document_type:
            doc_type = st.session_state.detected_document_type
        else:
            st.error("❌ Type de document non spécifié")
            return
        
        # Normaliser le type de document
        normalized_type = normalize_document_type(doc_type, st.session_state.ocr_result)
        
        # Récupérer le GID approprié
        if normalized_type in SHEET_GIDS:
            gid = SHEET_GIDS[normalized_type]
            st.success(f"✅ Synchronisation avec Google Sheets - Type: {normalized_type} - GID: {gid}")
            # Ici, vous ajouteriez le code pour envoyer les données à Google Sheets
        else:
            st.error(f"❌ Type de document non reconnu : {normalized_type}")
            return
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la synchronisation: {str(e)}")

# ============================================================
# INTERFACE STREAMLET PRINCIPALE
# ============================================================
def main():
    st.set_page_config(page_title="Scanner de Documents", page_icon="📄", layout="wide")
    
    st.title("📄 Système de Scan et Importation de Documents")
    
    # Initialisation des variables de session
    if 'uploaded_file' not in st.session_state:
        st.session_state.uploaded_file = None
    if 'uploaded_image' not in st.session_state:
        st.session_state.uploaded_image = None
    if 'ocr_result' not in st.session_state:
        st.session_state.ocr_result = None
    if 'detected_document_type' not in st.session_state:
        st.session_state.detected_document_type = None
    if 'confirmed_document_type' not in st.session_state:
        st.session_state.confirmed_document_type = None
    if 'show_results' not in st.session_state:
        st.session_state.show_results = False
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'import_confirmed' not in st.session_state:
        st.session_state.import_confirmed = False
    if 'edited_standardized_df' not in st.session_state:
        st.session_state.edited_standardized_df = None
    
    # Section de téléchargement
    st.header("1. Téléchargement du Document")
    uploaded = st.file_uploader("Choisissez un fichier image", type=['png', 'jpg', 'jpeg', 'pdf'])
    
    # Section de traitement
    if uploaded and uploaded != st.session_state.uploaded_file:
        st.session_state.uploaded_file = uploaded
        st.session_state.uploaded_image = Image.open(uploaded)
        st.session_state.processing = True
        st.session_state.show_results = False
        st.session_state.import_confirmed = False
        st.session_state.confirmed_document_type = None
        
        with st.spinner("🔍 Analyse du document en cours..."):
            try:
                buf = BytesIO()
                st.session_state.uploaded_image.save(buf, format="JPEG")
                image_bytes = buf.getvalue()
                
                # Prétraitement de l'image
                img_processed = preprocess_image(image_bytes)
                
                # Analyse avec OpenAI Vision
                result = openai_vision_ocr_improved(image_bytes)
                
                if result:
                    st.session_state.ocr_result = result
                    raw_doc_type = result.get("type_document", "DOCUMENT INCONNU")
                    
                    # Détecter le type de document
                    detected_type = detect_document_type_by_title(result)
                    if detected_type == "INCONNU":
                        detected_type = normalize_document_type(raw_doc_type, result)
                    
                    st.session_state.detected_document_type = detected_type
                    st.session_state.show_results = True
                    
                    # Si c'est une facture, réanalyser avec le modèle spécifique
                    if "FACTURE" in detected_type.upper():
                        st.info("📄 Document détecté comme FACTURE - Analyse spécifique en cours...")
                        facture_result = openai_vision_ocr_facture(image_bytes)
                        if facture_result:
                            st.session_state.ocr_result = facture_result
                    
                    st.success("✅ Analyse terminée avec succès!")
                    
                else:
                    st.error("❌ Échec de l'analyse IA - Veuillez réessayer")
                    st.session_state.processing = False
                
            except Exception as e:
                st.error(f"❌ Erreur système: {str(e)}")
                st.session_state.processing = False
    
    # Affichage des résultats et confirmation
    if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
        st.header("2. Résultats de l'Analyse")
        
        # Afficher les informations extraites
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📋 Informations du Document")
            if 'client' in st.session_state.ocr_result:
                st.info(f"**Client:** {st.session_state.ocr_result.get('client', 'Non trouvé')}")
            if 'date' in st.session_state.ocr_result:
                st.info(f"**Date:** {st.session_state.ocr_result.get('date', 'Non trouvée')}")
            if 'numero_facture' in st.session_state.ocr_result:
                st.info(f"**N° Facture:** {st.session_state.ocr_result.get('numero_facture', 'Non trouvé')}")
            elif 'numero' in st.session_state.ocr_result:
                st.info(f"**N° Document:** {st.session_state.ocr_result.get('numero', 'Non trouvé')}")
        
        with col2:
            st.subheader("🎯 Type Détecté")
            st.markdown(f"""
            <div style="padding: 15px; background-color: #e8f4f8; border-radius: 10px; border-left: 5px solid #3B82F6;">
                <h4 style="margin: 0; color: #1A1A1A;">{st.session_state.detected_document_type}</h4>
                <p style="margin: 5px 0 0 0; color: #4B5563; font-size: 14px;">
                Basé sur l'analyse du titre et du contenu
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        # Afficher les articles
        if 'articles' in st.session_state.ocr_result and st.session_state.ocr_result['articles']:
            st.subheader("📦 Articles Détectés")
            articles_df = pd.DataFrame(st.session_state.ocr_result['articles'])
            st.dataframe(articles_df, use_container_width=True)
        
        # SECTION DE CONFIRMATION AVANT IMPORTATION
        st.markdown("---")
        st.header("3. Confirmation avant Importation")
        
        # Afficher la boîte de confirmation seulement si non encore confirmé
        if not st.session_state.import_confirmed:
            confirmed_type = show_confirmation_before_import(st.session_state.detected_document_type)
            
            if confirmed_type == "CANCEL":
                st.warning("❌ Importation annulée. Le document ne sera pas enregistré.")
                st.session_state.import_confirmed = False
            elif confirmed_type:
                st.session_state.confirmed_document_type = confirmed_type
                st.session_state.import_confirmed = True
                st.success(f"✅ Confirmation reçue : le document sera enregistré comme **{confirmed_type}**")
                st.rerun()
        else:
            # Préparer les données standardisées
            if 'articles' in st.session_state.ocr_result:
                std_data = []
                for article in st.session_state.ocr_result['articles']:
                    raw_name = article.get('article_brut', article.get('article', ''))
                    
                    # Pour les factures
                    if "FACTURE" in st.session_state.confirmed_document_type.upper():
                        produit_brut = raw_name
                        produit_standard, confidence, status = standardize_product_name_improved(raw_name)
                        
                        std_data.append({
                            "Produit Brute": produit_brut,
                            "Produit Standard": produit_standard,
                            "Quantité": article.get("quantite", 0),
                            "Confiance": f"{confidence*100:.1f}%",
                            "Auto": confidence >= 0.7
                        })
                    else:
                        # Pour les BDC
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
                
                # Créer le dataframe standardisé
                st.session_state.edited_standardized_df = pd.DataFrame(std_data)
                
                # Afficher les données préparées
                st.subheader("📋 Données préparées pour l'importation")
                st.dataframe(st.session_state.edited_standardized_df, use_container_width=True)
                
                # Bouton final pour synchroniser
                st.markdown("---")
                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button("🚀 Synchroniser avec Google Sheets", 
                                type="primary", 
                                use_container_width=True,
                                key="final_sync_button"):
                        sync_to_google_sheets()
                with col2:
                    if st.button("🔄 Recommencer", 
                                type="secondary",
                                use_container_width=True,
                                key="restart_button"):
                        # Réinitialiser les variables de session
                        for key in ['uploaded_file', 'uploaded_image', 'ocr_result', 
                                  'detected_document_type', 'confirmed_document_type',
                                  'show_results', 'processing', 'import_confirmed',
                                  'edited_standardized_df']:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()

if __name__ == "__main__":
    main()
