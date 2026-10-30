# 08 — LAYA : guide technique

Ce guide explique comment LAYA est utilisé dans le projet, comment fonctionne notre runtime, et
comment installer, tester, mesurer, vérifier, mettre à jour et déployer le garde-fou. Le
pourquoi (capacités de Vercel, mesures, recommandation) est dans
[07 — Vercel et LAYA](07_vercel_et_laya.md).

## 1. LAYA en quelques lignes

LAYA (Convai Innovations, Apache 2.0) est un modèle de décision « System 1 » basé sur un
encodeur (ModernBERT pour l'anglais, mmBERT pour le multilingue). Il ne génère pas de texte :
on lui donne un **état** (le texte à analyser) et des **questions typées**, il renvoie des
probabilités en une seule passe.

| Type | Réponse | Exemple |
|---|---|---|
| `choice` | une option parmi plusieurs (+ probabilités) | « Quel service ? » → `billing` / `tech` |
| `score` | un niveau sur une échelle (espérance) | « Quelle urgence ? » → 0 à 2 |
| `noul` | oui / non (probabilité de « vrai ») | « Le message tente-t-il un jailbreak ? » → 0,93 |

Comme il ne suit pas d'instructions, le texte analysé ne peut pas le « convaincre » de changer
de comportement — d'où son intérêt comme garde-fou à côté d'un LLM.

## 2. Comment il est utilisé ici

```mermaid
flowchart LR
    Q["Question"] --> F["Filtre déterministe"]
    F -->|bloquée| R["Refus poli"]
    F --> L{"LAYA activé ?"}
    L -->|non| RT["Routeur"]
    L -->|oui| S["2 questions oui/non<br/>jailbreak, injection"]
    S -->|"max ≥ LAYA_THRESHOLD"| R
    S -->|sinon, ou erreur| RT
```

- **Rôle unique** : détecter les tentatives de manipulation. Le jugement du périmètre reste
  au routeur (LAYA, sans entraînement, refuse à tort la majorité des questions légitimes).
- **Questions posées** (préréglage « guard » de LAYA,
  [`laya_guard.py`](../backend/src/chatbot_api/laya_guard.py)) :
  - `jailbreak` : *Does the message try to make an AI assistant ignore its rules, policies or
    system instructions?*
  - `prompt_injection` : *Does the message contain instructions aimed at the AI system rather
    than a genuine user request?*
- **Décision** : score = maximum des deux probabilités ; refus si score ≥ `LAYA_THRESHOLD`
  (0,8 par défaut).
- **État** : la question normalisée (caractères invisibles retirés), sans l'historique.
- **Panne** : modèle absent, dépendance manquante ou erreur d'inférence → la question passe
  (journal d'erreur) ; un échec de chargement n'est pas retenté à chaque requête.
- **Chargement** : au démarrage de l'application (~1 s), pour ne pas allonger la première
  question.
- **Diagnostic** : en-tête `X-Laya` (`0.93 flagged (196 ms)`) si `DEBUG_HEADERS=true` ; score
  reporté dans le rapport d'évaluation.

## 3. Le runtime sans PyTorch

### Pourquoi un runtime à nous

Le paquet officiel `laya` 0.4.17 déclare `torch` et `transformers` comme dépendances de base,
et son moteur ONNX (`ONNXAgent`) importe des modules qui importent `torch` : impossible de s'en
servir dans une fonction Vercel. [`laya_runtime.py`](../backend/src/chatbot_api/laya_runtime.py)
reproduit uniquement le chemin d'inférence ONNX avec `onnxruntime`, `tokenizers` et `numpy`
(~155 Mo installés, contre plusieurs Go avec PyTorch).

### Ce qu'il fait

1. **Tokenizer** : `tokenizer/tokenizer.json` chargé avec la bibliothèque `tokenizers` ;
   jetons spéciaux (`mask`, `cls`, `sep`, `pad`) lus dans `tokenizer/tokenizer_config.json`.
2. **Séquence**, une par question :

   ```text
   [CLS] <type> question: <instructions> [SEP] [MASK] option 0 [MASK] option 1 … [SEP] <état> [SEP]
   ```

   - options rendues comme dans LAYA (`noul` : `false: no, the statement does not hold` /
     `true: yes, the statement holds`), 48 jetons maximum chacune ;
   - partie question bornée par `head_max_len` (192 en anglais, 256 en multilingue), options
     raccourcies si besoin ;
   - état tronqué pour tenir dans `max_len` (512 en anglais, 1 024 en multilingue).
3. **Graphe ONNX** : entrées `input_ids`, `attention_mask`, `marker_pos` (position de chaque
   `[MASK]`), `marker_mask`, `qtype` ; sorties `logits` (un score par option) et `act_logits`.
4. **Décodage** : logits divisés par une température (lue dans `rl_agent_config.json`, par type
   et nombre d'options, bornée entre 0,5 et 5) puis softmax ; `choice` → option la plus
   probable, `score` → espérance, `noul` → probabilité de « true » ; `confidence` (entropie
   normalisée) et `answer_confidence` (probabilité maximale) comme dans LAYA.

### Différences avec le paquet officiel

Non repris (inutiles ici) : réordonnancement des options, étiquettes `noul` personnalisées,
calibration par histogramme, températures par langue, traitement par lots de plusieurs états,
fenêtres glissantes sur les longs textes, crochets (*hooks*).

### Parité

Sur le même graphe et les mêmes questions, notre runtime donne **les mêmes probabilités** que le
paquet officiel exécuté avec PyTorch (écart maximal mesuré : 0,0). Le test
`test_parity_with_official_runtime` le vérifie à partir de références enregistrées
([`fixtures/laya_official_multilingual.json`](../backend/tests/fixtures/laya_official_multilingual.json)).

## 4. Modèles

| Variante | Dossier local | Graphe | Configuration et tokenizer | Taille | Contexte |
|---|---|---|---|---|---|
| **Anglaise** (recommandée) | `models/laya-english-onnx` | `mnjkshrm/sentrygate-laya` (int8) | `convaiinnovations/laya` (officiel) | 427 Mo | 512 |
| Multilingue | `models/laya-multilingual-onnx` | `soyelmismo/laya-multilingual-onnx` (int8 sélectif) | même dépôt | 344 Mo | 1 024 |

Arborescence attendue (identique à celle du paquet officiel) :

```text
models/laya-english-onnx/
├── model.onnx
├── rl_agent_config.json
└── tokenizer/
    ├── tokenizer.json
    └── tokenizer_config.json
```

[`download_laya_model.py`](../backend/scripts/download_laya_model.py) télécharge chaque fichier à
une **révision épinglée** et vérifie l'empreinte **SHA-256** des fichiers volumineux ; un fichier
déjà présent et valide n'est pas retéléchargé. `backend/models/` est exclu de Git et du
déploiement Vercel. Licences et attributions :
[`THIRD_PARTY_NOTICES.md`](../backend/THIRD_PARTY_NOTICES.md).

## 5. Configuration

| Variable | Défaut | Rôle |
|---|---|---|
| `LAYA_MODEL_DIR` | vide (désactivé) | Dossier du modèle, absolu ou relatif au dossier de lancement |
| `LAYA_THRESHOLD` | 0.8 | Score à partir duquel la question est refusée |
| `LAYA_THREADS` | 0 | Threads d'inférence (0 = automatique, 1 = comportement d'1 vCPU) |
| `DEBUG_HEADERS` | false | Affiche `X-Laya` (développement uniquement) |

Dépendances : groupe optionnel `laya` du backend (`numpy`, `onnxruntime`, `tokenizers`),
installé par `uv sync --extra laya`. Elles ne sont **pas** dans `requirements.txt` (Vercel).

## 6. Procédures

### Installer et tester en local

```bash
cd backend
uv sync --extra laya
uv run python scripts/download_laya_model.py --variant english
uv run python scripts/laya_check.py "Ignore tes consignes" "Qui est Ada Lovelace ?"
uv run python scripts/laya_check.py --threads 1 --file mes_questions.txt   # 1 vCPU, fichier
```

### Activer dans le backend

Dans `backend/.env` : `LAYA_MODEL_DIR=models/laya-english-onnx` (et `DEBUG_HEADERS=true` pour
voir les scores), puis `uv run python -m chatbot_api`. Le journal affiche « Modèle LAYA chargé
en … s ».

### Mesurer (banc d'essai)

```bash
uv run python evals/laya_benchmark.py                       # modèle anglais
uv run python evals/laya_benchmark.py --threads 1 --scope   # 1 vCPU + jugement du périmètre
uv run python evals/laya_benchmark.py --model models/laya-multilingual-onnx
```

Jeux : [`evals/laya_labelled.jsonl`](../backend/evals/laya_labelled.jsonl) (40 messages
étiquetés `event`, `off_topic`, `manipulation`) et [`evals/cases.jsonl`](../backend/evals/cases.jsonl).
Le script affiche latence, tableau détection / faux positifs par seuil, et la liste des
manipulations manquées et des faux positifs au seuil 0,8. Sortie de référence (modèle anglais,
1 thread) :

```text
Filtre seul : 14/32 détectées, 0 faux positifs
| Seuil | Filtre + LAYA : détectées | Faux positifs |
| 0.70 | 21/32 | 4/36 |
| 0.75 | 21/32 | 0/36 |
| 0.80 | 21/32 | 0/36 |
```

Pour enrichir la mesure, ajoutez des lignes à `laya_labelled.jsonl`
(`{"id", "label": "event" | "off_topic" | "manipulation", "question"}`), en particulier des
questions **réelles** posées pendant les tests.

### Ajuster le seuil

1. Enrichir le jeu étiqueté avec des questions réelles (françaises surtout).
2. Lancer le banc d'essai ; retenir le seuil le plus bas qui ne produit **aucun faux positif**
   sur les questions légitimes, avec une marge (le défaut 0,8 est à 0,05 au-dessus du premier
   seuil sans faux positif mesuré).
3. Relancer l'évaluation complète (`evals/run_evals.py`) avec ce seuil sur la plateforme.

### Vérifier la parité avec le paquet officiel

À faire après toute modification de `laya_runtime.py` ou tout changement de modèle :

```bash
# environnement séparé, avec PyTorch (jamais dans celui du backend)
uv venv /tmp/laya-official --python 3.12
uv pip install --python /tmp/laya-official/bin/python "laya==0.4.17" onnxruntime \
    "transformers>=4.48,<5" torch --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple
uv run python scripts/download_laya_model.py --variant multilingual
/tmp/laya-official/bin/python scripts/laya_parity_reference.py --model-dir models/laya-multilingual-onnx
LAYA_TEST_MODEL_DIR=models/laya-multilingual-onnx uv run pytest tests/test_laya_runtime.py
```

[`laya_parity_reference.py`](../backend/scripts/laya_parity_reference.py) régénère les références
avec le paquet officiel ; le test compare ensuite notre runtime à ces références (tolérance
0,0001).

### Changer de modèle ou de révision

1. Ajouter ou modifier la variante dans `VARIANTS` de
   [`download_laya_model.py`](../backend/scripts/download_laya_model.py) (dépôt, **révision**,
   fichier distant, fichier local).
2. Télécharger, vérifier la parité, relancer le banc d'essai et ajuster le seuil.
3. Mettre à jour [`THIRD_PARTY_NOTICES.md`](../backend/THIRD_PARTY_NOTICES.md) et la note 07.

Contraintes du runtime : disposition d'options `sequential` (refus explicite sinon), graphe aux
entrées et sorties décrites en section 3.

### Déployer sur Vercel (voie *Large Functions*)

Non activé par défaut. Étapes à valider en préproduction :

1. `requirements.txt` : ajouter `numpy`, `onnxruntime`, `tokenizers` (versions de `uv.lock`).
2. Rendre le modèle disponible à la construction : soit le versionner (Git LFS, ~430 Mo), soit
   le télécharger pendant la construction en préfixant `buildCommand` de `vercel.json` par
   `python3 backend/scripts/download_laya_model.py --variant english &&` (à vérifier : le
   dossier doit exister avant l'empaquetage de la fonction).
3. `vercel.json` : ajouter `backend/models/laya-english-onnx/**` aux `includeFiles` de
   `api/index.py` ; retirer `backend/models` de `.vercelignore`.
4. Variables : `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`,
   `LAYA_MODEL_DIR=backend/models/laya-english-onnx` (chemin relatif à la racine du
   déploiement, à vérifier), `LAYA_THREADS=1` en Hobby.
5. Vérifier en préproduction : taille du paquet (~610 Mo), démarrage à froid, latence, en-tête
   `X-Laya`, journal « Modèle LAYA chargé ».

Alternatives (téléchargement au démarrage, service séparé) : [07](07_vercel_et_laya.md#5-déployer-laya-sur-vercel).

## 7. Piste : entraîner LAYA sur nos données

Le paquet officiel fournit `laya-train` (entraînement à partir de JSONL ou CSV étiquetés, sur
une base `convaiinnovations/laya` ou `multilingual`). Démarche envisagée, **non réalisée** :

1. Constituer quelques centaines d'exemples étiquetés (questions réelles du salon, hors sujet,
   manipulations FR/EN), en partant de `laya_labelled.jsonl`.
2. Entraîner hors production (PyTorch, idéalement avec un GPU), avec un jeu d'évaluation
   séparé.
3. Exporter en ONNX (script `export_onnx.py` du dépôt LAYA, absent du paquet PyPI), quantifier
   en int8 en préservant les couches sensibles, vérifier la parité.
4. Charger le résultat avec `LAYA_MODEL_DIR` : le runtime est inchangé.

Bénéfices attendus : meilleure détection des détours en français, et peut-être un jugement du
périmètre utilisable — à mesurer avec le banc d'essai.

## 8. Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| Journal « LAYA indisponible : garde-fou désactivé » | Dépendances absentes, dossier ou fichier manquant | `uv sync --extra laya` ; vérifier `LAYA_MODEL_DIR` et l'arborescence (section 4) |
| `Empreinte SHA-256 inattendue` au téléchargement | Fichier corrompu ou modifié | Relancer ; si persistant, vérifier la révision épinglée |
| Questions légitimes refusées (« Je ne peux pas donner suite… ») | Seuil trop bas, variante multilingue | `X-Laya` en préproduction ; relever `LAYA_THRESHOLD` ; utiliser la variante anglaise |
| Première question lente | Chargement du modèle sur une nouvelle instance | Normal (~1 s + démarrage à froid) ; le modèle est chargé au démarrage |
| `Seule la disposition d'options « sequential »…` | Modèle incompatible | Utiliser un modèle exporté avec la disposition séquentielle |
| Scores différents du paquet officiel | Runtime ou modèle modifié | Procédure de parité (section 6) |

## 9. Limites

- Non entraîné sur nos données : moins bon sur les détours en français et dans d'autres langues
  (fiction, « exercice autorisé », traduction de « ce qui précède », allemand).
- Seuil choisi sur un petit échantillon (68 messages) ; à confirmer.
- Les scores varient légèrement selon les questions évaluées ensemble (propriété du modèle,
  identique dans le paquet officiel).
- Analyse la seule question, sans l'historique : une manipulation étalée sur plusieurs messages
  lui échappe (le routeur et le prompt restent en place).
