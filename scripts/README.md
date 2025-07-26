# Scripts Dataset AStream

Ce dossier contient les scripts pour gérer le dataset d'URLs directes d'AStream.

## 🎯 Scripts disponibles

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

- **slug** : Slug de l'anime tel qu'il apparaît dans l'URL anime-sama.fr/catalogue/[SLUG]/ (ex: `one-piece`, `naruto`, `dragon-ball-z`)
- **season** : Numéro de saison (voir tableau ci-dessous)
- **episode** : Numéro d'épisode (commence à 1)
- **language** : Langue (`VOSTFR`, `VF`, `VF1`, `VF2`)
- **url** : URL du player vidéo (entre guillemets)

## Saisons spéciales

| Type | Numéro | Description |
|------|--------|-------------|
| Saisons normales | `1, 2, 3...` | Numérotation standard |
| Spéciaux/OAV | `0` | OAV et épisodes spéciaux |
| Films | `998` | Tous les films liés à l'anime |
| Hors-série | `999` | Épisodes hors-série |

## 📌 Exemples

### Épisode normal
```bash
# Windows
add_dataset.bat one-piece 1 1 VOSTFR "https://sibnet.ru/shell.php?videoid=123456"

# Linux
./add_dataset.sh one-piece 1 1 VOSTFR "https://sibnet.ru/shell.php?videoid=123456"
```

### Film
```bash
# Windows
add_dataset.bat bleach 998 1 VOSTFR "https://vidmoly.to/embed-film1.html"

# Linux
./add_dataset.sh bleach 998 1 VOSTFR "https://vidmoly.to/embed-film1.html"
```

### OAV/Spécial
```bash
# Windows
add_dataset.bat naruto 0 1 VF "https://sendvid.com/embed/special1"

# Linux
./add_dataset.sh naruto 0 1 VF "https://sendvid.com/embed/special1"
```

### Hors-série
```bash
# Windows
add_dataset.bat dragon-ball 999 1 VF1 "https://oneupload.to/embed/hs1"

# Linux
./add_dataset.sh dragon-ball 999 1 VF1 "https://oneupload.to/embed/hs1"
```

## Notes importantes

1. **Emplacement** : Exécutez les scripts depuis la racine du projet AStream
2. **Guillemets** : Toujours mettre l'URL entre guillemets
3. **Doublons** : Le script vérifie automatiquement les doublons
4. **Tri** : Les streams sont automatiquement triés par saison → épisode → langue
5. **Ordre des langues** : VOSTFR → VF → VF1 → VF2

## 🔧 Pré-requis

- **Windows** : Python installé et accessible via `python`
- **Linux/Mac** : Python installé (`python3` ou `python`)
- Fichier `dataset.json` présent dans le répertoire racine

## 🎯 Workflow recommandé

1. Trouver un anime sur Anime-Sama
2. Récupérer l'URL du player pour un épisode
3. Identifier le numéro de saison Stremio (voir mapping sous-saisons)
4. Ajouter avec le script
5. Vérifier le dataset mis à jour

## 📊 Mapping sous-saisons

Si AnimeSama a "saison4-2 épisode 5" et que la saison 4 normale a 16 épisodes :
- **Dans le dataset** : `saison 4 épisode 21` (16+5)
- **Raison** : AStream fusionne les sous-saisons dans la saison principale