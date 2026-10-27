# Assistant conversationnel de conférence

Chatbot augmenté pour les participants d'un événement : accès par QR code, une seule
conversation, réponses appuyées sur une base de connaissances (speakers, programme,
partenaires, informations pratiques, documentation thématique).

- **Mobile d'abord** : PWA, thème clair/sombre (système ou manuel), FR/EN, accessibilité RGAA.
- **Cartes visuelles** dans le chat : speakers (photo, fiche détaillée), sessions, partenaires.
- **Suggestions de relance** cliquables après chaque réponse.
- **Aucun compte, aucun upload** ; conversation conservée uniquement sur le téléphone.

## Architecture

```
 Téléphone (QR code)
        │
        ▼
 ┌────────────────────┐   POST /api/chat (SSE)  ┌─────────────────────┐   API OpenAI   ┌──────────────────────┐
 │ frontend/          │ ──────────────────────▶ │ backend/ (Flask)    │ ─────────────▶ │ Serveur LLM          │
 │ React + Vite (PWA) │ ◀── flux de la réponse ─│ prompt, limite/IP   │ ◀── streaming ─│ + base de            │
 └────────────────────┘                         └─────────────────────┘                │   connaissances      │
                                                                                       └──────────▲───────────┘
 tools/ : Excel ──▶ fiches Markdown (kb/) ──────────── chargement ─────────────────────────────────┘
```

| Dossier | Rôle | Stack |
|---|---|---|
| [`frontend/`](frontend) | Application de chat | React 19, TypeScript, Vite, Tailwind CSS 4, axios, i18next, Vitest, oxlint, Prettier |
| [`backend/`](backend) | Pont sécurisé vers le LLM | Python 3.12, Flask, SDK `openai`, pytest, ruff, uv |
| [`api/`](api) | Point d'entrée Vercel du backend | — |
| [`tools/`](tools) | Modèle Excel, import LinkedIn (PDF), génération de la base de connaissances | Python, openpyxl, pypdf |

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
squelette de carte.

## Démarrage local

Prérequis : Node 22+, Python 3.12+, [uv](https://docs.astral.sh/uv/).

```bash
# Backend (terminal 1)
cd backend
cp .env.example .env        # renseigner LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
uv sync
uv run python -m chatbot_api            # http://127.0.0.1:5000

# Frontend (terminal 2)
cd frontend
cp .env.example .env        # VITE_EVENT_NAME
npm install
npm run dev                             # http://localhost:5173 (proxy /api → Flask)
```

Pour tester depuis un téléphone sur le même réseau : `npm run dev -- --host`.

## Qualité

```bash
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd tools    && uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Données de l'événement

Voir [`tools/README.md`](tools/README.md) : remplir le classeur Excel, éventuellement le
pré-remplir depuis les exports PDF LinkedIn des speakers (avec leur consentement), générer
`kb/`, puis charger ces fichiers dans la base de connaissances du serveur LLM.

## Déploiement Vercel

Un seul projet Vercel sert le frontend statique et la fonction Python (`api/index.py`).
La configuration est dans [`vercel.json`](vercel.json) (build, réécriture `/api/*`, en-têtes de
sécurité dont la CSP, cache).

1. Importer le dépôt dans Vercel (répertoire racine : la racine du dépôt).
2. Variables d'environnement (Production) :

   | Variable | Exemple |
   |---|---|
   | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | `gpt-oss-120b` |
   | `LLM_REASONING_EFFORT` | `low` (latence réduite) |
   | `LLM_EXTRA_BODY` | paramètres propres au serveur LLM (JSON), si nécessaire |
   | `EVENT_NAME`, `VITE_EVENT_NAME` | nom de l'événement |
   | `RATE_LIMIT_ENABLED` | `true` (100 requêtes / IP / 24 h par défaut) |
   | `IP_HASH_SALT` | chaîne aléatoire |

3. **Limitation par IP partagée** : ajouter l'intégration *Upstash Redis* depuis le Marketplace
   Vercel (elle définit `KV_REST_API_URL` / `KV_REST_API_TOKEN`). Sans elle, chaque instance
   serverless compte séparément : la limite reste indicative.
4. Générer le QR code vers l'URL de production.

`maxDuration` de la fonction est fixé à 60 s : à ajuster selon le plan Vercel et la
latence du LLM (`LLM_TIMEOUT_SECONDS` doit rester inférieur).
`requirements.txt` (racine) est exporté depuis `backend/uv.lock` ; le régénérer après tout
changement de dépendances (commande en tête du fichier).

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
- Historique uniquement dans le `localStorage` du téléphone (bouton « Nouvelle conversation »).
- Côté serveur : aucune conversation stockée ; IP conservées uniquement sous forme d'empreinte
  salée, le temps de la fenêtre de limitation.
- Speakers : publication conditionnée au consentement tracé dans le classeur.
