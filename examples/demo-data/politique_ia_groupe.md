# Politique d'Utilisation de l'Intelligence Artificielle — Groupe Meridian

**Version 3.2 — Direction des Risques et de la Conformité**

## 1. Gouvernance des modèles

Tout modèle d'IA déployé en production doit être enregistré dans l'inventaire IA du groupe
avec une fiche modèle (model card) complète. Les modèles classés à **haut risque** selon
l'AI Act européen exigent une **validation humaine documentée par un Compliance Officer**
avant toute mise en production. Les modèles à risque prohibé ne peuvent jamais être déployés.

Chaque modèle en production doit conserver une version de repli (rollback) activable en
moins de 15 minutes.

## 2. Maîtrise des coûts

Les budgets de consommation LLM sont fixés **par projet et par mois**. Lorsqu'un projet
atteint 80% de son budget mensuel, le propriétaire du projet et l'équipe plateforme
reçoivent une notification automatique. Au-delà de 100%, les nouvelles requêtes sont
soumises à approbation du responsable de département.

## 3. Protection des données

Les données personnelles (emails, IBAN, numéros de téléphone, numéros de sécurité sociale)
doivent être **automatiquement caviardées** avant tout envoi à un modèle de langage.
Les conversations avec les assistants IA sont conservées 12 mois puis anonymisées.
L'utilisation de modèles hébergés hors de l'Union Européenne requiert l'accord préalable
du Délégué à la Protection des Données (DPO).

## 4. Traçabilité et audit

Chaque interaction avec un système d'IA (requête, réponse, coût, latence, utilisateur,
projet) est journalisée dans une piste d'audit **infalsifiable** (chaînage cryptographique).
Les auditeurs internes et le régulateur peuvent exporter cette piste sur demande.
Les réponses des assistants documentaires doivent citer leurs sources avec un score de
fiabilité ; toute réponse dont le score d'ancrage (groundedness) est inférieur à 70%
doit afficher un avertissement à l'utilisateur.

## 5. Sécurité

Les tentatives d'injection de prompt et de contournement (jailbreak) sont bloquées et
déclenchent une alerte sécurité au-delà de 20 tentatives en 15 minutes. Les clés d'API
des fournisseurs de modèles sont stockées exclusivement dans le gestionnaire de secrets
et font l'objet d'une rotation trimestrielle.
