#!/usr/bin/env bash
# push 后必取 CI 回执的一条命令（把"记得去查"从人身上挪到脚本上）。
# 用法：bash _test/push_and_watch.sh [remote] [branch]     默认 origin main
# 退出码 = ci_watch 的退出码：0 全绿 / 1 有红 / 2 未验证（无 run、超时、gh 不可用）
set -u
REMOTE="${1:-origin}"; BRANCH="${2:-main}"
git push "$REMOTE" "$BRANCH" || { echo "PUSH-FAILED ⇒ 不进入 CI 判定"; exit 1; }
SHA="$(git rev-parse HEAD)"
echo "[push_and_watch] 已推 $SHA，等 CI 结论…"
python _test/ci_watch.py --sha "$SHA" --timeout "${CI_WATCH_TIMEOUT:-420}"
rc=$?
case $rc in
  0) echo "[push_and_watch] CI-GREEN，本轮可收口" ;;
  1) echo "[push_and_watch] CI-RED：按上面输出的「下一步指令」修，修完重推并复跑本命令" ;;
  *) echo "[push_and_watch] CI-UNVERIFIED：未拿到结论，**不得记为通过**（网络/gh/超时）" ;;
esac
exit $rc
