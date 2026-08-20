@echo off
REM Instalacao, uma vez so. Depois disso, usa-se apenas o abrir.bat.
REM
REM Sem acento nas mensagens de proposito: o console do Windows nao usa UTF-8 por
REM padrao, e "instalacao" legivel vale mais que "instalação" quebrado.
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Triagem trabalhista - instalacao
echo ==========================================
echo.

REM O launcher "py" vem com o instalador oficial do python.org e e mais confiavel
REM que "python", que no Windows pode cair no atalho da Microsoft Store.
set PY=py
%PY% --version >nul 2>&1
if errorlevel 1 (
  set PY=python
  python --version >nul 2>&1
  if errorlevel 1 (
    echo [ERRO] Python nao encontrado.
    echo.
    echo Instale em https://www.python.org/downloads/
    echo IMPORTANTE: marque "Add Python to PATH" na primeira tela do instalador.
    echo.
    pause
    exit /b 1
  )
)

for /f "tokens=*" %%v in ('%PY% --version') do echo Python encontrado: %%v
echo.

if exist ".venv\Scripts\python.exe" (
  echo Ambiente ja existe, reaproveitando.
) else (
  echo Criando ambiente isolado...
  %PY% -m venv .venv
  if errorlevel 1 goto erro
)

echo.
echo Instalando dependencias ^(cerca de 170 MB, pode levar alguns minutos^)...
echo.
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro

echo.
if exist "dados\corpus.db" (
  echo Corpus normativo encontrado: a consulta a lei vai funcionar.
) else (
  echo [AVISO] dados\corpus.db nao esta aqui.
  echo         A entrevista e a minuta funcionam sem ele.
  echo         A consulta a lei so funciona com o arquivo copiado para dados\.
)

REM O modelo de busca por sentido. Sem ele o sistema funciona - a busca por
REM referencia e a busca por palavra continuam inteiras -, mas a busca por
REM sentido ("dispensa imotivada" achando "sem justo motivo") fica de fora.
echo.
if exist "modelos\bge-m3\model.onnx_data" (
  echo Modelo de busca por sentido encontrado.
) else (
  echo O modelo de busca por sentido nao esta nesta pasta.
  echo Sao 2,2 GB de download, uma vez so.
  echo.
  choice /c SN /n /m "Baixar agora? [S/N] "
  if errorlevel 2 (
    echo.
    echo Pulado. O sistema funciona assim mesmo.
    echo Para baixar depois, rode este instalar.bat de novo.
  ) else (
    echo.
    echo Baixando. Pode levar de 2 a 30 minutos, conforme a internet...
    echo.
    ".venv\Scripts\python.exe" -m app.corpus.baixar_modelo
    if errorlevel 1 (
      echo.
      echo [AVISO] O download falhou. O sistema funciona sem ele.
      echo         Rode este instalar.bat de novo para tentar outra vez.
    )
  )
)

echo.
echo ==========================================
echo   Pronto. Use o abrir.bat daqui em diante.
echo ==========================================
echo.
pause
exit /b 0

:erro
echo.
echo [ERRO] A instalacao falhou. Mostre esta janela para quem te passou o sistema.
echo.
pause
exit /b 1
