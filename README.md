# RisqBar v4 — Validation externe

> **À destination des équipes cliniques ou de recherche souhaitant valider le modèle RisqBar v4 sur une cohorte indépendante.**
>
> Ce dépôt contient le script officiel de validation externe du score de risque bariatrique préopératoire RisqBar v4, développé par l'équipe HEKA (INRIA / PariSanté Campus).

---

## Contexte scientifique

RisqBar v4 est un modèle de prédiction du risque de **complication grave (Clavien ≥ III) à 90 jours** après chirurgie bariatrique (sleeve gastrectomie + bypass gastrique).

| Caractéristique | Valeur |
|---|---|
| Modèle | Elastic Net (régression logistique pénalisée L1+L2) |
| Calibration | Platt Scaling |
| Cohorte de développement | 182 916 patients — PMSI France 2020–2025 |
| Outcome | Clavien ≥ III à 90 jours (prévalence 4.2 %) |
| AUC (bootstrap corrigé) | 0.677 |
| Score de Brier calibré | 0.039 |
| Pente de calibration | 0.922 |
| Variables préopératoires | 13 (dont 1 terme d'interaction) |

**Objectif de la validation externe :** vérifier que les performances du modèle se maintiennent sur une cohorte indépendante (autre hôpital, autre registre, autre période).

---

## Ce que vous devez faire — en 4 étapes

### Étape 1 — Récupérer le script (2 minutes)

```bash
git clone https://github.com/iz235/risqbar-validation-externe.git
cd risqbar-validation-externe
```

Si vous n'avez pas Git : téléchargez le ZIP depuis GitHub (bouton **Code → Download ZIP**), puis décompressez.

---

### Étape 2 — Installer Python et les dépendances (5 minutes)

**Vérifier si Python est déjà installé :**
```bash
python --version
```
Si la commande renvoie `Python 3.x.x` (x ≥ 9), passez à la suite.
Sinon, téléchargez Python sur [python.org/downloads](https://www.python.org/downloads/) (version 3.11 recommandée).

**Installer les dépendances :**
```bash
pip install -r requirements.txt
```

---

### Étape 3 — Préparer votre fichier de données

Votre fichier doit être au format **CSV** (`.csv`) avec les colonnes suivantes :

| Colonne | Description | Valeurs autorisées |
|---|---|---|
| `age_cat` | Tranche d'âge | `0` (18–30 ans), `1` (30–40), `2` (40–50), `3` (50–60), `4` (>60) |
| `BMI_ord` | IMC préopératoire | `1` (<40 kg/m²), `2` (40–50), `3` (>50) |
| `diab_cat` | Statut diabétique | `0` (absent), `1` (simple), `2` (avec complications) |
| `sexe_bin` | Sexe | `1` (Femme), `0` (Homme) |
| `baria_t_BPG` | Type de chirurgie | `1` (Bypass), `0` (Sleeve) |
| `ord_baria_bin` | Reprise bariatrique | `1` (Reprise ≥ 2e interv.), `0` (Primaire) |
| `hta` | Hypertension artérielle | `1` (Oui), `0` (Non) |
| `osas_elix` | Syndrome d'apnée du sommeil | `1` (Oui), `0` (Non) |
| `dyslipidemia` | Dyslipidémie | `1` (Oui), `0` (Non) |
| `cong_heart_elix` | Cardiopathie congénitale | `1` (Oui), `0` (Non) |
| `alcohol_elix` | Dépendance à l'alcool | `1` (Oui), `0` (Non) |
| `neuro_elix` | Troubles neurologiques | `1` (Oui), `0` (Non) |
| `clavien_bin` | **Outcome** — complication Clavien ≥ III à 90 j | `1` (Oui), `0` (Non) |

> **Important :**
> - Séparateur : virgule `,` ou point-virgule `;` (détecté automatiquement)
> - Valeurs manquantes : les lignes incomplètes sont exclues automatiquement
> - La 13e variable `reprise_sleeve` est **calculée automatiquement** par le script — ne pas l'inclure
> - Inclure **uniquement** les patients sleeve gastrectomie (SLE) et bypass gastrique (BPG) — exclure les anneaux et autres procédures

**Voir un exemple de fichier :** `exemple_donnees/exemple_format.csv`

---

### Étape 4 — Lancer le script de validation

**Test avec les données exemple (avant vos vraies données) :**
```bash
python validate.py --data exemple_donnees/exemple_format.csv --institution "Test"
```

**Avec vos données réelles :**
```bash
python validate.py --data votre_fichier.csv --institution "CHU Lyon"
```

Remplacez `votre_fichier.csv` par le chemin vers votre fichier, et `"CHU Lyon"` par le nom de votre institution.

---

### Étape 5 — Retourner le rapport

Le script génère automatiquement un fichier **`validation_report.txt`** dans le dossier courant.

**Ce fichier contient uniquement des métriques agrégées — aucune donnée patient individuelle.**

Retournez ce fichier par email à :
- **Izadine Massar** — massarizzadinealkhali@gmail.com
- **Pr. Andrea LAZZATI** — INRIA / Équipe HEKA / PariSanté Campus

---

## Exemple de rapport généré

```
==============================================================
  RAPPORT DE VALIDATION EXTERNE — RisqBar v4
  Score de risque bariatrique preoperatoire
  Elastic Net v4 + Platt Scaling
==============================================================

  Institution : CHU Lyon
  Date        : 21/07/2026 14:30
  Script      : validate.py (github.com/iz235/risqbar-validation-externe)

--------------------------------------------------------------
  COHORTE
--------------------------------------------------------------
  N patients total          : 4 521
  N evenements Clavien>=III : 198
  Prevalence                : 4.38%
  N exclus (NA)             : 12

--------------------------------------------------------------
  DISCRIMINATION
--------------------------------------------------------------
  AUC-ROC    : 0.661  [IC95% : 0.632 - 0.690]
  (Ref. article : 0.674  [bootstrap B=200])

--------------------------------------------------------------
  CALIBRATION
--------------------------------------------------------------
  Score de Brier       : 0.041
  (Ref. article        : 0.039)
  Pente de calibration : 0.891  (ideal = 1.0)
  (Ref. article        : 0.922)
  Intercept            : -0.041  (ideal = 0.0)

--------------------------------------------------------------
  STRATIFICATION EN 4 GROUPES DE RISQUE
--------------------------------------------------------------
  Faible (<3%)
    N = 2 205 (48.8%)  |  Clavien obs. = 2.18%  [IC95%: 1.65%-2.85%]
    (Ref. article : 51.6% cohorte, taux 2.33%)

  Modere (3-6%)
    N = 1 389 (30.7%)  |  Clavien obs. = 4.53%  [IC95%: 3.60%-5.67%]
    (Ref. article : 28.9% cohorte, taux 4.26%)

  Eleve (6-9%)
    N = 521 (11.5%)    |  Clavien obs. = 7.87%  [IC95%: 5.82%-10.53%]
    (Ref. article : 11.5% cohorte, taux 7.54%)

  Tres eleve (>=9%)
    N = 406 (9.0%)     |  Clavien obs. = 10.84%  [IC95%: 7.99%-14.50%]
    (Ref. article : 8.0% cohorte, taux 11.25%)
==============================================================
```

---

## Confidentialité des données

Le script fonctionne **entièrement en local** sur vos machines.

- Aucune donnée patient n'est transmise à l'extérieur
- Le rapport `validation_report.txt` ne contient que des métriques agrégées
- Aucun identifiant patient n'apparaît dans le rapport

La démarche est conforme au principe de **validation externe distribuée** : le modèle voyage vers les données, les données ne voyagent pas vers le modèle.

---

## Problèmes fréquents

| Erreur | Cause | Solution |
|---|---|---|
| `Colonnes manquantes` | Nom de colonne incorrect | Vérifier les noms exactement (minuscules, underscores) |
| `ModuleNotFoundError` | Dépendances non installées | Relancer `pip install -r requirements.txt` |
| `N < 100 patients` | Cohorte trop petite | Les métriques seront peu fiables — le mentionner dans le rapport |
| `Prévalence < 1%` | Outcome rare ou mal codé | Vérifier le codage de `clavien_bin` |
| Séparateur CSV non reconnu | Mauvais séparateur | Ouvrir le CSV dans un éditeur, vérifier si `,` ou `;` |

---

## Structure du dépôt

```
risqbar-validation-externe/
├── validate.py                    ← Script principal (à lancer)
├── requirements.txt               ← Dépendances Python
├── README.md                      ← Ce fichier
├── exemple_donnees/
│   └── exemple_format.csv         ← Données fictives pour tester
└── models/                        ← Modèle RisqBar v4 (ne pas modifier)
    ├── etape7_en_pipeline.joblib
    ├── etape7_platt.json
    ├── etape7_features.json
    ├── etape7_percentiles.json
    └── etape7_risk_distribution.json
```

---

## Contact

**Izadine Massar**
Stagiaire ING5-ITS — EPISEN / UPEC
INRIA — Équipe HEKA — PariSanté Campus
massarizzadinealkhali@gmail.com

**Pr. Andrea LAZZATI**
Chirurgien bariatrique — Chercheur associé HEKA
INRIA / AP-HP — PariSanté Campus, Paris
