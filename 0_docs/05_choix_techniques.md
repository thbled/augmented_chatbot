# 05 — Choix techniques

Chaque décision suit le format : contexte, décision, alternatives écartées, conséquences.

### D1. Un seul projet Vercel (frontend statique + fonction Python)

- **Contexte** : hébergement imposé sur Vercel ; trafic concentré sur une journée.
- **Décision** : frontend React servi en statique, backend Flask en fonction Python
  (`api/index.py`), même domaine.
- **Alternatives** : deux hébergements séparés (CORS, deux déploiements) ; serveur dédié avec
  Docker (plus de liberté, mais à administrer).
- **Conséquences** : pas de CORS, déploiement unique. Contraintes : durée de la fonction
  (fixée à 60 s dans `vercel.json`, jusqu'à 300 s autorisés en Hobby, 800 s en Pro) partagée
  entre routeur, planning et réponse ; mémoire propre à chaque instance (Redis nécessaire pour
  une limite par IP partagée) ; CPU uniquement, 2 Go en Hobby et 4 Go en Pro (un modèle comme
  LAYA n'y tient qu'en version compressée, voir [07](07_vercel_et_laya.md)) ; région par
  défaut aux États-Unis ; l'offre Hobby est réservée à un usage non commercial.

### D2. Le backend, seul point d'accès au LLM

- **Contexte** : clé d'API à protéger ; règles et contrôles à appliquer à chaque échange.
- **Décision** : le téléphone appelle uniquement `/api/chat` ; le backend ajoute heure,
  planning, prompt, garde-fous et contrôle de sortie.
- **Alternative** : appel direct depuis le navigateur — clé exposée, aucun contrôle possible.
- **Conséquences** : toute la logique de confiance est côté serveur ; le frontend reste simple.

### D3. SSE vers le téléphone, WebSocket vers la plateforme

- **Contexte** : afficher la réponse au fil de l'eau ; la plateforme LLM expose une API
  WebSocket.
- **Décision** : flux SSE (HTTP) entre téléphone et backend ; WebSocket entre backend et
  plateforme. Un événement `replace` permet d'envoyer le texte final faisant foi.
- **Alternative** : WebSocket jusqu'au navigateur — non supporté par les fonctions Vercel.
- **Conséquences** : compatible Vercel ; possibilité de corriger l'affichage en fin de réponse
  (ordre des tokens, contrôle de sortie).

### D4. Connaissances dans la base de la plateforme, cartes recopiées par le LLM

- **Contexte** : souhait de tout centraliser dans la base de connaissances vectorisée ; besoin
  d'un affichage riche (photo, bio, horaires).
- **Décision** : chaque fiche de la base contient le JSON de sa carte ; le LLM le recopie dans un
  bloc ` ```speaker `, ` ```session ` ou ` ```partner ` ; le frontend l'affiche.
- **Alternative écartée** : données structurées servies par une API et cartes affichées par
  identifiant (`[[speaker:ada]]`) — plus robuste et plus économe, mais duplique la source.
- **Conséquences** : plus de tokens générés (textes des cartes bornés : bio 600 caractères,
  résumé 240) ; risque de carte inventée, couvert par la vérification contre `scope.json` ;
  cartes compactées dans l'historique envoyé au LLM.

### D5. Planning du jour via l'API de la régie

- **Contexte** : horaires susceptibles de bouger le jour J ; la base de connaissances est figée.
- **Décision** : le backend lit l'API de la régie (cache 30 s) ; elle fait foi pour les
  horaires et le statut ; la base apporte le détail.
- **Conséquences** : réponses à jour ; contrôle de cohérence nécessaire entre les deux
  (`check-planning`) ; en développement, décalage des données de test sur le jour simulé.

### D6. Routeur LLM, et LAYA en complément

- **Contexte** : besoin d'un garde-fou qui classe la question avant le modèle principal.
  LAYA (classifieur non génératif, ModernBERT, probabilités calibrées) a été étudié.
- **Décision** : petit modèle de la plateforme (`amazon.nova-lite-v1:0`), appelé sans RAG,
  encadré par le code (seuil, noms connus, reformulation vérifiée, passage en cas de panne),
  pour le **périmètre** et la **reformulation**. **LAYA en option**, uniquement pour la
  **détection des manipulations** (version anglaise, seuil 0,8), avec un runtime ONNX écrit
  pour se passer de PyTorch. Le choix découle des mesures de [07](07_vercel_et_laya.md).

| Critère | LAYA | Routeur LLM actuel |
|---|---|---|
| Résistance à l'injection | meilleure (ne suit pas d'instructions) | plus faible (c'est un LLM) |
| Confiance | calibrée | déclarée |
| Latence / coût | ~0,1–0,5 s sur CPU, gratuit | ~1–2 s, payant à l'appel |
| Français | non évalué publiquement | à mesurer |
| Reformulation de la question | impossible | oui |
| Hébergement | dans le backend ; sur Vercel via *Large Functions* (~610 Mo) ou service séparé | aucun |
| Mesuré : manipulations détectées (avec le filtre) | 21/32, 0 faux positif sur 36 | à mesurer sur la plateforme |
| Mesuré : jugement du périmètre | inutilisable sans entraînement (4 à 14 faux refus sur 15) | oui |

- **Conséquences** : les deux sont complémentaires — LAYA ne se laisse pas convaincre par
  le texte (il ne suit pas d'instructions) mais ne sait pas juger le périmètre ; le routeur juge
  le périmètre et reformule, mais reste un LLM manipulable. LAYA est désactivé par défaut et ne
  tient pas dans une fonction Vercel standard (500 Mo) : déploiement via *Large Functions*,
  téléchargement au démarrage ou service séparé ([07](07_vercel_et_laya.md#5-déployer-laya-sur-vercel)).
  Piste : un entraînement spécifique de LAYA sur nos exemples pour gagner en précision.

### D7. Horaires calculés par le code, pas par le LLM

- **Contexte** : « que se passe-t-il à 15h12 ? » exige une comparaison d'heures sur une liste
  de créneaux ; les LLM s'y trompent régulièrement.
- **Décision** : reconnaissance des expressions horaires par expressions régulières (FR/EN) et
  calcul du créneau par le backend ; le LLM ne fait que formuler.
- **Alternative** : demander l'heure normalisée au routeur — dépendance à un modèle pour une
  tâche déterministe.
- **Conséquences** : réponses horaires exactes si les données le sont ; les formulations non
  reconnues retombent sur le comportement du LLM.

### D8. Filtre déterministe en plus du routeur

- **Décision** : motifs FR/EN appliqués avant tout appel, sans coût ni latence.
- **Conséquences** : bloque les attaques les plus courantes même si le routeur est contourné ou
  en panne ; motifs conservateurs pour éviter les faux refus.

### D9. Mémoire gérée par le téléphone

- **Décision** : conversation stockée sur le téléphone et envoyée en entier ; plafond de taille
  côté serveur ; cartes compactées dans la copie envoyée au LLM ; `sessionId` aléatoire par
  requête (la plateforme ne garde rien).
- **Conséquences** : aucune donnée de conversation côté serveur ; requêtes plus volumineuses
  (limite de corps portée à 2 Mo).

### D10. Pas d'authentification, données minimales

- **Contexte** : accès par QR code, usage d'une journée, RGPD à minimiser.
- **Décision** : pas de compte ni de cookie ; limite par IP (empreinte salée), budget de la
  plateforme ; journaux anonymes.
- **Conséquences** : quiconque a l'URL peut utiliser l'assistant ; coût borné par la limite et
  le budget.

### D11. Images et plans

- **Contexte** : la base de connaissances n'indexe que du texte.
- **Décision** : images hébergées comme fichiers statiques (`frontend/public/images/…`) ou sur
  des domaines autorisés ; la base ne contient que leur URL (comme les photos de speakers).
  Prévu : onglet « Lieux » dans le classeur, carte « lieu » affichant le plan (une image, un
  seul niveau) avec un repère positionné par coordonnées, description textuelle pour la
  recherche (« où sont les toilettes ? »).
- **Conséquences** : aucune image ne transite par le LLM ; les URL d'images sont limitées aux
  domaines autorisés (sécurité).

### D12. Comportement en cas de panne

- **Décision** : routeur en panne → la question passe ; fuite du prompt → réponse coupée ;
  planning en panne → dernière copie valide ; plateforme en erreur → message générique.
- **Conséquences** : disponibilité privilégiée pour les contrôles « intelligents »,
  sécurité privilégiée pour les fuites.

### D13. Modèles

- **Routeur** : `amazon.nova-lite-v1:0` (rapide, peu coûteux) ; repli possible sur Gemma 3 12B
  si la précision en français est insuffisante.
- **Modèle principal** : configurable (`LLM_MODEL`). Devstral est spécialisé dans le code ; un
  modèle généraliste solide en français (par exemple Mistral Large 3 : 675 Md de paramètres au
  total, 41 Md actifs par token) est à comparer avec le jeu d'évaluation.

### D14. Données : classeur Excel et import LinkedIn par PDF

- **Décision** : un classeur unique (événement, speakers, programme, partenaires, infos
  pratiques) transformé en base de connaissances par les outils. Profils LinkedIn : export PDF
  fourni ou téléchargé avec l'autorisation écrite du speaker, structuré par le LLM ; **pas de
  scraping** (interdit par les conditions de LinkedIn).
- **Conséquences** : consentement tracé dans le classeur ; textes générés à relire ; contrôle
  des contenus suspects à la génération.

### D15. Outillage

- Frontend : React 19, TypeScript, Vite, Tailwind CSS 4, axios, i18next, Vitest, oxlint,
  Prettier ; PWA.
- Backend et outils : Python 3.12, uv, Flask, ruff, pytest.
- Tests unitaires et d'intégration sur chaque brique ; jeu d'évaluation sur la vraie
  plateforme pour ce que les tests ne peuvent pas couvrir (comportement du modèle).
