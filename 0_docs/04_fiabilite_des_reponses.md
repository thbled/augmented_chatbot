# 04 — Fiabilité des réponses

Un LLM ne garantit jamais une réponse exacte. La stratégie est donc :

1. **calculer par le code** tout ce qui peut l'être (horaires, créneaux) et le fournir au LLM
   comme fait vérifié ;
2. **restreindre** le LLM aux sources (base de connaissances, planning) et lui imposer de dire
   « je ne sais pas » ;
3. **vérifier** après coup ce qui est vérifiable (cartes, horaires cités) ;
4. **contrôler les données** en amont (cohérence planning / programme) ;
5. **mesurer** avec des questions de référence avant l'événement.

## 1. Sources de vérité

| Sujet | Source qui fait foi |
|---|---|
| Heure courante | Horloge du serveur (Europe/Paris) |
| Horaires et statut du jour | API planning de la régie (début + durée ajustée) |
| Calcul « que se passe-t-il à 15h12 », « combien de temps reste-t-il » | Faits calculés par le backend |
| Bios, descriptions, partenaires, infos pratiques | Base de connaissances (générée depuis le classeur) |
| Existence d'un speaker, partenaire, session | Fiche de périmètre `scope.json` (+ titres du planning) |
| Coordonnées pouvant être communiquées | Coordonnées officielles de `scope.json` |

En cas de conflit d'horaire entre la base de connaissances et le planning, **le planning
l'emporte** (règle du prompt).

## 2. Faits calculés par le code

[`timefacts.py`](../backend/src/chatbot_api/timefacts.py) analyse la question avec des
expressions régulières (pas d'IA) et calcule le résultat à partir du planning en direct.

| Reconnu | Exemples | Fait produit |
|---|---|---|
| Heure précise | « 15h12 », « 15 h », « 15 heures 30 », « 15:12 », « 3:12 pm », « midi » | créneau en cours à cette heure, temps écoulé et restant, créneau suivant |
| Heure relative | « dans 20 minutes », « dans une demi-heure », « in an hour » | idem, à partir de l'heure serveur |
| Période | « ce matin », « cet après-midi », « ce soir », « this afternoon » | liste des créneaux de la période |
| Jour relatif | « demain », « hier », « tomorrow » | créneaux de ce jour, ou « aucun créneau » (événement d'un jour) |
| Titre cité | « la pause café », « la session Atlassian » | horaire et statut : en cours (fin dans…), à venir (début dans…), terminé |
| « Maintenant », « ensuite » | « en ce moment », « what's next » | créneaux en cours (statut de la régie) et à venir, déjà dans le prompt |

Exemple, pour « Que se passe-t-il à 15h12 ? » :

```text
- À 15:12 : « ATLASSIAN: New ways of Working avec l'IA » (15:00–15:45) — commencé depuis 12 min, se termine dans 33 min.
- Créneau suivant : « Pause café » (15:45–16:00).
```

Ces faits sont placés dans le prompt avec la consigne de les utiliser tels quels ; les titres
concernés sont aussi ajoutés à la recherche documentaire, pour que la fiche de la session
(speakers, description, carte) soit retrouvée.

Précautions : « la session dure 2h » n'est pas lu comme un horaire ; « dans 1 h » n'est pas
lu comme 01:00 ; « après-midi » n'est pas lu comme « midi ».

**Limites** : une formulation non reconnue (« après le déjeuner », « pendant la keynote »)
ne produit aucun fait ; le LLM s'appuie alors sur la liste du jour présente dans le prompt.
La justesse dépend des données de la régie (début + durée ajustée).

## 3. Règles imposées au LLM

Dans le [prompt système](../backend/src/chatbot_api/prompts/system_prompt.md) :

- faits de l'événement uniquement depuis la base de connaissances et le planning ;
- jamais d'invention de speaker, session, horaire, salle, entreprise, URL ou image ;
- information absente : le dire clairement et proposer une alternative ;
- question ambiguë : demander une précision plutôt que deviner ;
- connaissances générales autorisées seulement pour expliquer un sujet de fond, sans les
  présenter comme des informations de l'événement ;
- vérifier chaque fait avant de répondre (méthode de réflexion interne).

## 4. Cartes : contenu recopié, puis vérifié

- Le JSON de chaque carte est **produit par les outils** dans la fiche correspondante de la
  base de connaissances ; le LLM a pour consigne de le recopier à l'identique.
- Le contrôle de sortie **retire toute carte absente de la fiche de périmètre** : une fiche de
  speaker inventée n'est jamais affichée.
- Le frontend valide chaque champ et ignore un bloc illisible.

## 5. Vérification des horaires cités

Chaque heure présente dans la réponse est comparée aux heures du planning, des faits calculés,
de la question et à l'heure courante. Un écart est **signalé** (journal, rapport d'évaluation)
sans modifier la réponse : une heure peut légitimement venir de la base de connaissances
(programme du classeur), d'où l'importance du contrôle de cohérence ci-dessous.

## 6. Cohérence des données

| Contrôle | Commande | Détecte |
|---|---|---|
| Classeur | `conference-tools validate` | champs manquants, horaires invalides, speakers inconnus, consentements |
| Planning ↔ classeur | `conference-tools check-planning` | sessions absentes d'un côté, horaires différents (> 5 min) |
| Contenus | `conference-tools build-kb` | passages suspects (injection indirecte) |

## 7. Mesurer : questions de référence

Fichier JSONL avec, pour chaque question, les éléments que la réponse **doit** contenir :

```json
{"id": "instant-15h12", "locale": "fr", "question": "Que se passe-t-il à 15h12 ?", "expect": "answer", "expect_contains": ["Atlassian"]}
```

`uv run python evals/run_evals.py --cases evals/golden.jsonl` vérifie automatiquement chaque cas
et produit un rapport (réponse, faits calculés, cartes retirées, horaires non vérifiés). À
construire avec les données réelles à partir de
[`golden.example.jsonl`](../backend/evals/golden.example.jsonl), et à relancer après chaque
changement de modèle, de prompt ou de données.

## Ce qui est garanti, ce qui ne l'est pas

| | Niveau |
|---|---|
| Heure courante, créneau à une heure reconnue, temps restant | **Calculé** : exact si les données de la régie le sont |
| Existence des speakers, sessions et partenaires affichés en carte | **Vérifié** contre la fiche de périmètre |
| Coordonnées communiquées | **Vérifiées** contre les coordonnées officielles |
| Contenu des bios, descriptions, conseils d'approfondissement | **Encadré** par les règles du prompt et la recherche documentaire, non garanti |
| Horaires cités hors faits calculés | **Signalés** s'ils ne correspondent à rien de connu |

## Prochaines étapes

- **Garde-fou n°3 — réponse fondée** : utiliser les documents trouvés par la plateforme (et
  leurs scores) pour répondre « je n'ai pas cette information » quand rien de pertinent n'est
  trouvé. En attente d'un extrait des messages WebSocket bruts (`WS_DEBUG_RAW=true`).
- Élargir les formulations reconnues selon les questions réellement posées pendant les tests.
- Onglet « Lieux » et carte « lieu » avec plan (voir [05](05_choix_techniques.md#d11-images-et-plans)).
