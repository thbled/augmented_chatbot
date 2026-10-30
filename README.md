# Assistant conversationnel de conférence

Chatbot augmenté pour les participants d'un événement : accès par QR code, une seule
conversation, réponses appuyées sur une base de connaissances (speakers, programme,
partenaires, informations pratiques, documentation thématique) et sur le planning en direct.

- **Mobile d'abord** : PWA, thème clair/sombre (système ou manuel), FR/EN, accessibilité RGAA.
- **Cartes visuelles** dans le chat : speakers (photo, fiche détaillée), sessions, partenaires.
- **Suggestions de relance** cliquables après chaque réponse.
- **Planning en direct** : ce qui se passe maintenant et ensuite, d'après la régie.
- **Fiabilité** : horaires calculés par le code (« que se passe-t-il à 15h12 ? »), cartes
  vérifiées, contrôle de cohérence planning / programme, réponses de référence.
- **Garde-fous** : filtre déterministe, routeur, prompt durci, contrôle des réponses, jeu
  d'évaluation.
- **Aucun compte, aucun upload** ; conversation conservée uniquement sur le téléphone.

## Architecture

```
 Téléphone (QR code)
        │  POST /api/chat (toute la conversation)          ┌───────────────────────────────┐
        ▼                                                  │ Plateforme LLM (WebSocket)    │
 ┌────────────────────┐  SSE   ┌──────────────────────┐    │                               │
 │ frontend/          │◀──────▶│ backend/ (Flask)     │───▶│ routeur : petit modèle,       │
 │ React + Vite (PWA) │        │ 1. limite par IP     │    │   sans RAG                    │
 └────────────────────┘        │ 2. filtre (guard)    │    │ réponse : modèle principal    │
                               │ 3. routeur           │───▶│   + RAG (workspaceId)  ◀──┐   │
                               │ 4. heure, planning,  │    └───────────────────────────┼───┘
                               │    faits calculés    │                                │
                               │ 5. LLM en streaming  │                                │
                               │ 6. contrôle réponse  │                                │
                               └──────────┬───────────┘                                │
                                          │ GET (cache 30 s)                           │
                                          ▼                                            │
                               API planning (régie)                                    │
                                                                                       │
 tools/ : Excel ──▶ fiches Markdown (kb/) ─────────────── chargement dans la KB ───────┘
                └─▶ backend/src/chatbot_api/data/scope.json (fiche de périmètre du routeur)
```

Le backend accepte aussi une API HTTP compatible OpenAI (`LLM_BASE_URL`) à la place du
WebSocket : le mode est choisi par la présence de `WS_WORKSPACE_ID`.

| Dossier | Rôle | Stack |
|---|---|---|
| [`frontend/`](frontend) | Application de chat | React 19, TypeScript, Vite, Tailwind CSS 4, axios, i18next, Vitest, oxlint, Prettier |
| [`backend/`](backend) | Pont sécurisé vers le LLM, garde-fous, planning | Python 3.12, Flask, websockets, SDK `openai`, httpx, pytest, ruff, uv |
| [`api/`](api) | Point d'entrée Vercel du backend | — |
| [`tools/`](tools) | Modèle Excel, import LinkedIn (PDF), base de connaissances, fiche de périmètre | Python, openpyxl, pypdf |

Le détail du traitement d'une question (filtre, routeur, heure, planning, historique) est dans
[`backend/README.md`](backend/README.md).

### Protocole des réponses

Le LLM répond en Markdown et peut insérer des blocs spéciaux, transformés en composants par le
frontend :

````
Voici la speaker qui correspond :

```speaker
{"id":"ada-lovelace","firstName":"Ada","lastName":"Lovelace","photoUrl":"/images/speakers/ada-lovelace.jpg",…}
```

```suggestions
["Quelles sont ses sessions ?", "Qui d'autre parle d'IA ?"]
```
````

Le JSON des cartes est généré par `tools` dans chaque fiche de la base de connaissances, et
le prompt système ([`system_prompt.md`](backend/src/chatbot_api/prompts/system_prompt.md))
impose de le recopier tel quel. Pendant le streaming, un bloc incomplet s'affiche comme un
squelette de carte. En fin de réponse, le backend envoie le texte final complet (événement SSE
`replace`), qui remplace le texte reçu au fil de l'eau : la réponse affichée est toujours
complète et dans l'ordre. Les renvois aux documents (« [Doc 1] ») sont retirés.

## Garde-fous et fiabilité

