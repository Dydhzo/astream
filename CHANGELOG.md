# 📋 Changelog

## 🚀 AStream v2.0.0
**Nouvelles fonctionnalités et corrections multiples**

### Nouvelles fonctionnalités et améliorations
✅ **API TMDB intégrée** : Support complet TMDB avec descriptions, images, trailers, années de sortie et genres personnalisés  
✅ **Exclusions personnalisées** : Les utilisateurs peuvent exclure des domaines et mots-clés en plus des exclusions par défaut  
✅ **Dataset optimisé** : URLs multiples pour un même épisode séparées par virgules, logique simplifiée  
✅ **Détection d'URLs directes** : Support automatique des fichiers .mp4, .m3u8, .mkv  
✅ **Recherche intelligente** : Re-vérification automatique si aucun résultat trouvé dans la DB  

### Corrections de bugs
🔧 **Installation Stremio** : Résolution du problème d'installation qui ne fonctionnait pas  
🔧 **Épisodes en trop** : Correction de l'affichage des notations sans "/"  
🔧 **Genres multiples** : Résolution des bugs d'affichage des genres  
🔧 **Saisons en doublon** : Correction des saisons qui apparaissaient à cause des notes Anime-Sama  
🔧 **Numérotation** : Correction des numéros de saison pour films et hors-séries  

### Améliorations techniques
🗄️ **Restructuration DB** : Base de données réorganisée et optimisée  
📁 **Organisation code** : Fichiers replacés aux bons endroits et renommés  
🔍 **Règle anti-doublon** : Évite les URLs du même domaine entre https:// et le premier /  
🌐 **Configuration URL** : Suppression des URLs par défaut, obligation de remplir dans le .env  
📝 **Cohérence DB/ENV** : Uniformisation singulier/pluriel dans la base et configuration  

---

## 🚀 AStream v1.1.0
**Nouvelles fonctionnalités et améliorations**

### Nouvelles fonctionnalités et améliorations
✅ **Système de dataset** : Ajout d'un système permettant d'intégrer manuellement des URLs pour les épisodes non disponibles ou incompatibles sur Anime-Sama  
✅ **Configuration de proxy avancée** : Ajout dans le .env d'une option pour modifier l'URL d'Anime-Sama afin de contourner les blocages Cloudflare via worker  
✅ **Bypass de domaine pour le proxy** : Support pour les domaines nécessitant un contournement spécifique  

### Corrections de bugs
🔧 **Correction Vidmoly** : Résolution du problème causé par le changement automatique de domaine de vidmoly vers moly  

### Améliorations techniques
📊 **Logs améliorés** : Informations plus détaillées et mieux structurées  
🧹 **Refactoring du code** : Organisation plus claire et propre  
🎨 **Amélioration de l'interface web** : Design retravaillé et ajout d'une section "Problèmes récurrents" dans les informations  

---

## 🚀 AStream v1.0.0
**Première version stable**

### ✨ Principales fonctionnalités
🔍 **Scraping intelligent** : Récupération dynamique du catalogue complet d'Anime-Sama  
🎬 **Support multi-lecteurs** : Extraction des liens depuis Sibnet, Vidmoly, Sendvid et Oneupload  
🌐 **Gestion des langues** : Support complet VOSTFR, VF et différentes versions françaises  
📺 **Organisation par saisons** : Détection intelligente des saisons, films, OAV et hors-séries  
⚡ **Performance optimisée** : Temps de réponse < 500ms (avec cache) et scraping parallèle  
🗄️ **Cache adaptatif** : Système de cache avec TTL ajusté selon le statut de l'anime  
🔒 **Verrouillage distribué** : Évite les doublons de scraping entre instances  

### 🛠️ Améliorations techniques
- Système de détection automatique des métadonnées (titres, genres, images, synopsis)
- Architecture modulaire pour faciliter les extensions futures
- Consommation mémoire optimisée (~100MB)
- Support pour plus de 100 utilisateurs simultanés

### 🚢 Installation simplifiée
- Déploiement Docker en une seule commande
- Configuration via variables d'environnement
- Documentation complète des paramètres

---

📌 **Note** : AStream est un projet non officiel développé de manière indépendante. Il n'est pas affilié à Anime-Sama ou Stremio.

Si vous rencontrez des problèmes ou avez des suggestions, n'hésitez pas à ouvrir une issue sur GitHub ou à contribuer au projet !