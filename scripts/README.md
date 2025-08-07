# Scripts Dataset AStream

Ce dossier contient les scripts pour gérer le dataset d'URLs directes d'AStream.

## 📦 Format du Dataset

Le dataset utilise un format avec URLs groupées pour économiser l'espace :

```json
{
  "anime": [{
    "slug": "one-piece",
    "streams": [
      {
        "season": 1,
        "episode": 1,
        "language": "VOSTFR", 
        "urls": ["https://domaine1.com/embed/test-1", "https://domaine2.com/embed/test-2"]
      },
      {
        "season": 1,
        "episode": 1,
        "language": "VF",
        "urls": ["https://domaine3.com/embed/test-3"]
      }
    ]
  }]
}
```

**Avantages :**
- URLs multiples regroupées par épisode/langue
- Plus de répétition de saison/épisode/langue
- Réduction de taille de ~60%

## Scripts disponibles

### Windows : `add_dataset.bat`
### Linux/Mac : `add_dataset.sh`

## 📝 Usage

```bash
# Windows
add_dataset.bat <slug> <season> <episode> <language> <url>

# Linux/Mac  
./add_dataset.sh <slug> <season> <episode> <language> <url>
```

## 🔢 Paramètres

- **slug** : Slug de l'anime tel qu'il apparaît dans l'URL ANIMESAMA_URL/catalogue/[SLUG]/ (ex: `one-piece`, `naruto`, `dragon-ball-z`)
- **season** : Numéro de saison (voir tableau ci-dessous)
- **episode** : Numéro d'épisode (commence à 1)
- **language** : Langue (`VOSTFR`, `VF`, `VF1`, `VF2`)
- **url** : URL du player vidéo (entre guillemets)

## Saisons spéciales

| Type | Numéro | Description |
|------|--------|-------------|
| Saisons normales | `1, 2, 3...` | Numérotation standard |
| Spéciaux/OAV | `0` | OAV et épisodes spéciaux |
| Films | `990` | Tous les films liés à l'anime |
| Hors-série | `991` | Épisodes hors-série |

## 📌 Exemples

### Épisode normal
```bash
# Windows
add_dataset.bat one-piece 1 1 VOSTFR "https://domaine1.com/embed/test-1"

# Linux
./add_dataset.sh one-piece 1 1 VOSTFR "https://domaine1.com/embed/test-1"
```

### Film
```bash
# Windows
add_dataset.bat bleach 990 1 VOSTFR "https://domaine2.com/embed/test-2"

# Linux
./add_dataset.sh bleach 990 1 VOSTFR "https://domaine2.com/embed/test-2"
```

### OAV/Spécial
```bash
# Windows
add_dataset.bat naruto 0 1 VF "https://domaine3.com/embed/test-3"

# Linux
./add_dataset.sh naruto 0 1 VF "https://domaine3.com/embed/test-3"
```

### Hors-série
```bash
# Windows
add_dataset.bat dragon-ball 991 1 VF1 "https://domaine4.com/embed/test-4"

# Linux
./add_dataset.sh dragon-ball 991 1 VF1 "https://domaine4.com/embed/test-4"
```

## Notes importantes

1. **Emplacement** : Exécutez les scripts depuis la racine du projet AStream
2. **Guillemets** : Toujours mettre l'URL entre guillemets
3. **URLs multiples** : Si vous ajoutez une URL pour un épisode/langue existant, elle sera automatiquement ajoutée au tableau `urls`
4. **Doublons** : Le script vérifie automatiquement les doublons d'URLs
5. **Tri** : Les streams sont automatiquement triés par saison → épisode → langue
6. **Ordre des langues** : VOSTFR → VF → VF1 → VF2

## 🔧 Pré-requis

- **Windows** : Python installé et accessible via `python`
- **Linux/Mac** : Python installé (`python3` ou `python`)
- Fichier `dataset.json` présent dans le répertoire racine

## Workflow recommandé

1. Trouver un anime sur Anime-Sama
2. Récupérer l'URL du player pour un épisode
3. Identifier le numéro de saison Stremio (voir mapping sous-saisons)
4. Ajouter avec le script (si l'épisode/langue existe déjà, l'URL sera ajoutée au tableau)
5. Vérifier le dataset mis à jour

## 💡 Exemple pratique

```bash
# Premier ajout pour One Piece S1E1 VOSTFR
./add_dataset.sh one-piece 1 1 VOSTFR "https://domaine1.com/embed/test-1"

# Deuxième URL pour le même épisode - sera automatiquement groupée
./add_dataset.sh one-piece 1 1 VOSTFR "https://domaine2.com/embed/test-2"

# Résultat dans le dataset :
# {
#   "season": 1, "episode": 1, "language": "VOSTFR",
#   "urls": ["https://domaine1.com/embed/test-1", "https://domaine2.com/embed/test-2"]
# }
```

## 📊 Mapping sous-saisons

Si AnimeSama a "saison4-2 épisode 5" et que la saison 4 normale a 16 épisodes :
- **Dans le dataset** : `saison 4 épisode 21` (16+5)
- **Raison** : AStream fusionne les sous-saisons dans la saison principale