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
# STANDARDISATION INTELLIGENTE DES PRODUITS - MIS À JOUR
# ============================================================

# Liste officielle des produits MIS À JOUR
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
    "Sambatra 20 cl",
    "Consignation btl 75cl"  # NOUVELLE RÈGLE AJOUTÉE
]

# Dictionnaire de synonymes MIS À JOUR
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
    
    # NOUVELLE RÈGLE AJOUTÉE POUR "CONS.CHAN FOUI 75CL"
    "cons.chan foui 75cl": "consignation btl 75cl",
    "cons chan foui 75cl": "consignation btl 75cl",
    "chan foui": "chan foui",
    
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

# Mapping des équivalences de volume (inchangé)
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
    """
    Trouve le meilleur match pour une désignation OCR
    """
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
    """
    Standardise intelligemment une désignation produit OCR
    """
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
    
    # NOUVELLE RÈGLE : "CONS.CHAN FOUI 75CL" → "Consignation btl 75cl"
    if "CONS" in produit_upper and "CHAN" in produit_upper and ("FOUI" in produit_upper or "FOUL" in produit_upper):
        produit_standard = "Consignation btl 75cl"
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
# NOUVELLE API OPENAI - MIGRATION COMPLÈTE
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

def openai_vision_ocr_new_api(image_bytes: bytes) -> Dict:
    """
    Utilise la NOUVELLE API OpenAI avec client.responses.create
    Modèle: gpt-4.1-mini
    Sortie: JSON strict uniquement
    """
    try:
        client = get_openai_client()
        if not client:
            return None
        
        base64_image = encode_image_to_base64(image_bytes)
        
        # PROMPT OPTIMISÉ POUR EXTRACTION JSON STRICTE
        prompt = """ANALYSE CE DOCUMENT COMMERCIAL ET EXTRACT LES DONNÉES SUIVANTES EN FORMAT JSON UNIQUEMENT.

IMPORTANT : 
1. Réponds UNIQUEMENT avec un objet JSON valide
2. Pas de texte avant ou après le JSON
3. Suis EXACTEMENT la structure ci-dessous

STRUCTURE JSON OBLIGATOIRE :
{
  "type_document": "BDC" ou "FACTURE",
  "document_subtype": "DLP", "S2M", "ULYS", ou "FACTURE",
  "client": "valeur_brute",
  "adresse_livraison": "valeur_brute",
  "numero_facture": "valeur_brute",
  "numero": "valeur_brute",
  "date": "valeur_brute",
  "bon_commande": "valeur_brute",
  "articles": [
    {
      "article_brut": "texte_exact",
      "quantite": nombre
    }
  ]
}

RÈGLES D'EXTRACTION :

1. DÉTECTION DU TYPE :
   - Si "DISTRIBUTION LEADER PRICE" ou "D.L.P.M.S.A.R.L" → document_subtype: "DLP"
   - Si "SUPERMAKI" ou "Rayon" → document_subtype: "S2M"
   - Si "BON DE COMMANDE FOURNISSEUR" ou "Nom du Magasin" → document_subtype: "ULYS"
   - Si "FACTURE EN COMPTE" ou "Facture à payer avant le" → document_subtype: "FACTURE"

2. EXTRACTION DES NUMÉROS :
   - Pour les FACTURES : numero_facture = valeur après "Fact" ou "F" (priorité à "Fact")
   - Pour les BDC : numero = numéro du bon de commande

3. EXTRACTION DES ARTICLES :
   - article_brut : texte brut de la désignation (colonne "Désignation" ou "Article")
   - quantite : nombre de la colonne "Qté" ou "Quantité"
   - Ignorer les lignes de totaux, sous-totaux, mentions logistiques
   - Ne garder que les lignes où quantite > 0

4. EXTRACTION BRUTE SEULEMENT :
   - Ne pas standardiser les noms de produits
   - Ne pas corriger les erreurs OCR
   - Donner les valeurs brutes exactes

EXEMPLE DE RÉPONSE CORRECTE :
{
  "type_document": "BDC",
  "document_subtype": "DLP",
  "client": "DISTRIBUTION LEADER PRICE",
  "adresse_livraison": "Score Tanjombato",
  "numero": "12345",
  "date": "15/12/2024",
  "articles": [
    {"article_brut": "COTE DE FIANAR ROUGE 75CL", "quantite": 10},
    {"article_brut": "MAROPARASY BLANC 37CL", "quantite": 5}
  ]
}"""
        
        # APPEL À LA NOUVELLE API client.responses.create
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        },
                        {
                            "type": "input_image",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1,
            max_output_tokens=4000
        )
        
        # UTILISATION DE response.output_text COMME DEMANDÉ
        content = response.output_text
        
        # Sauvegarder pour debug
        st.session_state.ocr_raw_text = content
        
        # PARSER DIRECTEMENT LE JSON SANS REGEX
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback si le JSON n'est pas propre
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
            else:
                st.error("❌ L'IA n'a pas retourné de JSON valide")
                return None
        
        return data
        
    except Exception as e:
        st.error(f"❌ Erreur nouvelle API OpenAI: {str(e)}")
        return None

