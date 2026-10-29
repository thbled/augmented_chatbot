
# Idées  :

	• Prendre la question 
	• Guard rail 1 :
		○  (LAYA ? ) On détermine le but, l'objectif de la question (routeur + décision model ) si c'est hors scope on rejette poliment 
	• Guard rail 2 : 
		○ (LAYA ? ) On prend la question du user et on cherche dans nos sources et Knowledge base si on sait répondre avec fiabilité
		○  liste de speaker, programme, aide, … toute la knowledge base
		○ si le pourcentage est élevée alors on répond sinon on demande précision ou dit clairement qu'on le sais pas répondre avec certitude à cette question 
	
Question user => Laya (objectif question en accord avec salon ?) => Laya + recherche knowledge base (a-t-on vraiment l'information exactement demandé ou il faut des précision ou alors dire qu'on ne sait pas) => si ok et tout vert alors on répond avec le LLM en augmentant ses connaissance de la donnée recherchée 

Idée de rajout tech sur CPU : 
	• LAYA
	• RASA ou autres (classification d'intention ? )
 Exemple d'architecture technique LAYA ? 
Utilisateur → [Authentification] → [LAYA : Validation de l'objectif]
       ↓
[Recherche RAG : Knowledge Base approuvée]
       ↓
[LAYA : Vérification de la pertinence/précision]
       ↓
[LLM : Génération de la réponse + Guardrails]
       ↓
[Logging : Enregistrement anonymisé]





# Rajout / Amélioration : 
	• A la session (tel) on fait un call api pour aller chercher le planning à jour de l'event via : une requête REST
	• Le prompt et le message du user doivent être toujours préfixé de l'heure locale pour avoir connaissance de l'heure actuelle et il ne se base que sur la valeur system coté backend (heure paris), l'utilisateur ne peux pas décider de la changer (par prompting ou autre)
	• La mémoire de la conversation est géré entièrement pas le téléphone et tout est envoyé à chaque fois pour ne pas perdre de contexte. 
	• Le prompt system doit avoir le type de langue choisit dans la réponse comme contrainte (on se base sur son réglage) 
	• Guard rails :
		○ Le prompt system doit avoir les bonnes règles de safe guard 
		○ Le model ne doit pas inventer ou mentir ou haluciner (Utilisation de LAYA peut gérer ca ? )
		○ Le model doit detecter les tentatives de jailsbreak ou autre et refuser poliment
		○ Le chatbot va sans doute être testé par des personnes fortement avertis, il faut donc de bon guardrails, bon prompt system, bonne contrainte, model décisionnel … 
		○ Le schéma et autres est peut-être à revoir car ça plante des fois quand même (mauvais affichage, …)
	• l'utilisateur pourra demander des informations sur le batiments ou où sont tel ou tel chose ? 
		○ On pourrait soit lui répondre soit lui afficher une image d'un plan ou autre
	• Parfois les messages ne sont pas entier (coupé au début ou à la fin, mal formaté ou étrange comme le montre l'échange si dessous : 
		○ User : What are the ongoing activities?
		○ LLM : At 14:52, there are no ongoing sessions or activities listed in 2026, at 11:34, titled " the program. The next session is scheduled for tomorrow, November 18,ATLASSIAN: New ways of Working avec l'IA" [Doc
	
		