| Étape | Rôle | Où |
|---|---|---|
| Limite par IP, taille des messages | abus, coût | backend |
| **Filtre déterministe** | normalisation (caractères invisibles), blocage des manipulations courantes en FR/EN | [`guard.py`](backend/src/chatbot_api/guard.py) |
| **LAYA** (optionnel, local, CPU) | détection des manipulations par un classifieur qui ne suit pas d'instructions ; version anglaise, seuil 0,8 | [`laya_guard.py`](backend/src/chatbot_api/laya_guard.py), [07](0_docs/07_vercel_et_laya.md) |
| **Routeur** (petit modèle, sans RAG) | hors sujet / manipulation, reformulation pour la recherche ; ne refuse jamais une question citant un élément connu ; laisse passer en cas de panne | [`router.py`](backend/src/chatbot_api/router.py) |
| **Faits calculés** | heures, périodes, titres cités : créneau exact calculé par le code, fourni au LLM comme fait vérifié | [`timefacts.py`](backend/src/chatbot_api/timefacts.py) |
| **Prompt durci** | question encadrée, règles de sécurité et d'exactitude, langue imposée, jeton canari | [`system_prompt.md`](backend/src/chatbot_api/prompts/system_prompt.md) |
| **Contrôle de la réponse** | fuite du prompt (canari) → refus ; cartes inconnues retirées ; coordonnées non officielles masquées ; langage grossier → refus ; horaires non vérifiés signalés | [`output_guard.py`](backend/src/chatbot_api/output_guard.py) |
| Affichage | pas de HTML, images Markdown bloquées, images de cartes limitées aux domaines autorisés, liens filtrés, CSP | frontend, [`vercel.json`](vercel.json) |
| **Contenus de la base** | caractères invisibles retirés, passages suspects signalés (injection indirecte) | `conference-tools build-kb` |
| **Cohérence des données** | planning REST ↔ programme du classeur | `conference-tools check-planning` |
| **Évaluation** | jeu d'attaques FR/EN/autres langues, réponses de référence (`expect_contains`) | [`backend/evals/`](backend/evals) |

Aucune de ces couches n'est infaillible seule : c'est leur empilement qui protège. Les
évaluations mesurent le résultat réel sur la plateforme et doivent être relancées après chaque
changement de modèle, de prompt ou de données.

## Démarrage local

