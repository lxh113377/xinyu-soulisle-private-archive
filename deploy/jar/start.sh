#!/usr/bin/env bash
# SoulIsle fat-jar launcher (Linux / macOS)
# Usage:
#   ./start.sh                          # port 8080, serve ./web if present else <repo>/src
#   ./start.sh --port 8123
#   ./start.sh --web-root /opt/xinyu/web
#   ./start.sh --token my-secret        # enable X-Xinyu-Token gate (empty = open)
set -euo pipefail

PORT=8080
WEB_ROOT=""
TOKEN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --web-root) WEB_ROOT="$2"; shift 2 ;;
    --token) TOKEN="$2"; shift 2 ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

JAR="$HERE/soulisle-server.jar"
if [[ ! -f "$JAR" ]]; then
  REPO="$(cd "$HERE/../.." && pwd)"
  JAR="$REPO/server/target/soulisle-server.jar"
fi
[[ -f "$JAR" ]] || { echo "jar not found. Build first: mvn -f server/pom.xml package" >&2; exit 1; }

if [[ -z "$WEB_ROOT" ]]; then
  if [[ -f "$HERE/web/index.html" ]]; then
    WEB_ROOT="$HERE/web"
  else
    REPO="$(cd "$HERE/../.." && pwd)"
    WEB_ROOT="$REPO/src"
  fi
fi
[[ -f "$WEB_ROOT/index.html" ]] || { echo "index.html not found under: $WEB_ROOT" >&2; exit 1; }

export XINYU_WEB_ROOT="$WEB_ROOT"
[[ -n "$TOKEN" ]] && export XINYU_API_TOKEN="$TOKEN"
if [[ -z "${DEEPSEEK_KEY:-}" ]]; then
  echo "WARN: DEEPSEEK_KEY not set -> /api/chat falls back to offline templates." >&2
fi
if [[ -z "${XINYU_EVAL_DATASET:-}" && -f "$HERE/emotion-eval-dataset.json" ]]; then
  export XINYU_EVAL_DATASET="$HERE/emotion-eval-dataset.json"
fi

# Probe for a JDK >= 17 (mirrors the Windows trap: a stale JAVA_HOME of JDK 8
# makes Spring Boot 3 die with UnsupportedClassVersionError).
is_java17() {
  [[ -n "$1" && -x "$1" ]] || return 1
  local out major
  out="$("$1" -version 2>&1 || true)"
  major="$(printf '%s' "$out" | sed -n 's/.*version "\([0-9]*\).*/\1/p' | head -n1)"
  [[ -n "$major" && "$major" -ge 17 ]]
}

CANDIDATES=()
[[ -n "${JAVA_HOME:-}" ]] && CANDIDATES+=("$JAVA_HOME/bin/java")
command -v java >/dev/null 2>&1 && CANDIDATES+=("$(command -v java)")
for d in /usr/lib/jvm/jdk-17* /usr/lib/jvm/java-17* /opt/jdk-17* /opt/java/jdk-17*; do
  [[ -x "$d/bin/java" ]] && CANDIDATES+=("$d/bin/java")
done

JAVA_BIN=""
for c in "${CANDIDATES[@]}"; do
  if is_java17 "$c"; then JAVA_BIN="$c"; break; fi
done
[[ -n "$JAVA_BIN" ]] || { echo "No JDK >= 17 found. Install JDK 17 or set JAVA_HOME." >&2; exit 1; }

echo "jar     : $JAR"
echo "webRoot : $XINYU_WEB_ROOT"
echo "port    : $PORT"
echo "token   : ${TOKEN:+ON}${TOKEN:-OFF (open)}"
echo "--- starting (Ctrl+C to stop) ---"
exec "$JAVA_BIN" -jar "$JAR" --server.port="$PORT"
