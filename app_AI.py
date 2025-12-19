# ============================================
# TEST OPENAI API — STREAMLIT (FINAL)
# ============================================

import streamlit as st
from openai import OpenAI

# ----------------------------
# Configuration de la page
# ----------------------------
st.set_page_config(
    page_title="Test OpenAI API",
    page_icon="🧪",
    layout="centered"
)

st.title("🧪 Test OpenAI API")
st.caption("Vérification clé API + crédit + projet")

# ----------------------------
# Vérification des secrets
# ----------------------------
if "OPENAI_API_KEY" not in st.secrets:
    st.error("❌ OPENAI_API_KEY non trouvé dans les secrets Streamlit")
    st.stop()

st.success("✅ OPENAI_API_KEY détectée")

# ----------------------------
# Initialisation OpenAI
# ----------------------------
openai_client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"],
    project=st.secrets.get("OPENAI_PROJECT_ID")
)

# ----------------------------
# Bouton de test
# ----------------------------
if st.button("TEST OPENAI"):
    try:
        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            input="Réponds uniquement par OK",
            max_output_tokens=16
        )

        st.success("✅ Appel OpenAI réussi")
        st.subheader("Réponse du modèle :")
        st.code(response.output_text)

    except Exception as e:
        st.error("❌ Erreur OpenAI")
        st.exception(e)

# ----------------------------
# Footer
# ----------------------------
st.caption("Powered by OpenAI API • Test minimal")
