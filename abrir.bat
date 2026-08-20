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

echo ==========================================
echo   Triagem trabalhista
echo ==========================================
echo.
echo Abrindo em http://127.0.0.1:8000
echo.
echo NAO FECHE ESTA JANELA enquanto estiver usando o sistema.
echo Para encerrar: feche esta janela, ou aperte Ctrl+C.
echo.

REM Dois segundos de folga para o servidor subir antes do navegador bater nele.
REM Sem isso o Chrome mostra "nao foi possivel acessar" e a pessoa acha que quebrou.
start "" /b cmd /c "timeout /t 2 /nobreak >nul & start """" http://127.0.0.1:8000"

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

REM So se chega aqui quando o servidor cai. Sem o pause a janela some junto com o
REM erro, e nao sobra nada para diagnosticar.
echo.
echo O servidor foi encerrado.
pause
