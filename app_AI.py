def extract_bdc_ulys(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    result = {
        "client": "ULYS",
        "numero": "",
        "date": "",
        "articles": []
    }

    # Métadonnées
    m = re.search(r"N[°o]\s*(\d{8,})", text)
    if m:
        result["numero"] = m.group(1)

    m = re.search(r"Date de la Commande\s*:?[\s\-]*(\d{2}/\d{2}/\d{4})", text)
    if m:
        result["date"] = m.group(1)

    # -----------------------------
    # PARSING AMÉLIORÉ (PRÉCIS)
    # -----------------------------
    in_table = False
    current_designation = ""
    waiting_qty = False

    def is_valid_qty(s: str) -> bool:
        s = s.replace("D", "").replace("O", "0").replace("G", "0")
        return re.fullmatch(r"\d{1,3}", s) is not None

    def clean_designation(s: str) -> str:
        s = re.sub(r"\b\d{6,}\b", "", s)   # codes longs
        s = re.sub(r"\b(PAQ|/PC)\b", "", s)
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip()

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

        # Ignorer sections catégories
        if re.match(r"\d{6}\s+(VINS|CONSIGNE|LIQUEUR)", up):
            continue

        # Parasites OCR → on continue d'attendre la quantité
        if up in ["PAQ", "/PC", "D3", "D31", "IPAQ"]:
            waiting_qty = True
            continue

        # -------------------------
        # DÉSIGNATION (MULTI-LIGNE)
        # -------------------------
        if (
            ("VIN " in up or "CONS." in up)
            and not re.match(r"\d{6,}", line)
            and not is_valid_qty(line)
        ):
            if current_designation:
                current_designation += " " + line
            else:
                current_designation = line

            current_designation = clean_designation(current_designation)
            waiting_qty = True
            continue

        # -------------------------
        # QUANTITÉ
        # -------------------------
        if current_designation and waiting_qty:
            clean = (
                line.replace("D", "")
                    .replace("O", "0")
                    .replace("G", "0")
            )

            if is_valid_qty(clean):
                result["articles"].append({
                    "Désignation": current_designation.title(),
                    "Quantité": int(clean)
                })

                # ⚠️ on réinitialise PROPREMENT
                current_designation = ""
                waiting_qty = False
                continue

    return result