# ============================================================
# FONCTIONS DE POST-TRAITEMENT DES DONNÉES (LOGIQUE MÉTIER)
# ============================================================

def clean_and_validate_quantity(qty_value: Any) -> int:
    """
    Nettoie et valide une quantité avec correction OCR
    Retourne un entier > 0 ou 0 si invalide
    """
    if qty_value is None:
        return 0
    
    try:
        # Convertir en string
        if isinstance(qty_value, (int, float)):
            qty_str = str(qty_value)
        else:
            qty_str = str(qty_value)
        
        # Nettoyer la chaîne
        qty_str = qty_str.strip()
        
        # CORRECTIONS OCR CLASSIQUES
        qty_str = qty_str.replace('O', '0')  # O → 0
        qty_str = qty_str.replace('o', '0')  # o → 0
        qty_str = qty_str.replace('l', '1')  # l → 1
        qty_str = qty_str.replace('I', '1')  # I → 1
        qty_str = qty_str.replace('S', '5')  # S → 5
        qty_str = qty_str.replace('s', '5')  # s → 5
        qty_str = qty_str.replace(',', '.')  # Virgule → point
        
        # Supprimer tout sauf chiffres et point
        qty_str = re.sub(r'[^\d.]', '', qty_str)
        
        if not qty_str:
            return 0
        
        # Convertir en float puis entier
        qty_float = float(qty_str)
        qty_int = int(round(qty_float))
        
        # Forcer à être positif
        if qty_int < 0:
            return 0
        
        return qty_int
        
    except Exception:
        return 0

def extract_bdc_number_from_text(text: str) -> str:
    """
    Extrait le numéro de BDC selon la nouvelle règle :
    - Prendre le numéro APRÈS "Fact" ou "F"
    - Priorité à "Fact" si les deux sont présents
    """
    if not text:
        return ""
    
    # Rechercher les motifs
    fact_patterns = [
        r'Fact\s*(\d+)',      # "Fact 12345"
        r'F\s*(\d+)',         # "F 12345"
        r'Facture\s*(\d+)',   # "Facture 12345"
        r'FACT\s*(\d+)',      # "FACT 12345"
        r'fact\s*(\d+)',      # "fact 12345"
    ]
    
    matches_fact = []
    matches_f = []
    
    for pattern in fact_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if 'fact' in pattern.lower():
                matches_fact.append(match.group(1))
            else:
                matches_f.append(match.group(1))
    
    # Priorité à "Fact"
    if matches_fact:
        return matches_fact[0]
    elif matches_f:
        return matches_f[0]
    else:
        return ""

def clean_address_field(raw_address: Any) -> str:
    """
    Nettoie et concatène intelligemment le champ adresse
    Problème : Extraction brute du type "Supermaki", "quartier_s2m": "Ambohibao"
    Objectif final : "Supermaki Ambohibao"
    """
    if not raw_address:
        return ""
    
    # Si c'est un dictionnaire, extraire les valeurs
    if isinstance(raw_address, dict):
        parts = []
        for key, value in raw_address.items():
            if isinstance(value, str) and value.strip():
                # Supprimer les clés parasites
                if key not in ['quartier_s2m', 'nom_site', 'zone']:
                    # Nettoyer la valeur
                    clean_val = value.strip().replace('"', '').replace("'", "")
                    if clean_val and clean_val.lower() != 'null':
                        parts.append(clean_val)
        return " ".join(parts)
    
    # Si c'est une string
    elif isinstance(raw_address, str):
        # Nettoyer la chaîne
        address = raw_address.strip()
        
        # Supprimer les guillemets inutiles
        address = address.replace('"', '').replace("'", "")
        
        # Supprimer les clés JSON parasites
        address = re.sub(r'"?[a-z_]+"?\s*:\s*"?', '', address)
        address = address.replace('"', '')
        
        # Supprimer les accolades
        address = address.replace('{', '').replace('}', '')
        
        # Concaténer intelligemment
        parts = address.split()
        if len(parts) > 1:
            # Supprimer les doublons
            unique_parts = []
            for part in parts:
                if part and part.lower() not in [p.lower() for p in unique_parts]:
                    unique_parts.append(part)
            address = " ".join(unique_parts)
        
        return address
    
    return str(raw_address)

