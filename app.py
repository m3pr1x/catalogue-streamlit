# -*- coding: utf-8 -*-
"""
app.py – Générateur PC + page « Mise à jour M2 »
------------------------------------------------
• **Générateur PC** : identique à l’outil existant (contrôle des codes + 4
  fichiers de sortie).
• **Mise à jour M2**  : identique au Générateur mais les codes passent d’abord
  par une table de correspondance *M2_ancien → M2_nouveau*.

Nouveautés globales
===================
- Contrôle des codes M2 (6 chiffres) sur les deux pages.
- Lecture CSV/Excel robuste (séparateur + encodages).
- Dans « Mise à jour », on charge désormais **aussi** le fichier « Numéros de
  compte » (comme sur la page Générateur).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import io
import pandas as pd
import streamlit as st

# ─────────────────────────────  CONFIG  ─────────────────────────────
st.set_page_config(page_title="Générateur DFRX / AFRX", page_icon="🛠️", layout="wide")

# ───────────────────────────  OUTILS I/O  ───────────────────────────

def today_yyMMdd() -> str:
    return datetime.today().strftime("%y%m%d")


def read_csv(buf: io.BytesIO) -> pd.DataFrame:
    for enc in ("utf-8", "latin1", "cp1252"):
        buf.seek(0)
        try:
            sample = buf.read(2048).decode(enc, errors="ignore")
            sep = csv.Sniffer().sniff(sample, delimiters=";,|\t").delimiter
            buf.seek(0)
            return pd.read_csv(buf, sep=sep, encoding=enc, engine="python", on_bad_lines="skip")
        except (UnicodeDecodeError, csv.Error, pd.errors.ParserError):
            continue
    raise ValueError("CSV illisible (encodage ou séparateur)")


def read_any(file) -> pd.DataFrame:
    suffix = Path(file.name.lower()).suffix
    if suffix == ".csv":
        return read_csv(io.BytesIO(file.getvalue()))
    if suffix in {".xlsx", ".xls"}:
        file.seek(0)
        engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
        return pd.read_excel(file, engine=engine)
    raise ValueError(f"Extension non gérée : {suffix}")


def sanitize_code(code: str) -> str | None:
    s = str(code).strip()
    if not s.isdigit():
        return None
    if len(s) == 5:
        s = s.zfill(6)
    if len(s) != 6:
        return None
    return s

# ─────────────────────────────  NAVIGATION  ─────────────────────────────
page = st.sidebar.radio("Navigation", ["Générateur PC", "Mise à jour M2"])

# ═══════════════════════════  PAGE 1 – GÉNÉRATEUR  ════════════════════════
if page == "Générateur PC":
    st.title("🛠️ Outil Personal Catalogue")
    st.markdown("Déposez vos fichiers **codes produit** et **numéros de compte** (CSV / Excel).")

    codes_file = st.file_uploader("📄 Codes produit", type=("csv", "xlsx", "xls"))
    col_idx_codes = st.number_input("🔢 Colonne Codes M2", 1, 50, 1) if codes_file else None

    compte_file = st.file_uploader("📄 Numéros de compte", type=("csv", "xlsx", "xls"))
    col_idx_comptes = st.number_input("🔢 Colonne comptes (1=A)", 1, 50, 1) if compte_file else None

    entreprise = st.text_input("🏢 Entreprise")
    statut     = st.selectbox("📌 Statut", ["", "INCLUDE", "EXCLUDE"])

    if st.button("🚀 Générer"):
        if not all([codes_file, compte_file, entreprise, statut, col_idx_codes, col_idx_comptes]):
            st.warning("Remplir tous les champs et joindre les 2 fichiers.")
            st.stop()

        try:
            df_codes   = read_any(codes_file)
            df_comptes = read_any(compte_file)
        except Exception as e:
            st.error(f"Erreur lecture : {e}")
            st.stop()

        try:
            raw_codes = df_codes.iloc[:, col_idx_codes-1].dropna().astype(str).str.strip()
            comptes   = df_comptes.iloc[:, col_idx_comptes-1].dropna().astype(str).str.strip()
        except IndexError:
            st.error("Indice colonne hors plage.")
            st.stop()

        sanitized = raw_codes.apply(sanitize_code)
        if sanitized.isna().any():
            st.error("Codes M2 invalides détectés.")
            st.dataframe(raw_codes[sanitized.isna()].to_frame("Code fourni"))
            st.stop()

        codes = sanitized
        dstr  = today_yyMMdd()

        df1 = pd.DataFrame({
            0: [f"PC_PROFILE_{entreprise}"] * len(codes),
            1: [statut] * len(codes),
            2: [None] * len(codes),
            3: [f"M2_{c}" for c in codes],
            4: ["frxProductCatallog:Online"] * len(codes),
        }).drop_duplicates()

        st.download_button(
            f"📥 DFRXHYBRPCP{dstr}0000",
            df1.to_csv(sep=";", index=False, header=False),
            file_name=f"DFRXHYBRPCP{dstr}0000",
            mime="text/plain",
        )

        ack_cmp = f"DFRXHYBRCMP{dstr}000068240530ITDFRXHYBRCMP{dstr}CCMGHYBFRX                    OK000000"
        st.download_button("📥 ACK CMP", ack_cmp, file_name=f"AFRXHYBRCMP{dstr}0000", mime="text/plain")

        cmp_content = f"PC_{entreprise};PC_{entreprise};PC_PROFILE_{entreprise};{','.join(comptes)};frxProductCatalog:Online"
        st.download_button("📥 DFRXHYBRCMP{dstr}0000", cmp_content, file_name=f"DFRXHYBRCMP{dstr}0000", mime="text/plain")

        ack_pcp = f"DFRXHYBRPCP{dstr}000068200117ITDFRXHYBRPCP{dstr}RCMRHYBFRX                    OK000000"
        st.download_button("📥 ACK PCP", ack_pcp, file_name=f"AFRXHYBRPCP{dstr}0000", mime="text/plain")

# ═══════════════════════════  PAGE 2 – MISE À JOUR  ═══════════════════════
if page == "Mise à jour M2":
    st.title("🔄 Mise à jour des codes M2")
    st.markdown("Chargez vos fichiers **codes produit**, **numéros de compte** et **M2_MisAJour**. Les codes seront mis à jour avant génération des fichiers.")

    codes_file = st.file_uploader("📄 Codes produit", type=("csv", "xlsx", "xls"))
    col_idx_codes = st.number_input("🔢 Colonne Codes M2", 1, 50, 1, key="maj_codes_col") if codes_file else None

    compte_file = st.file_uploader("📄 Numéros de compte", type=("csv", "xlsx", "xls"))
    col_idx_comptes = st.number_input("🔢 Colonne comptes (1=A)", 1, 50, 1, key="maj_comptes_col") if compte_file else None

    map_file = st.file_uploader("📄 Fichier M2_MisAJour", type=("csv", "xlsx", "xls"))
    if map_file:
        col_idx_old = st.number_input("🔢 Colonne M2 ancien", 1, 50, 1)
        col_idx_new = st.number_input("🔢 Colonne M2 nouveau", 1, 50, 2)
    else:
        col_idx_old = col_idx_new = None

    entreprise = st.text_input("🏢 Entreprise")
    statut     = st.selectbox("📌 Statut", ["", "INCLUDE", "EXCLUDE"])

    if st.button("🚀 Générer MàJ"):
        required = [codes_file, compte_file, map_file, entreprise, statut, col_idx_codes, col_idx_comptes, col_idx_old, col_idx_new]
        if not all(required):
            st.warning("Veuillez remplir tous les champs et joindre les trois fichiers.")
            st.stop()

        try:
            df_codes   = read_any(codes_file)
            df_comptes = read_any(compte_file)
            df_map     = read_any(map_file)
        except Exception as e:
            st.error(f"Erreur lecture : {e}")
            st.stop()

        # ----- extraction codes & comptes -----
        try:
            raw_codes = df_codes.iloc[:, col_idx_codes-1].dropna().astype(str).str.strip()
            comptes   = df_comptes.iloc[:, col_idx_comptes-1].dropna().astype(str).str.strip()
        except IndexError:
            st.error("Indice colonne hors plage.")
            st.stop()

        sanitized = raw_codes.apply(sanitize_code)
        if sanitized.isna().any():
            st.error("Codes M2 invalides détectés.")
            st.dataframe(raw_codes[sanitized.isna()].to_frame("Code fourni"))
            st.stop()

        # ----- mapping -----
        try:
            old_codes = df_map.iloc[:, col_idx_old-1].astype(str).apply(sanitize_code)
            new_codes = df_map.iloc[:, col_idx_new-1].astype(str).apply(sanitize_code)
        except IndexError:
            st.error("Indice colonne mapping hors plage.")
            st.stop()

        map_df = pd.DataFrame({"old": old_codes, "new": new_codes}).dropna()
        mapping = map_df.drop_duplicates("old").set_index("old")["new"].to_dict()

        updated_codes = sanitized.map(lambda c: mapping.get(c, c))
        changed_mask  = updated_codes != sanitized
        not_found     = (~sanitized.isin(mapping.keys()))

        st.success("Mise à jour terminée :")
        st.write(f"• {changed_mask.sum()} code(s) remplacé(s)")
        st.write(f"• {not_found.sum()} code(s) sans correspondance → conservés")

        if changed_mask.any():
            st.expander("Voir détails").dataframe(pd.DataFrame({"Ancien": sanitized[changed_mask].values, "Nouveau": updated_codes[changed_mask].values}))

        # ----- génération fichiers -----
        dstr = today_yyMMdd()
        df1 = pd.DataFrame({
            0: [f"PC_PROFILE_{entreprise}"] * len(updated_codes),
            1: [statut] * len(updated_codes),
            2: [None] * len(updated_codes),
            3: [f"M2_{c}" for c in updated_codes],
            4: ["frxProductCatallog:Online"] * len(updated_codes),
        }).drop_duplicates()

        st.download_button("📥 DFRXHYBRPCP{dstr}0000", df1.to_csv(sep=";", index=False, header=False), file_name=f"DFRXHYBRPCP{dstr}0000", mime="text/plain")

        ack_cmp = f"DFRXHYBRCMP{dstr}000068240530ITDFRXHYBRCMP{dstr}CCMGHYBFRX                    OK000000"
        st.download_button("📥 ACK CMP", ack_cmp, file_name=f"AFRXHYBRCMP{dstr}0000", mime="text/plain")

        cmp_content = f"PC_{entreprise};PC_{entreprise};PC_PROFILE_{entreprise};{','.join(comptes)};frxProductCatalog:Online"
        st.download_button("📥 DFRXHYBRCMP{dstr}0000", cmp_content, file_name=f"DFRXHYBRCMP{dstr}0000", mime="text/plain")

        ack_pcp = f"DFRXHYBRPCP{dstr}000068200117ITDFRXHYBRPCP{dstr}RCMRHYBFRX                    OK000000"
        st.download_button("📥 ACK PCP", ack_pcp, file_name=f"AFRXHYBRPCP{dstr}0000", mime="text/plain")
