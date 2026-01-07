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
# NOUVEAU SYSTÈME DE SCORING MULTI-INDICES POUR DÉTECTION DE DOCUMENTS
# ============================================================

def detect_table_columns(text_upper: str) -> set:
    """
    Détecte les colonnes de tableau présentes dans le texte
    """
    columns = set()
    
    # Liste des colonnes courantes
    common_columns = [
        # Facture
        "P.U HT", "MONTANT HT", "TVA", "TTC", "TOTAL HT",
        "DESIGNATION", "QUANTITE", "PRIX UNITAIRE", "MONTANT",
        "NB BILLS", "BTLLS/COLIS",
        
        # DLP
        "QTÉ CÉDÉE", "QTE CEDEE", "QTÉ LIVRÉE", "QTE LIVREE",
        "COND/MENT", "COND. MENT", "CONDITIONNEMENT",
        
        # S2M
        "PCB", "NB COLIS", "QUANTITE", "PA UNITAIRE", "PA FACT",
        "COLIS", "PIECES",
        
        # ULYS
        "PAQ", "PC", "QUANTITE", "DESIGNATION",
        
        # Général
        "ARTICLE", "REFERENCE", "CODE ARTICLE", "LIBELLE",
        "UNITÉ", "UNITE", "PU", "PRIX"
    ]
    
    for column in common_columns:
        if column in text_upper:
            columns.add(column)
    
    # Recherche de motifs spécifiques
    if re.search(r'\b\d+C/\d+\b', text_upper):
        columns.add("FORMAT_COND")
    
    if "1 PAQ = 12" in text_upper or "1PAQ=12" in text_upper:
        columns.add("PAQ_12")
    
    return columns

def calculate_document_scores(text: str) -> Dict[str, Any]:
    """
    Calcule les scores pour chaque type de document basé sur le système multi-indices
    """
    text_upper = text.upper()
    
    # Initialisation des scores
    scores = {
        "FACTURE": 0,
        "DLP": 0,
        "S2M": 0,
        "ULYS": 0,
        "AUTRE": 0
    }
    
    # Détection des colonnes dans le texte
    columns_found = detect_table_columns(text_upper)
    
    # ====================================================
    # SCORING FACTURE EN COMPTE
    # ====================================================
    
    # Entête & mentions légales
    if "FACTURE EN COMPTE" in text_upper:
        scores["FACTURE"] += 4
    
    if "CETTE FACTURE TIENT LIEU DE TITRE DE MOUVEMENT" in text_upper:
        scores["FACTURE"] += 3
    
    if "NET A PAYER" in text_upper:
        scores["FACTURE"] += 2
    
    if "TVA 20%" in text_upper or "TVA 20 %" in text_upper:
        scores["FACTURE"] += 2
    
    if "STAT :" in text_upper or "NIF :" in text_upper:
        scores["FACTURE"] += 2
    
    # Colonnes spécifiques facture
    facture_columns = ["P.U HT", "MONTANT HT", "TVA", "TTC", "TOTAL HT"]
    facture_cols_found = sum(1 for col in facture_columns if col in text_upper)
    scores["FACTURE"] += facture_cols_found * 2
    
    # Mentions de paiement
    if "FACTURE A PAYER AVANT" in text_upper:
        scores["FACTURE"] += 2
    
    if "ARRETEE LA PRESENTE FACTURE A LA SOMME DE" in text_upper:
        scores["FACTURE"] += 2
    
    # Structure de tableau facture
    if {"P.U HT", "TVA", "TTC"}.issubset(columns_found):
        scores["FACTURE"] += 3
    
    # ====================================================
    # SCORING DLP (LEADER PRICE)
    # ====================================================
    
    # Identité juridique
    if "DISTRIBUTION LEADER PRICE" in text_upper:
        scores["DLP"] += 5
    
    if "D.L.P.M.S.A.R.L" in text_upper:
        scores["DLP"] += 3
    
    if "ANKADIMBAHOAKA" in text_upper or "PK 6 ROUTE D'ANOSIBE" in text_upper:
        scores["DLP"] += 2
    
    # Vocabulaire logistique spécifique
    if "QTÉ CÉDÉE" in text_upper or "QTE CEDEE" in text_upper:
        scores["DLP"] += 3
    
    if "QTÉ LIVRÉE" in text_upper or "QTE LIVREE" in text_upper:
        scores["DLP"] += 2
    
    if "COND/MENT" in text_upper or "COND. MENT" in text_upper:
        scores["DLP"] += 2
    
    # Formats spécifiques DLP
    if re.search(r'\b\d+C/\d+\b', text_upper):
        scores["DLP"] += 2
    
    # Structure de tableau DLP
    if {"QTÉ CÉDÉE", "COND/MENT"}.issubset(columns_found):
        scores["DLP"] += 3
    
    # ====================================================
    # SCORING S2M / SUPERMAKI
    # ====================================================
    
    # Marque & localisation
    if "SUPERMAKI" in text_upper:
        scores["S2M"] += 5
    
    if "RAYON" in text_upper and "SECTEUR" in text_upper:
        scores["S2M"] += 2
    
    # Structure du tableau S2M
    s2m_columns = ["PCB", "NB COLIS", "PA UNITAIRE", "PA FACT"]
    s2m_cols_found = sum(1 for col in s2m_columns if col in text_upper)
    scores["S2M"] += s2m_cols_found * 2
    
    if "PCB" in text_upper and "NB COLIS" in text_upper:
        scores["S2M"] += 3
    
    # Quartier détection
    if "AMBOHIBAO" in text_upper or "IVANDRA" in text_upper:
        scores["S2M"] += 1
    
    # Structure de tableau S2M
    if {"PCB", "NB COLIS", "PA FACT"}.issubset(columns_found):
        scores["S2M"] += 4
    
    # ====================================================
    # SCORING ULYS
    # ====================================================
    
    # Entête
    if "BON DE COMMANDE FOURNISSEUR" in text_upper:
        scores["ULYS"] += 5
    
    if "ULYS" in text_upper:
        scores["ULYS"] += 3
    
    # Champs magasin
    if "NOM DU MAGASIN" in text_upper:
        scores["ULYS"] += 3
    
    if "N° MAGASIN" in text_upper or "NO MAGASIN" in text_upper:
        scores["ULYS"] += 2
    
    # Unités spécifiques
    if "PAQ" in text_upper and "1 PAQ = 12" in text_upper:
        scores["ULYS"] += 2
    
    if "PC" in text_upper and "PAQ" in text_upper:
        scores["ULYS"] += 1
    
    # Structure de tableau ULYS
    if {"PAQ", "PC"}.issubset(columns_found):
        scores["ULYS"] += 3
    
    # ====================================================
    # DÉTECTION PAR STRUCTURE DE TABLEAU (BONUS)
    # ====================================================
    
    # Bonus pour correspondance forte de structure
    if {"P.U HT", "TVA", "TTC"}.issubset(columns_found):
        scores["FACTURE"] += 2
    
    if {"PCB", "NB COLIS", "PA FACT"}.issubset(columns_found):
        scores["S2M"] += 2
    
    if {"QTÉ CÉDÉE", "COND/MENT"}.issubset(columns_found):
        scores["DLP"] += 2
    
    if {"PAQ", "PC"}.issubset(columns_found):
        scores["ULYS"] += 2
    
    # ====================================================
    # RÈGLES MÉTIER SPÉCIFIQUES (OVERRIDE)
    # ====================================================
    
    # Règle 1: Si DLP détecté, c'est TOUJOURS un BDC (pas une facture)
    if scores["DLP"] >= 4:
        # Réduire le score facture si DLP fort
        if scores["FACTURE"] > 0:
            scores["FACTURE"] = max(0, scores["FACTURE"] - 3)
    
    # Règle 2: "FACTURE EN COMPTE" est décisif pour les factures
    if "FACTURE EN COMPTE" in text_upper:
        scores["FACTURE"] += 2
        # Réduire les scores BDC si facture claire
        for bdc_type in ["DLP", "S2M", "ULYS"]:
            if scores[bdc_type] > 0:
                scores[bdc_type] = max(0, scores[bdc_type] - 2)
    
    # Règle 3: "SUPERMAKI" est décisif pour S2M
    if "SUPERMAKI" in text_upper:
        scores["S2M"] += 2
    
    # ====================================================
    # EXTRACTION DES INFORMATIONS SPÉCIFIQUES
    # ====================================================
    
    extracted_info = {
        "quartier_s2m": "",
        "nom_magasin_ulys": "",
        "fact_manuscrit": "",
        "columns_detected": list(columns_found)
    }
    
    # Extraction quartier S2M
    if "SUPERMAKI" in text_upper:
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if "SUPERMAKI" in line.upper():
                if i + 1 < len(lines):
                    quartier_line = lines[i + 1].strip()
                    if quartier_line and len(quartier_line) > 3:  # Au moins 3 caractères
                        extracted_info["quartier_s2m"] = clean_quartier(quartier_line)
                        break
    
    # Extraction nom magasin ULYS
    if "NOM DU MAGASIN" in text_upper:
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if "NOM DU MAGASIN" in line.upper():
                if i + 1 < len(lines):
                    magasin_line = lines[i + 1].strip()
                    if magasin_line:
                        extracted_info["nom_magasin_ulys"] = magasin_line
                        break
    
    # Extraction FACT manuscrit
    extracted_info["fact_manuscrit"] = extract_fact_number_from_handwritten(text)
    
    # Détermination du type final
    max_score = max(scores.values())
    max_types = [doc_type for doc_type, score in scores.items() if score == max_score]
    
    if max_score < 3:  # Seuil minimum
        document_type = "AUTRE"
    elif len(max_types) == 1:
        document_type = max_types[0]
    else:
        # En cas d'égalité, priorité: FACTURE > DLP > S2M > ULYS
        priority_order = ["FACTURE", "DLP", "S2M", "ULYS", "AUTRE"]
        for doc_type in priority_order:
            if doc_type in max_types:
                document_type = doc_type
                break
        else:
            document_type = "AUTRE"
    
    # Mapping vers les types standardisés
    type_mapping = {
        "FACTURE": "FACTURE EN COMPTE",
        "DLP": "BDC LEADERPRICE",
        "S2M": "BDC S2M",
        "ULYS": "BDC ULYS",
        "AUTRE": "DOCUMENT INCONNU"
    }
    
    final_type = type_mapping.get(document_type, "DOCUMENT INCONNU")
    
    return {
        "document_type": final_type,
        "raw_type": document_type,
        "scores": scores,
        "extracted_info": extracted_info,
        "max_score": max_score
    }

