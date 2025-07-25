#!/bin/bash

# Script d'ajout au dataset AStream - Linux/Mac
# Usage: ./add_dataset.sh <slug> <season> <episode> <language> <url>

set -e

# Fonction d'aide
show_usage() {
    echo "Usage: $0 <slug> <season> <episode> <language> <url>"
    echo ""
    echo "Exemples:"
    echo "  $0 one-piece 1 1 VOSTFR \"https://sibnet.ru/shell.php?videoid=123456\""
    echo "  $0 naruto 4 21 VF \"https://vidmoly.to/embed-abc123.html\""
    echo "  $0 bleach 998 1 VOSTFR \"https://sendvid.com/embed/film1\""
    echo ""
    echo "Saisons speciales:"
    echo "  0   = OAV/Speciaux"
    echo "  998 = Films"
    echo "  999 = Hors-serie"
}

# Vérifier le nombre de paramètres
if [ $# -ne 5 ]; then
    echo "Erreur: Nombre de paramètres incorrect"
    show_usage
    exit 1
fi

SLUG="$1"
SEASON="$2"  
EPISODE="$3"
LANGUAGE="$4"
URL="$5"

# Valider les paramètres
if [ -z "$SLUG" ]; then
    echo "Erreur: Slug anime requis"
    exit 1
fi

if ! [[ "$SEASON" =~ ^[0-9]+$ ]] || [ "$SEASON" -lt 0 ]; then
    echo "Erreur: Numéro de saison invalide"
    exit 1
fi

if ! [[ "$EPISODE" =~ ^[0-9]+$ ]] || [ "$EPISODE" -lt 1 ]; then
    echo "Erreur: Numéro d'épisode invalide"  
    exit 1
fi

if [[ ! "$LANGUAGE" =~ ^(VOSTFR|VF|VF1|VF2)$ ]]; then
    echo "Erreur: Langue invalide. Utiliser: VOSTFR, VF, VF1, VF2"
    exit 1
fi

if [ -z "$URL" ]; then
    echo "Erreur: URL requise"
    exit 1
fi

# Vérifier que dataset.json existe
DATASET_PATH="dataset.json"
if [ ! -f "$DATASET_PATH" ]; then
    echo "Erreur: Fichier dataset.json introuvable"
    echo "Assurez-vous d'être dans le répertoire racine d'AStream"
    exit 1
fi

# Vérifier que Python est disponible
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "Erreur: Python n'est pas installé"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

# Créer script Python temporaire
TEMP_SCRIPT=$(mktemp)
cat > "$TEMP_SCRIPT" << 'EOF'
import json
import sys

slug = sys.argv[1]
season = int(sys.argv[2])
episode = int(sys.argv[3])
language = sys.argv[4]
url = sys.argv[5]

# Charger dataset
with open('dataset.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Trouver ou créer anime
anime = None
for a in data['anime']:
    if a['slug'] == slug:
        anime = a
        break

if not anime:
    anime = {'slug': slug, 'streams': []}
    data['anime'].append(anime)

# Vérifier si cette URL exacte existe déjà
for stream in anime['streams']:
    if (stream['season'] == season and stream['episode'] == episode and 
        stream['language'] == language and stream['url'] == url):
        print('Cette URL est déjà présente pour cet épisode!')
        sys.exit(1)

# Ajouter nouveau stream
new_stream = {
    'season': season,
    'episode': episode, 
    'language': language,
    'url': url
}
anime['streams'].append(new_stream)

# Trier: VOSTFR, VF, VF1, VF2
ordre = {'VOSTFR': 0, 'VF': 1, 'VF1': 2, 'VF2': 3}
anime['streams'].sort(key=lambda x: (x['season'], x['episode'], ordre.get(x['language'], 99)))

# Sauvegarder
with open('dataset.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'Ajouté: {slug} S{season}E{episode} {language}')
EOF

# Exécuter le script Python
if $PYTHON_CMD "$TEMP_SCRIPT" "$SLUG" "$SEASON" "$EPISODE" "$LANGUAGE" "$URL"; then
    echo ""
    echo "🎉 Dataset mis à jour avec succès!"
    RESULT=0
else
    echo ""
    echo "💥 Échec de la mise à jour du dataset"
    RESULT=1
fi

# Nettoyer
rm -f "$TEMP_SCRIPT"

exit $RESULT