#!/usr/bin/env bash
# Instala o servico numa maquina Ubuntu 24.04 nova - ARM (Oracle) ou x86 (Lightsail).
#
#   sudo git clone https://github.com/RodrigoAraujo12/IA-Judicial.git /opt/triagem
#   sudo bash /opt/triagem/implantacao/instalar-servidor.sh DOMINIO EMAIL
#
# DOMINIO precisa ja apontar para o IP desta maquina (o HTTPS depende disso);
# EMAIL vai para o Let's Encrypt, que avisa se o certificado for expirar.
#
# Pode rodar de novo quantas vezes quiser: cada passo confere se ja foi feito, e
# nada em /var/lib/triagem (contas e casos) e apagado ou sobrescrito.
#
# O guia completo, com a criacao da maquina, esta em IMPLANTACAO.md.

set -euo pipefail

DOMINIO="${1:-}"
EMAIL="${2:-}"
APP=/opt/triagem
DADOS=/var/lib/triagem
USUARIO=triagem
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

falha() { echo "ERRO: $*" >&2; exit 1; }
passo() { echo; echo "==> $*"; }

[ "$(id -u)" -eq 0 ] || falha "rode com sudo"
[ -n "$DOMINIO" ] && [ -n "$EMAIL" ] || falha "uso: sudo bash $0 DOMINIO EMAIL"
[ "$AQUI" = "$APP/implantacao" ] || falha "o repositorio precisa estar em $APP (esta em ${AQUI%/implantacao})"
# shellcheck source=/dev/null
. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID%%.*}" -ge 24 ] ||
	falha "precisa de Ubuntu 24.04 ou mais novo (esta maquina: ${PRETTY_NAME:-desconhecido})"

passo "Pacotes do sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
# caddy: proxy com HTTPS automatico. sqlite3 e gnupg: backup consistente e
# cifrado. rclone: leva o backup para fora da maquina.
apt-get install -y -q python3-venv git sqlite3 gnupg rclone caddy curl

passo "Memoria de troca"
# Com 4 GB (Lightsail) o app usa ~2,7 GB com o modelo carregado. A troca nao e
# para uso normal - e para um pico nao derrubar o processo.
memoria_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
if [ "$memoria_kb" -lt 6000000 ] && ! swapon --show | grep -q .; then
	fallocate -l 2G /swapfile
	chmod 600 /swapfile
	mkswap /swapfile
	swapon /swapfile
	grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
	echo "2 GB de troca criados"
else
	echo "nao precisa (memoria suficiente, ou ja existe troca)"
fi

passo "Usuario do servico e pastas"
id -u "$USUARIO" >/dev/null 2>&1 ||
	useradd --system --home-dir "$DADOS" --shell /usr/sbin/nologin "$USUARIO"
# Contas e casos: so o servico le. E a pasta que o backup leva.
install -d -o "$USUARIO" -g "$USUARIO" -m 700 "$DADOS"
# Corpus e modelo: reconstruiveis, mas o servico precisa gravar no corpus (ele
# migra esquema ao abrir).
install -d -o "$USUARIO" -g "$USUARIO" -m 755 "$APP/dados" "$APP/modelos"

passo "Ambiente Python e dependencias"
[ -x "$APP/.venv/bin/python" ] || python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"

passo "Modelo de busca por sentido (2,2 GB, uma vez)"
if [ -s "$APP/modelos/bge-m3/model.onnx_data" ]; then
	echo "ja esta la"
else
	(cd "$APP" && sudo -u "$USUARIO" "$APP/.venv/bin/python" -m app.corpus.baixar_modelo)
fi

passo "Configuracao"
if [ ! -f /etc/triagem.env ]; then
	cat > /etc/triagem.env <<EOF
TRIAGEM_MODO=servico
TRIAGEM_DADOS=$DADOS
# Destino externo do backup, no formato do rclone (ex.: oracle:triagem-backups).
# Vazio = backup so local. Ver IMPLANTACAO.md, "Backup fora da maquina".
TRIAGEM_BACKUP_REMOTO=
EOF
fi
chown root:"$USUARIO" /etc/triagem.env
chmod 640 /etc/triagem.env

passo "Servico do app"
install -m 644 "$AQUI/triagem.service" /etc/systemd/system/triagem.service
systemctl daemon-reload
systemctl enable triagem >/dev/null
systemctl restart triagem

passo "HTTPS (Caddy) para $DOMINIO"
sed -e "s|__DOMINIO__|$DOMINIO|" -e "s|__EMAIL__|$EMAIL|" "$AQUI/Caddyfile" > /etc/caddy/Caddyfile
systemctl enable caddy >/dev/null
systemctl restart caddy

passo "Firewall da maquina"
# As imagens Ubuntu da Oracle vem com iptables recusando tudo menos SSH - alem da
# Security List no painel, que e outra camada. Aqui so se abre a da maquina.
if command -v iptables >/dev/null && iptables -S INPUT 2>/dev/null | grep -q -- '-j REJECT'; then
	for porta in 80 443; do
		iptables -C INPUT -p tcp --dport "$porta" -m state --state NEW -j ACCEPT 2>/dev/null ||
			iptables -I INPUT 1 -p tcp --dport "$porta" -m state --state NEW -j ACCEPT
	done
	if command -v netfilter-persistent >/dev/null; then netfilter-persistent save; fi
	echo "portas 80 e 443 abertas no iptables"
else
	echo "nada a fazer (sem regra de bloqueio no iptables)"
fi

passo "Backup diario"
if [ ! -f /etc/triagem-backup.chave ]; then
	head -c 48 /dev/urandom | base64 -w0 > /etc/triagem-backup.chave
	CHAVE_NOVA=1
fi
chmod 600 /etc/triagem-backup.chave
install -m 755 "$AQUI/backup.sh" /usr/local/sbin/triagem-backup
install -m 644 "$AQUI/triagem-backup.service" "$AQUI/triagem-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now triagem-backup.timer >/dev/null
install -m 755 "$AQUI/triagem-contas" /usr/local/bin/triagem-contas

passo "Conferencia"
for _ in $(seq 1 30); do
	codigo=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/login || true)
	[ "$codigo" = 200 ] && break
	sleep 1
done
[ "$codigo" = 200 ] || falha "o app nao respondeu em 127.0.0.1:8000 - veja: journalctl -u triagem -n 50"
echo "app no ar (127.0.0.1:8000/login -> 200)"

echo
echo "======================================================================"
echo " Instalado. Proximos passos (detalhe em IMPLANTACAO.md):"
echo
if [ ! -s "$APP/dados/corpus.db" ]; then
	echo " * FALTA O CORPUS. Do seu computador:"
	echo "     scp dados/corpus.db ubuntu@IP:/tmp/"
	echo "   e aqui:"
	echo "     sudo install -o $USUARIO -g $USUARIO -m 600 /tmp/corpus.db $APP/dados/corpus.db"
	echo "     sudo systemctl restart triagem"
	echo
fi
echo " * Crie o escritorio e a primeira pessoa:"
echo "     sudo triagem-contas criar-escritorio \"Nome do Escritorio\""
echo "     sudo triagem-contas criar-usuario 1 email@escritorio.adv.br \"Nome\""
echo
echo " * Abra https://$DOMINIO"
if [ "${CHAVE_NOVA:-0}" = 1 ]; then
	echo
	echo " * GUARDE A CHAVE DO BACKUP fora do servidor (gerenciador de senhas):"
	echo "     sudo cat /etc/triagem-backup.chave"
	echo "   Sem ela, nenhum backup abre."
fi
echo "======================================================================"