# ============================================================
# STANDARDISATION INTELLIGENTE DES PRODUITS - MIS À JOUR
# ============================================================

# Liste officielle des produits mise à jour
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
    # Ajout des nouveaux produits demandés
    "Côte de Fianar Gris 3L",
    "Côteau d'Ambalavao Special 75 cl",  # Alternative orthographe
    "Aperao Peche 37 cl",  # Alternative orthographe
    "Côteau d'Ambalavao Special 75 cl",  # Pour "Côteau d'Ambalavao Rouge" conversion
    "Cuvee Speciale 75cls"  # Conversion demandée
]

# ============================================================
# FONCTION POUR EXTRACTION DU NUMERO FACT MANUSCRIT
# ============================================================
def extract_fact_number_from_handwritten(text: str) -> str:
    """Extrait le numéro après 'F' ou 'Fact' manuscrit - pour TOUS les BDC"""
    if not text:
        return ""
    
    # Normaliser le texte
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Chercher les motifs avec "Fact" ou "F" manuscrit suivi de chiffres
    patterns = [
        r'\bFact\s*[:.]?\s*(\d{4,})\b',      # Fact 12345 ou Fact: 12345
        r'\bF\s*[:.]?\s*(\d{4,})\b',         # F 12345 ou F: 12345
        r'\bfact\s*[:.]?\s*(\d{4,})\b',      # fact 12345 (minuscule)
        r'\bf\s*[:.]?\s*(\d{4,})\b',         # f 12345 (minuscule)
        r'Fact\.?\s*(\d{4,})',               # Fact.12345
        r'F\.?\s*(\d{4,})',                  # F.12345
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
    
    # 1. Priorité aux matches qui contiennent "Fact" (pas juste "F")
    fact_matches = [m for m in all_matches if m['is_fact']]
    if fact_matches:
        fact_matches.sort(key=lambda x: x['position'], reverse=True)
        return fact_matches[0]['number']
    
    # 2. Sinon, prendre le dernier "F" trouvé
    all_matches.sort(key=lambda x: x['position'], reverse=True)
    return all_matches[0]['number']

# ============================================================
# FONCTION POUR NETTOYER LE QUARTIER S2M
# ============================================================
def clean_quartier(quartier: str) -> str:
    """Nettoie le nom du quartier pour S2M"""
    if not quartier:
        return ""
    
    # Supprimer les guillemets, deux-points, etc.
    quartier = re.sub(r'["\'\[\]:]', '', quartier)
    
    # Supprimer "quartier_s2m" et variations
    quartier = re.sub(r'quartier[_\-]?s2m', '', quartier, flags=re.IGNORECASE)
    
    # Nettoyer les espaces
    quartier = ' '.join(quartier.split())
    
    return quartier.strip()

# ============================================================
# FONCTION POUR NETTOYER L'ADRESSE S2M
# ============================================================
def clean_adresse(adresse: str) -> str:
    """Nettoie l'adresse extraite pour S2M"""
    if not adresse:
        return ""
    
    # Si l'adresse contient le format JSON-like
    if '"quartier_s2m"' in adresse or "quartier_s2m" in adresse:
        # Extraire juste le quartier
        match = re.search(r'"quartier_s2m":\s*"([^"]+)"', adresse)
        if match:
            quartier = match.group(1)
            return f"Supermaki {quartier}"
        
        # Autre format
        match = re.search(r'quartier_s2m[":\s]+([^",}\]]+)', adresse)
        if match:
            quartier = match.group(1).strip()
            quartier = clean_quartier(quartier)
            return f"Supermaki {quartier}"
    
    # Si c'est déjà "Supermaki" suivi de quelque chose
    if "Supermaki" in adresse:
        # Nettoyer les caractères spéciaux
        adresse = re.sub(r'["\'\[\]:]', ' ', adresse)
        adresse = re.sub(r'\s+', ' ', adresse)
        return adresse.strip()
    
    return adresse.strip()

# Dictionnaire de synonymes et normalisations MIS À JOUR
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
    "cons. chan foul": "consignation btl",
    "cons chan foul": "consignation btl",
    "cons.chan foui": "consignation btl",
    "cons.chan foui 75cl": "consignation btl 75cl",
    "cons chan foui 75cl": "consignation btl 75cl",
    
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
    
    # NOUVEAUX SYNONYMES POUR AMÉLIORATION
    "coteau d'ambalavao rouge": "cuvee speciale 75cls",  # Conversion demandée
    "coteau d ambalavao rouge": "cuvee speciale 75cls",
    "ambalavao rouge": "cuvee speciale 75cls",
    "coteau ambalavao rouge": "cuvee speciale 75cls",
    "côteau d'ambalavao rouge": "cuvee speciale 75cls",
    "côteau ambalavao rouge": "cuvee speciale 75cls",
    
    # Standardisation améliorée
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
        # Remplacer par "Consignation btl 75cl"
        if "75" in produit_upper or "750" in produit_upper:
            produit_standard = "Consignation btl 75cl"
        else:
            produit_standard = "Consignation btl"
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
        elif "ROSE" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Rosé 3L"
            confidence = 0.9
            status = "matched"
        elif "GRIS" in produit_upper and "FIANAR" in produit_upper:
            produit_standard = "Côte de Fianar Gris 3L"
            confidence = 0.9
            status = "matched"
    
    # CONVERSION SPÉCIFIQUE DEMANDÉE : "Coteau d'Ambalavao Rouge" -> "Cuvee Speciale 75cls"
    if "COTEAU" in produit_upper and "AMBALAVAO" in produit_upper and "ROUGE" in produit_upper:
        produit_standard = "Cuvee Speciale 75cls"
        confidence = 0.95
        status = "matched"
    
    # Standardisation améliorée pour les produits avec fautes d'orthographe
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
    
    # Standardisation pour Aperao Peche
    if "APERAO" in produit_upper and "PECHE" in produit_upper:
        if "37" in produit_upper or "370" in produit_upper:
            produit_standard = "Aperao Peche 37 cl"
        else:
            produit_standard = "Aperao Pêche 75 cl"
        confidence = 0.9
        status = "matched"
    
    # Standardisation pour Côteau d'Ambalavao Special
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
if "fact_manuscrit" not in st.session_state:
    st.session_state.fact_manuscrit = ""

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
        
        /* FORCER LE TEXTE EN NOIR SUR BLANC - FILTRE 1 */
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
            color: #1E293B !important;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #27414A;
            box-shadow: 0 0 0 3px rgba(39, 65, 74, 0.1);
            outline: none;
            color: #1E293B !important;
        }
        
        /* Correction pour le placeholder */
        .stTextInput > div > div > input::placeholder {
            color: #64748b !important;
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
            color: #856404 !important;
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
        <div style="font-size: 3rem; margin-bottom: 20px; color: #1A1A1A !important;">
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
        • Votre compte est protégé<br>
        • Vos informations sont en sécurité<br>
        • Personne d'autre ne peut y accéder<br>
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
                    0 0 0 1px rgba(39, 65,74, 0.05);
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
        border: 1px solid rgba(255, 255,255, 0.8);
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
# GOOGLE SHEETS CONFIGURATION - VERSION PRODUCTION
# ============================================================
SHEET_ID = "1h4xT-cw9Ys1HbkhMWVtRnDOxsZ0fBOaskjPgRyIj3K8"

SHEET_GIDS = {
    "FACTURE EN COMPTE": 0,
    "BDC LEADERPRICE": 581432835,
    "BDC S2M": 581432835,
    "BDC ULYS": 581432835
}

# ============================================================
# FONCTION DE NORMALISATION DU TYPE DE DOCUMENT - VERSION AMÉLIORÉE V1.3
# ============================================================
def normalize_document_type(doc_type: str) -> str:
    """Normalise le type de document pour correspondre aux clés SHEET_GIDS - VERSION AMÉLIORÉE V1.3"""
    if not doc_type:
        return "DOCUMENT INCONNU"
    
    # Utiliser le système de scoring si possible
    if st.session_state.ocr_raw_text:
        scoring_result = calculate_document_scores(st.session_state.ocr_raw_text)
        if scoring_result["max_score"] >= 3:
            return scoring_result["document_type"]
    
    # Fallback à l'ancienne logique
    doc_type_upper = doc_type.upper()
    
    facture_keywords = [
        "FACTURE", "INVOICE", "BILL", "FACTURA",
        "FACTURE EN COMPTE", "FACTURE N°", "FACTURE NO",
        "DOIT", "AU NOM DE", "NOM DU CLIENT", "N° FACTURE"
    ]
    
    bdc_keywords = [
        "BDC", "BON DE COMMANDE", "ORDER", "COMMANDE",
        "BON COMMANDE", "PURCHASE ORDER", "PO",
        "DATE ÉMISSION", "DATE EMISSION", "BON DE COMMANDE N°"
    ]
    
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
        elif "BDC" in doc_type_upper or "BON DE COMMANDE" in doc_type_upper:
            if "LEADERPRICE" in doc_type_upper or "DLP" in doc_type_upper:
                return "BDC LEADERPRICE"
            elif "S2M" in doc_type_upper or "SUPERMAKI" in doc_type_upper:
                return "BDC S2M"
            elif "ULYS" in doc_type_upper:
                return "BDC ULYS"
            else:
                return "BDC LEADERPRICE"
        else:
            if any(word in doc_type_upper for word in ["FACTURE", "INVOICE", "BILL", "DOIT"]):
                return "FACTURE EN COMPTE"
            elif any(word in doc_type_upper for word in ["COMMANDE", "ORDER", "PO", "BDC"]):
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
# FONCTION DE DÉTECTION PRÉCISE DU TYPE DE DOCUMENT (MAINTENANT AVEC SCORING)
# ============================================================
def detect_document_type_from_text(text: str) -> Dict[str, Any]:
    """Détecte précisément le type de document basé sur le système de scoring"""
    scoring_result = calculate_document_scores(text)
    
    # Transformation au format attendu par le code existant
    indicators_found = []
    
    if scoring_result["raw_type"] == "DLP":
        indicators_found.extend(["DISTRIBUTION LEADER PRICE", "D.L.P.M.S.A.R.L"])
    elif scoring_result["raw_type"] == "S2M":
        indicators_found.extend(["SUPERMAKI", "RAYON"])
    elif scoring_result["raw_type"] == "ULYS":
        indicators_found.extend(["BON DE COMMANDE FOURNISSEUR", "NOM DU MAGASIN"])
    elif scoring_result["raw_type"] == "FACTURE":
        indicators_found.extend(["FACTURE EN COMPTE", "NET A PAYER"])
    
    return {
        "type": scoring_result["raw_type"],
        "scores": scoring_result["scores"],
        "indicators_found": indicators_found,
        "scoring_result": scoring_result  # Ajout du résultat complet pour usage ultérieur
    }

# ============================================================
# FONCTIONS OCR AMÉLIORÉES POUR MEILLEURE DÉTECTION - VERSION SCORING V1.3
# ============================================================
def extract_text_features_for_detection(text: str) -> Dict[str, Any]:
    """Extrait les caractéristiques du texte pour aider à la détection du type de document"""
    # Cette fonction est maintenant remplacée par calculate_document_scores
    # Conservée pour compatibilité
    scoring_result = calculate_document_scores(text)
    
    return {
        'has_facture': scoring_result["scores"]["FACTURE"] > 0,
        'has_bdc': any(scoring_result["scores"][bdc_type] > 0 for bdc_type in ["DLP", "S2M", "ULYS"]),
        'facture_keywords': ["FACTURE"] if scoring_result["scores"]["FACTURE"] > 0 else [],
        'bdc_keywords': [],
        'facture_score': scoring_result["scores"]["FACTURE"],
        'bdc_score': max(scoring_result["scores"]["DLP"], scoring_result["scores"]["S2M"], scoring_result["scores"]["ULYS"])
    }

def openai_vision_ocr_improved(image_bytes: bytes) -> Dict:
    """Utilise OpenAI Vision pour analyser le document avec un prompt amélioré pour la détection V1.3"""
    try:
        client = get_openai_client()
        if not client:
            return None
        
        base64_image = encode_image_to_base64(image_bytes)
        
        # PROMPT AMÉLIORÉ AVEC SYSTÈME DE SCORING MULTI-INDICES
        prompt = """
        ANALYSE CE DOCUMENT ET EXTRACT LES INFORMATIONS SUIVANTES:

        IMPORTANT - UTILISER LE SYSTÈME DE SCORING MULTI-INDICES:

        1. FACTURE EN COMPTE (score le plus élevé si):
           - "FACTURE EN COMPTE" présent (+4)
           - "NET A PAYER", "TVA 20%", "STAT :", "NIF :" présents (+2 chacun)
           - Colonnes "P.U HT", "MONTANT HT", "TVA", "TTC" détectées (+2 chacune)
           - "Facture à payer avant le" présent (+2)
        
        2. BDC DLP (LEADER PRICE) (score le plus élevé si):
           - "DISTRIBUTION LEADER PRICE" présent (+5)
           - "D.L.P.M.S.A.R.L" présent (+3)
           - "Qté Cédée", "Qté livrée", "Cond/ment" présents (+3 chacun)
           - Formats "30C/12", "10C/12", "40C/12" détectés (+2)
           - RÈGLE MÉTIER: TOUT DOCUMENT DLP EST UN BDC
        
        3. BDC S2M / SUPERMAKI (score le plus élevé si):
           - "SUPERMAKI" présent (+5)
           - "RAYON" et "SECTEUR" présents (+2)
           - Colonnes "PCB", "Nb Colis", "PA Unitaire", "PA Fact" détectées (+2 chacune)
           - Quartier détecté sous "SUPERMAKI"
        
        4. BDC ULYS (score le plus élevé si):
           - "BON DE COMMANDE FOURNISSEUR" présent (+5)
           - "ULYS" présent (+3)
           - "Nom du Magasin", "N° Magasin" présents (+3)
           - "PAQ", "1 PAQ = 12 / PC" présents (+2)

        Pour TOUS les BDC, chercher le numéro manuscrit écrit après "F" ou "Fact"

        Extraire:
        {
            "type_document": "BDC" ou "FACTURE",
            "document_subtype": "DLP", "S2M", "ULYS", ou "FACTURE",
            "client": "...",
            "adresse_livraison": "...",
            "quartier_s2m": "...",  (si S2M: le quartier sous "SUPERMAKI")
            "nom_magasin_ulys": "...",  (si ULYS: le nom du magasin)
            "fact_manuscrit_trouve": "oui" ou "non",
            "fact_manuscrit": "...",  (le numéro exact après F ou Fact)
        }

        RÈGLES MÉTIER OBLIGATOIRES:
        • DLP → client = "DLP", adresse = "Leader Price Akadimbahoaka" (TOUJOURS)
        • S2M → client = "S2M", adresse = "Supermaki " + quartier_s2m (forcer adresse)
        • ULYS → client = "ULYS", adresse = nom_magasin_ulys
        • FACTURE → utiliser colonnes "Désignation" et "Nb bills"

        Priorité en cas de doute: FACTURE > DLP > S2M > ULYS
        Seuil minimum: Score total ≥ 3 pour validation
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
                
                document_subtype = data.get("document_subtype", "").upper()
                
                if document_subtype in ["DLP", "S2M", "ULYS"]:
                    fact_manuscrit = data.get("fact_manuscrit", "")
                    
                    st.session_state.fact_manuscrit = fact_manuscrit
                    
                    data["numero"] = fact_manuscrit
                
                # CORRECTION DLP: FORCER L'ADRESSE À "Leader Price Akadimbahoaka"
                if document_subtype == "DLP":
                    data["client"] = "DLP"
                    data["adresse_livraison"] = "Leader Price Akadimbahoaka"
                
                # Correction S2M
                elif document_subtype == "S2M":
                    data["client"] = "S2M"
                    quartier = data.get("quartier_s2m", "")
                    if quartier:
                        quartier_nettoye = clean_quartier(quartier)
                        adresse_nettoyee = clean_adresse(f"Supermaki {quartier_nettoye}")
                        data["adresse_livraison"] = adresse_nettoyee
                        st.session_state.quartier_s2m = quartier_nettoye
                    else:
                        adresse = data.get("adresse_livraison", "")
                        data["adresse_livraison"] = clean_adresse(adresse) if adresse else "Supermaki"
                
                # Correction ULYS
                elif document_subtype == "ULYS":
                    data["client"] = "ULYS"
                    nom_magasin = data.get("nom_magasin_ulys", "")
                    if nom_magasin:
                        data["adresse_livraison"] = nom_magasin
                        st.session_state.nom_magasin_ulys = nom_magasin
                    else:
                        data["adresse_livraison"] = "ULYS Magasin"
                
                # NOUVELLE CORRECTION: Pour les factures avec "Autre client", forcer client = adresse
                elif document_subtype == "FACTURE":
                    client_value = data.get("client", "")
                    adresse_value = data.get("adresse_livraison", "")
                    
                    # Si le client est "Autre" ou n'est pas DLP/ULYS/S2M, forcer client = adresse
                    if client_value.upper() not in ["DLP", "ULYS", "S2M"]:
                        data["client"] = adresse_value
                
                return data
                
            except json.JSONDecodeError:
                json_str = re.sub(r'[\x00-\x1f\x7f]', '', json_str)
                try:
                    data = json.loads(json_str)
                    return data
                except:
                    return guess_document_type_from_text(content)
        else:
            return guess_document_type_from_text(content)
            
    except Exception as e:
        st.error(f"❌ Erreur OpenAI Vision: {str(e)}")
        return None

def guess_document_type_from_text(text: str) -> Dict:
    """Devine le type de document à partir du texte OCR"""
    scoring_result = calculate_document_scores(text)
    
    fact_manuscrit = extract_fact_number_from_handwritten(text)
    
    if scoring_result["raw_type"] == "DLP":
        return {
            "type_document": "BDC",
            "document_subtype": "DLP",
            "client": "DLP",
            "adresse_livraison": "Leader Price Akadimbahoaka",
            "fact_manuscrit": fact_manuscrit,
            "numero": fact_manuscrit,
            "articles": []
        }
    elif scoring_result["raw_type"] == "S2M":
        quartier = scoring_result["extracted_info"]["quartier_s2m"] or ""
        return {
            "type_document": "BDC",
            "document_subtype": "S2M",
            "client": "S2M",
            "adresse_livraison": clean_adresse(f"Supermaki {quartier}" if quartier else "Supermaki"),
            "fact_manuscrit": fact_manuscrit,
            "numero": fact_manuscrit,
            "articles": []
        }
    elif scoring_result["raw_type"] == "ULYS":
        nom_magasin = scoring_result["extracted_info"]["nom_magasin_ulys"] or ""
        return {
            "type_document": "BDC",
            "document_subtype": "ULYS",
            "client": "ULYS",
            "adresse_livraison": nom_magasin if nom_magasin else "ULYS Magasin",
            "fact_manuscrit": fact_manuscrit,
            "numero": fact_manuscrit,
            "articles": []
        }
    elif scoring_result["raw_type"] == "FACTURE":
        return {
            "type_document": "FACTURE",
            "document_subtype": "FACTURE",
            "articles": []
        }
    else:
        # Fallback à l'ancienne logique
        if scoring_result["scores"]["FACTURE"] > scoring_result["scores"]["DLP"]:
            return {"type_document": "FACTURE", "document_subtype": "FACTURE", "articles": []}
        else:
            return {"type_document": "BDC", "document_subtype": "UNKNOWN", "fact_manuscrit": fact_manuscrit, "numero": fact_manuscrit, "articles": []}

def analyze_document_with_backup(image_bytes: bytes) -> Dict:
    """Analyse le document avec vérification de cohérence et scoring amélioré"""
    # Analyse initiale par OpenAI
    result = openai_vision_ocr_improved(image_bytes)
    
    if not result:
        return {"type_document": "DOCUMENT INCONNU", "articles": []}
    
    # Extraction du texte brut pour scoring
    if st.session_state.ocr_raw_text:
        # Appliquer le scoring multi-indices
        scoring_result = calculate_document_scores(st.session_state.ocr_raw_text)
        
        # Stocker les informations extraites
        st.session_state.quartier_s2m = scoring_result["extracted_info"]["quartier_s2m"]
        st.session_state.nom_magasin_ulys = scoring_result["extracted_info"]["nom_magasin_ulys"]
        st.session_state.fact_manuscrit = scoring_result["extracted_info"]["fact_manuscrit"]
        
        # Vérifier la cohérence avec l'analyse OpenAI
        ai_subtype = result.get("document_subtype", "").upper()
        scoring_type = scoring_result["raw_type"]
        
        # Mapping entre les types
        type_mapping = {
            "FACTURE": "FACTURE",
            "DLP": "DLP",
            "S2M": "S2M",
            "ULYS": "ULYS",
            "AUTRE": "UNKNOWN"
        }
        
        scoring_mapped = type_mapping.get(scoring_type, "UNKNOWN")
        
        # Si contradiction et score élevé, corriger
        if (ai_subtype != scoring_mapped and 
            scoring_result["max_score"] >= 5 and 
            scoring_mapped != "UNKNOWN"):
            
            st.session_state.document_analysis_details = {
                "original_type": ai_subtype,
                "adjusted_type": scoring_mapped,
                "reason": "Scoring multi-indices plus fiable",
                "scores": scoring_result["scores"],
                "max_score": scoring_result["max_score"]
            }
            
            # Appliquer les corrections selon le type
            if scoring_mapped == "DLP":
                result["document_subtype"] = "DLP"
                result["client"] = "DLP"
                result["adresse_livraison"] = "Leader Price Akadimbahoaka"
                result["type_document"] = "BDC"
                
                # Utiliser le FACT manuscrit si trouvé
                if st.session_state.fact_manuscrit:
                    result["fact_manuscrit"] = st.session_state.fact_manuscrit
                    result["numero"] = st.session_state.fact_manuscrit
            
            elif scoring_mapped == "S2M":
                result["document_subtype"] = "S2M"
                result["client"] = "S2M"
                quartier = st.session_state.quartier_s2m or ""
                result["adresse_livraison"] = clean_adresse(f"Supermaki {quartier}" if quartier else "Supermaki")
                result["type_document"] = "BDC"
                
                if st.session_state.fact_manuscrit:
                    result["fact_manuscrit"] = st.session_state.fact_manuscrit
                    result["numero"] = st.session_state.fact_manuscrit
            
            elif scoring_mapped == "ULYS":
                result["document_subtype"] = "ULYS"
                result["client"] = "ULYS"
                nom_magasin = st.session_state.nom_magasin_ulys or ""
                result["adresse_livraison"] = nom_magasin if nom_magasin else "ULYS Magasin"
                result["type_document"] = "BDC"
                
                if st.session_state.fact_manuscrit:
                    result["fact_manuscrit"] = st.session_state.fact_manuscrit
                    result["numero"] = st.session_state.fact_manuscrit
            
            elif scoring_mapped == "FACTURE":
                result["document_subtype"] = "FACTURE"
                result["type_document"] = "FACTURE"
        
        # Toujours forcer l'adresse DLP si DLP détecté
        if scoring_mapped == "DLP" or ai_subtype == "DLP":
            result["client"] = "DLP"
            result["adresse_livraison"] = "Leader Price Akadimbahoaka"
        
        # Toujours forcer le quartier pour S2M si détecté
        if scoring_mapped == "S2M" or ai_subtype == "S2M":
            result["client"] = "S2M"
            quartier = st.session_state.quartier_s2m or ""
            if quartier:
                result["adresse_livraison"] = clean_adresse(f"Supermaki {quartier}")
    
    return result

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
    """Formate la date au format français JJ/MM/AAAA"""
    try:
        # Essayer de parser la date avec différents formats
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%d %m %Y",
            "%d/%m/%y", "%d-%m-%y", "%d %m %y",
            "%d %B %Y", "%d %b %Y", "%Y-%m-%d"
        ]
        
        for fmt in formats:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime("%d/%m/%Y")  # FORMAT CORRIGÉ: JJ/MM/AAAA
            except:
                continue
        
        # Essayer avec dateutil.parser
        try:
            date_obj = parser.parse(date_str, dayfirst=True)
            return date_obj.strftime("%d/%m/%Y")  # FORMAT CORRIGÉ: JJ/MM/AAAA
        except:
            # Si aucune date n'est trouvée, retourner la date d'aujourd'hui
            return datetime.now().strftime("%d/%m/%Y")
    except:
        return datetime.now().strftime("%d/%m/%Y")

def get_month_from_date(date_str: str) -> str:
    """Extrait le mois français d'une date"""
    months_fr = {
        1: "janvier", 2: "février", 3: "mars", 4: "avril",
        5: "mai", 6: "juin", 7: "juillet", 8: "août",
        9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
    }
    
    try:
        # Essayer de parser la date
        date_obj = parser.parse(date_str, dayfirst=True)
        return months_fr[date_obj.month]
    except:
        # Si la date n'est pas valide, utiliser le mois actuel
        return months_fr[datetime.now().month]

def format_quantity(qty: Any) -> str:
    """Formate la quantité - GARANTIT QUE C'EST UN NOMBRE ENTIER SANS VIRGULE"""
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
# FONCTIONS POUR PRÉPARER LES DONNÉES POUR GOOGLE SHEETS (PRODUCTION)
# ============================================================
def prepare_facture_rows(data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
    """Prépare les lignes pour les factures (PRODUCTION - 8 colonnes) - CORRECTION DATE APPLIQUÉE"""
    rows = []
    
    try:
        mois = data.get("mois", get_month_from_date(data.get("date", "")))
        
        # CORRECTION 1: Utiliser la date extraite et la formater en JJ/MM/AAAA
        date_facture = data.get("date", "")
        date_formatted = format_date_french(date_facture)  # FORMAT CORRIGÉ
        
        client = data.get("client", "")
        numero_facture = data.get("numero_facture", "")
        magasin = data.get("adresse_livraison", "")
        editeur = st.session_state.username
        
        for _, row in articles_df.iterrows():
            quantite = row.get("Quantité", 0)
            if pd.isna(quantite) or quantite == 0 or str(quantite).strip() == "0":
                continue
            
            quantite_str = format_quantity(quantite)
            
            try:
                quantite_int = int(float(quantite_str))
                quantite_str = str(quantite_int)
            except:
                quantite_str = "0"
                continue
            
            designation = str(row.get("Produit Standard", "")).strip()
            if not designation:
                designation = str(row.get("Produit Brute", "")).strip()
            
            rows.append([
                mois,           # Mois
                date_formatted, # Date au format JJ/MM/AAAA (CORRIGÉ)
                client,         # Client
                numero_facture, # N* facture
                magasin,        # Magasin
                designation,    # Désignation
                quantite_str,   # Quantité
                editeur         # Editeur
            ])
        
        return rows
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la préparation des données facture: {str(e)}")
        return []

def prepare_bdc_rows(data: dict, articles_df: pd.DataFrame) -> List[List[str]]:
    """Prépare les lignes pour les BDC (PRODUCTION - 8 colonnes) - CORRECTION DATE APPLIQUÉE"""
    rows = []
    
    try:
        date_emission = data.get("date", "")
        mois = get_month_from_date(date_emission)
        
        # CORRECTION 1: Utiliser la date extraite et la formater en JJ/MM/AAAA
        date_formatted = format_date_french(date_emission)  # FORMAT CORRIGÉ
        
        client = data.get("client", "")
        numero_bdc = data.get("numero", "")
        magasin = data.get("adresse_livraison", "")
        editeur = st.session_state.username
        
        for _, row in articles_df.iterrows():
            quantite = row.get("Quantité", 0)
            if pd.isna(quantite) or quantite == 0 or str(quantite).strip() == "0":
                continue
            
            quantite_str = format_quantity(quantite)
            
            try:
                quantite_int = int(float(quantite_str))
                quantite_str = str(quantite_int)
            except:
                quantite_str = "0"
                continue
            
            designation = str(row.get("Produit Standard", "")).strip()
            if not designation:
                designation = str(row.get("Produit Brute", "")).strip()
            
            rows.append([
                mois,           # Colonne 1 (mois)
                date_formatted, # Date au format JJ/MM/AAAA (CORRIGÉ)
                client,         # Client
                numero_bdc,     # FACT
                magasin,        # Magasin
                designation,    # Désignation
                quantite_str,   # Quantité
                editeur         # Editeur
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
# FONCTIONS DE DÉTECTION DE DOUBLONS - FILTRE 3: Même logique pour BDC et factures
# ============================================================
def check_for_duplicates(document_type: str, extracted_data: dict, worksheet) -> Tuple[bool, List[Dict]]:
    """Vérifie si un document existe déjà dans Google Sheets"""
    try:
        all_data = worksheet.get_all_values()
        
        if len(all_data) <= 1:
            return False, []
        
        client_col = 2
        current_client = extracted_data.get('client', '')
        
        if "FACTURE" in document_type.upper():
            doc_num_col = 3
            current_doc_num = extracted_data.get('numero_facture', '')
        else:
            doc_num_col = 3
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
                        date_col = 1
                        current_date = ""
                        date_facture = extracted_data.get('date', '')
                        if date_facture:
                            try:
                                date_obj = parser.parse(date_facture, dayfirst=True)
                                current_date = date_obj.strftime("%d/%m/%Y")
                            except:
                                current_date = ""
                        
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
        
        normalized_type = normalize_document_type(document_type)
        
        if normalized_type not in SHEET_GIDS:
            st.warning(f"⚠️ Type de document '{document_type}' non reconnu. Utilisation de la feuille par défaut.")
            normalized_type = "FACTURE EN COMPTE"
        
        sa_info = dict(st.secrets["gcp_sheet"])
        gc = gspread.service_account_from_dict(sa_info)
        sh = gc.open_by_key(SHEET_ID)
        
        target_gid = SHEET_GIDS.get(normalized_type)
        
        if target_gid is None:
            st.error(f"❌ GID non trouvé pour le type: {normalized_type}")
            return sh.get_worksheet(0)
        
        for worksheet in sh.worksheets():
            if int(worksheet.id) == target_gid:
                return worksheet
        
        st.warning(f"⚠️ Feuille avec GID {target_gid} non trouvée. Utilisation de la première feuille.")
        return sh.get_worksheet(0)
        
    except Exception as e:
        st.error(f"❌ Erreur lors de la connexion à Google Sheets: {str(e)}")
        return None

def find_table_range(worksheet, num_columns=8):
    """Trouve la plage de table dans la feuille avec un nombre de colonnes spécifique"""
    try:
        all_data = worksheet.get_all_values()
        
        if not all_data:
            return "A1:H1"
        
        headers = ["Mois", "Date", "Client", "N* facture", "Magasin", "Désignation", "Quantité", "Editeur"]
        
        first_row = all_data[0] if all_data else []
        header_found = any(header in str(first_row) for header in headers)
        
        if header_found:
            last_row = len(all_data) + 1
            if len(all_data) <= 1:
                return "A2:H2"
            else:
                return f"A{last_row}:H{last_row}"
        else:
            for i, row in enumerate(all_data, start=1):
                if not any(cell.strip() for cell in row):
                    return f"A{i}:H{i}"
            
            return f"A{len(all_data)+1}:H{len(all_data)+1}"
            
    except Exception as e:
        return "A2:H2"

def save_to_google_sheets(document_type: str, data: dict, articles_df: pd.DataFrame, 
                         duplicate_action: str = None, duplicate_rows: List[int] = None):
    """Sauvegarde les données dans Google Sheets (version production)"""
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
        
        st.info(f"📋 **Aperçu des données à enregistrer (lignes avec quantité > 0):**")
        
        if "FACTURE" in document_type.upper():
            columns = ["Mois", "Date", "Client", "N* facture", "Magasin", "Désignation", "Quantité", "Editeur"]
        else:
            columns = ["Mois", "Date", "Client", "FACT", "Magasin", "Désignation", "Quantité", "Editeur"]
        
        preview_df = pd.DataFrame(new_rows, columns=columns)
        st.dataframe(preview_df, use_container_width=True)
        
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

st.markdown(f'''
<div class="user-info">
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" style="margin-right: 6px;">
        <path d="M8 8C10.2091 8 12 6.20914 12 4C12 1.79086 10.2091 0 8 0C5.79086 0 4 1.79086 4 4C4 6.20914 5.79086 8 8 8Z" fill="white"/>
        <path d="M8 9C4.13401 9 1 12.134 1 16H15C15 12.134 11.866 9 8 9Z" fill="white"/>
    </svg>
    {st.session_state.username}
</div>
''', unsafe_allow_html=True)

st.markdown('<div class="tech-grid"></div>', unsafe_allow_html=True)

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
    <span class="tech-badge" style="background: linear-gradient(135deg, #10B98115 0%, #34D39915 100%); color: #10B981 !important;">Multi-Scoring V1.3</span>
</div>
''', unsafe_allow_html=True)

st.markdown(f'''
<p class="brand-sub">
    Système intelligent de traitement de documents • Connecté en tant que <strong style="color: #1A1A1A !important;">{st.session_state.username}</strong>
</p>
''', unsafe_allow_html=True)

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
# TRAITEMENT AUTOMATIQUE DE L'IMAGE - VERSION AMÉLIORÉE V1.3
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
    
    progress_container = st.empty()
    with progress_container.container():
        st.markdown('<div class="progress-container">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 3rem; margin-bottom: 1rem;">🤖</div>', unsafe_allow_html=True)
        st.markdown('<h3 style="color: white !important;">Initialisation du système IA V1.3</h3>', unsafe_allow_html=True)
        st.markdown(f'<p class="progress-text-dark">Analyse en cours avec Scoring Multi-Indices...</p>', unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        steps = [
            "Chargement de l'image...",
            "Prétraitement des données...",
            "Analyse par IA GPT-4 Vision...",
            "Application du scoring multi-indices...",
            "Détection des colonnes de tableau...",
            "Extraction du FACT manuscrit...",
            "Vérification de cohérence...",
            "Finalisation avec règles métier..."
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
            
            if st.session_state.document_analysis_details:
                correction = st.session_state.document_analysis_details
                st.info(f"⚠️ Correction appliquée: {correction.get('original_type')} → {correction.get('adjusted_type')}")
            
            fact_manuscrit = result.get("fact_manuscrit", "")
            if fact_manuscrit and document_subtype in ["DLP", "S2M", "ULYS"]:
                st.success(f"✅ FACT manuscrit détecté: {fact_manuscrit}")
            
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
            
            progress_container.empty()
            st.rerun()
        else:
            st.error("❌ Échec de l'analyse IA - Veuillez réessayer avec une image plus claire")
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
    
    col_img, col_info = st.columns([2, 1])
    
    with col_img:
        st.image(st.session_state.uploaded_image, use_column_width=True)
    
    with col_info:
        st.markdown(f"""
        <div class="info-box" style="height: 100%;">
            <strong style="color: {PALETTE['text_dark']} !important;">📊 Métadonnées :</strong><br><br>
            • Résolution : Haute définition<br>
            • Format : Image numérique<br>
            • Statut : Analysé par IA V1.3<br>
            • Confiance : Élevée<br><br>
            <small style="color: {PALETTE['text_light']} !important;">Document prêt pour traitement</small>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# AFFICHAGE DES RÉSULTATS - AVEC SECTION SCORING MULTI-INDICES V1.3
# ============================================================
if st.session_state.show_results and st.session_state.ocr_result and not st.session_state.processing:
    result = st.session_state.ocr_result
    doc_type = st.session_state.detected_document_type
    
    # NOUVELLE SECTION : Analyse de scoring multi-indices
    with st.expander("🎯 Analyse de scoring multi-indices V1.3"):
        if st.session_state.ocr_raw_text:
            scoring_result = calculate_document_scores(st.session_state.ocr_raw_text)
            
            st.write("**Résultats du scoring:**")
            
            # Afficher les scores
            scores_df = pd.DataFrame(
                list(scoring_result["scores"].items()),
                columns=["Type", "Score"]
            ).sort_values("Score", ascending=False)
            
            st.dataframe(scores_df, use_container_width=True)
            
            # Afficher le type détecté
            st.write(f"**Type final détecté:** {scoring_result['document_type']}")
            st.write(f"**Score maximal:** {scoring_result['max_score']}")
            
            # Afficher les colonnes détectées
            if scoring_result["extracted_info"]["columns_detected"]:
                st.write("**Colonnes détectées:**", ", ".join(scoring_result["extracted_info"]["columns_detected"]))
            
            # Afficher les informations extraites
            if scoring_result["extracted_info"]["quartier_s2m"]:
                st.write(f"**Quartier S2M:** {scoring_result['extracted_info']['quartier_s2m']}")
            
            if scoring_result["extracted_info"]["nom_magasin_ulys"]:
                st.write(f"**Nom magasin ULYS:** {scoring_result['extracted_info']['nom_magasin_ulys']}")
            
            if scoring_result["extracted_info"]["fact_manuscrit"]:
                st.write(f"**FACT manuscrit:** {scoring_result['extracted_info']['fact_manuscrit']}")
            
            # Indicateurs de confiance
            if scoring_result["max_score"] >= 8:
                st.success("✅ Détection très fiable (score ≥ 8)")
            elif scoring_result["max_score"] >= 5:
                st.info("ℹ️ Détection fiable (score ≥ 5)")
            else:
                st.warning("⚠️ Détection peu fiable (score < 5)")
    
    with st.expander("🔍 Analyse de détection détaillée"):
        st.write("**Type brut détecté par l'IA:**", result.get("type_document", "Non détecté"))
        st.write("**Sous-type détecté:**", result.get("document_subtype", "Non détecté"))
        st.write("**Type normalisé:**", doc_type)
        
        if st.session_state.document_analysis_details:
            st.write("**Corrections appliquées:**", st.session_state.document_analysis_details)
        
        if st.session_state.ocr_raw_text:
            detection = detect_document_type_from_text(st.session_state.ocr_raw_text)
            st.write("**Détection par texte:**")
            st.write(f"- Type détecté: {detection['type']}")
            st.write(f"- Scores: {detection['scores']}")
            st.write(f"- Indicateurs trouvés: {detection['indicators_found']}")
            
            if st.session_state.quartier_s2m:
                st.write(f"- Quartier S2M extrait: {st.session_state.quartier_s2m}")
            if st.session_state.nom_magasin_ulys:
                st.write(f"- Nom magasin ULYS extrait: {st.session_state.nom_magasin_ulys}")
            
            fact_extrait = extract_fact_number_from_handwritten(st.session_state.ocr_raw_text)
            if fact_extrait:
                st.write(f"- FACT manuscrit extrait du texte: {fact_extrait}")
    
    st.markdown('<div class="success-box fade-in">', unsafe_allow_html=True)
    st.markdown(f'''
    <div style="display: flex; align-items: start; gap: 15px;">
        <div style="font-size: 2.5rem; color: {PALETTE['success']} !important;">✅</div>
        <div>
            <strong style="font-size: 1.1rem; color: #1A1A1A !important;">Analyse IA V1.3 terminée avec succès</strong><br>
            <span style="color: #333333 !important;">Type détecté : <strong>{doc_type}</strong> | Scoring : <strong>Multi-Indices Activé</strong></span><br>
            <small style="color: #4B5563 !important;">Veuillez vérifier les données extraites avant validation</small>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
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
    # INFORMATIONS EXTRAITES - AVEC CHANGEMENTS APPLIQUÉS
    # ========================================================
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>📋 Informations extraites</h4>', unsafe_allow_html=True)
    
    if "FACTURE" in doc_type.upper():
        col1, col2 = st.columns(2)
        with col1:
            # NOUVELLE AMÉLIORATION: Afficher l'adresse d'abord
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Adresse</div>', unsafe_allow_html=True)
            adresse = st.text_input("", value=result.get("adresse_livraison", ""), key="facture_adresse", label_visibility="collapsed")
            
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">N° Facture</div>', unsafe_allow_html=True)
            numero_facture = st.text_input("", value=result.get("numero_facture", ""), key="facture_num", label_visibility="collapsed")
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Bon de commande</div>', unsafe_allow_html=True)
            bon_commande = st.text_input("", value=result.get("bon_commande", ""), key="facture_bdc", label_visibility="collapsed")
        
        with col2:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Client</div>', unsafe_allow_html=True)
            
            client_options = ["ULYS", "S2M", "DLP", "Autre"]
            
            extracted_client = result.get("client", "")
            
            document_subtype = result.get("document_subtype", "").upper()
            if document_subtype == "DLP":
                extracted_client = "DLP"
            elif document_subtype == "S2M":
                extracted_client = "S2M"
            elif document_subtype == "ULYS":
                extracted_client = "ULYS"
            
            mapped_client = map_client(extracted_client)
            default_index = 3  # Par défaut "Autre"
            if mapped_client in client_options:
                default_index = client_options.index(mapped_client)
            elif extracted_client in client_options:
                default_index = client_options.index(extracted_client)
            
            client_choice = st.selectbox(
                "Sélectionnez le client",
                options=client_options,
                index=default_index,
                key="facture_client_select",
                label_visibility="collapsed"
            )
            
            # NOUVELLE AMÉLIORATION: Forcer client = adresse si "Autre"
            if client_choice == "Autre":
                client = adresse
            else:
                client = client_choice
            
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Date</div>', unsafe_allow_html=True)
            date_extracted = result.get("date", "")
            date_formatted = format_date_french(date_extracted)
            date = st.text_input("", value=date_formatted, key="facture_date", label_visibility="collapsed")
            
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
            
            client_options = ["ULYS", "S2M", "DLP", "Autre"]
            
            extracted_client = result.get("client", "")
            
            document_subtype = result.get("document_subtype", "").upper()
            if document_subtype == "DLP":
                extracted_client = "DLP"
            elif document_subtype == "S2M":
                extracted_client = "S2M"
            elif document_subtype == "ULYS":
                extracted_client = "ULYS"
            
            mapped_client = map_client(extracted_client)
            default_index = 0
            if mapped_client in client_options:
                default_index = client_options.index(mapped_client)
            elif extracted_client in client_options:
                default_index = client_options.index(extracted_client)
            
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
                st.info(f"🔍 FACT manuscrit détecté: {fact_manuscrit}")
            else:
                numero_a_afficher = numero_standard
            
            numero = st.text_input("", 
                                  value=numero_a_afficher, 
                                  key="bdc_numero", 
                                  label_visibility="collapsed",
                                  help="Numéro manuscrit extrait après 'F' ou 'Fact' (peut être vide si non trouvé)")
        
        with col2:
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Date</div>', unsafe_allow_html=True)
            date_extracted = result.get("date", "")
            date_formatted = format_date_french(date_extracted)
            date = st.text_input("", value=date_formatted, key="bdc_date", label_visibility="collapsed")
            
            st.markdown(f'<div style="margin-bottom: 5px; font-weight: 500; color: #1A1A1A !important;">Adresse</div>', unsafe_allow_html=True)
            
            adresse_value = result.get("adresse_livraison", "")
            
            if document_subtype == "DLP":
                adresse_value = "Leader Price Akadimbahoaka"
            elif document_subtype == "S2M":
                quartier = st.session_state.quartier_s2m or ""
                if quartier:
                    adresse_value = clean_adresse(f"Supermaki {quartier}")
                else:
                    adresse_value = clean_adresse(adresse_value) if adresse_value else "Supermaki"
            elif document_subtype == "ULYS":
                nom_magasin = st.session_state.nom_magasin_ulys or ""
                if nom_magasin:
                    adresse_value = nom_magasin
                else:
                    adresse_value = "ULYS Magasin"
            
            adresse = st.text_input("", value=adresse_value, key="bdc_adresse", label_visibility="collapsed")
        
        data_for_sheets = {
            "client": client,
            "numero": numero,
            "date": date,
            "adresse_livraison": adresse
        }
    
    st.session_state.data_for_sheets = data_for_sheets
    
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
    # TABLEAU STANDARDISÉ ÉDITABLE
    # ========================================================
    if st.session_state.edited_standardized_df is not None and not st.session_state.edited_standardized_df.empty:
        st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
        st.markdown('<h4>📘 Standardisation des Produits</h4>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="margin-bottom: 20px; padding: 12px; background: rgba(59, 130, 246, 0.05); border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.1);">
            <small style="color: #1A1A1A !important;">
            💡 <strong>Mode édition activé avec améliorations :</strong> 
            • <strong>Amélioration 1:</strong> Standardisation "Coteau d'Ambalavao Rouge" → "Cuvee Speciale 75cls"<br>
            • <strong>Amélioration 2:</strong> Liste de produits étendue avec meilleure détection des fautes d'orthographe<br>
            • <strong>Amélioration 3:</strong> Détection améliorée pour Aperao Peche, Côteau d'Ambalavao Special, etc.<br>
            • Colonne "Produit Brute" : texte original extrait par l'IA de Chanfoui AI<br>
            • Colonne "Produit Standard" : standardisé automatiquement par Chafoui AI (éditable)<br>
            • <strong>Note :</strong> Veuillez prendre la photo le plus près possible du document et avec une netteté maximale.
            </small>
        </div>
        """, unsafe_allow_html=True)
        
        df_with_zero_qty = st.session_state.edited_standardized_df[
            (st.session_state.edited_standardized_df["Quantité"] == 0) | 
            (st.session_state.edited_standardized_df["Quantité"].isna())
        ]
        
        if len(df_with_zero_qty) > 0:
            st.warning(f"⚠️ **Attention :** {len(df_with_zero_qty)} ligne(s) avec quantité 0 seront automatiquement supprimées lors de l'export")
        
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
                    help="Quantité commandée (lignes avec 0 seront supprimées à l'export) - FORCÉ EN ENTIER",
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
        
        if "Quantité" in edited_df.columns:
            edited_df["Quantité"] = edited_df["Quantité"].apply(
                lambda x: int(round(float(x))) if pd.notna(x) else 0
            )
        
        st.session_state.edited_standardized_df = edited_df
        
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
        
        if st.button("🔄 Re-standardiser tous les produits", 
                    key="restandardize_button",
                    help="Appliquer la standardisation intelligente à tous les produits"):
            new_data = []
            for _, row in edited_df.iterrows():
                produit_brut = row["Produit Brute"]
                
                if any(cat in produit_brut.upper() for cat in ["VINS ROUGES", "VINS BLANCS", "VINS ROSES", "LIQUEUR", "CONSIGNE", "122111", "122112", "122113"]):
                    new_data.append({
                        "Produit Brute": produit_brut,
                        "Produit Standard": produit_brut,
                        "Quantité": row["Quantité"],
                        "Confiance": "0%",
                        "Auto": False
                    })
                else:
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
    # TEST DE STANDARDISATION AMÉLIORÉE
    # ============================================================
    with st.expander("🧪 Tester la standardisation améliorée"):
        test_examples = [
            "Coteau d'Ambalavao Rouge",
            "Coteau d'Ambalavao Rouge 75cl",
            "Côteau d'Ambalavao Rouge",
            "Coteau d Ambalavao Rouge",
            "Coteau d'ambalavao rouge",
            "Côte de Fianar Gris 3L",
            "Cote de Fianar Gris 3L",
            "Aperao Peche 37 cl",
            "Aperao Peche 37cl",
            "Côteau d'Ambalavao Special 75cl",
            "Coteau d'Ambalavao Special 75cl",
            "Consignation Btl 75cl",
            "Jus de raisin Rouge 70 cl",
            "Jus de raisin Blanc 20 cl",
            "Rhum Sambatra 20 cl"
        ]
        
        if st.button("Tester les améliorations de standardisation"):
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
            
            perfect_matches = sum(1 for _, row in test_df.iterrows() 
                                if float(row["Confiance"].replace('%', '')) >= 85.0 and row["Statut"] == "matched")
            accuracy = (perfect_matches / len(test_df)) * 100
            st.success(f"📈 Précision améliorée : {accuracy:.1f}%")
            
            conversion_test = test_df[test_df["Produit Brute"].str.contains("Coteau.*Rouge", case=False, na=False)]
            if not conversion_test.empty:
                st.info(f"**Conversion testée:** 'Coteau d'Ambalavao Rouge' → '{conversion_test.iloc[0]['Produit Standard']}'")
    
    # ============================================================
    # BOUTON D'EXPORT PAR DÉFAUT
    # ============================================================
    st.markdown('<div class="card fade-in">', unsafe_allow_html=True)
    st.markdown('<h4>🚀 Export vers Cloud</h4>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="info-box">
        <strong style="color: #1A1A1A !important;">🌐 Destination :</strong> Google Sheets (Cloud)<br>
        <strong style="color: #1A1A1A !important;">🔒 Sécurité :</strong> Chiffrement AES-256<br>
        <strong style="color: #1A1A1A !important;">⚡ Vitesse :</strong> Synchronisation en temps réel<br>
        <strong style="color: #1A1A1A !important;">🔄 Vérification :</strong> Détection automatique des doublons<br>
        <strong style="color: #1A1A1A !important;">✨ AMÉLIORATIONS APPLIQUÉES V1.3 :</strong><br>
        • <strong>Détection multi-indices:</strong> Scoring avancé pour FACTURE/DLP/S2M/ULYS<br>
        • <strong>Colonnes détectées:</strong> Analyse structurelle des tableaux<br>
        • <strong>Règles métier:</strong> DLP=TOUJOURS BDC, adresse forcée<br>
        • <strong>Priorité:</strong> FACTURE > DLP > S2M > ULYS en cas d'égalité<br>
        • <strong>Seuil minimal:</strong> Score ≥ 3 pour validation<br>
        • <strong>Extraction améliorée:</strong> Quartier S2M, nom magasin ULYS, FACT manuscrit<br>
        • <strong>Correction 1:</strong> Date formatée JJ/MM/AAAA (extraite du document)<br>
        • <strong>Correction 2:</strong> Adresse DLP forcée à "Leader Price Akadimbahoaka"<br>
        • <strong>Correction 3:</strong> Pour factures "Autre client", client = adresse<br>
        • <strong>Amélioration 1:</strong> Standardisation "Coteau d'Ambalavao Rouge" appliquée<br>
        • <strong>Amélioration 2:</strong> Bibliothèque de produits étendue<br>
        • <strong>Amélioration 3:</strong> Meilleure détection des fautes d'orthographe<br>
        • <strong>Amélioration 4:</strong> Extraction correcte colonnes facture
    </div>
    """, unsafe_allow_html=True)
    
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
            <div style="font-size: 0.8rem; color: #4B5563 !important;">Export instantané<br>Scoring Multi-Indices V1.3</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ============================================================
    # VÉRIFICATION AUTOMATIQUE DES DOUBLONS APRÈS CLIC SUR EXPORT
    # ============================================================
    if st.session_state.export_triggered and st.session_state.export_status is None:
        with st.spinner("🔍 Analyse des doublons en cours ..."):
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
                st.error("❌ Connexion cloud échouée - Vérifiez votre connexion")
                st.session_state.export_status = "error"
    
    # ============================================================
    # AFFICHAGE DES OPTIONS EN CAS DE DOUBLONS
    # ============================================================
    if st.session_state.export_status == "duplicates_found":
        st.markdown('<div class="duplicate-box fade-in">', unsafe_allow_html=True)
        
        st.markdown(f'''
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
            <div style="font-size: 2rem; color: #F59E0B !important;">⚠️</div>
            <div>
                <h3 style="margin: 0; color: #1A1A1A !important;">ALERTE : DOUBLON DÉTECTÉ </h3>
                <p style="margin: 5px 0 0 0; color: #4B5563 !important; font-size: 0.9rem;">Document similaire existant dans la base cloud - Même logique pour BDC et factures</p>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
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
                    <div><strong>FACT :</strong> {st.session_state.data_for_sheets.get('numero', 'Non détecté')}</div>
                    <div><strong>Doublons :</strong> {len(st.session_state.duplicate_rows)} trouvé(s)</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown(f'<div style="color: #1A1A1A !important; margin-bottom: 10px; font-weight: 600;">Sélectionnez une action :</div>', unsafe_allow_html=True)
        
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
    
    # ============================================================
    # EXPORT EFFECTIF DES DONNÉES
    # ============================================================
    if st.session_state.export_status in ["no_duplicates", "ready_to_export"]:
        if st.session_state.export_status == "no_duplicates":
            st.session_state.duplicate_action = "add_new"
        
        export_df = st.session_state.edited_standardized_df.copy()
        
        zero_qty_rows = export_df[export_df["Quantité"] == 0]
        if len(zero_qty_rows) > 0:
            st.info(f"⚠️ {len(zero_qty_rows)} ligne(s) avec quantité 0 seront automatiquement exclues de l'export")
        
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
                <div style="padding: 25px; background: linear-gradient(135deg, #10B981 0%, #34D399 100%); color: white !important; border-radius: 18px; text-align: center; margin: 20px 0;">
                    <div style="font-size: 2.5rem; margin-bottom: 10px;">✅</div>
                    <h3 style="margin: 0 0 10px 0; color: white !important;">Synchronisation réussie !</h3>
                    <p style="margin: 0; opacity: 0.9;">Les données ont été exportées avec succès vers le cloud.</p>
                    <p style="margin: 10px 0 0 0; font-size: 0.9rem; opacity: 0.8;">
                        ✓ Détection multi-indices activée (Score: {scoring_result['max_score']})<br>
                        ✓ Correction 1: Date formatée JJ/MM/AAAA (extraite du document)<br>
                        ✓ Correction 2: Adresse DLP forcée à "Leader Price Akadimbahoaka"<br>
                        ✓ Correction 3: Pour factures "Autre client", client = adresse<br>
                        ✓ Amélioration 1: Standardisation "Coteau d'Ambalavao Rouge" appliquée<br>
                        ✓ Amélioration 2: Bibliothèque de produits étendue<br>
                        ✓ Amélioration 3: Meilleure détection des fautes d'orthographe<br>
                        ✓ Amélioration 4: Extraction correcte colonnes facture
                    </p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.session_state.export_status = "error"
                st.error("❌ Échec de l'export - Veuillez réessayer")
                
        except Exception as e:
            st.error(f"❌ Erreur système : {str(e)}")
            st.session_state.export_status = "error"
    
    # ============================================================
    # BOUTONS DE NAVIGATION - AMÉLIORATION DU BOUTON "NOUVEAU DOCUMENT"
    # ============================================================
    if st.session_state.document_scanned:
        st.markdown("---")
        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<h4>🧭 Navigation</h4>', unsafe_allow_html=True)
        
        col_nav1, col_nav2 = st.columns(2)
        
        with col_nav1:
            if st.button("📄 Nouveau document", 
                        use_container_width=True, 
                        type="secondary",
                        key="new_doc_main_nav",
                        help="Effacer toutes les informations et revenir au début"):
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
                
                st.markdown(
                    """
                    <script>
                        window.scrollTo(0, 0);
                    </script>
                    """,
                    unsafe_allow_html=True
                )
                
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
# FOOTER
# ============================================================
st.markdown("---")

with st.container():
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"<center style='color: #1A1A1A !important;'>🤖</center>", unsafe_allow_html=True)
        st.markdown(f"<center><small style='color: #4B5563 !important;'>AI Vision Amélioré</small></center>", unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"<center style='color: #1A1A1A !important;'>⚡</center>", unsafe_allow_html=True)
        st.markdown(f"<center><small style='color: #4B5563 !important;'>Fast Processing</small></center>", unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"<center style='color: #1A1A1A !important;'>🔒</center>", unsafe_allow_html=True)
        st.markdown(f"<center><small style='color: #4B5563 !important;'>Secure Cloud</small></center>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <center style='margin: 15px 0;'>
        <span style='font-weight: 700; color: #27414A !important;'>{BRAND_TITLE}</span>
        <span style='color: #4B5563 !important;'> • Système IA Amélioré • © {datetime.now().strftime("%Y")}</span>
    </center>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <center style='font-size: 0.8rem; color: #4B5563 !important;'>
        <span style='color: #10B981 !important;'>●</span> 
        Système actif • Session : 
        <strong style='color: #1A1A1A !important;'>{st.session_state.username}</strong>
        • Améliorations activées • {datetime.now().strftime("%H:%M:%S")}
    </center>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <center style='font-size: 0.75rem; color: #3B82F6 !important; margin-top: 5px;'>
        <strong>✨ VERSION 1.3 :</strong> Détection multi-indices • Scoring avancé • Structure tableau • Règles métier renforcées
    </center>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
