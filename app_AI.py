# ============================================================
# FONCTION DE NORMALISATION DU TYPE DE DOCUMENT
# ============================================================
def normalize_document_type(doc_type: str) -> str:
    """Normalise le type de document pour correspondre aux clés SHEET_GIDS"""
    if not doc_type:
        return "DOCUMENT INCONNU"
    
    doc_type_upper = doc_type.upper()
    
    # Mapping des types de documents
    if "FACTURE" in doc_type_upper:
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
            # Par défaut, retourner BDC avec le nom du client
            return doc_type
    else:
        return doc_type

# ============================================================
# GOOGLE SHEETS CONFIGURATION (ajout d'une clé par défaut)
# ============================================================
SHEET_ID = "1FooEwQBwLjvyjAsvHu4eDes0o-eEm92fbEWv6maBNyE"

SHEET_GIDS = {
    "FACTURE EN COMPTE": 16102465,
    "BDC LEADERPRICE": 954728911,
    "BDC S2M": 954728911,
    "BDC ULYS": 954728911,
    "DOCUMENT INCONNU": 16102465  # Feuille par défaut pour les types inconnus
}

# ============================================================
# MODIFICATION DE LA FONCTION get_worksheet
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
            normalized_type = "FACTURE EN COMPTE"  # Ou "DOCUMENT INCONNU"
        
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

# ============================================================
# MODIFICATION DANS LA SECTION DE TRAITEMENT DE L'IMAGE
# ============================================================
if uploaded and uploaded != st.session_state.uploaded_file:
    # ... (code existant) ...
    
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
            
            # ... (reste du code existant) ...

# ============================================================
# MODIFICATION DANS LA SECTION DE VÉRIFICATION DES DOUBLONS
# ============================================================
if not st.session_state.duplicate_check_done:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h4>🔍 Vérification des doublons</h4>', unsafe_allow_html=True)
    
    if st.button("🔎 Vérifier si le document existe déjà", use_container_width=True, key="check_duplicates"):
        with st.spinner("Recherche de documents similaires..."):
            # Utiliser le type de document normalisé
            normalized_doc_type = normalize_document_type(doc_type)
            ws = get_worksheet(normalized_doc_type)
            
            if ws:
                # Afficher des informations de débogage
                st.info(f"📄 Type de document: {doc_type} → {normalized_doc_type}")
                st.info(f"🔗 Connexion à la feuille: {ws.title}")
                
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
