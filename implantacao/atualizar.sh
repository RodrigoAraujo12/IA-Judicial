#!/usr/bin/env bash
# Traz a versao nova do GitHub e reinicia o servico.
#
#   sudo bash /opt/triagem/implantacao/atualizar.sh
#
# Contas e casos nao sao tocados: moram em /var/lib/triagem, fora do codigo.
# Se a atualizacao mexer nos arquivos de implantacao (servico, timer, Caddy),
# rode de novo o instalar-servidor.sh - ele e seguro de repetir.

set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "rode com sudo" >&2; exit 1; }

cd /opt/triagem
git pull --ff-only
.venv/bin/pip install -q -r requirements.txt
systemctl restart triagem
sleep 3
systemctl --no-pager --lines=5 status triagem