Prérequis : Node 22+, Python 3.12+, [uv](https://docs.astral.sh/uv/).

```bash
# Backend (terminal 1)
cd backend
cp .env.example .env        # voir ci-dessous
uv sync
uv run python -m chatbot_api            # http://127.0.0.1:5000

# Frontend (terminal 2)
cd frontend
cp .env.example .env        # VITE_EVENT_NAME
npm install
npm run dev                             # http://localhost:5173 (proxy /api → Flask)
```

Variables essentielles du backend (toutes documentées dans
[`backend/.env.example`](backend/.env.example)) :

| Variable | Rôle |
|---|---|
| `WS_URL`, `WS_WORKSPACE_ID`, `WS_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` | plateforme LLM et base de connaissances |
| `PLANNING_URL` | API du planning en direct (GET, identifiant dans l'URL) |
| `ROUTER_MODEL` | modèle du routeur, ex. `amazon.nova-lite-v1:0` (vide = routeur désactivé) |
| `EVENT_NAME`, `EVENT_TIMEZONE` | nom et fuseau de l'événement |
| `EVENT_FAKE_DATE` | **dev uniquement** : jour simulé (ex. `2026-11-18`), l'heure reste réelle ; le planning de test, daté du jour réel, est décalé sur ce jour |
| `RATE_LIMIT_ENABLED` | `false` en développement |

Pour tester depuis un téléphone sur le même réseau : `npm run dev -- --host`.

## Qualité

```bash
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd tools    && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

Évaluation des garde-fous sur le vrai LLM (rapport Markdown dans `backend/evals/reports/`) :

```bash
cd backend && uv run python evals/run_evals.py                              # garde-fous
cd backend && uv run python evals/run_evals.py --cases evals/golden.jsonl   # réponses de référence
```

Voir [`backend/README.md`](backend/README.md#évaluation-des-garde-fous).

## Données de l'événement

Voir [`tools/README.md`](tools/README.md) :

1. remplir le classeur Excel, éventuellement le pré-remplir depuis les exports PDF LinkedIn
   des speakers (avec leur consentement) ;
2. `conference-tools build-kb` : génère `kb/` **et** la fiche de périmètre du routeur
   (`backend/src/chatbot_api/data/scope.json`, à commiter pour qu'elle soit déployée) ;
3. charger `kb/` dans la base de connaissances de la plateforme LLM ;
4. `conference-tools check-planning` : vérifier que le planning de la régie et le programme du
   classeur concordent (titres, horaires).

Le planning du jour (horaires, statut en cours / à venir / terminé) vient de l'API de la régie
et fait foi sur les horaires de la base de connaissances.

## Déploiement Vercel

Un seul projet Vercel sert le frontend statique et la fonction Python (`api/index.py`).
La configuration est dans [`vercel.json`](vercel.json) (build, réécriture `/api/*`, en-têtes de
sécurité dont la CSP, cache).

1. Importer le dépôt dans Vercel (répertoire racine : la racine du dépôt).
2. Variables d'environnement (Production) :

   | Variable | Exemple / valeur |
   |---|---|
   | `WS_URL`, `WS_WORKSPACE_ID`, `WS_PROVIDER` | plateforme LLM et base de connaissances |
   | `LLM_API_KEY`, `LLM_MODEL` | clé et modèle principal |
   | `LLM_TIMEOUT_SECONDS` | `45` (voir la contrainte de durée ci-dessous) |
   | `ROUTER_MODEL` | `amazon.nova-lite-v1:0` |
   | `PLANNING_URL` | URL de l'API du planning |
   | `EVENT_NAME`, `VITE_EVENT_NAME` | nom de l'événement |
   | `VITE_IMAGE_HOSTS` | domaines des photos et logos externes (vide si tout est dans `frontend/public/images`) |
   | `RATE_LIMIT_ENABLED` | `true` (100 requêtes / IP / 24 h par défaut) |
   | `IP_HASH_SALT` | chaîne aléatoire |
   | `EVENT_FAKE_DATE`, `EVENT_FAKE_NOW` | **vides** en production |
   | `WS_DEBUG_RAW`, `DEBUG_HEADERS` | **`false`** en production (journalisent du contenu ou exposent les décisions) |

   En mode HTTP compatible OpenAI : `LLM_BASE_URL` (+ `LLM_REASONING_EFFORT`,
   `LLM_EXTRA_BODY` si le serveur les gère) à la place des variables `WS_*`.

3. **Images externes** : si des photos ou logos sont hébergés hors de l'application, ajouter
   leurs domaines à la fois dans `VITE_IMAGE_HOSTS` et dans `img-src` de la CSP
   ([`vercel.json`](vercel.json)), qui n'autorise par défaut que les images de l'application.
4. **Limitation par IP partagée** : ajouter l'intégration *Upstash Redis* depuis le Marketplace
   Vercel (elle définit `KV_REST_API_URL` / `KV_REST_API_TOKEN`). Sans elle, chaque instance
   serverless compte séparément : la limite reste indicative.
5. Générer le QR code vers l'URL de production.

**Durée maximale** : `maxDuration` de la fonction est fixé à 60 s dans `vercel.json` (Vercel
autorise jusqu'à 300 s en Hobby, 800 s en Pro). Le routeur, l'appel au planning et la réponse du LLM s'enchaînent dans la même requête :
`ROUTER_TIMEOUT_SECONDS` (6) + délai du planning (4) + `LLM_TIMEOUT_SECONDS` (45) doit rester
inférieur à `maxDuration`, sinon Vercel coupe la réponse avant le message d'erreur propre.

**Dépendances Python** : `requirements.txt` (racine) est exporté depuis `backend/uv.lock` ; le
régénérer après tout changement de dépendances du backend (commande en tête du fichier), sans
quoi le déploiement échoue à l'import.

**Budget LLM** : la plateforme coupe les appels une fois le budget atteint ; l'application
affiche alors « assistant momentanément indisponible ». Le pare-feu Vercel (règles de
limitation de débit) peut compléter la limite par IP si nécessaire.

**Offre Vercel** : l'offre Hobby est réservée à un usage personnel non commercial ; vérifier
l'offre adaptée pour un événement d'entreprise.

**Région** : `vercel.json` fixe la région `cdg1` (Paris) au lieu de `iad1` (États-Unis) par
défaut : latence réduite vers la plateforme LLM et traitement en Europe. Détails et
faisabilité de LAYA sur Vercel : [`0_docs/07_vercel_et_laya.md`](0_docs/07_vercel_et_laya.md).

## Accessibilité (RGAA)

- Structure : un `h1` (application), un `h2` par message, liens d'évitement, régions nommées.
- Annonces vocales (`<output aria-live>`) : début de rédaction puis contenu de la réponse,
  sans lecture fragment par fragment ; erreurs en `role="alert"`.
- Fiche speaker en `<dialog>` modal natif : focus piégé, Échap, focus restitué.
- Cibles tactiles ≥ 44 px, focus visible, contrastes AA en clair et sombre,
  `prefers-reduced-motion` respecté, liens externes signalés (« nouvelle fenêtre »),
  attribut `lang` mis à jour au changement de langue.
- À compléter par un audit sur appareils réels (VoiceOver iOS, TalkBack Android).

## Données personnelles

- Pas de compte, pas de cookie, pas d'analytics, pas de police chargée depuis un service tiers.
- Historique uniquement dans le `localStorage` du téléphone (bouton « Nouvelle conversation ») ;
  il est envoyé en entier à chaque question puis oublié par le serveur.
- Côté serveur : aucune conversation stockée ; journaux techniques anonymes (catégorie d'un
  refus, jamais le texte de la question) ; IP conservées uniquement sous forme d'empreinte
  salée, le temps de la fenêtre de limitation. `WS_DEBUG_RAW` (diagnostic) journalise le
  contenu des échanges : à réserver au développement.
- Speakers : publication conditionnée au consentement tracé dans le classeur.
