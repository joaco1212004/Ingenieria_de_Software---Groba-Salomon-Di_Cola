#!/usr/bin/env bash
# Limpieza recurrente de disco para EC2-1 (small, 15 GB). Corre por cron
# (ver instalacion abajo). Solo toca cruft regenerable: NUNCA borra volumenes
# de Docker (warehouse, MinIO, Prometheus) ni datos.
#
# Motivacion: el CD hace `docker compose up -d --build` en cada deploy a main,
# y cada rebuild deja la imagen anterior como capa colgada (<none>, ~774 MB).
# Sin limpieza eso llena los 15 GB en pocas semanas (paso: la small llego a
# 100% de disco). Esto ataca ese leak + los caches de pip/poetry.
#
# Instalacion en EC2-1 (una vez):
#   sudo cp scripts/ec2-cleanup.sh /usr/local/bin/ec2-cleanup.sh
#   sudo chmod +x /usr/local/bin/ec2-cleanup.sh
#   ( crontab -l 2>/dev/null; echo '0 4 * * 0 /usr/local/bin/ec2-cleanup.sh >> /var/log/ec2-cleanup.log 2>&1' ) | crontab -
#   # -> domingos 04:00. Log en /var/log/ec2-cleanup.log
set -uo pipefail

echo "=== ec2-cleanup $(date -Is) ==="
echo "-- disco antes --"; df -h / | tail -1

# 1) Capas de imagenes colgadas de rebuilds viejos (el leak principal).
#    -f = sin prompt. NO se usa -a: eso borraria imagenes base en uso.
docker image prune -f 2>/dev/null || true

# 2) Cache de build (BuildKit/legacy).
docker builder prune -f 2>/dev/null || true

# 3) Caches de descarga de pip/poetry (se regeneran solos si hace falta).
rm -rf "$HOME/.cache/pip" "$HOME/.cache/pypoetry" 2>/dev/null || true

# 4) Logs de systemd a 7 dias (inofensivo si estan en tmpfs).
sudo journalctl --vacuum-time=7d 2>/dev/null || true

# 5) Cache de apt.
sudo apt-get clean 2>/dev/null || true

echo "-- disco despues --"; df -h / | tail -1
echo "=== fin ==="