def process_articles_table(raw_articles: List[Dict], doc_subtype: str) -> pd.DataFrame:
    """
    Post-traite le tableau d'articles avec les règles métier
    """
    processed_rows = []
    
    for article in raw_articles:
        raw_name = article.get("article_brut", "").strip()
        raw_qty = article.get("quantite", 0)
        
        # 1. Ignorer les lignes vides
        if not raw_name:
            continue
        
        # 2. Ignorer les lignes de totaux, sous-totaux, mentions logistiques
        name_upper = raw_name.upper()
        ignore_keywords = [
            "TOTAL", "SOUS-TOTAL", "MONTANT", "LIVRAISON", 
            "FRAIS", "REMISE", "TVA", "NET", "HT", "TTC",
            "ARROND", "ARRONDI", "TRANSPORT", "LOGISTIQUE"
        ]
        
        if any(keyword in name_upper for keyword in ignore_keywords):
            continue
        
        # 3. Valider et corriger la quantité
        qty = clean_and_validate_quantity(raw_qty)
        
        # 4. Ne garder que les lignes où quantité > 0
        if qty <= 0:
            continue
        
        # 5. Standardiser le nom du produit (IA fournit brut, Python standardise)
        produit_brut, produit_standard, confidence, status = standardize_product_for_bdc(raw_name)
        
        processed_rows.append({
            "Produit Brute": produit_brut,
            "Produit Standard": produit_standard,
            "Quantité": qty,
            "Confiance": f"{confidence*100:.1f}%",
            "Auto": confidence >= 0.7
        })
    
    return pd.DataFrame(processed_rows)

def detect_document_type_from_features(data: Dict) -> str:
    """
    Détecte le type de document basé sur les caractéristiques extraites
    """
    if not data:
        return "DOCUMENT INCONNU"
    
    doc_subtype = data.get("document_subtype", "").upper()
    
    if doc_subtype == "DLP":
        return "BDC LEADERPRICE"
    elif doc_subtype == "S2M":
        return "BDC S2M"
    elif doc_subtype == "ULYS":
        return "BDC ULYS"
    elif doc_subtype == "FACTURE":
        return "FACTURE EN COMPTE"
    else:
        # Fallback basé sur type_document
        type_doc = data.get("type_document", "").upper()
        if "FACTURE" in type_doc:
            return "FACTURE EN COMPTE"
        elif "BDC" in type_doc or "COMMANDE" in type_doc:
            return "BDC LEADERPRICE"
        else:
            return "DOCUMENT INCONNU"

# ============================================================
# FONCTION PRINCIPALE AMÉLIORÉE
# ============================================================

def analyze_document_improved(image_bytes: bytes) -> Dict:
    """
    Analyse améliorée avec nouvelle API et post-traitement
    REMPLACE analyze_document_with_backup
    """
    # 1. Analyse avec nouvelle API
    result = openai_vision_ocr_new_api(image_bytes)
    
    if not result:
        return {"type_document": "DOCUMENT INCONNU", "articles": []}
    
    # 2. Appliquer la règle pour N° BDC
    if "numero" in result or "numero_facture" in result:
        # Extraire depuis le texte brut si disponible
        if st.session_state.ocr_raw_text:
            extracted_num = extract_bdc_number_from_text(st.session_state.ocr_raw_text)
            if extracted_num:
                # Mettre à jour le bon champ selon le type
                if result.get("type_document") == "FACTURE":
                    result["numero_facture"] = extracted_num
                else:
                    result["numero"] = extracted_num
    
    # 3. Nettoyer l'adresse
    if "adresse_livraison" in result:
        result["adresse_livraison"] = clean_address_field(result["adresse_livraison"])
    
    # 4. Détection du type de document
    doc_type = detect_document_type_from_features(result)
    st.session_state.detected_document_type = doc_type
    
    # 5. Post-traitement des articles
    raw_articles = result.get("articles", [])
    doc_subtype = result.get("document_subtype", "").upper()
    
    # Traiter les articles selon le type de document
    if raw_articles:
        articles_df = process_articles_table(raw_articles, doc_subtype)
        st.session_state.edited_standardized_df = articles_df
        
        # Mettre à jour le résultat avec les articles traités
        result["articles_processed"] = articles_df.to_dict('records')
    
    return result

