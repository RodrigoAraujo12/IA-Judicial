# Pôr o serviço no ar

Guia para subir o modo serviço (login, um escritório por conta) num servidor de
verdade. Escrito em 23/09/2026, quando a instalação ficou pronta no repositório e
a conta no provedor ainda não existia. **Continue daqui.**

## Onde paramos

- **O código está pronto**: login e isolamento entre escritórios (`README.md`,
  seção "Modo serviço"), e a instalação para servidor em [`implantacao/`](implantacao/).
- **Provedor do teste: Oracle Cloud, plano grátis** (R$ 0). Se o teste der certo,
  migrar para a **AWS Lightsail em São Paulo, plano de 4 GB (US$ 24/mês)**. A
  Magalu Cloud foi considerada e saiu cara; a comparação completa está no fim.
- **Só casos fictícios no teste.** Dado real de cliente só depois do contrato de
  LGPD com o escritório (o escritório é controlador, o serviço é operador), em
  qualquer provedor.
- **Os scripts rodaram pela primeira vez em 23/09/2026, e funcionaram.** Até ali
  tinham sido escritos e conferidos só na sintaxe, num Windows. A execução real
  foi numa `VM.Standard.E2.1.Micro` da Oracle (Ubuntu 24.04.5, 1 GB, x86), e o
  serviço subiu com HTTPS válido na primeira tentativa. O que a execução ensinou
  está anotado ao longo deste guia; nada precisou ser corrigido no meio.
- **Conferido em 23/09/2026, antes da primeira execução:** os quatro scripts
  passam em `bash -n` e estão com fim de linha Unix (CRLF faria o Linux recusar
  o interpretador); o pacote `caddy` existe no Ubuntu 24.04 (universe, 2.6.2), e
  `numpy`, `onnxruntime` e `tokenizers` publicam pacote pronto para ARM64 em
  Python 3.12 — sem isso o `pip` tentaria compilar e a instalação levaria horas
  no processador do plano grátis.

## O que você vai precisar

- Cartão de crédito (a Oracle só verifica, não cobra dentro do plano grátis).
- Uns 40 minutos, a maior parte esperando download.
- O arquivo `dados/corpus.db` deste computador (89 MB). Ele não está no GitHub, e
  montar o corpus no servidor levaria horas no processador fraco do plano grátis.

  **Confira que ele é o corpus inteiro antes de copiar**, porque o banco não vai
  pelo git e a máquina de onde você copia pode estar atrasada em relação ao
  código:

  ```
  python -c "from app.corpus import banco; c=banco.conectar(); print(banco.estatisticas(c))"
  ```

  Tem de dizer 14 obras e 16.799 redações, com `com_vetor` igual a `redacoes`.
  Se disser menos, refaça com `python -m app.corpus.indexar` e
  `python -m app.corpus.indexar tst trt13 vetores` — a ingestão leva um minuto e
  os vetores, cerca de uma hora em CPU, retomáveis de onde pararem.

## O que a primeira execução mostrou (23/09/2026)

Subiu em `https://triagem-teste.duckdns.org`, do zero, em cerca de 20 minutos de
relógio — a maior parte esperando `apt` e `pip` numa máquina de 1 GB.

| Etapa | Resultado |
|---|---|
| Rede | o formulário de criação de instância **não** monta a rede sozinho: é preciso o assistente de VCN antes (ver passo 2) |
| Máquina ARM | esgotada em São Paulo; caiu-se para a Micro de 1 GB |
| Instalação | os oito passos do script correram sem erro |
| Modelo | pulado sozinho, como previsto para memória abaixo de 3 GB |
| HTTPS | certificado do Let's Encrypt emitido na primeira tentativa, válido por 90 dias |
| Cabeçalhos | HSTS, `X-Frame-Options: DENY`, `nosniff` e `Referrer-Policy` conferidos de fora |
| Backup | rodou à mão, gerou o arquivo cifrado, e o timer ficou agendado para 03h39 |
| Registro de acesso | gravou entrada e listagem com o IP real de quem acessou |
| Memória em uso | 475 MB dos 954, com o app servindo |

Duas coisas que só aparecem rodando: o `git clone` como root deixa o repositório
com dono root, e `git` recusa comandos do usuário `ubuntu` ali dentro
("dubious ownership") — use `sudo git -C /opt/triagem`. E o corpus vai por `scp`
para `/tmp` antes de entrar no lugar definitivo, porque o usuário `ubuntu` não
escreve em `/opt/triagem/dados`.

## 1. Conta na Oracle Cloud

1. Em <https://cloud.oracle.com>, "Start for free".
2. **Região principal (Home Region): Brazil East (Sao Paulo).** Isso não muda
   depois, e o que é grátis só vale na região principal.
3. Terminar o cadastro com o cartão.

## 2. A máquina

Menu → **Compute → Instances → Create instance**:

