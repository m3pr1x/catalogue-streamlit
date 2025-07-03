# -*- coding: utf-8 -*-
"""
app.py – Générateur PC + page « Mise à jour M2 »
------------------------------------------------
• **Générateur PC** : identique à l’outil existant (contrôle des codes + 4
  fichiers de sortie).
• **Mise à jour M2**  : reprend le même workflow mais applique d’abord un
  tableau de correspondance *M2_ancien  →  M2_nouveau* fourni par l’utilisateur.

Nouveautés globales
===================
- Contrôle des codes M2 (6 chiffres) côté Générateur **et** côté MàJ.
- Gestion des fichiers CSV/Excel multi‑encodages + message d’erreur clair.
- Affichage des codes invalides **et** des codes non trouvés dans la table de
  correspondance.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import io
import pandas as pd
import streamlit as st

# ─────────────────────────────  CONFIG GLOBALE  ─────────────────────────────
st.set_page_config(page_title="Générateur DFRX / AFRX", page_icon="🛠️", layout="wide")

# ─────────────────────────────  OUTILS GÉNÉRIQUES  ──────────────────────────

def today_yyMMdd() -> str:
    return datetime.today().strftime("%y%m%d")


def read_csv(buf: io.BytesIO) -> pd.DataFrame:
    """Lecture robuste d'un CSV : détecteur de séparateur + 3 encodages."""
    for enc in ("utf-8", "latin1", "cp1252"):
        buf.seek(0)
        try:
            sample = buf.read(2048).decode(enc, errors="ignore")
            sep = csv.Sniffer().sniff(sample, delimiters=";,|\t").delimiter
            buf.seek(0)
            return pd.read_csv(buf, sep=sep, encoding=enc, engine="python", on_bad_lines="skip")
        except (UnicodeDecodeError, csv.Error, pd.errors.ParserError):
            continue
    raise ValueError("CSV illisible (encodage/séparateur)")


def read_any(file) -> pd.DataFrame:
    """CSV / Excel (xlsx / xls). Relance un seek(0) si encodage suivant."""
    suffix = Path(file.name.lower()).suffix
    if suffix == ".csv":
        data = file.getvalue()
        return read_csv(io.BytesIO(data))
    if suffix in {".xlsx", ".xls"}:
        file.seek(0)
        engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
        return pd.read_excel(file, engine=engine)
    raise ValueError(f"Extension non gérée : {suffix}")


def sanitize_code(code: str) -> str | None:
    """Vérifie qu'un code est numérique ; retourne 6 chiffres, zéro‑padding."""
    s = str(code).strip()
    if not s.isdigit():
        return None
    if len(s) == 5:
        s = s.zfill(6)
    if len(s) != 6:
        return None
    return s


# ─────────────────────────────  PAGE SELECTOR  ──────────────────────────────
page = st.sidebar.radio("Navigation", ["Générateur PC", "Mise à jour M2"])

