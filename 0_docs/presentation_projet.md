
# Présentation du projet : 
Le projet est de faire un chatbot augmenté (avec un pseudo RAG déjà connecté à un LLM sur un endpoint accessible via url / tokens). 
L'application sera hébergé sur vercel (frontend et backend). 
l'utilsateur scannera un QR code pour être redirrigé sur l'application qui sera êtremement bien conçu d'un point de vue : UX/UI, responsive (97% utilisation sur tel), suivie thème dark/light, langue : FR/EN, RGAA.
Le but est un chatbot augmenté qui permettra aux utilisateur via une seule conversation, s'informer sur des conférences : 
- speakers (affichage photo + bio + détail, epxertise,), consultation de sa fiche et information
- programme de la journée (heure / speaker / conférences), demande d'information, répondre aux questions sur le programme
- recommendation de speaker ou conférence / création d'un planning en fonction de centre d'intéret, etc.
- bio partenaire (entreprise, url, bio, activité, ... )
- suggéstion de questions à poser ou alors d'approfondissement d'un sujet (pour s'informer sur le sujet de la conférence)



# frontend 
React, responsive, voir PWA mais on se servira pas des uploads (aucun upload autorisé), une page simple : 
chatbot, une conversation.
oxlint, pretierc, TU, axios, call backend flask pour LLM, pas d'authentification user.
librairie de composant, on réinvente la roue.

# backend 
python flask, auth uniquement l'application LLM (pas call direct), il doit permettre de faire le pont entre l'appli frontend (react) et le LLM exposant une communication via URL + api key, de type openAI compatible. ruff, TU, etc.


# tools
- permet la collecte de donnée pour le RAG pour avoir des informations sur des speakers depuis leur compte linkedin : fichier input xls : nom,Prénom et lien linkedin


# rag LLM
une knowledge base sera cablé directement sur le serveur LLM (qui lui est déjà fait et ne sera intérrogeable que par call api depuis le backend python.)
il sera composé des données des : 
- speaker
- du programme 
- des partenaires
- base documentaires sur certains sujet spécifiques ou particularité technique sur un sujet
- informations pratiques
- information sur le chatbot et ses capacité 

Le model doit être limité dans un domaine professionnel, si possible toute question en lien avec les différents sujets pro traité dans le salon (pas de perso, pas chose non pro.), vocabulaire professionel, répondre solide et intelligente, proposition de questions ou d'axes de réflection types chips à cliquer. 
Intelligence : reformulation interne de la questions, développer davantage dans les réponse (penser à la question suivante ... )

