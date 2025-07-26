# <p align="center"><img src="https://raw.githubusercontent.com/Dydhzo/astream/refs/heads/main/astream/assets/astream-logo.jpg" width="150"></p>

<p align="center">
  <a href="https://github.com/Dydhzo/astream/releases/latest">
    <img alt="GitHub release" src="https://img.shields.io/github/v/release/Dydhzo/astream?style=flat-square&logo=github&logoColor=white&labelColor=1C1E26&color=4A5568">
  </a>
  <a href="https://www.python.org/">
    <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-blue?style=flat-square&logo=python&logoColor=white&labelColor=1C1E26&color=4A5568">
  </a>
  <a href="https://github.com/Dydhzo/astream/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/Dydhzo/astream?style=flat-square&labelColor=1C1E26&color=4A5568">
  </a>
</p>

<p align="center">
  <strong>Addon non officiel pour Stremio permettant d'accéder au contenu d'Anime-Sama (non affilié à Anime-Sama)</strong>
</p>

---

## 🌟 À propos

**AStream** est un addon Stremio spécialisé dans le streaming d'anime depuis le site français Anime-Sama. Il offre une intégration transparente du catalogue complet d'Anime-Sama directement dans votre interface Stremio.

### 🎯 Ce que fait AStream

- **Scraping intelligent** : Récupère la page d'accueil et effectue des recherches sur Anime-Sama
- **Extraction multi-sources** : Détecte et extrait les liens depuis plusieurs lecteurs vidéo
- **Gestion des langues** : Support complet VOSTFR, VF, VF1, VF2
- **Organisation par saisons** : Détection automatique des saisons, sous-saisons, films, OAV et hors-séries
- **Cache intelligent** : Système de cache avec TTL adaptatif selon le statut de l'anime
- **Performance optimisée** : Scraping parallèle et verrouillage distribué

---

## ✨ Fonctionnalités

### Système de Scraping

- **Parser HTML avancé** avec BeautifulSoup4
- **Détection automatique** des métadonnées :
  - Titres
  - Genres
  - Images de couverture
  - Synopsis
- **Extraction intelligente** :
  - Nombre d'épisodes par saison
  - Support structures complexes (sous-saisons)
  - Gestion contenus spéciaux

### Lecteurs Vidéo Supportés

**Testés et fonctionnels :**
- **Sibnet** - Extraction avec contournement protection
- **Vidmoly** - Support complet
- **Sendvid** - Support complet
- **Oneupload** - Support complet

**Non supportés :**
- **VK** - Protection complexe
- **Moveanime** - Protection complexe
- **Smoothanime** - Protection complexe

**Note :** D'autres lecteurs peuvent fonctionner mais n'ont pas été testés officiellement. Certains lecteurs peuvent également ne pas fonctionner

### Organisation des Contenus

| Type de Contenu | Numéro de Saison | Description |
|-----------------|------------------|-------------|
| Saisons normales | `1, 2, 3...` | Numérotation standard |
| Sous-saisons | `4-2, 4-3...` | Intégrées dans la saison principale (ex: saison4-2 → dans saison 4) |
| Films | `998` | Tous les films liés à l'anime |
| Hors-série | `999` | Épisodes hors-série |
| Spéciaux/OAV | `0` | OAV et épisodes spéciaux |

---

## Installation

> 📄 **Pour configurer les variables d'environnement, consultez le fichier [`.env.example`](.env.example)**

### 🐳 Docker Compose (Recommandé)

1. **Créez un fichier `docker-compose.yml`** :

```yaml
services:
  astream:
    image: dydhzo/astream:latest
    container_name: astream
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - astream:/data

volumes:
  astream:
```

2. **Démarrez le conteneur** :
```bash
docker compose up -d
```

3. **Vérifiez les logs** :
```bash
docker compose logs -f astream
```

### 🐍 Installation Manuelle

#### Prérequis
- Python 3.11 ou supérieur
- Git

#### Étapes

1. **Clonez le dépôt** :
```bash
git clone https://github.com/Dydhzo/astream.git
cd astream
```

2. **Installez les dépendances** :
```bash
pip install -r requirements.txt
```

3. **Configurez l'environnement** :
```bash
cp .env.example .env
# Éditez .env selon vos besoins
```

4. **Lancez l'application** :
```bash
python -m astream.main
```

---

## ⚙️ Configuration

### 📱 Ajout dans Stremio

1. **Ouvrez Stremio**
2. **Paramètres** → **Addons**
3. **Collez l'URL** : `http://votre-ip:8000/manifest.json`
4. **Cliquez** sur "Installer"

L'addon apparaîtra avec le logo AStream dans votre liste d'addons.

### 🔧 Variables d'Environnement

Toutes les variables disponibles dans le fichier `.env` :