# ═════════════════════════════  PAGE 1  ════════════════════════════════════
if page == "Générateur PC":
    st.title("🛠️ Outil Personal Catalogue")
    st.markdown("Déposez vos fichiers **codes produit** et **numéros de compte** (CSV / Excel).")

    # -------------------------  Upload fichiers  -------------------------
    codes_file = st.file_uploader("📄 Codes produit", type=("csv", "xlsx", "xls"))
    if codes_file:
        col_idx_codes = st.number_input("🔢 Numéro de colonne des **Codes M2**", 1, 50, 1)
    else:
        col_idx_codes = None

    compte_file = st.file_uploader("📄 Numéros de compte", type=("csv", "xlsx", "xls"))
    if compte_file:
        col_idx_comptes = st.number_input("🔢 Colonne comptes (1=A)", 1, 50, 1)
    else:
        col_idx_comptes = None

    entreprise = st.text_input("🏢 Entreprise")
    statut     = st.selectbox("📌 Statut", ["", "INCLUDE", "EXCLUDE"])

    # -------------------------  Génération  ------------------------------
    if st.button("🚀 Générer"):
        if not (codes_file and compte_file and entreprise and statut and col_idx_codes and col_idx_comptes):
            st.warning("Remplir tous les champs et joindre les 2 fichiers.")
            st.stop()

        try:
            df_codes   = read_any(codes_file)
            df_comptes = read_any(compte_file)
        except Exception as e:
            st.error(f"Erreur de lecture : {e}")
            st.stop()

        # extraction brut
        try:
            raw_codes = df_codes.iloc[:, col_idx_codes-1].dropna().astype(str).str.strip()
            comptes   = df_comptes.iloc[:, col_idx_comptes-1].dropna().astype(str).str.strip()
        except IndexError:
            st.error("Indice de colonne hors plage.")
            st.stop()

        sanitized = raw_codes.apply(sanitize_code)
        invalid   = sanitized.isna()
        if invalid.any():
            st.error(f"{invalid.sum()} code(s) invalide(s) :")
            st.dataframe(raw_codes[invalid].to_frame("Code fourni"))
            st.stop()

        codes = sanitized
        dstr  = today_yyMMdd()

        # ------- Construction fichiers -------
        df1 = pd.DataFrame({
            0: [f"PC_PROFILE_{entreprise}"] * len(codes),
            1: [statut] * len(codes),
            2: [None] * len(codes),
            3: [f"M2_{c}" for c in codes],
            4: ["frxProductCatallog:Online"] * len(codes),
        }).drop_duplicates()

        st.download_button(
            f"📥 Fichier DFRXHYBRPCP{dstr}0000",
            df1.to_csv(sep=";", index=False, header=False),
            file_name=f"DFRXHYBRPCP{dstr}0000",
            mime="text/plain",
        )

        ack_cmp = f"DFRXHYBRCMP{dstr}000068240530ITDFRXHYBRCMP{dstr}CCMGHYBFRX                    OK000000"
        st.download_button(
            f"📥 ACK CMP",
            ack_cmp,
            file_name=f"AFRXHYBRCMP{dstr}0000",
            mime="text/plain",
        )

        cmp_content = f"PC_{entreprise};PC_{entreprise};PC_PROFILE_{entreprise};{','.join(comptes)};frxProductCatalog:Online"
        st.download_button(
            f"📥 DFRXHYBRCMP{dstr}0000",
            cmp_content,
            file_name=f"DFRXHYBRCMP{dstr}0000",
            mime="text/plain",
        )

        ack_pcp = f"DFRXHYBRPCP{dstr}000068200117ITDFRXHYBRPCP{dstr}RCMRHYBFRX                    OK000000"
        st.download_button(
            f"📥 ACK PCP",
            ack_pcp,
            file_name=f"AFRXHYBRPCP{dstr}0000",
            mime="text/plain",
        )

