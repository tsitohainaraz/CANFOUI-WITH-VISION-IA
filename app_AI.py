def extract_bdc_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # =========================
    # MÉTADONNÉES
    # =========================
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?\s*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # =========================
    # PARSING TABLEAU
    # =========================
    in_table = False
    buffer = []

    def is_quantity(line: str) -> bool:
        clean = (
            line.replace("D", "")
                .replace("O", "0")
                .replace("G", "0")
                .replace("I", "1")
        )
        return clean.isdigit() and 1 <= int(clean) <= 999

    def is_noise(line: str) -> bool:
        return (
            "PAQ" in line.upper()
            or "/PC" in line.upper()
            or "PAQ=" in line.upper()
            or re.search(r"\d{2}\.\d{2}\.\d{4}", line)
        )

    def is_section_title(line: str) -> bool:
        return re.match(r"\d{6}\s+(VINS|CONSIGNE|LIQUEUR)", line.upper())

    for line in lines:
        up = line.upper()

        # Début tableau
        if "DESCRIPTION DE L'ARTICLE" in up:
            in_table = True
            continue

        if not in_table:
            continue

        # Fin tableau
        if "TOTAL DE LA COMMANDE" in up:
            break

        # Ignorer titres
        if is_section_title(line):
            continue

        # Ignorer bruit
        if is_noise(line):
            continue

        # =========================
        # QUANTITÉ → CRÉATION ARTICLE
        # =========================
        if buffer and is_quantity(line):
            designation = " ".join(buffer)
            designation = re.sub(r"\s{2,}", " ", designation).strip()

            result["articles"].append({
                "Désignation": designation.title(),
                "Quantité": int(line.replace("D", "").replace("O", "0"))
            })

            buffer = []  # RESET OBLIGATOIRE
            continue

        # =========================
        # DÉSIGNATION → BUFFER
        # =========================
        if any(k in up for k in [
            "VIN", "CONS.", "MAROPARASY", "COTE", "FIANAR", "GRIS"
        ]):
            buffer.append(line)

    return result
