---
name: synthese-comex
description: "Lit un document (surtout une présentation PowerPoint .pptx, mais aussi PDF, Word ou texte collé) et en tire une diapositive PowerPoint unique de résumé exécutif pour le COMEX ou un comité de direction : message clé, contexte, chiffres clés, enjeux et risques, options, recommandation et décision attendue. Utilise ce skill dès que l'utilisateur veut résumer, synthétiser, condenser ou « faire une one-page / un executive summary / une slide de synthèse » d'un deck ou d'un rapport pour un COMEX, CODIR, comité exécutif, board, direction générale ou des dirigeants, même s'il ne dit pas « COMEX » ni « PowerPoint » explicitement (par ex. « fais-moi la slide pour le comité de lundi à partir de ce deck »)."
---

# Synthèse COMEX en une diapositive

Le but : transformer un document long en **une seule diapositive** qu'un membre du COMEX comprend en 60 secondes et qui lui permet de décider. Le lecteur n'a pas lu le document source et ne le lira pas ; il veut savoir ce qu'on lui demande, pourquoi, combien ça coûte ou rapporte, et ce qui peut mal tourner.

## Déroulé

### 1. Lire tout le document

Pour un `.pptx` :

```bash
python <chemin-du-skill>/scripts/extract_pptx.py source.pptx source.md
```

Le script sort titres, textes, tableaux, données des graphiques, texte alternatif des images et **notes de l'orateur**. Lisez le Markdown en entier, notes comprises : dans beaucoup de decks, le vrai raisonnement (hypothèses, chiffres sous-jacents, réserves) est dans les notes ou les annexes, pas sur les diapos de titre.

Pour un PDF ou un Word, extrayez le texte avec l'outil disponible (`markitdown fichier.pdf`, ou le skill pdf/docx) puis suivez la même démarche.

### 2. Analyser avant d'écrire

Répondez pour vous-même à ces questions, à partir du document seulement :

1. **Quelle décision ou quelle information** le document cherche-t-il à faire passer au COMEX ? Si c'est un document d'information sans demande, la « décision attendue » devient « Prendre acte de… » ou « Valider l'orientation… ».
2. **Quel est le message clé en une phrase**, conclusion d'abord ? (« Lancer X au T2 : +18 M€ pour 6 M€ investis », pas « Point sur le projet X »).
3. **Quels sont les 3-4 chiffres** qui font la décision : montant en jeu, coût, rentabilité/délai, indicateur de performance ou de risque. Préférez les chiffres qui comparent ou qui tranchent.
4. **Quels risques** un dirigeant sceptique soulèverait ? Chiffrez-les quand le document le permet.
5. **Quelles options** ont été envisagées, et laquelle est recommandée ?

Règles de fidélité, parce qu'une synthèse COMEX engage la crédibilité de celui qui la présente :
- N'inventez aucun chiffre et ne recalculez rien qui ne soit pas trivial. Si vous dérivez un chiffre (somme, écart), dites-le dans les notes.
- Si une information clé manque (pas de coût, pas de recommandation, pas d'option), ne la fabriquez pas : laissez le champ facultatif vide, ou écrivez honnêtement « Non chiffré dans le document » et signalez-le à l'utilisateur.
- Si le document se contredit (deux montants différents pour la même chose), retenez le plus récent ou le plus détaillé, et signalez l'écart dans les notes et dans votre réponse.

### 3. Rédiger le contenu

Écrivez un fichier JSON au format décrit dans `references/format_contenu.md` (lisez-le : il donne les champs, les longueurs cibles et un exemple complet).

Style attendu, parce que la place est comptée et que le lecteur survole :
- Phrases courtes, verbes d'action, chiffres plutôt qu'adjectifs (« +12 %/an » plutôt que « forte croissance »).
- Une idée par puce. Pas de jargon interne non expliqué, pas d'acronymes du projet.
- Le titre porte la conclusion ; les blocs la justifient. Un lecteur qui ne lit que le titre et la décision attendue doit avoir compris l'essentiel.
- Rédigez dans la langue du document source, sauf demande contraire.
- Renseignez `instance` avec le nom de l'instance que l'utilisateur emploie (COMEX, CODIR, Board…) : il apparaît dans l'en-tête de la décision et le pied de page.
- Pour chaque chiffre clé avec une tendance, dites si elle est favorable (`tendance_favorable`) : une baisse de coûts est une bonne nouvelle et doit apparaître en vert.
- Si le document compare des options sur des critères chiffrés communs, donnez-leur des `valeurs` : elles s'afficheront en tableau, beaucoup plus lisible pour arbitrer qu'une liste.
- Mettez dans `notes` ce qui est utile à l'oral mais n'a pas sa place sur la diapo : renvois aux diapos sources, hypothèses, réserves, écarts relevés.

### 4. Générer la diapositive

```bash
python <chemin-du-skill>/scripts/build_slide.py contenu.json synthese_comex.pptx --png
```

Le script produit une diapositive 16:9 au format fixe et, avec `--png`, un aperçu image. Nommez la sortie d'après le document (ex. `Synthese_COMEX_<nom-du-document>.pptx`) et enregistrez-la là où l'utilisateur la retrouvera (le répertoire de travail ou celui qu'il a indiqué).

Le script place Contexte, Enjeux et Options avec une taille de police commune et répartit l'espace disponible : s'il n'y a pas d'options, les autres blocs prennent la place. S'il affiche un **AVERTISSEMENT**, traitez-le : un texte trop long se raccourcit dans le JSON (ne laissez pas une zone en petite police, c'est le premier signe d'une synthèse qui n'a pas fait ses choix), une flèche grise signale un `tendance_favorable` manquant. Relancez jusqu'à ne plus avoir d'avertissement.

Après génération, ne retouchez pas la diapositive à la main : si quelque chose ne va pas, corrigez le JSON et relancez, pour que le fichier reste reproductible.

Ouvrez ensuite le PNG et vérifiez : aucun texte coupé ou qui chevauche, titre lisible, chiffres bien en évidence. Corrigez et relancez si besoin.

Si le document source a une charte de couleurs marquée et que l'utilisateur veut la reprendre, renseignez `theme` dans le JSON.

### 5. Rendre compte

Dans votre réponse, en quelques lignes :
- le chemin du fichier `.pptx` produit ;
- le message clé retenu ;
- ce que vous avez dû arbitrer ou ce qui manquait dans le document (chiffres absents, contradictions, recommandation implicite), pour que l'utilisateur sache ce qu'il doit vérifier avant le COMEX.
