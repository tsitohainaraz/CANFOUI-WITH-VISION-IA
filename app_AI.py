# ============================================================
# TEST DE STANDARDISATION ULYS - FILTRE 2 test
# ============================================================
with st.expander("🧪 Tester la standardisation ULYS (Filtre 2)"):
    # Exemples de test avec focus sur FILTRE 2
    test_examples = [
        "CONS. CHAN FOUI 75CL",
        "CONS. CHAN FOUL 75CL",
        "CONS CHAN FOUI 75CL",
        "CONS CHAN FOUL 75CL",
        "CONS.CHAN FOUI 75CL",  # Nouveau test
        "CONS.CHAN FOUL 75CL",  # Nouveau test
        "VIN ROUGE COTE DE FIANAR 3L",
        "VIN ROUGE COTE DE FIANARA 750ML NU",
        "VIN BLANC COTE DE FIANAR 3L",
        "VIN BLANC DOUX MAROPARASY 750ML NU",
        "VIN BLANC COTE DE FIANARA 750ML NU",
        "VIN GRIS COTE DE FIANARA 750ML NU",
        "VIN ROUGE DOUX MAROPARASY 750ML NU",
        "COTE DE FIANAR 3L",
        "MAROPARASY 750ML",
        "VIN ROUGE COTE DE FLANAR 3L",
    ]
    
    if st.button("Tester les filtres avec des exemples typiques ULYS"):
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
        
        # Vérification spécifique du FILTRE 2
        filter2_test = test_df[test_df["Produit Brute"].str.contains("CHAN FOUI|CHAN FOUL", case=False, na=False)]
        if not filter2_test.empty:
            st.info(f"**Filtre 2 testé:** 'CONS. CHAN FOUI 75CL' → '{filter2_test.iloc[0]['Produit Standard']}'")
        
        # Calculer l'accuracy
        perfect_matches = sum(1 for _, row in test_df.iterrows() 
                            if float(row["Confiance"].replace('%', '')) >= 85.0 and row["Statut"] == "matched")
        accuracy = (perfect_matches / len(test_df)) * 100
        st.success(f"📈 Précision pour ULYS : {accuracy:.1f}%")