# ═════════════════════════════  PAGE 2  ════════════════════════════════════
if page == "Mise à jour M2":
    st.title("🔄 Mise à jour des codes M2")
    st.markdown("""Ce module met à jour vos codes M2 à partir d’une table de
    correspondance **M2_ancien → M2_nouveau** avant de générer les fichiers
    PC/ACK habituels.""")

    # ---------------------  Upload codes produit ----------------------
    codes_file = st.file_uploader("📄 Codes produit (CSV / Excel)", type=("csv", "xlsx", "xls"))
    if codes_file:
        col_idx_codes = st.number_input("🔢 Colonne **Codes M2** dans ce fichier", 1, 50, 1)
    else:
        col_idx_codes = None

    # ---------------------  Upload table correspondance ---------------
    map_file = st.file_uploader("📄 Fichier 'M2_MisAJour' (CSV / Excel)", type=("csv", "xlsx", "xls"))
    if map_file:
        col_idx_old = st.number_input("🔢 Colonne **M2 ancien**", 1, 50, 1)
        col_idx_new = st.number_input("🔢 Colonne **M2 nouveau**", 1, 50, 2)
    else:
        col_idx_old = col_idx_new = None

    # ---------------------  Autres infos ------------------------------
    entreprise = st.text_input("🏢 Entreprise")
    statut     = st.selectbox("📌 Statut", ["", "INCLUDE", "EXCLUDE"])

    # ---------------------  Traitement -------------------------------
    if st.button("🚀 Générer MàJ"):
        if not (codes_file and map_file and entreprise and statut and col_idx_codes and col_idx_old and col_idx_new):
            st.warning("Veuillez remplir tous les champs et joindre les deux fichiers.")
            st.stop()

        try:
            df_codes = read_any(codes_file)
            df_map   = read_any(map_file)
        except Exception as e:
            st.error(f"Erreur de lecture : {e}")
            st.stop()

        # ---- extraction codes ----
        try:
            raw_codes = df_codes.iloc[:, col_idx_codes-1].dropna().astype(str).str.strip()
        except IndexError:
            st.error("Indice colonne codes hors plage.")
            st.stop()

        sanitized = raw_codes.apply(sanitize_code)
        invalid   = sanitized.isna()
        if invalid.any():
            st.error(f"{invalid.sum()} code(s) produit invalides :")
            st.dataframe(raw_codes[invalid].to_frame("Code fourni"))
            st.stop()

        # ---- préparation mapping ----
        try:
            old_codes = df_map.iloc[:, col_idx_old-1].astype(str).apply(sanitize_code)
            new_codes = df_map.iloc[:, col_idx_new-1].astype(str).apply(sanitize_code)
        except IndexError:
            st.error("Indice colonne mapping hors plage.")
            st.stop()

        map_df = pd.DataFrame({"old": old_codes, "new": new_codes}).dropna()
        if map_df.empty:
            st.error("Table de correspondance vide ou invalide.")
            st.stop()

        # dict mapping (ancien → nouveau), priorité à la première occurrence
        mapping = (map_df.drop_duplicates("old").set_index("old")['new']).to_dict()

        # ---- application mapping ----
        updated_codes = sanitized.map(lambda c: mapping.get(c, c))
        changed_mask  = updated_codes != sanitized
        not_found     = (~sanitized.isna()) & (~sanitized.isin(mapping.keys()))

        # ---- feedback utilisateur ----
        st.success("Mise à jour terminée :")
        st.write(f"• {changed_mask.sum()} code(s) remplacé(s)")
        st.write(f"• {not_found.sum()} code(s) sans correspondance → conservés tels quels")

        if changed_mask.any():
            diff_df = pd.DataFrame({
                "Ancien": sanitized[changed_mask].values,
                "Nouveau": updated_codes[changed_mask].values,
            })
            st.expander("Voir la liste des codes mis à jour").dataframe(diff_df)

        # ---- génération fichiers (identique à page 1) ----
        dstr = today_yyMMdd()
        df1 = pd.DataFrame({
            0: [f"PC_PROFILE_{entreprise}"] * len(updated_codes),
            1: [statut] * len(updated_codes),
            2: [None] * len(updated_codes),
            3: [f"M2_{c}" for c in updated_codes],
            4: ["frxProductCatallog:Online"] * len(updated_codes),
        }).drop_duplicates()

        st.download_button(
            f"📥 DFRXHYBRPCP{dstr}0000",
            df1.to_csv(sep=";", index=False, header=False),
            file_name=f"DFRXHYBRPCP{dstr}0000",
            mime="text/plain",
        )

        ack_cmp = f"DFRXHYBRCMP{dstr}000068240530ITDFRXHYBRCMP{dstr}CCMGHYBFRX                    OK000000"
        st.download_button(
            f"📥 ACK CMP",
            ack_cmp,
            file_name=f"AFRXHYBRCMP{dstr}0000",
            mime="text/plain",
        )

        cmp_content = f"PC_{entreprise};PC_{entreprise};PC_PROFILE_{entreprise};(MAPPING);frxProductCatalog:Online"
        st.download_button(
            f"📥 DFRXHYBRCMP{dstr}0000",
            cmp_content,
            file_name=f"DFRXHYBRCMP{dstr}0000",
            mime="text/plain",
        )

        ack_pcp = f"DFRXHYBRPCP{dstr}000068200117ITDFRXHYBRPCP{dstr}RCMRHYBFRX                    OK000000"
        st.download_button(
            f"📥 ACK PCP",
            ack_pcp,
            file_name=f"AFRXHYBRPCP{dstr}0000",
            mime="text/plain",
        )
