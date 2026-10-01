@echo off
rem Actualizacion del mapa de VUT de Marbella desde este ordenador (alternativa a GitHub Actions).
rem Descarga el RTA, completa el Catastro de parcelas nuevas y publica en GitHub si hay cambios.
cd /d "%~dp0"
git pull -q || exit /b 1
"C:\Users\josem\AppData\Local\Python\pythoncore-3.14-64\python.exe" generar_mapa.py || exit /b 1
"C:\Users\josem\AppData\Local\Python\pythoncore-3.14-64\python.exe" generar_edificios.py
git add -A
git diff --cached --quiet && (echo Sin cambios & exit /b 0)
git commit -q -m "Actualizacion automatica (local) %date%"
git push -q
