"""
validate.py — Script de validation externe RisqBar v4
======================================================
Usage :
    python validate.py --data votre_fichier.csv --institution "CHU Lyon"

Ce script applique le modèle RisqBar v4 sur vos données et génère
un rapport de validation (validation_report.txt) à retourner aux auteurs.

AUCUNE donnee patient n'est incluse dans le rapport genere.
"""

import argparse
import json
import sys
import os
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from scipy.special import expit, logit
from scipy import stats
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")

# ── Chemins ────────────────────────────────────────────────────
MODELS_DIR = Path(__file__).parent / "models"

# ── Variables requises dans le CSV ─────────────────────────────
VARIABLES_REQUISES = [
    "age_cat",          # 0=18-30, 1=30-40, 2=40-50, 3=50-60, 4=>60 ans
    "BMI_ord",          # 1=<40, 2=40-50, 3=>50 kg/m2
    "diab_cat",         # 0=absent, 1=simple, 2=avec complications
    "sexe_bin",         # 1=Femme, 0=Homme
    "baria_t_BPG",      # 1=Bypass, 0=Sleeve
    "ord_baria_bin",    # 1=Reprise, 0=Primaire
    "hta",              # 1=Oui, 0=Non
    "osas_elix",        # 1=Oui, 0=Non
    "dyslipidemia",     # 1=Oui, 0=Non
    "cong_heart_elix",  # 1=Oui, 0=Non
    "alcohol_elix",     # 1=Oui, 0=Non
    "neuro_elix",       # 1=Oui, 0=Non
    "clavien_bin",      # OUTCOME : 1=Clavien>=III, 0=pas de complication
]


def charger_modele():
    """Charge les 5 fichiers du modele RisqBar v4."""
    print("  Chargement du modele...", end=" ")
    pipe  = joblib.load(MODELS_DIR / "etape7_en_pipeline.joblib")
    platt = json.load(open(MODELS_DIR / "etape7_platt.json"))
    feats = json.load(open(MODELS_DIR / "etape7_features.json"))
    # Correctif compatibilite scikit-learn
    clf = pipe.named_steps["clf"]
    if not hasattr(clf, "multi_class"):
        clf.multi_class = "auto"
    print("OK")
    return pipe, platt, feats


def predict_proba_calibree(df, pipe, platt, feats):
    """Applique le modele et la calibration Platt Scaling."""
    X = df[feats].values.astype(float)
    p_raw = pipe.predict_proba(X)[:, 1]
    lp = np.clip(p_raw, 1e-7, 1 - 1e-7)
    lp = np.log(lp / (1 - lp))
    return expit(platt["a"] * lp + platt["b"])


def ic95_proportion(n_success, n_total):
    """Intervalle de confiance 95% Wilson pour une proportion."""
    if n_total == 0:
        return 0.0, 0.0
    p = n_success / n_total
    z = 1.96
    denom = 1 + z**2 / n_total
    centre = (p + z**2 / (2 * n_total)) / denom
    delta  = z * np.sqrt(p * (1 - p) / n_total + z**2 / (4 * n_total**2)) / denom
    return max(0, centre - delta), min(1, centre + delta)


def ic95_auc_bootstrap(y_true, y_score, n_boot=1000, seed=42):
    """IC 95% AUC par bootstrap (B=1000)."""
    rng = np.random.default_rng(seed)
    aucs = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y_true), len(y_true))
        if y_true[idx].sum() == 0 or y_true[idx].sum() == len(idx):
            continue
        aucs.append(roc_auc_score(y_true[idx], y_score[idx]))
    return np.percentile(aucs, [2.5, 97.5])


def calibration_slope_intercept(y_true, y_prob):
    """Pente et intercept de calibration (regression logistique sur logit)."""
    lp = np.log(np.clip(y_prob, 1e-7, 1 - 1e-7) / (1 - np.clip(y_prob, 1e-7, 1 - 1e-7)))
    lr = LogisticRegression(fit_intercept=True, max_iter=1000)
    lr.fit(lp.reshape(-1, 1), y_true)
    return float(lr.coef_[0][0]), float(lr.intercept_[0])


