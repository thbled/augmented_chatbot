# Outils — données de l'événement et base de connaissances

Chaîne de préparation des données :

```
classeur Excel  ──(linkedin-import, optionnel)──▶  classeur complété
      │
      └──(validate)──▶ rapport  ──(build-kb)──▶  kb/*.md  ──▶  base de connaissances du serveur LLM
```

## Installation

```bash
uv sync
cp .env.example .env    # uniquement pour linkedin-import (accès au LLM)
```

## 1. Créer le classeur

```bash
uv run conference-tools template               # crée data/conference.xlsx (avec exemples)
uv run conference-tools template --empty       # sans lignes d'exemple
```

Un modèle prêt à l'emploi est aussi disponible :
[`templates/modele_conference.xlsx`](templates/modele_conference.xlsx).

| Onglet | Contenu |
|---|---|
| Instructions | Mode d'emploi |
| Événement | Nom, dates, lieu, contact, thématiques… (une valeur par ligne) |
| Speakers | Prénom*, Nom*, URL LinkedIn, **Consentement*** (Oui/Non), date du consentement, URL photo, entreprise, poste, biographie, expertises |
| Programme | Date*, Début*, Fin*, Titre*, format, salle, thématique, speakers, description, mots-clés, langue |
| Partenaires | Nom*, niveau, logo, site web, secteur, présentation, offre, stand |
| Infos pratiques | Catégorie*, Question*, Réponse* |

Les en-têtes portent une aide (commentaire), les colonnes à choix ont une liste déroulante.
Listes : valeurs séparées par `;`. Colonne *Speakers* du programme : « Prénom Nom » ou identifiant.

**Consentement** : sans « Oui », le speaker n'apparaît que par son nom dans le programme
(pas de fiche, pas de bio, pas de photo, pas de LinkedIn).

**Images** : URL `https://…`, ou fichiers déposés dans `frontend/public/images/speakers/`
et `frontend/public/images/partners/`, référencés par `/images/speakers/prenom-nom.jpg`.
Format carré conseillé pour les photos (≥ 400×400 px), logos en SVG ou PNG transparent.

## 2. (Optionnel) Pré-remplir les speakers depuis LinkedIn

Pas de scraping : on part de l'export PDF du profil (sur LinkedIn : *Plus* → *Enregistrer au
format PDF*), récupéré avec l'autorisation écrite du speaker.

```bash
# PDF nommés prenom-nom.pdf (ou contenant ce nom), photos nommées prenom-nom.jpg
uv run conference-tools linkedin-import --pdf-dir linkedin_pdfs --dry-run
uv run conference-tools linkedin-import --pdf-dir linkedin_pdfs
```

- Seuls les speakers avec consentement « Oui » sont traités.
- Seules les cellules vides sont remplies (`--overwrite` pour remplacer).
- Le LLM extrait poste, entreprise, biographie (FR, 3ᵉ personne) et expertises.
- Les photos trouvées dans `frontend/public/images/speakers/` sont référencées automatiquement
  (`--photos-dir` pour un autre dossier). Le PDF LinkedIn ne contient pas la photo.
- **Relisez** toujours les textes générés avant publication.

## 3. Vérifier puis générer la base de connaissances

```bash
uv run conference-tools validate
uv run conference-tools build-kb --out kb
```

Le dossier `kb/` (vidé à chaque génération) contient :

| Fichier | Rôle |
|---|---|
| `evenement.md` | Informations générales |
| `programme.md` | Programme complet par jour (tableau) et par thématique |
| `speakers.md`, `partenaires.md` | Listes récapitulatives |
| `infos_pratiques.md` | Questions / réponses pratiques |
| `speakers/speaker_<id>.md` | Une fiche par speaker publié |
| `sessions/session_<id>.md` | Une fiche par session |
| `partenaires/partenaire_<id>.md` | Une fiche par partenaire |
| `assistant.md`, `documentation/*.md` | Documents rédigés de [`kb_static/`](kb_static) |

Chaque fiche se termine par un bloc ` ```speaker `, ` ```session ` ou ` ```partner ` contenant
le JSON de la carte. Le LLM le recopie tel quel et l'application l'affiche en carte visuelle
(photo, horaires, boutons). Le format est défini dans
[`models.py`](src/conference_tools/models.py) et
[`frontend/src/types/cards.ts`](../frontend/src/types/cards.ts).

Chargez ensuite le contenu de `kb/` dans la base de connaissances du serveur LLM. Conseil :
un document = un fragment (chunk) si le serveur le permet, pour garder chaque fiche entière.

## Base documentaire

Ajoutez vos documents thématiques (Markdown) dans
[`kb_static/documentation/`](kb_static/documentation). Ils sont copiés dans `kb/`.
[`kb_static/assistant.md`](kb_static/assistant.md) décrit l'assistant et ses capacités.

## Qualité

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```
