# Backend — API Flask

Pont entre l'application React et la plateforme LLM : WebSocket avec RAG sur la base de
connaissances (`WS_WORKSPACE_ID`), ou API HTTP compatible OpenAI (`LLM_BASE_URL`). Le backend
ajoute les garde-fous, l'heure de référence et le planning en direct. Le frontend n'appelle
jamais le LLM directement : la clé d'API reste côté serveur.

## Démarrage

```bash
cp .env.example .env      # WS_* ou LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, PLANNING_URL, ROUTER_MODEL…
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
| `{"type":"replace","text":"…"}` | texte complet faisant foi, qui remplace ce qui a été reçu (fin de réponse WebSocket) |
| `{"type":"debug","output":{…}}` | uniquement si `DEBUG_HEADERS=true` : résultat du contrôle de sortie |
| `{"type":"done"}` | fin de la réponse |
| `{"type":"error","code":"llm_timeout" \| "llm_unavailable" \| "internal_error"}` | erreur pendant la génération |

Erreurs avant le flux (JSON `{"error": code}`) :

| Statut | Code |
|---|---|
| 400 | `invalid_payload`, `invalid_messages`, `message_too_long` |
| 413 | `payload_too_large` |
| 429 | `rate_limited` (en-tête `Retry-After`) |

## Fonctionnement

Chaque question suit la chaîne suivante :

```
validation → limite par IP → garde-fou n°1 (filtre) → LAYA (optionnel) → garde-fou n°2 (routeur)
           → préparation du tour (heure, planning, faits calculés)
           → LLM (HTTP ou WebSocket RAG) → contrôle de la réponse → flux SSE