| Campo | Valor | Por quê |
|---|---|---|
| Image | **Canonical Ubuntu 24.04** | o script exige 24.04 ou mais novo |
| Shape | **Ampere → VM.Standard.A1.Flex**, **2 OCPUs, 8 GB** | não use 12 GB: ver abaixo. Sem vaga ARM? ver "Quando o ARM está esgotado" |
| Networking | criar VCN e sub-rede pública, **com IPv4 público** | |
| SSH keys | **Generate a key pair** e baixar a chave privada | sem ela não se entra na máquina |
| Boot volume | o padrão (~47 GB) basta | o plano grátis dá 200 GB |

**Por que 8 GB e não os 12 que o plano dá:** a Oracle desliga máquinas grátis que
pareçam paradas — 7 dias com processador, rede **e memória** abaixo de 20%. O app
usa ~2,7 GB; com 12 GB isso dá 22%, colado no limite. Com 8 GB dá ~34%.

Se aparecer **"Out of capacity"**, as máquinas ARM grátis esgotaram na região
naquele momento. São Paulo tem um único Availability Domain, então não há outro
para tentar: ou se espera, ou se troca de máquina.

### Quando o ARM está esgotado

Aconteceu na primeira tentativa real, em 23/09/2026. A saída que destrava no
mesmo dia é a outra máquina do plano grátis: **VM.Standard.E2.1.Micro**, Intel,
**1 núcleo e 1 GB**, que quase sempre tem vaga.

Nela **o modelo de busca por sentido não entra** — carregado ele ocupa ~2,5 GB.
O instalador detecta memória abaixo de 3 GB e **pula o download sozinho**,
dizendo o que fez; para forçar, `TRIAGEM_COM_MODELO=1 sudo -E bash ...`.

O que se perde é só a busca por sentido: acerto@5 cai de 62/72 para 58/72. A
consulta por artigo e a busca por palavra ficam inteiras, e a busca degrada
sozinha em vez de quebrar (`testar_busca.py` tranca isso). Tudo o que o teste de
implantação precisa validar — HTTPS, login, isolamento entre escritórios, backup
e registro de acesso — não depende do modelo.

É máquina de teste, não de produção: 1 GB e um núcleo fraco atendem uma pessoa
de cada vez. Para valer, o destino é o ARM com 8 GB quando houver vaga, ou a
Lightsail.

Anote o **IP público** da máquina.

## 3. Abrir as portas 80 e 443

Menu → **Networking → Virtual cloud networks** → a VCN criada → a sub-rede →
**Security List** → **Add Ingress Rules**, duas vezes:

- Source CIDR `0.0.0.0/0`, protocolo TCP, porta de destino **80**
- Source CIDR `0.0.0.0/0`, protocolo TCP, porta de destino **443**

(O firewall de dentro da máquina o script abre sozinho.)

## 4. Um domínio grátis para o teste

O HTTPS exige um domínio. Para testar, <https://www.duckdns.org>: entre com a
conta Google ou GitHub, crie um subdomínio (ex.: `triagem-teste.duckdns.org`) e
ponha nele o IP público da máquina. Para valer, compra-se um `.com.br` no
registro.br (~R$ 40/ano).

## 5. Instalar

Do seu computador (PowerShell serve):

```
ssh -i CAMINHO\DA\CHAVE.key ubuntu@IP
```

Se o Windows reclamar da permissão da chave, rode antes, no PowerShell:
`icacls CAMINHO\DA\CHAVE.key /inheritance:r /grant:r "$($env:USERNAME):(R)"`.

Na máquina:

```
sudo git clone https://github.com/RodrigoAraujo12/IA-Judicial.git /opt/triagem
sudo bash /opt/triagem/implantacao/instalar-servidor.sh triagem-teste.duckdns.org seu@email.com
```

O script instala os pacotes, cria o usuário `triagem`, baixa o modelo (2,2 GB —
pulado sozinho em máquina com menos de 3 GB de memória), sobe o app como serviço,
configura o HTTPS e agenda o backup. No fim ele diz o que falta.

## 6. Levar o corpus

Do seu computador, na pasta do projeto:

```
scp -i CAMINHO\DA\CHAVE.key dados\corpus.db ubuntu@IP:/tmp/
```

Na máquina:

```
sudo install -o triagem -g triagem -m 600 /tmp/corpus.db /opt/triagem/dados/corpus.db
sudo systemctl restart triagem
```

## 7. Criar o escritório e entrar

```
sudo triagem-contas criar-escritorio "Escritório Teste"
sudo triagem-contas criar-usuario 1 voce@email.com "Seu Nome"
```

Abra `https://triagem-teste.duckdns.org` e entre. Para conferir o isolamento, crie
um segundo escritório com outra pessoa e veja que um não enxerga os casos do outro.

## 8. Guardar a chave do backup

```
sudo cat /etc/triagem-backup.chave
```

