@echo off
REM Uso diario: dois cliques. Sobe o servidor e abre o navegador.
REM
REM O servidor escuta so em 127.0.0.1 - ou seja, so nesta maquina. Nada fica
REM exposto na rede, e isso importa: a entrevista guarda nome, CPF, salario e
REM dado de saude do cliente.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] O sistema ainda nao foi instalado nesta maquina.
  echo.
  echo Rode o instalar.bat primeiro ^(dois cliques nele^).
  echo.
  pause
  exit /b 1
)

REM Clicar duas vezes e o erro mais provavel de todos, e sem este teste o segundo
REM clique despeja um WinError 10048 sobre "bind on address" - que nao diz nada a
REM quem so quer usar o sistema. Se ja esta no ar, abre o navegador e pronto.
netstat -ano | findstr /r /c:"127.0.0.1:8000 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo O sistema JA ESTA ABERTO nesta maquina.
  echo.
  echo Procure a janela preta que ja estava aberta - e ela que mantem o
  echo sistema no ar. Esta aqui pode fechar.
  echo.
  start "" http://127.0.0.1:8000
  "%SystemRoot%\System32\timeout.exe" /t 8 /nobreak >nul
  exit /b 0
)

echo ==========================================
echo   Triagem trabalhista
echo ==========================================
echo.
echo Abrindo em http://127.0.0.1:8000
echo.
echo NAO FECHE ESTA JANELA enquanto estiver usando o sistema.
echo Para encerrar: feche esta janela, ou aperte Ctrl+C.
echo.

REM Tres segundos de folga para o servidor subir antes do navegador bater nele.
REM Sem isso o Chrome mostra "nao foi possivel acessar" e a pessoa acha que quebrou.
REM
REM timeout.exe vai com caminho completo: se houver outro "timeout" no PATH - o do
REM Git Bash, por exemplo - o comando curto pega o errado e a espera nao acontece.
start "" /b cmd /c "%SystemRoot%\System32\timeout.exe /t 3 /nobreak >nul & start """" http://127.0.0.1:8000"

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

REM So se chega aqui quando o servidor cai. Sem o pause a janela some junto com o
REM erro, e nao sobra nada para diagnosticar.
echo.
echo O servidor foi encerrado.
pause
