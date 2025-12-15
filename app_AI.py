import re
import pandas as pd

def extract_designation_nb_bills(ocr_text: str) -> pd.DataFrame:
    """
    Extraction fidèle FACTURE EN COMPTE Chan Foui & Fils
    Colonnes :
      - Désignation des marchandises
      - Nb bills
    """

    lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]

    # =============================
    # 1. EXTRACTION DES DÉSIGNATIONS
    # =============================
    designations = []
    in_table = False

    for line in lines:
        up = line.upper()

        if "DÉSIGNATION DES MARCHANDISES" in up:
            in_table = True
            continue

        # arrêt STRICT à la fin du tableau
        if in_table and ("TOTAL HT" in up or "MONTANT HT" in up):
            break

        if in_table:
            # on ignore CONSIGNE hors tableau
            if up == "CONSIGNE":
                continue

            # désignation = texte (pas de chiffres)
            if len(line) > 10 and not re.search(r"\d", line):
                designations.append(line)

    # =============================
    # 2. EXTRACTION DE LA COLONNE NB BILLS
    # =============================
    nb_bills = []
    in_nb_bills = False

    for line in lines:
        up = line.upper()

        if "NB BILLS" in up:
            in_nb_bills = True
            continue

        if in_nb_bills:
            # arrêt colonne Nb bills
            if "TOTAL HT" in up or "MONTANT HT" in up:
                break

            # ignorer montants
            if "," in line or "." in line:
                continue

            # récupérer UNIQUEMENT les nombres
            nums = re.findall(r"\d{1,3}", line)
            for n in nums:
                nb_bills.append(int(n))

    # =============================
    # 3. ASSOCIATION 1 ↔ 1 (FIDÈLE)
    # =============================
    rows = []
    for d, q in zip(designations, nb_bills):
        rows.append({
            "Désignation": d,
            "Nb bills": q
        })

    return pd.DataFrame(rows)