def valider(args):
    print("\n" + "="*62)
    print("  VALIDATION EXTERNE — RisqBar v4")
    print("="*62)

    # ── 1. Charger le modele ────────────────────────────────────
    pipe, platt, feats = charger_modele()

    # ── 2. Lire les donnees ─────────────────────────────────────
    print(f"  Lecture des donnees : {args.data}", end=" ")
    try:
        df = pd.read_csv(args.data, sep=None, engine="python")
    except Exception as e:
        print(f"\n  ERREUR lecture CSV : {e}")
        sys.exit(1)
    print(f"OK  ({len(df)} lignes, {len(df.columns)} colonnes)")

    # ── 3. Verifier les colonnes ────────────────────────────────
    manquantes = [c for c in VARIABLES_REQUISES if c not in df.columns]
    if manquantes:
        print("\n  ERREUR — Colonnes manquantes dans votre fichier :")
        for c in manquantes:
            print(f"    - {c}")
        print("\n  Consultez exemple_donnees/exemple_format.csv pour le format attendu.")
        sys.exit(1)

    # ── 4. Supprimer les lignes avec valeurs manquantes ─────────
    n_initial = len(df)
    df = df.dropna(subset=VARIABLES_REQUISES)
    n_apres = len(df)
    n_exclus = n_initial - n_apres
    if n_exclus > 0:
        print(f"  Attention : {n_exclus} lignes exclues (valeurs manquantes)")

    # ── 5. Calculer la variable d'interaction ───────────────────
    df["reprise_sleeve"] = (
        df["ord_baria_bin"].astype(int) *
        (1 - df["baria_t_BPG"].astype(int))
    ).astype(float)

    y_true  = df["clavien_bin"].values.astype(int)
    n_total = len(y_true)
    n_event = int(y_true.sum())
    prev    = n_event / n_total

    print(f"  N patients  : {n_total:,}")
    print(f"  N evenements: {n_event:,} ({prev*100:.2f}%)")

    if n_event < 10:
        print("\n  ATTENTION : moins de 10 evenements — les metriques seront peu fiables.")

    # ── 6. Predictions ──────────────────────────────────────────
    print("  Calcul des probabilites...", end=" ")
    y_prob = predict_proba_calibree(df, pipe, platt, feats)
    print("OK")

    # ── 7. Metriques ────────────────────────────────────────────
    print("  Calcul des metriques...", end=" ")

    auc   = roc_auc_score(y_true, y_prob)
    auc_ic = ic95_auc_bootstrap(y_true, y_prob)
    brier = brier_score_loss(y_true, y_prob)
    slope, intercept = calibration_slope_intercept(y_true, y_prob)

    # 4 groupes
    groupes = {
        "Faible (<3%)"      : (y_prob < 0.03),
        "Modere (3-6%)"     : ((y_prob >= 0.03) & (y_prob < 0.06)),
        "Eleve (6-9%)"      : ((y_prob >= 0.06) & (y_prob < 0.09)),
        "Tres eleve (>=9%)" : (y_prob >= 0.09),
    }
    stats_groupes = {}
    for nom, masque in groupes.items():
        n_g   = masque.sum()
        ev_g  = y_true[masque].sum()
        taux  = ev_g / n_g if n_g > 0 else 0
        ic_lo, ic_hi = ic95_proportion(ev_g, n_g)
        stats_groupes[nom] = (n_g, ev_g, taux, ic_lo, ic_hi)

    print("OK")

    # ── 8. Rapport ──────────────────────────────────────────────
    institution = args.institution if args.institution else "Non renseignee"
    date_rapport = datetime.now().strftime("%d/%m/%Y %H:%M")

    lignes = [
        "=" * 62,
        "  RAPPORT DE VALIDATION EXTERNE — RisqBar v4",
        "  Score de risque bariatrique preoperatoire",
        "  Elastic Net v4 + Platt Scaling",
        "=" * 62,
        "",
        f"  Institution : {institution}",
        f"  Date        : {date_rapport}",
        f"  Script      : validate.py (github.com/iz235/risqbar-validation-externe)",
        "",
        "-" * 62,
        "  COHORTE",
        "-" * 62,
        f"  N patients total     : {n_total:,}",
        f"  N evenements Clavien>=III : {n_event:,}",
        f"  Prevalence           : {prev*100:.2f}%",
        f"  N exclus (NA)        : {n_exclus:,}",
        "",
        "-" * 62,
        "  DISCRIMINATION",
        "-" * 62,
        f"  AUC-ROC              : {auc:.3f}  [IC95% : {auc_ic[0]:.3f} - {auc_ic[1]:.3f}]",
        f"  (Ref. article        : 0.674  [bootstrap B=200])",
        "",
        "-" * 62,
        "  CALIBRATION",
        "-" * 62,
        f"  Score de Brier       : {brier:.4f}",
        f"  (Ref. article        : 0.039)",
        f"  Pente de calibration : {slope:.3f}  (ideal = 1.0)",
        f"  (Ref. article        : 0.922)",
        f"  Intercept            : {intercept:.3f}  (ideal = 0.0)",
        "",
        "-" * 62,
        "  STRATIFICATION EN 4 GROUPES DE RISQUE",
        "-" * 62,
    ]

    ref_taux = {
        "Faible (<3%)"      : (51.6, 2.33),
        "Modere (3-6%)"     : (28.9, 4.26),
        "Eleve (6-9%)"      : (11.5, 7.54),
        "Tres eleve (>=9%)" : (8.0,  11.25),
    }

    for nom, (n_g, ev_g, taux, ic_lo, ic_hi) in stats_groupes.items():
        pct_g   = n_g / n_total * 100 if n_total > 0 else 0
        ref_p, ref_t = ref_taux[nom]
        lignes += [
            f"  {nom}",
            f"    N = {n_g:,} ({pct_g:.1f}%)  |  Clavien obs. = {taux*100:.2f}%  [IC95%: {ic_lo*100:.2f}%-{ic_hi*100:.2f}%]",
            f"    (Ref. article : {ref_p:.1f}% cohorte, taux {ref_t:.2f}%)",
            "",
        ]

    lignes += [
        "=" * 62,
        "  INSTRUCTIONS",
        "=" * 62,
        "  Ce fichier est a retourner aux auteurs par email.",
        "  AUCUNE donnee patient n'est incluse dans ce rapport.",
        "  Seules les metriques agregees sont presentees.",
        "",
        "  Contact : Izadine Massar — massarizzadinealkhali@gmail.com",
        "            Pr. Andrea LAZZATI — INRIA / Equipe HEKA",
        "=" * 62,
    ]

    rapport = "\n".join(lignes)

    # Sauvegarder
    output_path = Path("validation_report.txt")
    output_path.write_text(rapport, encoding="utf-8")

    print("\n" + rapport)
    print(f"\n  Rapport sauvegarde : {output_path.resolve()}")
    print("  --> Retournez ce fichier aux auteurs par email.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validation externe RisqBar v4 — Script officiel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python validate.py --data mon_fichier.csv
  python validate.py --data mon_fichier.csv --institution "CHU Lyon"
  python validate.py --data mon_fichier.csv --institution "CHRU Lille"

Format du fichier CSV :
  - Separateur : virgule (,) ou point-virgule (;) detecte automatiquement
  - Colonnes requises : voir README.md section 'Format des donnees'
  - Tester d'abord avec : python validate.py --data exemple_donnees/exemple_format.csv
        """
    )
    parser.add_argument(
        "--data",
        required=True,
        help="Chemin vers votre fichier CSV de donnees patients"
    )
    parser.add_argument(
        "--institution",
        default="",
        help='Nom de votre institution (ex: "CHU Lyon")'
    )
    args = parser.parse_args()
    valider(args)
