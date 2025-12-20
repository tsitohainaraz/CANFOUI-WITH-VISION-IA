# ============================================================
# EXPORT VERS GOOGLE SHEETS (DEUX BOUTONS) - CORRIGÉ
# ============================================================
if (st.session_state.duplicate_check_done and not st.session_state.duplicate_found) or \
   (st.session_state.duplicate_check_done and st.session_state.duplicate_action):
    
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h4>📤 Export vers Google Sheets</h4>', unsafe_allow_html=True)
    
    action = None
    if st.session_state.duplicate_action:
        action = st.session_state.duplicate_action
    
    # Deux boutons côte à côte - CORRECTION DES CLÉS
    col_export1, col_export2 = st.columns(2)
    
    with col_export1:
        if st.button("📄 Enregistrer données BRUTES", 
                    use_container_width=True, 
                    type="primary", 
                    key="export_raw_data"):  # CLÉ UNIQUE
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
                    key="export_standardized_data"):  # CLÉ UNIQUE
            try:
                # Préparer le dataframe pour l'export standardisé
                export_std_df = st.session_state.standardized_data_df[["designation_standard", "quantite"]].copy()
                export_std_df.columns = ["designation_brute", "quantite"]
                
                success, message = save_to_google_sheets(
                    doc_type,
                    st.session_state.data_for_sheets,
                    export_std_df,
                    duplicate_action=action,
                    duplicate_rows=st.session_state.duplicate_rows if action == "overwrite" else None,
                    use_raw=False
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
    
    # Options après enregistrement - CORRECTION DES CLÉS
    st.markdown("---")
    col_reset1, col_reset2 = st.columns(2)
    
    with col_reset1:
        if st.button("📄 Scanner un nouveau document", 
                    use_container_width=True, 
                    type="secondary",
                    key="new_doc_after_export"):  # CLÉ UNIQUE
            st.session_state.uploaded_file = None
            st.session_state.uploaded_image = None
            st.session_state.ocr_result = None
            st.session_state.show_results = False
            st.session_state.detected_document_type = None
            st.session_state.duplicate_check_done = False
            st.session_state.duplicate_found = False
            st.session_state.duplicate_action = None
            st.rerun()
    
    with col_reset2:
        if st.button("🔄 Recommencer l'analyse", 
                    use_container_width=True, 
                    type="secondary",
                    key="restart_after_export"):  # CLÉ UNIQUE
            st.session_state.uploaded_file = None
            st.session_state.uploaded_image = None
            st.session_state.ocr_result = None
            st.session_state.show_results = False
            st.session_state.detected_document_type = None
            st.session_state.duplicate_check_done = False
            st.session_state.duplicate_found = False
            st.session_state.duplicate_action = None
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# BOUTONS DE NAVIGATION - CORRIGÉ
# ============================================================
st.markdown("---")
col_nav1, col_nav2 = st.columns([1, 1])

with col_nav1:
    if st.button("📄 Scanner un nouveau document", 
                use_container_width=True, 
                type="secondary",
                key="new_doc_main_nav"):  # CLÉ UNIQUE
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
                key="restart_main_nav"):  # CLÉ UNIQUE
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
# BOUTON DE DÉCONNEXION - CORRIGÉ
# ============================================================
st.markdown("---")
if st.button("🚪 Déconnexion", 
            use_container_width=True, 
            type="secondary",
            key="logout_button_main"):  # CLÉ UNIQUE
    logout()
