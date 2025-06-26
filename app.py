# -*- coding: utf-8 -*-
"""
app.py – Générateur PC + page « Mise à jour M2 »
Ajout d’un sélecteur dans la barre latérale :
    • “Générateur PC” (écran existant)
    • “Mise à jour M2”  (page encore vide, simple retour possible)
"""

from __future__ import annotations
import pandas as pd
from datetime import datetime
import csv, io
import streamlit as st

# ─────────────────────────────  GLOBALES  ────────────────────────────
st.set_page_config(page_title="Générateur DFRX / AFRX", page_icon="🛠️", layout="wide")

def today_yyMMdd() -> str:
    return datetime.today().strftime("%y%m%d")

def read_any(file):
    name = file.name.lower()
    if name.endswith(".csv"):
        for enc in ("utf-8", "latin1", "cp1252"):
            try:
                return pd.read_csv(file, encoding=enc)
            except UnicodeDecodeError:
                file.seek(0)
        raise ValueError("Encodage CSV non reconnu")
    return pd.read_excel(file, engine="openpyxl")

# ───────────────────────  SIDEBAR NAVIGATION  ────────────────────────
page = st.sidebar.radio("Navigation", ["Générateur PC", "Mise à jour M2"])

# ═══════════════════════  PAGE 1 – GÉNÉRATEUR  ═══════════════════════
if page == "Générateur PC":
    st.title("🛠️ Outil Personal Catalogue")
    st.markdown("Déposez vos fichiers **codes produit** et **numéros de compte** (CSV / Excel).")

    # ------- uploads + index -------
    with st.container():
        codes_file = st.file_uploader("📄 Codes produit", type=("csv", "xlsx", "xls"))
        col_idx_codes = (
            st.number_input("🔢 Colonne codes (1=A)", 1, 50, 1, key="codes_col")
            if codes_file else None
        )

    with st.container():
        compte_file = st.file_uploader("📄 Numéros de compte", type=("csv", "xlsx", "xls"))
        col_idx_comptes = (
            st.number_input("🔢 Colonne comptes (1=A)", 1, 50, 1, key="comptes_col")
            if compte_file else None
        )

    entreprise = st.text_input("🏢 Entreprise")
    statut     = st.selectbox("📌 Statut", ["", "INCLUDE", "EXCLUDE"])

    # ------- génération fichiers -------
    if st.button("🚀 Générer"):
        if not (codes_file and compte_file and entreprise and statut
                and col_idx_codes and col_idx_comptes):
            st.warning("Remplir tous les champs + joindre les 2 fichiers.")
            st.stop()
        try:
            df_codes   = read_any(codes_file)
            df_comptes = read_any(compte_file)
        except Exception as e:
            st.error(f"❌ Erreur lecture : {e}")
            st.stop()

        # extraction & contrôles
        try:
            codes = (df_codes.iloc[:, col_idx_codes-1].dropna().astype(str).str.strip())
            comptes = (df_comptes.iloc[:, col_idx_comptes-1].dropna().astype(str).str.strip())
        except IndexError:
            st.error("❌ Indice de colonne hors plage."); st.stop()

        if codes.empty or comptes.empty:
            st.error("❌ Aucune donnée trouvée."); st.stop()

        dstr = today_yyMMdd()

        # Fichier 1 DFRXHYBRPCP
        df1 = pd.DataFrame({
            0: [f"PC_PROFILE_{entreprise}"] * len(codes),
            1: [statut] * len(codes),
            2: [None] * len(codes),
            3: [f"M2_{c[:6]}" for c in codes],
            4: ["frxProductCatallog:Online"] * len(codes)
        }).drop_duplicates()

        st.download_button(f"📥 DFRXHYBRPCP{dstr}0000",
                           df1.to_csv(sep=";", index=False, header=False),
                           file_name=f"DFRXHYBRPCP{dstr}0000", mime="text/plain")

        # Fichier 2 ACK CMP
        ack_cmp = f"DFRXHYBRCMP{dstr}000068240530ITDFRXHYBRCMP{dstr}CCMGHYBFRX                    OK000000"
        st.download_button(f"📥 AFRXHYBRCMP{dstr}0000", ack_cmp,
                           file_name=f"AFRXHYBRCMP{dstr}0000", mime="text/plain")

        # Fichier 3 DFRXHYBRCMP
        cmp_content = f"PC_{entreprise};PC_{entreprise};PC_PROFILE_{entreprise};{','.join(comptes)};frxProductCatalog:Online"

        st.download_button(f"📥 DFRXHYBRCMP{dstr}0000", cmp_content,
                           file_name=f"DFRXHYBRCMP{dstr}0000", mime="text/plain")

        # Fichier 4 ACK PCP
        ack_pcp = f"DFRXHYBRPCP{dstr}000068200117ITDFRXHYBRPCP{dstr}RCMRHYBFRX                    OK000000"
        st.download_button(f"📥 AFRXHYBRPCP{dstr}0000", ack_pcp,
                           file_name=f"AFRXHYBRPCP{dstr}0000", mime="text/plain")

# ═══════════════════════  PAGE 2 – MISE À JOUR M2  ═══════════════════
else:
    st.title("🔄 Mise à jour M2")
    st.info("Page en cours de construction.\n\nUtilisez la barre latérale pour retourner au générateur PC.")
