@echo off
setlocal

:: Script d'ajout au dataset AStream - Windows
:: Usage: add_dataset.bat <slug> <season> <episode> <language> <url>

:: Verifier le nombre de parametres
if "%~5"=="" (
    echo Usage: %0 ^<slug^> ^<season^> ^<episode^> ^<language^> ^<url^>
    echo.
    echo Exemples:
    echo   %0 one-piece 1 1 VOSTFR "https://sibnet.ru/shell.php?videoid=123456"
    echo   %0 naruto 4 21 VF "https://vidmoly.to/embed-abc123.html"
    echo   %0 bleach 998 1 VOSTFR "https://sendvid.com/embed/film1"
    echo.
    echo Saisons speciales:
    echo   0   = OAV/Speciaux
    echo   998 = Films
    echo   999 = Hors-serie
    exit /b 1
)

:: Verifier que dataset.json existe
if not exist "dataset.json" (
    echo Erreur: Fichier dataset.json introuvable
    echo Assurez-vous d'etre dans le repertoire racine d'AStream
    exit /b 1
)

:: Verifier que Python est disponible
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    where python3 >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo Erreur: Python n'est pas installe
        exit /b 1
    )
    set "PYTHON_CMD=python3"
) else (
    set "PYTHON_CMD=python"
)

:: Creer script Python temporaire qui recupere tous les arguments
set "TEMP_SCRIPT=%TEMP%\add_dataset_%RANDOM%.py"

(
echo import json
echo import sys
echo.
echo # Recuperer tous les arguments apres le script
echo if len^(sys.argv^) ^< 6:
echo     print^("Erreur: Nombre de parametres incorrect"^)
echo     sys.exit^(1^)
echo.
echo slug = sys.argv[1]
echo season = sys.argv[2]
echo episode = sys.argv[3]
echo language = sys.argv[4]
echo.
echo # Reconstituer l'URL complete a partir de tous les arguments restants
echo # Cela gere le cas ou l'URL contient des espaces ou a ete decoupee
echo url_parts = sys.argv[5:]
echo url = ' '.join^(url_parts^)
echo.
echo # Valider les parametres
echo if not slug:
echo     print^("Erreur: Slug anime requis"^)
echo     sys.exit^(1^)
echo.
echo try:
echo     season = int^(season^)
echo     if season ^< 0:
echo         raise ValueError
echo except:
echo     print^("Erreur: Numero de saison invalide"^)
echo     sys.exit^(1^)
echo.
echo try:
echo     episode = int^(episode^)
echo     if episode ^< 1:
echo         raise ValueError
echo except:
echo     print^("Erreur: Numero d'episode invalide"^)
echo     sys.exit^(1^)
echo.
echo if language not in ['VOSTFR', 'VF', 'VF1', 'VF2']:
echo     print^("Erreur: Langue invalide. Utiliser: VOSTFR, VF, VF1, VF2"^)
echo     sys.exit^(1^)
echo.
echo if not url:
echo     print^("Erreur: URL requise"^)
echo     sys.exit^(1^)
echo.
echo # Charger dataset
echo with open^('dataset.json', 'r', encoding='utf-8'^) as f:
echo     data = json.load^(f^)
echo.
echo # Trouver ou creer anime
echo anime = None
echo for a in data['anime']:
echo     if a['slug'] == slug:
echo         anime = a
echo         break
echo.
echo if not anime:
echo     anime = {'slug': slug, 'streams': []}
echo     data['anime'].append^(anime^)
echo.
echo # Verifier si cette URL exacte existe deja
echo for stream in anime['streams']:
echo     if ^(stream['season'] == season and stream['episode'] == episode and 
echo         stream['language'] == language and stream['url'] == url^):
echo         print^('Cette URL est deja presente pour cet episode!'^)
echo         sys.exit^(1^)
echo.
echo # Ajouter nouveau stream
echo new_stream = {
echo     'season': season,
echo     'episode': episode,
echo     'language': language,
echo     'url': url
echo }
echo anime['streams'].append^(new_stream^)
echo.
echo # Trier: VOSTFR, VF, VF1, VF2
echo ordre = {'VOSTFR': 0, 'VF': 1, 'VF1': 2, 'VF2': 3}
echo anime['streams'].sort^(key=lambda x: ^(x['season'], x['episode'], ordre.get^(x['language'], 99^)^)^)
echo.
echo # Sauvegarder
echo with open^('dataset.json', 'w', encoding='utf-8'^) as f:
echo     json.dump^(data, f, ensure_ascii=False, indent=2^)
echo.
echo print^(f'Ajoute: {slug} S{season}E{episode} {language}'^)
) > "%TEMP_SCRIPT%"

:: Executer le script Python en passant TOUS les parametres
%PYTHON_CMD% "%TEMP_SCRIPT%" %*
set "RESULT=%ERRORLEVEL%"

:: Nettoyer
del "%TEMP_SCRIPT%" 2>nul

if %RESULT% equ 0 (
    echo.
    echo 🎉 Dataset mis a jour avec succes!
) else (
    echo.
    echo 💥 Echec de la mise a jour du dataset
)

exit /b %RESULT%