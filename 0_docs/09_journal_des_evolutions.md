# 09 — Journal des évolutions

Ce qui a changé depuis la première version, pourquoi, et où le trouver. Le plus récent en
premier.

## 30/10/2026 — Vercel et LAYA

| Évolution | Pourquoi | Où |
|---|---|---|
| Région Vercel `cdg1` (Paris) | Exécution par défaut aux États-Unis : latence vers la plateforme LLM européenne, traitement hors d'Europe | [`vercel.json`](../vercel.json) |
| Recherche sur les capacités de Vercel (taille, mémoire, durée, Sandbox, offre Hobby) | Savoir si LAYA peut tourner sur Vercel | [07](07_vercel_et_laya.md) |
| Runtime LAYA ONNX **sans PyTorch**, parité vérifiée avec le paquet officiel | Le paquet officiel exige PyTorch, incompatible avec une fonction Vercel | [`laya_runtime.py`](../backend/src/chatbot_api/laya_runtime.py), [08](08_laya_guide_technique.md) |
| Garde-fou LAYA optionnel (détection des manipulations, version anglaise, seuil 0,8) | Mesuré : +7 manipulations détectées sur 32, aucun faux positif ; classifieur non manipulable par instructions | [`laya_guard.py`](../backend/src/chatbot_api/laya_guard.py) |
| LAYA **non utilisé** pour le périmètre ; variante multilingue écartée | Mesuré : trop de faux refus | [07](07_vercel_et_laya.md#3-mesures) |
| Téléchargement des modèles à révision épinglée + SHA-256 ; test en ligne de commande ; banc d'essai ; références de parité | Reproductibilité et vérifiabilité | [`scripts/`](../backend/scripts), [`evals/laya_benchmark.py`](../backend/evals/laya_benchmark.py) |
| Filtre déterministe enrichi (« au-dessus », « you are now DAN », « sans filtre », faux `</question>`) | Cas manqués relevés pendant les mesures, sans faux positif ajouté | [`guard.py`](../backend/src/chatbot_api/guard.py) |
| Mentions de licence (Apache 2.0) | Code adapté de LAYA, modèles tiers | [`THIRD_PARTY_NOTICES.md`](../backend/THIRD_PARTY_NOTICES.md) |

## 30/10/2026 — Documentation projet

Création de `0_docs/` : architecture, backend et LLM, sécurité, fiabilité, choix techniques,
exploitation ([index](README.md)). Constat associé : la limite par IP risque de bloquer tout le
salon si les participants partagent l'IP publique du Wi-Fi ([06](06_exploitation.md#incidents)).

## 29–30/10/2026 — Fiabilité des réponses et sécurité

| Évolution | Pourquoi | Où |
|---|---|---|
| **Faits horaires calculés par le code** (« que se passe-t-il à 15h12 ? », « dans 20 minutes », « cet après-midi », titres cités) | Les LLM se trompent sur les comparaisons d'heures ; la réponse doit être exacte | [`timefacts.py`](../backend/src/chatbot_api/timefacts.py), [04](04_fiabilite_des_reponses.md#2-faits-calculés-par-le-code) |
| Contrôle de la réponse : jeton canari et phrases du prompt (fuite → réponse coupée), cartes inconnues retirées, coordonnées non officielles masquées, langage grossier refusé, horaires non vérifiés signalés | Garde-fous de sortie demandés en revue | [`output_guard.py`](../backend/src/chatbot_api/output_guard.py), [03](03_securite.md#couche-6--contrôle-de-la-réponse) |
| Analyse des contenus de la base (injection indirecte), caractères invisibles retirés du classeur | Une bio LinkedIn piégée pourrait manipuler le LLM | [`safety.py`](../tools/src/conference_tools/safety.py) |
| Coordonnées officielles dans la fiche de périmètre | Seules ces coordonnées peuvent être citées | [`kb.py`](../tools/src/conference_tools/kb.py) |
| Commande `check-planning` (planning REST ↔ classeur) | Détecter les données incohérentes avant qu'elles ne produisent de mauvaises réponses | [`planning_check.py`](../tools/src/conference_tools/planning_check.py) |
| Images des cartes limitées à l'application et aux domaines autorisés ; CSP `img-src` resserrée | Exfiltration de données par URL d'image | [`urls.ts`](../frontend/src/lib/urls.ts), [`vercel.json`](../vercel.json) |
| Réponses de référence (`expect_contains`), jailbreaks en anglais et autres langues, pièges horaires | Mesurer la fiabilité et la sécurité sur la vraie plateforme | [`evals/`](../backend/evals) |
| `LLM_TIMEOUT_SECONDS` ramené à 45 s | Routeur + planning + réponse dépassaient la durée maximale Vercel de 60 s | [`.env.example`](../backend/.env.example) |

## 29/10/2026 — Routeur (garde-fou n°2)

| Évolution | Pourquoi | Où |
|---|---|---|
| Routeur : petit modèle (Nova Lite), sans RAG, classe (`allow`, `off_topic`, `manipulation`) et reformule la question | Rejeter poliment le hors-sujet ; améliorer la recherche documentaire pour les questions de suivi | [`router.py`](../backend/src/chatbot_api/router.py) |
| Garde-fous de code autour du routeur : seuil de confiance, aucun refus si un élément connu est cité, reformulation sans invention, passage en cas de panne | Un petit modèle peut se tromper ; ses erreurs doivent rester sans gravité | [02](02_backend_et_llm.md#4-routeur-garde-fou-n2) |
| Fiche de périmètre `scope.json` générée par `build-kb` | Donner au routeur les noms de l'événement sans RAG | [`scope.py`](../backend/src/chatbot_api/scope.py) |
| Appel « complete » sans RAG dans les deux clients LLM | Nécessaire au routeur | [`ws_client.py`](../backend/src/chatbot_api/ws_client.py), [`llm.py`](../backend/src/chatbot_api/llm.py) |

## 29/10/2026 — Revue du TODO

| Évolution | Pourquoi | Où |
|---|---|---|
| **Tokens remis dans l'ordre** (`sequenceNumber`) et **réponse finale faisant foi** (événement `replace`), renvois « [Doc n] » retirés | Messages mélangés et tronqués observés (« …listed in 2026, at 11:34, titled " the program… ») | [`ws_client.py`](../backend/src/chatbot_api/ws_client.py) |
| Heure imposée par le serveur, devant chaque question ; jour simulé en développement (`EVENT_FAKE_DATE`) | L'heure ne doit pas venir du téléphone ; tester le 18/11 avant l'événement | [`clock.py`](../backend/src/chatbot_api/clock.py) |
| Planning en direct via l'API REST de la régie (cache 30 s, dernière copie valide) | Horaires à jour le jour J | [`planning.py`](../backend/src/chatbot_api/planning.py) |
| Historique complet envoyé par le téléphone ; plafond de taille côté serveur ; cartes compactées dans la copie envoyée au LLM | Ne pas perdre le contexte tout en maîtrisant les tokens | [`validation.py`](../backend/src/chatbot_api/validation.py), [`turn.py`](../backend/src/chatbot_api/turn.py) |
| Langue de réponse imposée par le réglage de l'application | Demande de revue | [`system_prompt.md`](../backend/src/chatbot_api/prompts/system_prompt.md) |
| Filtre déterministe (garde-fou n°1) et prompt durci (question encadrée, règles de sécurité et d'exactitude) | Testeurs avertis attendus | [`guard.py`](../backend/src/chatbot_api/guard.py) |
| Dépendances `websockets` et `tzdata` ajoutées à `requirements.txt` | Le déploiement Vercel aurait échoué à l'import | [`requirements.txt`](../requirements.txt) |

## 29/10/2026 — Passage à la plateforme WebSocket (par l'équipe)

Client WebSocket vers la plateforme LLM (RAG par `workspaceId`, modèles Bedrock), en
remplacement de l'API compatible OpenAI, toujours disponible en alternative.

## 23/10/2026 — Version initiale

Application React (PWA, FR/EN, thème, RGAA, cartes, suggestions), backend Flask (streaming SSE,
limite par IP, prompt système), outils (modèle Excel, import LinkedIn par PDF, génération de la
base de connaissances), déploiement Vercel.
