# Prompt Engineering — les choix de conception

Ce document explique *pourquoi* les prompts de SupplyChainGPT sont écrits comme ils le sont.
Chaque décision répond à un mode d'échec observé du text-to-SQL.

---

## 1. Le raisonnement AVANT le SQL dans le schéma de sortie

Le contrat JSON impose l'ordre `raisonnement` → `hypotheses` → `sql`. Ce n'est pas cosmétique :
un modèle autorégressif génère les champs dans l'ordre. En le forçant à écrire d'abord
« TS au grain ligne de commande, filtre mois courant, lignes livrées uniquement », le SQL qui
suit est conditionné par cette décision explicite. C'est un chain-of-thought structuré,
sans balise `<thinking>` à parser, et l'UI en tire gratuitement une trace d'audit.

## 2. Les hypothèses comme fonctionnalité, pas comme aveu

« Ce mois » = mois calendaire ou 30 jours glissants ? Toute question métier réelle contient
un choix de ce type. Plutôt que de trancher en silence (dangereux) ou de demander à chaque
fois (épuisant), le contrat impose : trancher selon l'usage métier dominant ET documenter le
choix dans `hypotheses[]`. L'UI les affiche sous le résultat — l'utilisateur corrige en une
relance s'il voulait autre chose. C'est le compromis exact entre fluidité et fiabilité.

## 3. Un router d'intention plutôt qu'un générateur naïf

Le modèle classe chaque question : `sql`, `clarification` ou `hors_perimetre`, avec un score
de confiance et une règle dure : **confiance < 0.6 → clarification**. Le prompt le formule en
termes métier : « le faux chiffre part en COPIL et coûte plus cher que la question de
clarification ». Donner au modèle la *raison économique* de la règle produit des refus
mieux calibrés que la règle seule.

## 4. La couche sémantique générée, jamais dupliquée

Les formules de KPI ne vivent PAS dans le prompt : elles vivent dans `src/semantic_layer.py`
(définition, formule canonique, synonymes terrain, pièges), et le prompt est assemblé au
runtime par `build_system_prompt()`. Conséquences :

- corriger une formule met à jour le prompt, la doc et l'agent Claude Code d'un coup ;
- les évals peuvent vérifier que chaque métrique déclarée est couverte ;
- le prompt versionné dans git reste un template lisible, le contenu vivant est du code testé.

## 5. Le schéma injecté avec les VALEURS réelles

`get_schema_context()` n'injecte pas que les colonnes : il échantillonne les valeurs des
colonnes catégorielles (`statut: 'livree', 'partielle', 'en_cours'…`, `motif_ecart: …`) et la
volumétrie de chaque table. La moitié des hallucinations de filtres WHERE (`statut = 'delivered'`)
disparaît quand le modèle voit les vraies valeurs.

## 6. Des few-shots qui enseignent les PIÈGES, pas la syntaxe

Claude sait écrire un GROUP BY. Les six exemples du prompt sont donc choisis pour couvrir les
modes d'échec spécifiques à CETTE base :

| Exemple | Ce qu'il enseigne |
|---|---|
| pires TS du mois | formule canonique + hypothèse « mois calendaire » explicitée |
| évolution hebdo + variation | CTE + `LAG()` — fenêtrage SQLite |
| mois courant vs précédent | agrégation conditionnelle `CASE` au lieu d'une auto-jointure fragile |
| « quels entrepôts saturent ? » | reconstruire une notion métier absente du schéma, en déclarant l'approximation (confiance 0.7) |
| « c'est quoi la performance ? » | clarification : UNE question fermée avec options |
| « supprime les commandes… » | refus net + alternative en lecture |

Le dernier point compte double : chaque refus few-shot **propose une alternative** — le modèle
apprend à refuser sans être inutile.

## 7. La procédure de décision : une checklist, pas des interdits

La section « Procédure de décision » du prompt (périmètre → grain → période → fan-out → NULL →
lisibilité) est ce qu'un senior fait relire à un junior. Formuler les gardes-fous en étapes de
raisonnement (« ma jointure multiplie-t-elle les lignes ? ») est plus robuste que des interdits
(« ne jamais sommer nb_colis après jointure ») car la checklist se généralise aux cas non prévus.

## 8. Le prompt de réparation est un prompt de DIAGNOSTIC

`fix_prompt.md` n'est pas « corrige cette requête » : c'est un arbre de diagnostic ordonné
(colonne hallucinée → dialecte SQLite → ambiguïté → grain), avec deux règles anti-obstination :
ne jamais supprimer une jointure ou un filtre juste pour faire passer la requête (le résultat
serait faux *en silence*), et abandonner proprement en `clarification` à la 2ᵉ tentative.

## 9. Préfixe assistant `{` + prompt caching

Deux détails d'implémentation dans `src/llm.py` :

- la conversation est pré-remplie avec un tour assistant `"{"` : la réponse ne peut être que
  du JSON, sans mode dédié ni parsing défensif lourd ;
- le system prompt (~3 500 tokens : contrat + schéma + couche sémantique + few-shots) porte
  un `cache_control: ephemeral` — en usage interactif, il n'est facturé en entrée pleine
  qu'une fois toutes les 5 minutes.

## 10. Les évals notent l'ÉQUIVALENCE d'exécution, pas la forme

`tests/run_evals.py` compare le **résultat** du SQL généré à celui d'un SQL de référence
(ensembles de lignes, insensible à l'ordre, aux alias et aux arrondis) — le standard
*execution accuracy* du text-to-SQL. Deux requêtes différentes qui donnent le même résultat
sont toutes deux justes ; une requête élégante qui donne un chiffre faux échoue. Le jeu de
tests est stratifié : `facile` (régression de base), `difficile` (fenêtrage, comparaison de
périodes), `piege` (snapshot, fan-out — les erreurs qui produisent des chiffres plausibles
et faux), `comportement` (clarification et refus — un text-to-SQL se juge aussi sur ce qu'il
refuse de faire).