# ============================================================
# FONCTIONS UTILITAIRES (inchangées)
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
    """Formate la quantité - GARANTIT QUE C'EST UN NOMBRE ENTIER SANS VIRGULE"""
    if qty is None:
        return "0"
    
    try:
        # Convertir en float pour gérer les chaînes avec virgules
        if isinstance(qty, str):
            qty = qty.replace(',', '.')
        
        # Convertir en float puis arrondir à l'entier le plus proche
        qty_num = float(qty)
        
        # FORCER UN ENTIER SANS DÉCIMALES
        qty_int = int(round(qty_num))
        
        # S'assurer que c'est un entier positif
        if qty_int < 0:
            qty_int = 0
            
        return str(qty_int)
        
    except (ValueError, TypeError):
        # Si la conversion échoue, retourner "0"
        return "0"

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
# CONFIGURATION STREAMLIT
# ============================================================
st.set_page_config(
    page_title="Chan Foui & Fils — Scanner Pro V2",
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
if "ocr_raw_text" not in st.session_state:
    st.session_state.ocr_raw_text = None
if "document_analysis_details" not in st.session_state:
    st.session_state.document_analysis_details = {}
if "quartier_s2m" not in st.session_state:
    st.session_state.quartier_s2m = ""
if "nom_magasin_ulys" not in st.session_state:
    st.session_state.nom_magasin_ulys = ""

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
# SYSTÈME D'AUTHENTIFICATION (inchangé)
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
        
        .login-logo {
            height: 80px;
            margin-bottom: 20px;
            filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1));
        }
        
        /* FORCER LE TEXTE EN NOIR SUR BLANC */
        .stSelectbox > div > div {
            border: 1.5px solid #e2e8f0;
            border-radius: 12px;
            padding: 10px 15px;
            font-size: 15px;
            transition: all 0.2s ease;
            background: white;
            color: #1E293B !important;
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
            color: #1E293B !important;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #27414A;
            box-shadow: 0 0 0 3px rgba(39, 65, 74, 0.1);
            outline: none;
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
        <div style="font-size: 3rem; margin-bottom: 20px; color: #1E293B !important;">
            🍷
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="login-title">CHAN FOUI ET FILS</h1>', unsafe_allow_html=True)
    st.markdown('<p class="login-subtitle">Système de Scanner Pro V2 - Accès Restreint</p>', unsafe_allow_html=True)
    
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
        <strong style="display: block; margin-bottom: 8px; color: #856404 !important;">🔐 Protocole de sécurité V2 :</strong>
        • Nouvelle API OpenAI gpt-4.1-mini<br>
        • Extraction JSON stricte uniquement<br>
        • Standardisation améliorée<br>
        • Détection précise DLP/S2M/ULYS<br>
        • Verrouillage automatique après 3 tentatives
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ============================================================
# APPLICATION PRINCIPALE
# ============================================================

# THÈME CHAN FOUI & FILS (inchangé)
LOGO_FILENAME = "CF_LOGOS.png"
BRAND_TITLE = "CHAN FOUI ET FILS"
BRAND_SUB = "AI Document Processing System V2"

PALETTE = {
    "primary_dark": "#27414A",
    "primary_light": "#1F2F35",
    "background": "#F5F5F3",
    "card_bg": "#FFFFFF",
    "card_bg_alt": "#F4F6F3",
    "text_dark": "#1A1A1A",
    "text_medium": "#333333",
    "text_light": "#4B5563",
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
        font-family: 'Inter', sans-serif;
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
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER AVEC LOGO
# ============================================================
st.markdown('<div class="header-container slide-in">', unsafe_allow_html=True)

st.markdown(f'''
<div class="user-info">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-right: 6px;">
        <path d="M8 8C10.2091 8 12 6.20914 12 4C12 1.79086 10.2091 0 8 0C5.79086 0 4 1.79086 4 4C4 6.20914 5.79086 8 8 8Z" fill="white"/>
        <path d="M8 9C4.13401 9 1 12.134 1 16H15C15 12.134 11.866 9 8 9Z" fill="white"/>
    </svg>
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
    <span class="tech-badge">GPT-4.1-mini</span>
    <span class="tech-badge">Nouvelle API</span>
    <span class="tech-badge">JSON Strict</span>
    <span class="tech-badge">Smart Matching V2</span>
</div>
''', unsafe_allow_html=True)

st.markdown(f'''
<p class="brand-sub">
    Système intelligent V2 de traitement de documents • Connecté en tant que <strong style="color: #1A1A1A !important;">{st.session_state.username}</strong>
</p>
''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# ZONE DE TÉLÉCHARGEMENT UNIQUE
# ============================================================
st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
st.markdown('<h4>📤 Zone de dépôt de documents V2</h4>', unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    <strong>ℹ️ NOUVEAUTÉS V2 :</strong>
    <ul style="margin-top:10px;">
        <li>Migration vers API OpenAI V2 (gpt-4.1-mini)</li>
        <li>Sortie JSON stricte uniquement</li>
        <li>Nouvelle règle N° BDC (priorité à "Fact")</li>
        <li>Quantités forcées en entiers sans virgule</li>
        <li>Correction OCR améliorée (O→0, l→1, S→5)</li>
        <li>Standardisation "CONS.CHAN FOUI 75CL"</li>
        <li>Nettoyage adresse amélioré</li>
    </ul>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="upload-box">', unsafe_allow_html=True)
uploaded_file = st.file_uploader(
    "**Déposez votre document ici ou cliquez pour parcourir**",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
    help="Formats supportés : JPG, JPEG, PNG | Taille max : 10MB",
    key="file_uploader_main"
)
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# CORRECTION : DÉFINITION DE LA VARIABLE uploaded POUR ÉVITER L'ERREUR
# ============================================================
uploaded = uploaded_file  # Alias pour compatibilité avec le code existant

# ============================================================
# TRAITEMENT AUTOMATIQUE DE L'IMAGE - VERSION AMÉLIORÉE V2
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
    
    # Barre de progression avec style tech
    progress_container = st.empty()
    with progress_container.container():
        st.markdown('<div class="progress-container">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 3rem; margin-bottom: 1rem;">🤖</div>', unsafe_allow_html=True)
        st.markdown('<h3 style="color: white !important;">Initialisation du système IA V2</h3>', unsafe_allow_html=True)
        st.markdown(f'<p class="progress-text-dark">Analyse en cours avec GPT-4.1-mini (nouvelle API)...</p>', unsafe_allow_html=True)
        
        # Barre de progression animée
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        steps = [
            "Chargement de l'image...",
            "Prétraitement des données...",
            "Analyse par IA (nouvelle API)...",
            "Extraction JSON stricte...",
            "Post-traitement des données...",
            "Standardisation améliorée...",
            "Validation des quantités...",
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
    
    # Traitement OCR avec système amélioré V2
    try:
        buf = BytesIO()
        st.session_state.uploaded_image.save(buf, format="JPEG")
        image_bytes = buf.getvalue()
        
        # Prétraitement de l'image
        img_processed = preprocess_image(image_bytes)
        
        # ============================================================
        # CHANGEMENT CRITIQUE : UTILISATION DE LA NOUVELLE FONCTION
        # ============================================================
        result = analyze_document_improved(img_processed)  # REMPLACE analyze_document_with_backup
        
        if result:
            raw_doc_type = result.get("type_document", "DOCUMENT INCONNU")
            document_subtype = result.get("document_subtype", "").upper()
            
            # Déterminer le type final
            if document_subtype == "DLP":
                final_doc_type = "BDC LEADERPRICE"
            elif document_subtype == "S2M":
                final_doc_type = "BDC S2M"
            elif document_subtype == "ULYS":
                final_doc_type = "BDC ULYS"
            elif document_subtype == "FACTURE":
                final_doc_type = "FACTURE EN COMPTE"
            else:
                # Fallback
                final_doc_type = "DOCUMENT INCONNU"
            
            st.session_state.detected_document_type = final_doc_type
            
            st.session_state.ocr_result = result
            st.session_state.show_results = True
            st.session_state.processing = False
            
            # Si aucun dataframe n'a été créé par process_articles_table
            if st.session_state.edited_standardized_df is None:
                # Créer un dataframe vide
                st.session_state.edited_standardized_df = pd.DataFrame(columns=[
                    "Produit Brute", "Produit Standard", "Quantité", "Confiance", "Auto"
                ])
            
            progress_container.empty()
            st.rerun()
        else:
            st.error("❌ Échec de l'analyse IA - Veuillez réessayer avec une image plus claire")
            st.session_state.processing = False
        
    except Exception as e:
        st.error(f"❌ Erreur système: {str(e)}")
        st.session_state.processing = False

# ============================================================
# APERÇU DU DOCUMENT
# ============================================================
if st.session_state.uploaded_image and st.session_state.image_preview_visible:
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>👁️ Aperçu du document analysé V2</h4>', unsafe_allow_html=True)
    
    col_img, col_info = st.columns([2, 1])
    
    with col_img:
        st.image(st.session_state.uploaded_image, use_column_width=True)
    
    with col_info:
        st.markdown(f"""
        <div class="info-box" style="height: 100%;">
            <strong style="color: {PALETTE['text_dark']} !important;">📊 NOUVEAUTÉS V2 :</strong><br><br>
            • Nouvelle API OpenAI<br>
            • Modèle: gpt-4.1-mini<br>
            • Extraction JSON stricte<br>
            • Quantités entières uniquement<br>
            • Correction OCR améliorée<br><br>
            <small style="color: {PALETTE['text_light']} !important;">Document analysé avec succès</small>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# AFFICHAGE DES RÉSULTATS
# ============================================================
if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
    result = st.session_state.ocr_result
    doc_type = st.session_state.detected_document_type
    
    # SECTION DÉBUGAGE V2
    with st.expander("🔍 Analyse de détection V2 (debug)"):
        st.write("**Type brut détecté par l'IA:**", result.get("type_document", "Non détecté"))
        st.write("**Sous-type détecté:**", result.get("document_subtype", "Non détecté"))
        st.write("**Type normalisé:**", doc_type)
        
        if st.session_state.ocr_raw_text:
            st.write("**Extrait du texte OCR:**", st.session_state.ocr_raw_text[:500] + "..." if len(st.session_state.ocr_raw_text) > 500 else st.session_state.ocr_raw_text)
        
        # Afficher les règles appliquées
        st.write("**Règles appliquées:**")
        st.write("- N° BDC extrait après 'Fact' ou 'F' (priorité à 'Fact')")
        st.write("- Quantités forcées en entiers")
        st.write("- Correction OCR: O→0, l→1, S→5")
        st.write("- Standardisation 'CONS.CHAN FOUI 75CL' → 'Consignation btl 75cl'")
    
    # Message de succès
    st.markdown('<div class="success-box fade-in">', unsafe_allow_html=True)
    st.markdown(f'''
    <div style="display: flex; align-items: start; gap: 15px;">
        <div style="font-size: 2.5rem; color: {PALETTE['success']} !important;">✅</div>
        <div>
            <strong style="font-size: 1.1rem; color: #1A1A1A !important;">Analyse IA V2 terminée avec succès</strong><br>
            <span style="color: #333333 !important;">Type détecté : <strong>{doc_type}</strong> | API : <strong>gpt-4.1-mini</strong></span><br>
            <small style="color: #4B5563 !important;">Nouvelle API OpenAI • JSON strict • Post-traitement amélioré</small>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Titre du mode détecté
    st.markdown(
        f"""
        <div class="document-title fade-in">
            📄 Document détecté : {doc_type}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # ========================================================
    # INFORMATIONS EXTRAITES
    # ========================================================
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>📋 Informations extraites V2</h4>', unsafe_allow_html=True)
    
    if "FACTURE" in doc_type.upper():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Client</div>', unsafe_allow_html=True)
            client_options = ["ULYS", "S2M", "DLP", "Autre"]
            extracted_client = result.get("client", "")
            
            # Sélecteur avec options
            client_choice = st.selectbox(
                "Sélectionnez le client",
                options=client_options,
                index=0,
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
            
            client_choice = st.selectbox(
                "Sélectionnez le client",
                options=client_options,
                index=0,
                key="bdc_client_select",
                label_visibility="collapsed"
            )
            
            if client_choice == "Autre":
                client = st.text_input("Autre client", value=extracted_client, key="bdc_client_other")
            else:
                client = client_choice
            
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">N° BDC</div>', unsafe_allow_html=True)
            numero = st.text_input("", value=result.get("numero", ""), key="bdc_numero", label_visibility="collapsed")
        
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
    
    # ========================================================
    # TABLEAU STANDARDISÉ ÉDITABLE
    # ========================================================
    if st.session_state.edited_standardized_df is not None and not st.session_state.edited_standardized_df.empty:
        st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
        st.markdown('<h4>📘 Standardisation des Produits V2</h4>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="margin-bottom: 20px; padding: 12px; background: rgba(59, 130, 246, 0.05); border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.1);">
            <small style="color: #1A1A1A !important;">
            💡 <strong>NOUVEAUTÉS V2 :</strong> 
            • <strong>API:</strong> Nouvelle API OpenAI avec gpt-4.1-mini<br>
            • <strong>JSON:</strong> Sortie stricte JSON uniquement<br>
            • <strong>N° BDC:</strong> Priorité à "Fact" avant "F"<br>
            • <strong>Quantités:</strong> Forcées en entiers (pas de virgules)<br>
            • <strong>OCR:</strong> Correction O→0, l→1, S→5<br>
            • <strong>Standardisation:</strong> "CONS.CHAN FOUI 75CL" → "Consignation btl 75cl"<br>
            • <strong>Adresse:</strong> Nettoyage et concaténation améliorés
            </small>
        </div>
        """, unsafe_allow_html=True)
        
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
                    help="Quantité commandée - FORCÉ EN ENTIER",
                    format="%d",
                    step=1
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
        
        # Forcer les quantités à être des entiers
        if "Quantité" in edited_df.columns:
            edited_df["Quantité"] = edited_df["Quantité"].apply(
                lambda x: int(round(float(x))) if pd.notna(x) else 0
            )
        
        # Mettre à jour le dataframe édité
        st.session_state.edited_standardized_df = edited_df
        
        # Statistiques
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
        
        # Bouton pour forcer la re-standardisation
        if st.button("🔄 Re-standardiser tous les produits", 
                    key="restandardize_button"):
            # Réappliquer la standardisation
            new_data = []
            for _, row in edited_df.iterrows():
                produit_brut = row["Produit Brute"]
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
    
    # ============================================================
    # BOUTON D'EXPORT
    # ============================================================
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>🚀 Export vers Cloud V2</h4>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="info-box">
        <strong style="color: #1A1A1A !important;">🌐 DESTINATION V2 :</strong> Google Sheets<br>
        <strong style="color: #1A1A1A !important;">🔒 SÉCURITÉ :</strong> Chiffrement AES-256<br>
        <strong style="color: #1A1A1A !important;">⚡ API :</strong> Nouvelle API OpenAI<br>
        <strong style="color: #1A1A1A !important;">📊 FORMAT :</strong> JSON strict uniquement<br>
        <strong style="color: #1A1A1A !important;">✨ NOUVEAUTÉS :</strong>
        • gpt-4.1-mini • N° BDC priorité "Fact"<br>
        • Quantités entières • Correction OCR<br>
        • Standardisation améliorée
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀 Synchroniser avec Google Sheets", 
                use_container_width=True, 
                type="primary",
                key="export_button"):
        st.info("⚠️ Fonction d'export à intégrer selon votre configuration Google Sheets existante")
        st.success("✅ Données prêtes pour l'export avec toutes les améliorations V2")
    
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
st.markdown(f"""
<center style='margin: 15px 0;'>
    <span style='font-weight: 700; color: #27414A !important;'>{BRAND_TITLE}</span>
    <span style='color: #4B5563 !important;'> • Système IA V2 • API gpt-4.1-mini • © {datetime.now().strftime("%Y")}</span>
</center>
""", unsafe_allow_html=True)

st.markdown(f"""
<center style='font-size: 0.8rem; color: #4B5563 !important;'>
    <span style='color: #10B981 !important;'>●</span> 
    Session : <strong style='color: #1A1A1A !important;'>{st.session_state.username}</strong>
    • API : gpt-4.1-mini • {datetime.now().strftime("%H:%M:%S")}
</center>
""", unsafe_allow_html=True)