Copie para o seu gerenciador de senhas. **Sem essa chave nenhum backup abre** —
eles saem cifrados.

## Backup fora da máquina

O backup diário (3h30) fica em `/var/backups/triagem`, 14 dias. Isso não
sobrevive à perda da máquina. Para mandar uma cópia para fora, dentro da Oracle
mesmo (o plano grátis dá 20 GB de armazenamento de objetos):

1. **Storage → Buckets → Create bucket** `triagem-backups`, privado.
2. No seu perfil, **Customer secret keys → Generate** — anote a chave e o segredo.
3. O *namespace* está em **Tenancy details**.
4. Na máquina, `sudo rclone config` → novo remoto `oracle`, tipo **s3**, provider
   **Other**, com a chave e o segredo, endpoint
   `https://NAMESPACE.compat.objectstorage.sa-saopaulo-1.oraclecloud.com` e
   região `sa-saopaulo-1`.
5. Em `/etc/triagem.env`: `TRIAGEM_BACKUP_REMOTO=oracle:triagem-backups`.
6. Teste: `sudo triagem-backup`.

## Dia a dia

| Para | Comando |
|---|---|
| atualizar o código | `sudo bash /opt/triagem/implantacao/atualizar.sh` |
| ver o app | `systemctl status triagem` e `journalctl -u triagem -n 50` |
| ver o HTTPS | `journalctl -u caddy -n 50` |
| contas | `sudo triagem-contas listar` / `redefinir-senha EMAIL` / `desativar EMAIL` |
| quem abriu qual caso | `sudo triagem-contas acessos` / `acessos EMAIL` / `acessos caso:7@1` |
| backup agora | `sudo triagem-backup` |

O registro de acesso mora em `contas.db` e por isso já entra no backup diário,
sem nada a configurar. Ele guarda 180 dias e se limpa sozinho — o porquê do prazo
está em [Registro de acesso](README.md#registro-de-acesso).

**Restaurar um backup**: o comando está no topo de
[`implantacao/backup.sh`](implantacao/backup.sh).

## Quando algo não funciona

- **O site não abre.** Nesta ordem: o domínio aponta para o IP (`ping DOMINIO`)?
  A Security List tem 80 e 443? `sudo iptables -S INPUT` tem as regras de ACCEPT?
  `journalctl -u caddy` diz se o certificado saiu.
- **Abre, mas dá erro.** `journalctl -u triagem -n 50`.
- **Ninguém consegue entrar.** Dez senhas erradas travam o e-mail por 15 minutos.
  Se foi esquecimento: `sudo triagem-contas redefinir-senha EMAIL`.
- **A busca por sentido não funciona, só a por palavra.** O modelo não baixou:
  `cd /opt/triagem && sudo -u triagem .venv/bin/python -m app.corpus.baixar_modelo`.

## Migrar para a Lightsail, se o teste der certo

1. Lightsail → região São Paulo → Linux/Ubuntu 24.04 → plano de 4 GB (US$ 24).
2. **Networking**: anexar um IP estático e liberar a porta **443** (a 80 já vem
   aberta).
3. Passos 5 e 6 deste guia, iguais — o script serve para as duas.
4. Trazer contas e casos: copiar o backup mais recente e a chave, e restaurar
   (comando no topo de `implantacao/backup.sh`).
5. Apontar o domínio para o IP novo e desligar a máquina da Oracle.

## A comparação que levou a esta escolha

Medido em 23/09/2026: o app usa ~2,2 GB de memória com o modelo carregado e
responde em ~50 ms por consulta. Precisa de disco persistente (os casos ficam em
arquivos), o que exclui Vercel, Cloud Run e parecidos; e de datacenter no Brasil,
o que exclui Render, Railway, DigitalOcean e Hetzner.

| Opção (São Paulo) | Configuração | Preço/mês |
|---|---|---|
| Oracle, plano grátis | 2 núcleos ARM, até 12 GB | R$ 0 — a Oracle cortou o plano pela metade em 2026 sem anunciar |
| AWS Lightsail | 2 núcleos, 4 GB, 80 GB | US$ 24 |
| AWS Lightsail | 2 núcleos, 8 GB, 160 GB | US$ 44 |
| Akamai (Linode) | 4 núcleos, 8 GB | US$ 67,20 + US$ 14 de backup |
| Google Cloud | e2-standard-2, 8 GB | US$ 77,65 + disco |
| Magalu Cloud | BV2-8-40 | em reais; saiu caro na calculadora |
| Hostinger VPS | 2 núcleos, 8 GB | R$ 38,99 em promoção — menos garantias para dado de saúde |

## O que ainda falta depois de no ar

- Troca de senha pelo próprio usuário, e recuperação por e-mail.
- Importar os casos de uma instalação local para um escritório do serviço.
- O contrato de LGPD com os escritórios — é o que libera dado real.
