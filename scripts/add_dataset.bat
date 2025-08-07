@echo off
setlocal

:: Script d'ajout au dataset AStream - Windows
:: Usage: add_dataset.bat <slug> <season> <episode> <language> <url>

:: Verifier le nombre de parametres
if "%~5"=="" (
    echo Usage: %0 ^<slug^> ^<season^> ^<episode^> ^<language^> ^<url^>
    echo.
    echo Exemples:
    echo   %0 one-piece 1 1 VOSTFR "https://domaine1.com/embed/test-1"
    echo   %0 naruto 4 21 VF "https://domaine2.com/embed/test-2"
    echo   %0 bleach 990 1 VOSTFR "https://domaine3.com/embed/test-3"
    echo.
    echo Saisons speciales:
    echo   0   = OAV/Speciaux
    echo   990 = Films
    echo   991 = Hors-serie
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

:: Creer script Python temporaire
set "TEMP_SCRIPT=%TEMP%\add_dataset_%RANDOM%.py"

echo # -*- coding: utf-8 -*- > "%TEMP_SCRIPT%"
echo import json >> "%TEMP_SCRIPT%"
echo import sys >> "%TEMP_SCRIPT%"
echo. >> "%TEMP_SCRIPT%"
echo # Recuperer arguments >> "%TEMP_SCRIPT%"
echo if len(sys.argv) ^< 6: >> "%TEMP_SCRIPT%"
echo     print("Erreur: Nombre de parametres incorrect") >> "%TEMP_SCRIPT%"
echo     sys.exit(1) >> "%TEMP_SCRIPT%"
echo. >> "%TEMP_SCRIPT%"
echo slug = sys.argv[1] >> "%TEMP_SCRIPT%"
echo season = int(sys.argv[2]) >> "%TEMP_SCRIPT%"
echo episode = int(sys.argv[3]) >> "%TEMP_SCRIPT%"
echo language = sys.argv[4] >> "%TEMP_SCRIPT%"
echo url_parts = sys.argv[5:] >> "%TEMP_SCRIPT%"
echo url = ' '.join(url_parts) >> "%TEMP_SCRIPT%"
echo. >> "%TEMP_SCRIPT%"
echo # Charger dataset >> "%TEMP_SCRIPT%"
echo with open('dataset.json', 'r', encoding='utf-8') as f: >> "%TEMP_SCRIPT%"
echo     data = json.load(f) >> "%TEMP_SCRIPT%"
echo. >> "%TEMP_SCRIPT%"
echo # Trouver ou creer anime >> "%TEMP_SCRIPT%"
echo anime = None >> "%TEMP_SCRIPT%"
echo for a in data['anime']: >> "%TEMP_SCRIPT%"
echo     if a['slug'] == slug: >> "%TEMP_SCRIPT%"
echo         anime = a >> "%TEMP_SCRIPT%"
echo         break >> "%TEMP_SCRIPT%"
echo. >> "%TEMP_SCRIPT%"
echo if not anime: >> "%TEMP_SCRIPT%"
echo     anime = {'slug': slug, 'streams': []} >> "%TEMP_SCRIPT%"
echo     data['anime'].append(anime) >> "%TEMP_SCRIPT%"
echo. >> "%TEMP_SCRIPT%"
echo # Chercher stream existant >> "%TEMP_SCRIPT%"
echo existing_stream = None >> "%TEMP_SCRIPT%"
echo for stream in anime['streams']: >> "%TEMP_SCRIPT%"
echo     if (stream['season'] == season and stream['episode'] == episode and stream['language'] == language): >> "%TEMP_SCRIPT%"
echo         existing_stream = stream >> "%TEMP_SCRIPT%"
echo         break >> "%TEMP_SCRIPT%"
echo. >> "%TEMP_SCRIPT%"
echo if existing_stream: >> "%TEMP_SCRIPT%"
echo     if url in existing_stream['urls']: >> "%TEMP_SCRIPT%"
echo         print('Cette URL est deja presente pour cet episode!') >> "%TEMP_SCRIPT%"
echo         sys.exit(1) >> "%TEMP_SCRIPT%"
echo     existing_stream['urls'].append(url) >> "%TEMP_SCRIPT%"
echo else: >> "%TEMP_SCRIPT%"
echo     new_stream = {'season': season, 'episode': episode, 'language': language, 'urls': [url]} >> "%TEMP_SCRIPT%"
echo     anime['streams'].append(new_stream) >> "%TEMP_SCRIPT%"
echo. >> "%TEMP_SCRIPT%"
echo # Trier >> "%TEMP_SCRIPT%"
echo ordre = {'VOSTFR': 0, 'VF': 1, 'VF1': 2, 'VF2': 3} >> "%TEMP_SCRIPT%"
echo anime['streams'].sort(key=lambda x: (x['season'], x['episode'], ordre.get(x['language'], 99))) >> "%TEMP_SCRIPT%"
echo. >> "%TEMP_SCRIPT%"
echo # Sauvegarder >> "%TEMP_SCRIPT%"
echo with open('dataset.json', 'w', encoding='utf-8') as f: >> "%TEMP_SCRIPT%"
echo     json.dump(data, f, ensure_ascii=False, indent=2) >> "%TEMP_SCRIPT%"
echo. >> "%TEMP_SCRIPT%"
echo print(f'Ajoute: {slug} S{season}E{episode} {language}') >> "%TEMP_SCRIPT%"

:: Executer le script Python
%PYTHON_CMD% "%TEMP_SCRIPT%" %*
set "RESULT=%ERRORLEVEL%"

:: Nettoyer
del "%TEMP_SCRIPT%" 2>nul

if %RESULT% equ 0 (
    echo.
    echo Dataset mis a jour avec succes!
) else (
    echo.
    echo Echec de la mise a jour du dataset
)

exit /b %RESULT%