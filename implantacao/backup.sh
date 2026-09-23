#!/usr/bin/env bash
# Copia de seguranca das contas e dos casos. Roda todo dia pelo timer
# triagem-backup; para rodar na mao: sudo triagem-backup
#
# O que entra: todo .db de TRIAGEM_DADOS (contas.db e escritorios/*/casos.db).
# O corpus e o modelo ficam de fora - sao reconstruiveis.
#
# `.backup` do sqlite3 copia o banco consistente mesmo com o app gravando no
# meio; copiar o arquivo com `cp` pode pegar uma transacao pela metade.
#
# O arquivo sai cifrado (gpg, AES-256) com a chave de /etc/triagem-backup.chave.
# SEM ESSA CHAVE O BACKUP NAO ABRE - guarde uma copia fora do servidor.
#
# Restaurar:
#   gpg --batch --pinentry-mode loopback --passphrase-file /etc/triagem-backup.chave \
#       -d ARQUIVO.tar.gz.gpg | tar -xzf - -C /var/lib/triagem
#   chown -R triagem:triagem /var/lib/triagem && systemctl restart triagem

set -euo pipefail

# shellcheck source=/dev/null
. /etc/triagem.env
DADOS="${TRIAGEM_DADOS:-/var/lib/triagem}"
CHAVE=/etc/triagem-backup.chave
LOCAL=/var/backups/triagem
MANTER_DIAS=14
# Destino externo, no formato do rclone ("oracle:triagem-backups"). Vazio =
# so a copia local, que nao sobrevive a perda da maquina.
REMOTO="${TRIAGEM_BACKUP_REMOTO:-}"

temp=$(mktemp -d)
trap 'rm -rf "$temp"' EXIT

cd "$DADOS"
while IFS= read -r -d '' banco; do
	mkdir -p "$temp/$(dirname "$banco")"
	sqlite3 "$banco" ".backup '$temp/$banco'"
done < <(find . -name '*.db' -print0)

mkdir -p "$LOCAL"
chmod 700 "$LOCAL"
arquivo="$LOCAL/triagem-$(date +%Y-%m-%d_%H%M).tar.gz.gpg"
tar -C "$temp" -czf - . |
	gpg --batch --yes --pinentry-mode loopback --symmetric --cipher-algo AES256 \
		--passphrase-file "$CHAVE" -o "$arquivo"
find "$LOCAL" -name 'triagem-*.tar.gz.gpg' -mtime +"$MANTER_DIAS" -delete

if [ -n "$REMOTO" ]; then
	rclone copy "$arquivo" "$REMOTO"
	echo "backup: $arquivo -> $REMOTO"
else
	echo "backup: $arquivo (so local - configure TRIAGEM_BACKUP_REMOTO)"
fi
