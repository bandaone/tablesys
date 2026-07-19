#!/usr/bin/env bash
# Usage: sudo ./scripts/enable_local_domains.sh start|stop
set -euo pipefail

PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
HOSTS_ENTRY="127.0.0.1 unza.tablesys.cloud demo.tablesys.cloud cbu.tablesys.cloud"
HOSTS_FILE=/etc/hosts
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.local-proxy.yml"

function start_proxy() {
  echo "Adding hosts entry to $HOSTS_FILE (idempotent)"
  if ! grep -q "unza.tablesys.cloud" $HOSTS_FILE 2>/dev/null; then
    echo "$HOSTS_ENTRY" >> $HOSTS_FILE
    echo "Hosts entries added."
  else
    echo "Hosts entries already present."
  fi

  echo "Starting local nginx proxy (requires docker)"
  docker compose -f "$COMPOSE_FILE" up -d local-proxy
  echo "Local proxy started. Visit http://unza.tablesys.cloud/login (or demo/cbu)."
}

function stop_proxy() {
  echo "Stopping local nginx proxy"
  docker compose -f "$COMPOSE_FILE" down

  if grep -q "unza.tablesys.cloud" $HOSTS_FILE 2>/dev/null; then
    echo "Removing hosts entries from $HOSTS_FILE"
    # Remove the exact line we added if present
    sudo sed -i.bak '/unza.tablesys.cloud/d' $HOSTS_FILE
    echo "Hosts entries removed (backup saved as /etc/hosts.bak)."
  else
    echo "No hosts entries found to remove."
  fi
}

if [ "$#" -ne 1 ]; then
  echo "Usage: sudo $0 start|stop"
  exit 2
fi

case "$1" in
  start)
    start_proxy
    ;;
  stop)
    stop_proxy
    ;;
  *)
    echo "Unknown command: $1"
    echo "Usage: sudo $0 start|stop"
    exit 2
    ;;
esac
