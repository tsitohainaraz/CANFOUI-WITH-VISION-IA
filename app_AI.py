import streamlit as st
import pandas as pd
import json
import re
from PIL import Image
from io import BytesIO
import base64
from typing import Dict, List, Tuple

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
    # Implémentation de votre client OpenAI
    # return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    return None

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
# FONCTIONS OCR
# ============================================================
def openai_vision_ocr_improved(image_bytes: bytes) -> Dict:
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
    return product_name, 1.0, "SUCCESS"

def standardize_product_for_bdc(product_name):
    """Standardise le nom du produit pour les BDC"""
    return product_name, product_name, 1.0, "SUCCESS"

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
def normalize_document_type(doc_type: str) -> str:
    """Normalise le type de document pour correspondre aux clés SHEET_GIDS"""
    if not doc_type:
        return "DOCUMENT INCONNU"
    
    doc_type_upper = doc_type.upper()
    
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
# MISE À JOUR DE LA PRÉPARATION DES DONNÉES POUR LES FACTURES
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
# APPLICATION STREAMLET PRINCIPALE
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
    if 'show_results' not in st.session_state:
        st.session_state.show_results = False
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'edited_standardized_df' not in st.session_state:
        st.session_state.edited_standardized_df = None
    
    # Section de téléchargement
    st.header("1. Téléchargement du Document")
    uploaded = st.file_uploader("Choisissez un fichier image", type=['png', 'jpg', 'jpeg', 'pdf'])
    
    # Traitement du document
    if uploaded and uploaded != st.session_state.uploaded_file:
        st.session_state.uploaded_file = uploaded
        st.session_state.uploaded_image = Image.open(uploaded)
        st.session_state.processing = True
        st.session_state.show_results = False
        
        with st.spinner("🔍 Analyse du document en cours..."):
            try:
                buf = BytesIO()
                st.session_state.uploaded_image.save(buf, format="JPEG")
                image_bytes = buf.getvalue()
                
                # Prétraitement de l'image
                img_processed = preprocess_image(image_bytes)
                
                # Analyse avec OpenAI Vision
                result = openai_vision_ocr_improved(img_processed)
                
                if result:
                    st.session_state.ocr_result = result
                    raw_doc_type = result.get("type_document", "DOCUMENT INCONNU")
                    
                    # Si c'est une facture, réanalyser avec le modèle spécifique facture
                    if "FACTURE" in raw_doc_type.upper():
                        st.info("📄 Document détecté comme FACTURE - Analyse spécifique en cours...")
                        # Réanalyser avec le modèle facture
                        facture_result = openai_vision_ocr_facture(img_processed)
                        if facture_result:
                            st.session_state.ocr_result = facture_result
                            raw_doc_type = "FACTURE EN COMPTE"
                    
                    # Normaliser le type de document détecté
                    st.session_state.detected_document_type = normalize_document_type(raw_doc_type)
                    st.session_state.show_results = True
                    st.session_state.processing = False
                    
                    # Préparer les données standardisées
                    if "articles" in st.session_state.ocr_result:
                        std_data = []
                        for article in st.session_state.ocr_result["articles"]:
                            raw_name = article.get("article_brut", article.get("article", ""))
                            
                            # Pour les factures, on standardise différemment
                            if "FACTURE" in st.session_state.detected_document_type.upper():
                                # Standardisation pour les factures
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
                                # Pour les BDC, utiliser la standardisation existante
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
                        
                        # Créer le dataframe standardisé pour l'édition
                        st.session_state.edited_standardized_df = pd.DataFrame(std_data)
                    
                    st.success("✅ Analyse terminée avec succès!")
                    
                else:
                    st.error("❌ Échec de l'analyse IA - Veuillez réessayer")
                    st.session_state.processing = False
                
            except Exception as e:
                st.error(f"❌ Erreur système: {str(e)}")
                st.session_state.processing = False
    
    # Affichage des résultats
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
                Basé sur l'analyse du contenu
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        # Afficher les articles
        if 'articles' in st.session_state.ocr_result and st.session_state.ocr_result['articles']:
            st.subheader("📦 Articles Détectés")
            articles_df = pd.DataFrame(st.session_state.ocr_result['articles'])
            st.dataframe(articles_df, use_container_width=True)
        
        # Afficher les données standardisées
        if st.session_state.edited_standardized_df is not None:
            st.subheader("📊 Données Standardisées")
            st.dataframe(st.session_state.edited_standardized_df, use_container_width=True)
            
            # Ajouter une mention spécifique pour les factures
            if "FACTURE" in st.session_state.detected_document_type.upper():
                st.markdown(f'''
                <div style="margin: 10px 0; padding: 12px; background: linear-gradient(135deg, #E8F4F8 0%, #D4EAF7 100%); 
                            border-radius: 12px; border-left: 4px solid #3B82F6;">
                    <strong style="color: #1A1A1A !important;">📄 FACTURE DÉTECTÉE :</strong><br>
                    <small style="color: #4B5563 !important;">
                    • Enregistrement dans le tableau Factures (GID: 16102465)<br>
                    • Détection de doublon active (Client + N° Facture)<br>
                    • 9 colonnes: Mois, Client, Date, NBC, NF, Lien, Magasin, Produit, Quantité
                    </small>
                </div>
                ''', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
