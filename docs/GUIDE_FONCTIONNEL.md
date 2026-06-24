# GUIDE FONCTIONNEL FONAQO
## Ce que fait l'application — Expliqué simplement

**Pour toute personne souhaitant comprendre FONAQO sans connaissance technique**  
*Version : 21 Juin 2026*

---

## QU'EST-CE QUE FONAQO ?

FONAQO est une **application mobile** qui met en contact deux types de personnes :

- 👤 **Le Client** : quelqu'un qui a besoin d'un service (réparer un robinet, faire une livraison, un déménagement léger, une réparation électrique, etc.)
- 👷 **L'Agent terrain** : un professionnel local qui peut réaliser ce service contre rémunération

Le tout est **sécurisé financièrement** : le client paye avant que la mission commence, mais l'argent ne part chez l'agent qu'une fois le travail terminé et validé par le client.

---

## LES ACTEURS DE LA PLATEFORME

### 👤 Le Client
- Crée une mission (décrit ce qu'il veut)
- Paye en avance (l'argent est sécurisé, pas directement versé à l'agent)
- Suit en temps réel l'avancement
- Valide ou conteste la prestation
- Peut noter l'agent après la mission

### 👷 L'Agent Terrain
- S'inscrit, passe une vérification d'identité (KYC)
- Voit les missions disponibles près de lui
- Accepte, se rend sur place, réalise, prend une photo de preuve
- Reçoit son paiement une fois que le client valide
- Peut noter le client aussi

### 🖥️ Le SuperAdmin (Équipe FONAQO)
- Vérifie les identités des agents (KYC)
- Génère et imprime les badges professionnels
- Suspend des comptes en cas d'abus
- Voit toutes les missions, tous les utilisateurs
- Configure les paramètres de la plateforme

---

## COMMENT ÇA MARCHE DE A À Z

### ÉTAPE 1 — Un Agent s'inscrit et se fait vérifier

**Ce que l'agent fait :**
1. Il télécharge l'app et crée un compte (téléphone, email, mot de passe)
2. Il accepte les Conditions Générales d'Utilisation
3. Il met à jour sa **photo de profil** → c'est la **première étape de sa vérification** d'identité
4. Il envoie **sa pièce d'identité** (recto/verso) et un **selfie avec la pièce**

**Ce que FONAQO fait derrière :**
- L'équipe admin reçoit une alerte pour examiner les documents
- Si tout est bon → le compte est **approuvé** (KYC validé)
- L'agent reçoit un **code unique** `AGT-00001` qui l'identifie sur la plateforme
- L'agent reçoit un **email de confirmation**

**Si les documents ne sont pas bons :** l'équipe rejette la demande avec un motif, et l'agent peut recommencer.

> ⚠️ La photo de profil ne peut être changée **qu'une seule fois**. C'est intentionnel : elle fait partie de l'identité officielle de l'agent.

---

### ÉTAPE 2 — L'Agent obtient son Badge Professionnel

**Ce que l'agent fait :**
- Depuis son profil, il fait une demande de badge

**Ce que FONAQO fait derrière :**
- L'équipe admin génère un **badge PDF professionnel** avec :
  - La photo de l'agent
  - Son nom, sa spécialité, son code ID
  - Un **QR code** qui pointe vers sa page publique
- Le badge est envoyé à l'agent et/ou **imprimé par FONAQO** et envoyé physiquement

**La page publique (scan QR) :**
- N'importe qui peut scanner le QR du badge et voir :
  - Le profil de l'agent, ses certifications
  - Combien de missions il a réalisées
  - Combien il a gagné au total
  - Sa note moyenne des clients

> 💡 Le badge est **gratuit** — c'est FONAQO qui s'en occupe et l'imprime.

---

### ÉTAPE 3 — Un Client crée une mission

**Ce que le client fait :**
1. Il décrit ce dont il a besoin (titre + description + localisation)
2. Il indique un budget
3. Il valide → la mission est publiée

**Ce que l'app fait derrière :**
- La mission est enregistrée avec le statut **"EN ATTENTE"** (`PENDING`)
- Les agents disponibles dans la zone peuvent la voir
- L'argent du client n'est **pas encore débité** à cette étape

---

### ÉTAPE 4 — Un Agent accepte la mission

**Ce que l'agent fait :**
- Il voit les missions disponibles sur son tableau de bord
- Il clique sur "Accepter" pour une mission

**Ce que l'app fait derrière :**
- Le système vérifie que l'agent est bien vérifié (KYC approuvé)
- Le système vérifie qu'il n'a pas déjà trop de missions actives en même temps
- Si tout est bon → la mission lui est assignée
- **L'argent du client est bloqué** dans un "séquestre" (comme un coffre-fort numérique) → statut `ACCEPTED`
- Le client et l'agent sont notifiés

> 🔒 Le "séquestre" (escrow) : l'argent est prélevé du compte du client mais **ne va pas encore** à l'agent. Il attend dans un espace sécurisé jusqu'à la fin de la mission.

---

### ÉTAPE 5 — L'Agent se rend sur place

L'agent met à jour son statut au fur et à mesure :

| Action de l'agent | Statut | Ce que le client voit |
|---|---|---|
| "Je pars vers vous" | EN ROUTE (`ON_THE_WAY`) | L'agent est en chemin |
| "Je suis arrivé" | ARRIVÉ (`ARRIVED`) | L'agent est là |
| "Je commence la mission" | EN COURS (`IN_PROGRESS`) | La mission a commencé |

Tout au long de ce processus, le client reçoit des **notifications** et peut suivre en temps réel dans l'app.

---

### ÉTAPE 6 — La mission est terminée, l'agent envoie une preuve

**Ce que l'agent fait :**
- Il prend une **photo de preuve** (photo du travail accompli)
- Il la soumet dans l'app

**Ce que l'app fait derrière :**
- La mission passe en statut **"EN ATTENTE DE VALIDATION"** (`IN_PROGRESS_REVIEW`)
- Le client voit la photo de preuve apparaître dans son écran
- Un bouton **"Valider et libérer les fonds"** apparaît automatiquement

---

### ÉTAPE 7 — Le Client valide (ou conteste)

**Option A — Le client valide ✅**
- Il appuie sur "Valider et libérer les fonds"
- L'argent est **distribué automatiquement** :
  - 🏆 **L'agent reçoit 88 %** du montant
  - 🏢 **FONAQO reçoit 10 %** (commission)
  - 🛡️ **2 % vont dans une réserve** technique/assurance
- La mission passe en statut **TERMINÉ** (`COMPLETED`)
- Les deux parties peuvent **se noter** (étoiles + commentaire)
- Le client reçoit une **facture PDF** téléchargeable

**Option B — Le client conteste ⚠️**
- Il peut ouvrir un **litige** depuis l'app
- L'équipe FONAQO intervient pour arbitrer
- La mission passe en statut **LITIGE** (`DISPUTED`)

---

### ÉTAPE 8 — Et si quelqu'un annule ?

**Si le client annule AVANT que l'agent accepte :**
- Annulation gratuite, rien n'a été débité

**Si le client annule APRÈS que l'agent a accepté :**
- L'agent est dédommagé : **15 % du montant** lui est versé automatiquement
- FONAQO retient **5 %** pour les frais d'administration
- Le client est remboursé de **80 %**

> Cela protège l'agent contre les clients qui font perdre son temps.

---

## LE SYSTÈME FINANCIER EN DÉTAIL

### Le Portefeuille (Wallet)
- Chaque utilisateur a un **portefeuille numérique** dans l'app
- Le client peut y déposer de l'argent (via FeexPay — Mobile Money)
- L'agent y reçoit ses paiements
- Chacun peut demander un **retrait** vers son compte Mobile Money

### Le Séquestre (Escrow)
Le séquestre est comme un coffre-fort automatique géré par l'app :
- Quand un agent accepte → l'argent entre dans le coffre
- Quand le client valide → le coffre s'ouvre automatiquement et distribue aux bons bénéficiaires
- Aucun humain ne "touche" à l'argent — tout est automatique et tracé

### Historique des Transactions
Chaque mouvement d'argent est **enregistré** avec :
- Le type (paiement mission, commission, retrait, etc.)
- Le montant
- La date et l'heure
- La mission concernée

---

## LE CHAT EN TEMPS RÉEL

Le client et l'agent peuvent **se messagerie directement** depuis la mission :
- Messages texte
- Messages vocaux
- Photos
- Indicateur "est en train d'écrire..."
- Statut des messages (envoyé / lu)

Le chat est accessible depuis la page de détail de la mission — un bouton ouvre une fenêtre de chat sans quitter l'écran de mission.

---

## LE SYSTÈME DE NOTATION

**Après chaque mission terminée :**
- Le client note l'agent : 1 à 5 étoiles + commentaire
- L'agent note le client : 1 à 5 étoiles + commentaire
- Ces notes sont publiques sur les profils
- La moyenne est calculée automatiquement
- La note de l'agent est visible sur sa page vitrine publique (scan QR)

---

## LES RÉCOMPENSES CLIENT

Plus un client utilise FONAQO, plus il accumule des **points et badges** :

| Badge | Comment l'obtenir |
|---|---|
| 🎯 Première Mission | Terminer sa 1ère mission |
| ⭐ Client Fidèle | Terminer 5 missions |
| 👑 VIP | Terminer 10 missions |
| 💰 Gros Dépenseur | Passer une mission > 10 000 FCFA |
| 💎 Super Dépenseur | Passer 3 missions > 10 000 FCFA |

Ces badges sont visibles sur le profil du client et permettront (dans les évolutions futures) d'obtenir des avantages.

---

## LE CLASSEMENT DES AGENTS

Les agents sont classés selon une formule qui prend en compte :
- **40 %** — Taux de complétion (missions terminées / acceptées)
- **30 %** — Note moyenne des clients
- **20 %** — Rapidité de réponse et de démarrage
- **10 %** — Nombre total de missions réalisées

Ce classement permet aux clients de voir les **meilleurs agents** de leur zone en premier.

---

## LE PASS BOOST VÉTÉRAN

Un agent qui a réalisé **20 missions complètes** reçoit automatiquement un **cadeau** :
- Un **Pass Boost Gratuit de 3 jours**
- Pendant ces 3 jours, il peut accepter jusqu'à **5 missions en même temps** (au lieu de 2)
- Ce pass est **unique à vie** — une seule fois par carrière

> Cela récompense les agents les plus actifs et les fidélise à la plateforme.

---

## LES AGENTS INTERNES

Certains agents ont le statut "Agent Interne" — ce sont les **agents salariés ou partenaires directs** de FONAQO.

- Ce statut est attribué **uniquement** par l'équipe FONAQO
- Ils apparaissent **en priorité** dans les suggestions aux clients
- Leur badge affiche **"AGENT CERTIFIÉ ★"** (avec étoile)
- Ce statut n'a rien à voir avec le KYC ou le badge — c'est purement organisationnel

---

## LA SÉCURITÉ — COMMENT ON PROTÈGE LES UTILISATEURS

### Anti-abus sur la connexion
- Si quelqu'un tente de se connecter trop vite de la même adresse (5 fois en 1 minute) → l'accès est bloqué temporairement
- Même chose pour les inscriptions (3 par minute maximum)

### Comptes suspendus
- L'équipe FONAQO peut suspendre un compte en cas de comportement frauduleux
- L'utilisateur suspendu voit un écran bloquant avec les informations pour contacter le support
- Aucune action n'est possible jusqu'à la réactivation

### Vérification des Agents (KYC = Know Your Customer)
- Chaque agent fournit une pièce d'identité + un selfie
- L'équipe FONAQO vérifie manuellement
- Seuls les agents vérifiés peuvent accepter des missions
- La photo de profil ne peut être changée qu'une fois (pour éviter l'usurpation d'identité)

---

## LE TABLEAU DE BORD SUPERADMIN

L'équipe FONAQO dispose d'un **panneau de contrôle web** complet (pas dans l'app mobile — accessible seulement via navigateur) :

### Ce qu'on peut voir
- Tous les agents, tous les clients, toutes les missions
- Les demandes de vérification KYC en attente
- Les demandes de badge en attente
- Les litiges ouverts
- Les statistiques globales de la plateforme

### Ce qu'on peut faire
- ✅ Approuver / ❌ Rejeter un KYC (avec email automatique)
- 🏅 Générer et approuver un badge
- 🚫 Suspendre un compte abusif (avec email automatique)
- ✅ Réactiver un compte (avec email automatique)
- 🔧 Modifier les paramètres (commissions, prix des boosts, etc.)
- 📱 Réinitialiser le mot de passe d'un utilisateur qui ne peut plus se connecter

### Traçabilité
- Toutes les actions de l'équipe admin sont **enregistrées dans un journal d'audit**
- Qui a fait quoi, à quelle heure, sur quel compte

---

## LES ARTISANS (ANNUAIRE LOCAL)

En plus des agents terrain, FONAQO maintient un **annuaire d'artisans locaux** (plombiers, électriciens, menuisiers, etc.) — similaire à LeBonCoin.

- Un artisan peut être listé dans cet annuaire
- Il n'est pas forcément un agent terrain FONAQO
- Un agent FONAQO peut être "promu" dans l'annuaire sans perdre son statut d'agent

---

## NOTIFICATIONS — NE RIEN RATER

L'app envoie des **notifications push** (comme WhatsApp) pour :
- Une nouvelle mission disponible dans votre zone (agents)
- Un agent a accepté votre mission (clients)
- L'agent est en route / arrivé / a commencé (clients)
- L'agent a soumis sa preuve — votre validation est attendue (clients)
- Votre mission est terminée, vous pouvez noter (les deux)
- Un nouveau message dans le chat
- Votre badge est prêt
- Votre KYC a été approuvé / rejeté

---

## RÉSUMÉ EN 30 SECONDES

1. **Client** crée une mission et décrit son besoin
2. **Agent** accepte → l'argent du client est sécurisé dans un coffre numérique
3. L'agent se rend sur place, réalise, prend une **photo de preuve**
4. Le client voit la photo et **valide** → l'argent est distribué automatiquement (88 % agent, 10 % FONAQO, 2 % réserve)
5. Les deux parties se notent → la réputation se construit mission après mission
6. Si un problème survient → l'équipe FONAQO arbitre via le système de litiges

**C'est simple, sécurisé, et transparent.**

---

*Document rédigé pour une compréhension non-technique complète de FONAQO*  
*Dernière mise à jour : 21 Juin 2026*
