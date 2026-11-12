#!/bin/sh
# Backup do Postgres do Horun — roda dentro de um container postgres:16-alpine
# (serviço "db-backup" do docker-compose.yml). Faz um dump ao subir e depois a
# cada BACKUP_INTERVAL_HOURS; apaga dumps com mais de BACKUP_KEEP_DAYS dias.
#
# Variáveis (vêm do compose): PGHOST PGUSER PGPASSWORD PGDATABASE,
# BACKUP_PREFIX (nome do arquivo), BACKUP_KEEP_DAYS, BACKUP_INTERVAL_HOURS,
# BACKUP_ONCE=1 (faz um dump só e sai — útil para testar).
#
# Arquivos enviados (revisão de 12/11/2026 — documentos do Financeiro e
# arquivos do Resultados ficavam SEM backup): com BACKUP_FILES_DIR (a pasta de
# uploads montada só-leitura), cada rodada também gera
# <prefixo>_arquivos_<data>.tar.gz, conferido e com rotação própria
# (BACKUP_FILES_KEEP_DAYS, padrão 7 — é uma cópia inteira por dia).
#
# Ao final de uma rodada sem erro, grava <prefixo>_ULTIMO_BACKUP_OK.txt com a
# data: é o que um monitor (ou uma olhada na pasta) usa para saber se o
# backup está em dia.
#
# Formato "custom" (-Fc): comprimido e restaurável com pg_restore, tabela a
# tabela se precisar. Como restaurar: Prompt_Horun_Core.md, seção 9.4.
set -eu

DIR="${BACKUP_TARGET:-/backups}"  # dentro do container; o compose monta BACKUP_DIR aqui
PREFIX="${BACKUP_PREFIX:-horun}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
INTERVAL_HOURS="${BACKUP_INTERVAL_HOURS:-24}"
FILES_DIR="${BACKUP_FILES_DIR:-}"
FILES_KEEP_DAYS="${BACKUP_FILES_KEEP_DAYS:-7}"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') [backup $PREFIX] $*"; }

dump_once() {
    stamp="$(date '+%Y-%m-%d_%H%M')"
    final="$DIR/${PREFIX}_${stamp}.dump"
    tmp="$DIR/.${PREFIX}_${stamp}.dump.tmp"
    # grava num temporário e só renomeia no fim: um dump interrompido nunca
    # fica parecendo um backup válido
    if ! pg_dump -Fc -f "$tmp"; then
        rm -f "$tmp"
        log "ERRO: pg_dump falhou"
        return 1
    fi
    # confere que o arquivo abre (lista o conteúdo sem restaurar nada)
    if ! pg_restore --list "$tmp" > /dev/null; then
        rm -f "$tmp"
        log "ERRO: dump gerado não abre com pg_restore — descartado"
        return 1
    fi
    mv "$tmp" "$final"
    log "ok: $(basename "$final") ($(du -h "$final" | cut -f1))"
    # rotação: só mexe nos arquivos deste prefixo
    find "$DIR" -maxdepth 1 -name "${PREFIX}_*.dump" -type f -mtime "+$KEEP_DAYS" -print -delete \
        | while read -r old; do log "apagado (mais de $KEEP_DAYS dias): $(basename "$old")"; done
}

files_once() {
    [ -n "$FILES_DIR" ] || return 0
    if [ ! -d "$FILES_DIR" ]; then
        log "ERRO: pasta de arquivos $FILES_DIR não existe"
        return 1
    fi
    stamp="$(date '+%Y-%m-%d_%H%M')"
    final="$DIR/${PREFIX}_arquivos_${stamp}.tar.gz"
    tmp="$DIR/.${PREFIX}_arquivos_${stamp}.tar.gz.tmp"
    if ! tar -czf "$tmp" -C "$FILES_DIR" .; then
        rm -f "$tmp"
        log "ERRO: cópia dos arquivos falhou"
        return 1
    fi
    if ! tar -tzf "$tmp" > /dev/null; then
        rm -f "$tmp"
        log "ERRO: cópia dos arquivos não abre — descartada"
        return 1
    fi
    mv "$tmp" "$final"
    log "ok: $(basename "$final") ($(du -h "$final" | cut -f1))"
    find "$DIR" -maxdepth 1 -name "${PREFIX}_arquivos_*.tar.gz" -type f -mtime "+$FILES_KEEP_DAYS" -print -delete \
        | while read -r old; do log "apagado (mais de $FILES_KEEP_DAYS dias): $(basename "$old")"; done
}

mkdir -p "$DIR"
until pg_isready -q; do
    log "aguardando o banco..."
    sleep 5
done

while true; do
    ok=1
    dump_once || ok=0
    files_once || ok=0
    if [ "$ok" = "1" ]; then
        date '+%Y-%m-%d %H:%M:%S' > "$DIR/${PREFIX}_ULTIMO_BACKUP_OK.txt"
    fi
    [ "${BACKUP_ONCE:-0}" = "1" ] && exit 0
    sleep $((INTERVAL_HOURS * 3600))
done
