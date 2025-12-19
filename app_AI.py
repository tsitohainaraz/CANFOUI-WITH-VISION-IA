import streamlit as st
from openai import OpenAI

# Initialisation OpenAI
openai_client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"]
)

st.subheader("🧪 Test OpenAI API")

if st.button("TEST OPENAI"):
    try:
        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            input="Réponds uniquement par OK",
            max_output_tokens=10
        )

        st.success("✅ Appel OpenAI réussi")
        st.write("Réponse du modèle :")
        st.code(response.output_text)

    except Exception as e:
        st.error("❌ Erreur OpenAI")
        st.exception(e)
