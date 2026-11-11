# Repères techniques

Le [README](README.md) décrit le parcours de démonstration, la convention du taux de service et les commandes de démarrage.

## Tables sources

| Table | Grain et champs principaux |
| --- | --- |
| `fournisseurs` | Un fournisseur par identifiant, code et nom |
| `entrepots` | Un entrepôt par identifiant, code et nom |
| `produits` | Une référence par EAN et code GESCOM, avec fournisseur, catégorie, conditionnement et prix d’achat |
| `commandes` | Une commande par numéro, avec fournisseur, entrepôt, dates de commande et de livraison, statut et volumes en colis |
| `lignes_commande` | Une ligne de commande avec référence, quantités en unités, prix unitaire et motif éventuel |
| `stocks` | Une observation produit × entrepôt × date de snapshot, avec stock, couverture et indicateurs de rupture et SLOB |

## Calculs

Pour la revue de service, `src/service_review.py` contient la requête et les paramètres affichés à l’écran. Le jeu de données porte sur des lignes de réception. L’unité de prise de décision est le fournisseur de la commande. Une surlivraison est plafonnée à la quantité commandée sur chaque ligne.

Pour l’analyse des stocks, sélectionner une seule date de snapshot pour valoriser un encours. Sur les données fictives, `flag_rupture` traduit un stock disponible nul et `flag_slob` une couverture supérieure à 90 jours.

Les commandes et les lignes générées se réconcilient via le conditionnement de six unités par colis. Les quantités livrées des commandes ouvertes restent inconnues.
