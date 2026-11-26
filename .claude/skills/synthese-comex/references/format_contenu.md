# Format du fichier de contenu (JSON)

`scripts/build_slide.py` lit ce JSON et place chaque champ dans une zone fixe de la diapositive.
Les longueurs indiquées sont celles qui tiennent confortablement en 12-13 pt ; au-delà, le script
réduit la police puis affiche un AVERTISSEMENT.

| Champ | Obligatoire | Contenu | Longueur cible |
|---|---|---|---|
| `titre` | oui | Le message clé, rédigé comme une phrase-action qui contient la conclusion et le chiffre principal. Pas un intitulé de sujet. | ≤ 110 caractères |
| `sous_titre` | non | « Synthèse de « <titre du document> » (<auteur/direction>, <n> diapos) — COMEX du <date> » | ≤ 110 car. |
| `contexte` | oui | 2-3 puces : pourquoi le sujet arrive au COMEX maintenant | ≤ 110 car. / puce |
| `enjeux_risques` | oui | 2-4 puces, chacune chiffrée quand le document le permet (montant, délai, probabilité) | ≤ 110 car. / puce |
| `options` | non | 2-3 objets `{ "nom": "A — Libellé court", "detail": "coût, gain, contrepartie" }`. Omettre si le document n'en présente pas. | `detail` ≤ 80 car. |
| `option_recommandee` | non | Index (0, 1, 2) de l'option recommandée dans `options` ; ajoute « (recommandée) » | — |
| `chiffres_cles` | oui | 3-4 objets `{ "valeur": "18 M€", "libelle": "…", "tendance": "hausse" \| "baisse" \| "neutre" }`. Ajouter `"tendance_favorable": false` quand une hausse est mauvaise (coûts, churn) pour afficher la flèche en rouge. | `valeur` ≤ 8 car., `libelle` ≤ 50 car. |
| `recommandation` | oui | Ce que l'équipe propose, en une ou deux phrases, avec les conditions éventuelles (jalons, go/no-go). | ≤ 220 car. |
| `decision_attendue` | oui | La question précise posée au COMEX, formulée comme une action : « Valider… », « Arbitrer entre… », « Prendre acte de… ». | ≤ 120 car. |
| `source` | non | « Source : <document>, <auteur>, <date> » | ≤ 100 car. |
| `confidentialite` | non | Mention de pied de page. Défaut : « Confidentiel — COMEX » | — |
| `notes` | non | Notes de l'orateur : détails utiles à l'oral, renvois aux diapos sources, points d'attention et hypothèses du rédacteur. | libre |
| `theme` | non | `{ "primaire": "1F3864", "accent": "C55A11" }` en hexadécimal sans `#`, pour reprendre la charte du document source. | — |

## Exemple

```json
{
  "titre": "Lancer l'offre Pro en Europe du Nord dès T2 2027 : +18 M€ de CA à 3 ans pour 6 M€ investis",
  "sous_titre": "Synthèse de « Plan d'expansion Nordics v3 » (Direction Stratégie, 24 diapos) — COMEX du 10/12/2026",
  "contexte": [
    "Le marché nordique croît de 12 %/an et nos 3 concurrents directs y sont déjà implantés.",
    "Le pilote suédois (6 mois, 40 clients) a atteint 92 % de rétention."
  ],
  "enjeux_risques": [
    "Fenêtre concurrentielle : au-delà de 2027, coût d'acquisition client estimé ×2.",
    "Risque d'exécution : recrutement de 25 ETP locaux en 9 mois.",
    "Change SEK/NOK : ±1,5 M€ d'impact sur l'EBITDA 2028."
  ],
  "options": [
    { "nom": "A — Ouverture directe", "detail": "filiale + équipe locale, 6 M€, rentable 2029" },
    { "nom": "B — Partenariat distributeur", "detail": "1,5 M€, marge −40 %, peu de contrôle client" },
    { "nom": "C — Report à 2028", "detail": "0 € mais perte de la fenêtre" }
  ],
  "option_recommandee": 0,
  "chiffres_cles": [
    { "valeur": "18 M€", "libelle": "CA additionnel cumulé à 3 ans", "tendance": "hausse" },
    { "valeur": "6 M€", "libelle": "Investissement total" },
    { "valeur": "2,4 ans", "libelle": "Délai de retour sur investissement" },
    { "valeur": "92 %", "libelle": "Rétention du pilote suédois", "tendance": "hausse" }
  ],
  "recommandation": "Option A : ouvrir une filiale à Stockholm au T2 2027, avec un go/no-go à T4 2027 sur l'objectif de 150 clients.",
  "decision_attendue": "Valider l'enveloppe de 6 M€ et nommer le sponsor COMEX du projet.",
  "source": "Source : Plan d'expansion Nordics v3, Direction Stratégie, nov. 2026",
  "notes": "Marché : diapos 4-9. Business plan : diapos 12-15. Hypothèse de change non sensibilisée dans le document."
}
```
