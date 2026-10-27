# Backend — API Flask

Pont entre l'application React et le serveur LLM (API compatible OpenAI, base de connaissances
câblée côté serveur LLM). Le frontend n'appelle jamais le LLM directement : la clé d'API reste
côté serveur.

## Démarrage

```bash
cp .env.example .env      # renseigner LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
uv sync
uv run python -m chatbot_api   # http://127.0.0.1:5000
```

## Qualité

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

## API

### `GET /api/health`
`{"status": "ok"}`

### `POST /api/chat`

Requête :

```json
{
  "locale": "fr",
  "messages": [
    { "role": "user", "content": "Qui intervient sur l'IA générative ?" }
  ]
}
```

Réponse : flux `text/event-stream` (SSE), un événement JSON par ligne `data:` :

| Événement | Description |
|---|---|
| `{"type":"delta","text":"…"}` | fragment de la réponse |
| `{"type":"done"}` | fin de la réponse |
| `{"type":"error","code":"llm_timeout" \| "llm_unavailable" \| "internal_error"}` | erreur pendant la génération |

Erreurs avant le flux (JSON `{"error": code}`) :

| Statut | Code |
|---|---|
| 400 | `invalid_payload`, `invalid_messages`, `message_too_long` |
| 413 | `payload_too_large` |
| 429 | `rate_limited` (en-tête `Retry-After`) |

## Fonctionnement

- **Prompt système** : [`src/chatbot_api/prompts/system_prompt.md`](src/chatbot_api/prompts/system_prompt.md).
  Il définit le périmètre professionnel, la méthode de réflexion (reformulation interne,
  anticipation de la question suivante), le style et le **protocole de sortie** :
  - cartes : blocs ` ```speaker `, ` ```session `, ` ```partner ` contenant le JSON de la
    base de connaissances, recopié tel quel ;
  - suggestions : un bloc ` ```suggestions ` final (tableau JSON de 2 à 4 questions).
- **Historique** : seuls les `MAX_HISTORY_MESSAGES` derniers messages sont transmis au LLM.
  Rien n'est stocké côté serveur.
- **Limitation par IP** : `RATE_LIMIT_MAX_REQUESTS` requêtes par fenêtre de
  `RATE_LIMIT_WINDOW_SECONDS`. Sur Vercel, configurer Upstash Redis pour un compteur partagé
  entre instances (sinon chaque instance compte de son côté). Les IP ne sont stockées que sous
  forme d'empreinte salée. Désactivée avec `RATE_LIMIT_ENABLED=false`.
- **Paramètres spécifiques au serveur LLM** : `LLM_EXTRA_BODY` (JSON) est ajouté tel quel au
  corps de la requête (identifiant de collection, options de RAG, etc.).

Voir [`.env.example`](.env.example) pour toutes les variables.
