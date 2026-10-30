# Documentation du projet

Assistant conversationnel de conférence : les participants scannent un QR code et posent leurs
questions (programme, speakers, partenaires, infos pratiques) dans une conversation unique,
sur leur téléphone. Les réponses s'appuient sur une base de connaissances et sur le planning en
direct de la régie.

## Par où commencer

| Document | Pour qui, pour quoi |
|---|---|
| [01 — Architecture](01_architecture.md) | Vue d'ensemble : composants, parcours d'une question, données, déploiement |
| [02 — Backend et LLM](02_backend_et_llm.md) | Fonctionnement détaillé du backend, du prompt, de la plateforme LLM, du routeur |
| [03 — Sécurité](03_securite.md) | Menaces, couches de défense, ce qu'elles couvrent ou non, risques résiduels |
| [04 — Fiabilité des réponses](04_fiabilite_des_reponses.md) | Sources de vérité, faits calculés, vérifications, mesure de la qualité |
| [05 — Choix techniques](05_choix_techniques.md) | Décisions prises, alternatives écartées et pourquoi |
| [06 — Exploitation](06_exploitation.md) | Configuration, préparation des données, évaluations, checklist avant l'événement, incidents |
| [07 — Vercel et LAYA](07_vercel_et_laya.md) | Capacités de Vercel, LAYA sans PyTorch : mesures, intégration, test en local, déploiement |
| [08 — LAYA : guide technique](08_laya_guide_technique.md) | Fonctionnement du runtime, modèles, configuration, procédures (test, mesure, parité, seuil, mise à jour, déploiement), dépannage |
| [09 — Journal des évolutions](09_journal_des_evolutions.md) | Ce qui a changé depuis la première version, pourquoi et où |

Documents d'origine : [présentation du projet](presentation_projet.md) et
[TODO / revues](2_TODO.md).

Documentation technique par dossier : [README racine](../README.md),
[backend](../backend/README.md), [outils](../tools/README.md).

## En une phrase par brique

- **Frontend** (React, PWA) : affiche la conversation, transforme les blocs spéciaux des
  réponses en cartes (speaker, session, partenaire) et en suggestions cliquables. Aucune
  logique métier ni secret.
- **Backend** (Flask sur Vercel) : seul point d'accès au LLM ; il filtre, classe, date,
  enrichit et contrôle chaque question et chaque réponse.
- **Plateforme LLM** (WebSocket, modèles Bedrock) : génère la réponse avec recherche dans la
  base de connaissances (RAG).
- **API planning** (régie) : horaires et statut des créneaux du jour, en direct.
- **Outils** (`tools/`) : classeur Excel → base de connaissances Markdown + fiche de périmètre ;
  import LinkedIn (PDF) ; contrôle de cohérence avec le planning.

## Suivi des revues du TODO

| Demande ([2_TODO.md](2_TODO.md)) | Réponse apportée | Détail |
|---|---|---|
| Garde-fou 1 : objectif de la question, rejet poli hors périmètre | Filtre déterministe + routeur (petit modèle) | [03](03_securite.md), [02](02_backend_et_llm.md#4-routeur-garde-fou-n2) |
| Garde-fou 2 : sait-on répondre avec fiabilité ? | Faits calculés, cartes vérifiées, « je ne sais pas » imposé ; vérification par les scores de documents en attente d'un extrait de log de la plateforme | [04](04_fiabilite_des_reponses.md) |
| LAYA / classification d'intention sur CPU | Implémenté en option (runtime ONNX sans PyTorch, parité vérifiée avec le paquet officiel) ; mesuré : utile pour **détecter les manipulations** (version anglaise, seuil 0,8 : 21/32 contre 14/32, 0 faux positif), inutilisable pour juger le périmètre ; déploiement Vercel possible via *Large Functions* | [07](07_vercel_et_laya.md), [05](05_choix_techniques.md#d6-routeur-llm-et-laya-en-complément) |
| Planning à jour via REST | Client avec cache 30 s, statut de la régie prioritaire | [02](02_backend_et_llm.md#6-planning-en-direct) |
| Heure locale imposée par le serveur | Horloge serveur (Europe/Paris), jamais celle du téléphone ni de la question ; jour figé en développement | [02](02_backend_et_llm.md#5-heure-de-référence) |
| Mémoire gérée par le téléphone, tout envoyé | Historique complet envoyé ; plafond de taille côté serveur | [02](02_backend_et_llm.md#7-historique-de-conversation) |
| Langue de réponse imposée par le réglage | Langue de l'interface imposée dans le prompt | [02](02_backend_et_llm.md#8-prompt-système) |
| Détection des jailbreaks, testeurs avertis | Défense en profondeur + jeu d'évaluation | [03](03_securite.md) |
| Messages coupés ou mal formés | Tokens remis dans l'ordre + réponse finale faisant foi | [02](02_backend_et_llm.md#9-client-websocket-et-streaming) |
| Infos bâtiment / plan | À venir : onglet « Lieux » et carte « lieu » avec plan | [05](05_choix_techniques.md#d11-images-et-plans) |