```

- **Garde-fou n°1** ([`guard.py`](src/chatbot_api/guard.py)) : normalisation (caractères
  invisibles, Unicode) et blocage des manipulations courantes (contournement des règles,
  extraction du prompt, faux balisage de rôles, charges encodées). Une question bloquée reçoit
  un refus poli, sans appel au LLM ; seule la catégorie est journalisée. `GUARD_ENABLED=false`
  pour le désactiver.
- **LAYA (optionnel)** ([`laya_guard.py`](src/chatbot_api/laya_guard.py),
  [`laya_runtime.py`](src/chatbot_api/laya_runtime.py)) : classifieur local (ONNX sur CPU, sans
  PyTorch) qui détecte les tentatives de manipulation ; refus au-delà de `LAYA_THRESHOLD`.
  Activation : `uv sync --extra laya`, `uv run python scripts/download_laya_model.py --variant
  english`, puis `LAYA_MODEL_DIR=models/laya-english-onnx`. Test rapide :
  `uv run python scripts/laya_check.py "question"`. Mesures et déploiement :
  [`0_docs/07_vercel_et_laya.md`](../0_docs/07_vercel_et_laya.md). Code adapté de LAYA
  (Apache 2.0) : [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- **Garde-fou n°2 : routeur** ([`router.py`](src/chatbot_api/router.py), prompt
  [`router_prompt.md`](src/chatbot_api/prompts/router_prompt.md)) : un petit modèle
  (`ROUTER_MODEL`, appelé **sans RAG**) classe la question (`allow`, `off_topic`,
  `manipulation`) et la reformule pour qu'elle se comprenne sans l'historique. Il connaît le
  périmètre grâce à la fiche [`data/scope.json`](src/chatbot_api/data/) (nom, thématiques,
  speakers, partenaires, sessions — générée par `conference-tools build-kb`) complétée par les
  titres du planning en direct. Sa sortie n'est jamais montrée à l'utilisateur et le code
  encadre ses erreurs :
  - refus seulement si sa confiance ≥ `ROUTER_REJECT_CONFIDENCE`, et jamais si la question cite
    un élément connu de la fiche ;
  - reformulation écartée si elle contient un nom ou un nombre absent de la question, de
    l'historique et de la fiche ; elle ne sert qu'à la recherche (« Contexte de recherche »),
    le modèle principal recevant toujours la question d'origine ;
  - réponse illisible, délai dépassé ou panne : la question passe telle quelle.

  Coût : un appel court supplémentaire avant la réponse (de l'ordre d'une à deux secondes).
- **Heure de référence** ([`clock.py`](src/chatbot_api/clock.py)) : uniquement celle du serveur
  (`EVENT_TIMEZONE`), rappelée dans le prompt système et devant chaque question. En dev,
  `EVENT_FAKE_DATE` fige le jour (l'heure reste réelle) et `EVENT_FAKE_NOW` fige l'instant.
- **Planning en direct** ([`planning.py`](src/chatbot_api/planning.py)) : `GET PLANNING_URL`,
  champ `slots` (`scheduledStart`, `durationAdjusted`, `status` PENDING/CURRENT/COMPLETED,
  `title`, `type`). Réponse en cache `PLANNING_TTL_SECONDS` ; dernière copie valide réutilisée
  en cas d'erreur. Les créneaux en cours, à venir et la journée complète sont injectés dans le
  prompt. Avec une date simulée, les créneaux de test (datés du jour réel) sont décalés sur le
  jour simulé.
- **Faits calculés** ([`timefacts.py`](src/chatbot_api/timefacts.py)) : les heures
  (« 15h12 », « 3 pm », « midi »), heures relatives (« dans 20 minutes »), périodes (« cet
  après-midi »), jours relatifs (« demain ») et titres de session cités dans la question sont
  reconnus par expressions régulières (FR/EN). Le créneau concerné est **calculé par le code**
  à partir du planning (début + durée ajustée par la régie) et fourni au LLM comme fait exact :
  « À 15:12 : « X » (15:00–15:45), commencé depuis 12 min, se termine dans 33 min ». Une
  formulation non reconnue ne produit aucun fait : le LLM s'appuie alors sur la liste du jour.
- **Contrôle de la réponse** ([`output_guard.py`](src/chatbot_api/output_guard.py)), appliqué
  au flux puis au texte final (corrections envoyées par un événement `replace`) :
  - fuite du prompt : un jeton canari secret (renouvelé à chaque démarrage) et des phrases
    caractéristiques du prompt ; la diffusion est coupée et la réponse remplacée par un refus ;
  - cartes : une carte absente de la fiche de périmètre est retirée (pas de fiche inventée) ;
  - coordonnées : e-mails et téléphones absents des coordonnées officielles masqués ;
  - langage grossier : réponse remplacée par un refus (liste courte, à compléter) ;
  - horaires : heures citées absentes du planning, des faits et de la question signalées
    (journal, évaluation), sans modifier la réponse.
- **Préparation du tour** ([`turn.py`](src/chatbot_api/turn.py)) : question encadrée par
  `<question>…</question>` ; dans la copie de l'historique envoyée au LLM, cartes JSON des
  anciennes réponses remplacées par `[fiche speaker : Nom]` (`HISTORY_COMPACT_CARDS`) ; pour
  les questions liées au moment présent, titres des créneaux concernés ajoutés à la requête de
  recherche RAG.
- **Prompt système** : [`src/chatbot_api/prompts/system_prompt.md`](src/chatbot_api/prompts/system_prompt.md).
  Périmètre professionnel, langue imposée par le réglage de l'application, règles de sécurité
  et d'exactitude (pas d'invention, « je ne sais pas » plutôt que deviner), méthode de
  réflexion interne et **protocole de sortie** :
  - cartes : blocs ` ```speaker `, ` ```session `, ` ```partner ` contenant le
    JSON de la base de connaissances, recopié tel quel ;
  - suggestions : un bloc ` ```suggestions ` final (tableau JSON de 2 à 4 questions).
- **Client WebSocket RAG** ([`ws_client.py`](src/chatbot_api/ws_client.py)) : tokens remis dans
  l'ordre de `sequenceNumber` (par `runId`), puis `final_response` fait foi (événement
  `replace`) ; renvois « [Doc n] » retirés. `WS_HISTORY_IN=system` place l'historique dans le
  prompt système pour que la recherche ne porte que sur la question. `WS_DEBUG_RAW=true`
  journalise les messages bruts (diagnostic).
- **Historique** : toute la conversation est envoyée par le téléphone ; le backend la conserve
  dans la limite de `MAX_HISTORY_CHARS` (les échanges les plus anciens sont retirés au-delà).
  Rien n'est stocké côté serveur.
- **Limitation par IP** : `RATE_LIMIT_MAX_REQUESTS` requêtes par fenêtre de
  `RATE_LIMIT_WINDOW_SECONDS`. Sur Vercel, configurer Upstash Redis pour un compteur partagé
  entre instances (sinon chaque instance compte de son côté). Les IP ne sont stockées que sous
  forme d'empreinte salée. Désactivée avec `RATE_LIMIT_ENABLED=false`.

Voir [`.env.example`](.env.example) pour toutes les variables.

## Évaluation des garde-fous

[`evals/cases.jsonl`](evals/cases.jsonl) regroupe des questions de test (légitimes, hors
périmètre, pièges sur l'heure, tentatives de jailbreak). Sur le vrai LLM :

```bash
uv run python evals/run_evals.py            # rapport Markdown dans evals/reports/
uv run python evals/run_evals.py --only jb- # uniquement les tentatives de jailbreak
```

Le rapport indique, pour chaque cas, la décision du filtre et du routeur et la question
reformulée : lancez-le avec chaque `ROUTER_MODEL` candidat pour comparer précision et latence.
**Réponses de référence** : un fichier au même format avec `expect_contains` (éléments que la
réponse doit contenir) est vérifié automatiquement ; partez de
[`evals/golden.example.jsonl`](evals/golden.example.jsonl) avec les données réelles :

```bash
uv run python evals/run_evals.py --cases evals/golden.jsonl
```

**LAYA** : `uv run python evals/laya_benchmark.py` mesure la détection des manipulations
(filtre seul et filtre + LAYA, par seuil) sur [`evals/laya_labelled.jsonl`](evals/laya_labelled.jsonl)
et les cas ci-dessus ; voir [`0_docs/08_laya_guide_technique.md`](../0_docs/08_laya_guide_technique.md).

Les cas `blocked` sont vérifiés automatiquement (et hors ligne par `pytest`) ; les autres sont
à relire dans le rapport. Enrichissez ce fichier au fil des tests réalisés par les équipes.
