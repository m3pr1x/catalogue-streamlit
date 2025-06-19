import pandas as pd
from datetime import datetime
import streamlit as st

# ─────────────────────────────── PAGE ───────────────────────────────
st.set_page_config(page_title="Générateur DFRX / AFRX", page_icon="🛠️")
st.title("🛠️ Outil Personal Catalogue")
st.markdown("Déposez vos fichiers **codes produit** et **numéros de compte** (CSV / Excel).")

# ───────────────────────────── UPLOADS + COLONNE IDX ────────────────
# Chaque sélecteur d’indice n’apparaît qu’une fois le fichier déposé
# et se situe immédiatement sous la zone *drag‑&‑drop* correspondante.

with st.container():
    codes_file = st.file_uploader("📄 Codes produit", type=("csv", "xlsx", "xls"))
    if codes_file is not None:
        col_idx_codes = st.number_input(
            "🔢 Numéro de colonne des codes (1 = première, 2 = deuxième, …)",
            min_value=1, value=1, key="codes_col_idx",
        )
    else:
        col_idx_codes = None

with st.container():
    compte_file = st.file_uploader("📄 Numéros de compte", type=("csv", "xlsx", "xls"))
    if compte_file is not None:
        col_idx_comptes = st.number_input(
            "🔢 Numéro de colonne des comptes (1 = première, 2 = deuxième, …)",
            min_value=1, value=1, key="compte_col_idx",
        )
    else:
        col_idx_comptes = None

# ───────────────────────────── AUTRES PARAMÈTRES ────────────────────
entreprise = st.text_input("🏢 Entreprise", placeholder="DALKIA / EIFFAGE / ITEC…")
statut     = st.selectbox("📌 Statut", ["", "INCLUDE", "EXCLUDE"])

# ───────────────────────────── UTILS ────────────────────────────────

def read_any(file):
    """Lit CSV ou Excel en gérant les encodages courants et ne lit que le 1ᵉʳ onglet."""
    name = file.name.lower()
    if name.endswith(".csv"):
        for enc in ("utf-8", "latin1", "cp1252"):
            try:
                return pd.read_csv(file, encoding=enc)
            except UnicodeDecodeError:
                file.seek(0)  # remet le curseur au début
        raise ValueError("Encodage CSV non reconnu")
    else:
        return pd.read_excel(file, engine="openpyxl")

def today_yyMMdd() -> str:
    return datetime.today().strftime("%y%m%d")

# ───────────────────────────── TRAITEMENT ───────────────────────────

def generate(dataset, comptes, col_code, col_compte, ent, stat):
    dstr = today_yyMMdd()

    # 1. Extraction des codes produit
    try:
        codes = (
            dataset.iloc[:, col_code - 1]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )
    except IndexError:
        st.error("❌ Colonne (codes) hors plage.")
        return
    if not codes:
        st.error("❌ Aucun code produit trouvé.")
        return

    # 2. Extraction des numéros de compte
    try:
        comptes_list = (
            comptes.iloc[:, col_compte - 1]
            .dropna()
            .astype(str)
            .str.strip()
            .tolist()
        )
    except IndexError:
        st.error("❌ Colonne (comptes) hors plage.")
        return
    if not comptes_list:
        st.error("❌ Aucun numéro de compte trouvé.")
        return

    # 3. Fichier 1 – DFRXHYBRPCP
    df1 = pd.DataFrame(
        {
            0: [f"PC_PROFILE_{ent}"] * len(codes),
            1: [stat] * len(codes),
            2: [None] * len(codes),
            3: [f"M2_{str(c)[:6]}" for c in codes],
            4: ["frxProductCatallog:Online"] * len(codes),
        }
    )

    df1 = df1.drop_duplicates(keep="first")  # dé-doublonnage

    data_pcp = df1.to_csv(sep=";", index=False, header=False)

    st.download_button(
        label=f"📥 DFRXHYBRPCP{dstr}0000",
        data=data_pcp,
        file_name=f"DFRXHYBRPCP{dstr}0000",
        mime="text/plain",
    )

    # 4. Fichier 2 – AFRXHYBRCMP (acknowledgement)
    ack_cmp = (
        f"DFRXHYBRCMP{dstr}000068240530IT" f"DFRXHYBRCMP{dstr}CCMGHYBFRX                    OK000000"
    )

    st.download_button(
        label=f"📥 AFRXHYBRCMP{dstr}0000",
        data=ack_cmp,
        file_name=f"AFRXHYBRCMP{dstr}0000",
        mime="text/plain",
    )

    # 5. Fichier 3 – DFRXHYBRCMP
    contenu_cmp = (
        f"PC_{ent};PC_{ent};PC_PROFILE_{ent};" f"{','.join(comptes_list)};frxProductCatalog:Online"
    )

    st.download_button(
        label=f"📥 DFRXHYBRCMP{dstr}0000",
        data=contenu_cmp,
        file_name=f"DFRXHYBRCMP{dstr}0000",
        mime="text/plain",
    )

    # 6. Fichier 4 – AFRXHYBRPCP (acknowledgement)
    ack_pcp = (
        f"DFRXHYBRPCP{dstr}000068200117IT" f"DFRXHYBRPCP{dstr}RCMRHYBFRX                    OK000000"
    )

    st.download_button(
        label=f"📥 AFRXHYBRPCP{dstr}0000",
        data=ack_pcp,
        file_name=f"AFRXHYBRPCP{dstr}0000",
        mime="text/plain",
    )

# ───────────────────────────── INTERFACE ────────────────────────────
if st.button("🚀 Générer"):
    if not (
        codes_file
        and compte_file
        and entreprise
        and statut
        and col_idx_codes is not None
        and col_idx_comptes is not None
    ):
        st.warning("🛈 Veuillez remplir tous les champs, joindre les deux fichiers et choisir les colonnes.")
    else:
        try:
            df_codes = read_any(codes_file)
            df_comptes = read_any(compte_file)
            generate(
                df_codes,
                df_comptes,
                col_idx_codes,
                col_idx_comptes,
                entreprise,
                statut,
            )
        except Exception as e:
            st.error(f"❌ Erreur : {e}")
