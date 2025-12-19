if st.button("TEST OPENAI"):
    r = openai_client.responses.create(
        model="gpt-4.1-mini",
        input="Réponds uniquement par OK"
    )
    st.write(r.output_text)
