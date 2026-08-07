#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${APP_NAME:-telegram-simple-bot}"
IMAGE_NAME="${IMAGE_NAME:-telegram-simple-bot:latest}"
CONFIG_NAME="${CONFIG:-prod}"
DATA_DIR="${DATA_DIR:-$HOME/telegram-simple-bot}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
WEBROOT_DIR="${WEBROOT_DIR:-$SCRIPT_DIR/web/webroot}"

echo ".deploy repo: $SCRIPT_DIR"
echo ".deploy app: $APP_NAME"
echo ".deploy image: $IMAGE_NAME"
echo ".deploy data dir: $DATA_DIR"
echo ".deploy webroot dir: $WEBROOT_DIR"

echo ".deploy pulling latest git changes"
git pull

echo ".deploy preparing external directories"
mkdir -p "$DATA_DIR/db" "$DATA_DIR/certs" "$DATA_DIR/data"
mkdir -p "$WEBROOT_DIR"

CONFIG_FILE="$DATA_DIR/data/app_config_${CONFIG_NAME}.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo ".deploy missing config: $CONFIG_FILE" >&2
  echo ".deploy create it from data/app_config_prod_example.json before running deploy" >&2
  exit 1
fi

if docker container inspect "$APP_NAME" >/dev/null 2>&1; then
  echo ".deploy removing existing container: $APP_NAME"
  docker rm -f "$APP_NAME"
else
  echo ".deploy no existing container: $APP_NAME"
fi

echo ".deploy building docker image"
docker build -t "$IMAGE_NAME" .

echo ".deploy starting container"
docker run -d \
  --name "$APP_NAME" \
  --restart unless-stopped \
  -p 80:8080 \
  -p 443:8443 \
  -e CONFIG="$CONFIG_NAME" \
  -v "$DATA_DIR/db:/app/db" \
  -v "$DATA_DIR/certs:/app/web/certs" \
  -v "$WEBROOT_DIR:/app/web/webroot" \
  -v "$CONFIG_FILE:/app/data/app_config_${CONFIG_NAME}.json:ro" \
  "$IMAGE_NAME"

echo ".deploy pruning unused docker images"
docker image prune -af

echo ".deploy waiting 1 second before logs"
sleep 1

echo ".deploy following logs: $APP_NAME"
docker logs -f "$APP_NAME"