| Variable | Description | Défaut | Type |
|----------|-------------|---------|------|
| **Configuration Serveur** |
| `FASTAPI_HOST` | Adresse d'écoute du serveur | `0.0.0.0` | IP |
| `FASTAPI_PORT` | Port d'écoute | `8000` | Port |
| `FASTAPI_WORKERS` | Nombre de workers (-1 = auto) | `1` | Nombre |
| `USE_GUNICORN` | Utiliser Gunicorn (Linux uniquement) | `True` | Booléen |
| **Base de Données** |
| `DATABASE_TYPE` | Type de base de données | `sqlite` | `sqlite`/`postgresql` |
| `DATABASE_PATH` | Chemin SQLite | `data/astream.db` | Chemin |
| `DATABASE_URL` | URL PostgreSQL (si DATABASE_TYPE=postgresql) | - | URL |
| **Configuration Dataset** |
| `DATASET_ENABLED` | Activer/désactiver le système de dataset | `true` | Booléen |
| `DATASET_URL` | URL du dataset à télécharger | `https://raw.githubusercontent.com/Dydhzo/astream/main/dataset.json` | URL |
| `AUTO_UPDATE_DATASET` | Mise à jour automatique du dataset | `true` | Booléen |
| `DATASET_UPDATE_INTERVAL` | Intervalle de vérification des mises à jour | `3600` (1h) | Secondes |
| **Configuration Cache (secondes)** |
| `DYNAMIC_LISTS_TTL` | Cache listes et catalogues | `3600` (1h) | Secondes |
| `EPISODE_PLAYERS_TTL` | Cache URLs des lecteurs | `3600` (1h) | Secondes |
| `ONGOING_ANIME_TTL` | Cache anime en cours | `3600` (1h) | Secondes |
| `FINISHED_ANIME_TTL` | Cache anime terminés | `604800` (7j) | Secondes |
| `PLANNING_CACHE_TTL` | Cache planning anime | `3600` (1h) | Secondes |
| **Scraping** |
| `SCRAPE_LOCK_TTL` | Durée des verrous de scraping | `300` (5min) | Secondes |
| `SCRAPE_WAIT_TIMEOUT` | Attente maximale pour un verrou | `30` | Secondes |
| **Réseau** |
| `HTTP_TIMEOUT` | Timeout HTTP général | `15` | Secondes |
| `RATE_LIMIT_PER_USER` | Délai entre requêtes par IP | `1` | Secondes |
| `PROXY_URL` | Proxy HTTP/HTTPS recommandé | - | URL |
| `PROXY_BYPASS_DOMAINS` | Domaines qui ne doivent pas utiliser le proxy | - | String |
| `ANIMESAMA_URL` | URL de base d'anime-sama (Worker Cloudflare) | `https://anime-sama.fr` | URL |
| **Filtrage** |
| `EXCLUDED_DOMAIN` | Domaines à exclure des streams | - | String |
| **Personnalisation** |
| `ADDON_ID` | Identifiant unique de l'addon | `community.astream` | String |
| `ADDON_NAME` | Nom affiché de l'addon | `AStream` | String |
| `CUSTOM_HEADER_HTML` | HTML personnalisé page config | - | HTML |
| `LOG_LEVEL` | Niveau de log | `DEBUG` | `DEBUG`/`PRODUCTION` |

---

## Performance

### 📊 Métriques

- **Temps de réponse catalogue** : < 500ms (avec cache)
- **Résolution stream** : 1-3 secondes
- **Consommation mémoire** : ~100MB
- **Support concurrent** : 100+ utilisateurs simultanés

### ⚡ Optimisations

- **Cache multiniveau** : Mémoire + Base de données
- **Scraping parallèle** : Traitement concurrent des saisons
- **Headers dynamiques** : Rotation User-Agent automatique
- **Verrouillage distribué** : Évite les doublons entre instances

---

## 🛠️ Développement

### 📁 Structure du Projet

```
astream/
├── api/                    # Routes FastAPI
│   ├── core.py            # Manifest, catalogue, métadonnées
│   └── stream.py          # Résolution des streams
├── scrapers/              # Extracteurs Anime-Sama
│   ├── animesama.py               # API principale
│   ├── animesama_parser.py        # Parser HTML
│   ├── animesama_player.py        # Extraction lecteurs
│   └── animesama_video_resolver.py # Résolution URLs
├── utils/                 # Utilitaires
│   ├── database.py        # Gestion cache/verrous
│   ├── logger.py          # Système de logs
│   └── http_client.py     # Client HTTP avec retry
├── config/                # Configuration
│   └── app_settings.py    # Paramètres application
└── main.py               # Point d'entrée
```

### 🧪 Tests et Debug

```bash
# Mode debug
LOG_LEVEL=DEBUG python -m astream.main

# Voir les logs Docker
docker compose logs -f astream
```

---

## 🤝 Contribution

Les contributions sont les bienvenues !

1. **Fork** le projet
2. **Créez** votre branche (`git checkout -b feature/amelioration`)
3. **Committez** vos changements (`git commit -m 'Ajout de...'`)
4. **Push** vers la branche (`git push origin feature/amelioration`)
5. **Ouvrez** une Pull Request

---

## 🙏 Crédits

L'architecture de base de ce projet est inspirée de [Comet](https://github.com/g0ldyy/comet) (MIT License).

```markdown
MIT License
Copyright (c) 2024 Goldy
Copyright (c) 2025 Dydhzo
```

La logique métier, les scrapers et toutes les fonctionnalités spécifiques à Anime-Sama ont été entièrement développées pour AStream.

### Remerciements

- **Anime-Sama** pour leur catalogue d'anime
- **Stremio** pour leur plateforme ouverte
- La communauté open source

---

## Avertissement

**AStream est un projet non officiel développé de manière indépendante.**

- **NON affilié à Anime-Sama**
- **NON affilié à Stremio**
- **Utilisez cet addon à vos propres risques**
- **Respectez les conditions d'utilisation des sites sources**
- **L'auteur décline toute responsabilité quant à l'utilisation de cet addon**

Cet addon est fourni "tel quel" sans aucune garantie. Il est de la responsabilité de l'utilisateur de vérifier la légalité de son utilisation dans sa juridiction.

---

## 📜 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

<p align="center">
  Fait avec ❤️ pour la communauté anime française
</p>
