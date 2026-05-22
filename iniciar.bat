@echo off
title Backbe Dashboard
cd /d "%~dp0"
echo Iniciando Backbe Dashboard...
echo Acesse: http://localhost:8502
echo.
echo Pressione Ctrl+C para encerrar.
python -m streamlit run app.py --server.port=8502
pause
