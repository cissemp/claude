# Agent Presse

Routine automatisée qui génère une revue de presse quotidienne et l'envoie par email.

## Fonctionnement

- **Fréquence** : tous les jours à 7h30 (Europe/Paris)
- **Destinataire** : mohamed.cisse@gmail.com
- **Envoi d'email** : via le connecteur MCP Brevo (`https://mcp.brevo.com/v1/anthropic/mcp`), avec repli sur l'API transactionnelle Brevo en HTTP direct si le connecteur MCP est indisponible
- **Contenu** : revue de presse structurée en 5 thématiques (voir "Prompt de la revue" ci-dessous)

## Configuration Brevo

### Méthode principale : connecteur MCP Brevo

La routine cloud a un connecteur MCP Brevo rattaché (visible dans `mcp_connections` de la routine, nom `Brevo`, url `https://mcp.brevo.com/v1/anthropic/mcp`). C'est la méthode d'envoi privilégiée : elle passe par un canal MCP authentifié plutôt que par un appel HTTP sortant classique, ce qui contourne les restrictions réseau (egress) de l'environnement cloud qui bloquent les appels `curl` directs vers `api.brevo.com`.

La routine doit chercher l'outil correspondant (ex. via une recherche d'outils avec un mot-clé comme "brevo") et l'utiliser pour envoyer l'email à mohamed.cisse@gmail.com avec le sujet et le contenu HTML générés.

**Méthode confirmée fonctionnelle (test du 13/08/2026, réponse 204)** : Brevo n'expose pas d'outil MCP d'envoi transactionnel direct à un destinataire arbitraire. Le contournement qui fonctionne consiste à :
1. Créer un template SMTP avec le HTML de la revue via `mcp__Brevo__templates_create_smtp_template` (retourne un `id` de template)
2. Envoyer ce template au destinataire via `mcp__Brevo__templates_send_test_template` avec `{"emailTo": ["mohamed.cisse@gmail.com"], "templateId": <id>}`

Le sujet et l'expéditeur du template sont définis à la création du template SMTP (`templates_create_smtp_template` accepte aussi `subject`, `sender`, `templateName`, etc.).

### Méthode de repli : API HTTP directe

Les identifiants sont stockés dans `.env` (fichier non versionné, voir `.gitignore`) :

- `BREVO_API_KEY` — clé API v3 Brevo
- `BREVO_SENDER_EMAIL` — mohamed.cisse@gmail.com (adresse expéditrice validée dans Brevo)
- `BREVO_SENDER_NAME` — nom d'expéditeur affiché ("Revue de presse")

**Ne jamais écrire la clé API en clair dans ce fichier ou dans le code.** Toujours la lire depuis `.env` / une variable d'environnement.

⚠️ Cette méthode a échoué lors des tests (403 Forbidden) car l'environnement cloud de la routine bloque les connexions sortantes vers `api.brevo.com` qui ne sont pas sur sa liste blanche réseau. Elle ne doit être tentée qu'en repli, si le connecteur MCP Brevo n'est pas disponible.

Endpoint : `POST https://api.brevo.com/v3/smtp/email`

Exemple d'appel (curl) :

```bash
curl -s -X POST "https://api.brevo.com/v3/smtp/email" \
  -H "api-key: $BREVO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sender": {"name": "'"$BREVO_SENDER_NAME"'", "email": "'"$BREVO_SENDER_EMAIL"'"},
    "to": [{"email": "mohamed.cisse@gmail.com"}],
    "subject": "Revue de presse du JJ/MM/AAAA",
    "htmlContent": "<html><body>...</body></html>"
  }'
```

## Prompt de la revue

### MISSION

Utilise l'outil de recherche web pour identifier les actualités les plus récentes (moins de 48 heures) et pertinentes sur chacune des 5 thématiques suivantes. Effectue une recherche ciblée et distincte par thématique (adapte les mots-clés si les premiers résultats sont trop anciens ou hors sujet) :

1. **Actualités Internationales** – grands titres mondiaux du jour (géopolitique, conflits, diplomatie, événements majeurs)
2. **Actualités France** – politique, économie, société française
3. **République de Guinée** – actualités de Guinée-Conakry (politique, économie, transition, société)
4. **Énergie & ENEDIS** – marché de l'énergie, électricité, transition énergétique, actualités ENEDIS/RTE
5. **IT & Intelligence Artificielle** – tendances tech, nouveaux modèles d'IA, levées de fonds, régulation, startups

### CONSIGNES DE RÉDACTION

- Pour chaque thématique, rédige exactement 5 points clés en français, factuels, synthétiques (un résumé synthétique). 
- Privilégie les informations datées d'aujourd'hui ou d'hier ; si rien de très récent n'existe sur un sujet, indique l'actualité la plus pertinente disponible sans inventer de faits.
- N'invente jamais de chiffres, noms ou événements : si une recherche ne donne rien d'exploitable, formule un point neutre du type "Aucune actualité majeure rapportée sur ce sujet aujourd'hui."
- Détermine le champ "tendance" pour chaque catégorie selon le ton dominant des actualités trouvées : "hausse", "baisse" ou "neutre" (n'utilise pas de valeur par défaut fixe, évalue-la à chaque fois).
- L'éditorial global doit être une synthèse de 2 phrases maximum, reliant si pertinent plusieurs thématiques entre elles.
- Pour chaque point (sauf les points neutres sans source, ex. "Aucune actualité majeure..."), conserve l'URL de l'article source utilisé (issue des résultats de recherche web) afin de l'inclure comme lien en fin de point dans le HTML.

### Mise en forme HTML — liens sources

Chaque point se termine par un lien hypertexte vers l'article source complet (ex. texte de lien "Lire l'article complet →", pointant vers l'URL de la source). Un point neutre sans source disponible n'a pas de lien.

## Planification

Routine planifiée quotidienne à 7h30 (Europe/Paris) qui :

1. Exécute la recherche web et génère la revue de presse selon le prompt ci-dessus (5 thématiques × 5 points + tendance + éditorial global), en conservant l'URL source de chaque point
2. Formate le contenu en HTML lisible (email), chaque point se terminant par un lien vers l'article source complet
3. Envoie l'email à mohamed.cisse@gmail.com via le connecteur MCP Brevo (méthode principale), avec repli sur l'API HTTP Brevo en cas d'indisponibilité du connecteur
