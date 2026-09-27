#!/usr/bin/env bash
# push 后必取 CI 回执的一条命令（把"记得去查"从人身上挪到脚本上）。
# 用法：bash _test/push_and_watch.sh [remote] [branch]     默认 origin main
# 退出码 = ci_watch 的退出码：0 全绿 / 1 有红 / 2 未验证（无 run、超时、gh 不可用）
set -u
REMOTE="${1:-origin}"; BRANCH="${2:-main}"
git push "$REMOTE" "$BRANCH" || { echo "PUSH-FAILED ⇒ 不进入 CI 判定"; exit 1; }
SHA="$(git rev-parse HEAD)"
echo "[push_and_watch] 已推 $SHA，等 CI 结论…"
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT
# 预算须 > 被等对象的天花板（2026-09-27 实测）：74 套件下 浏览器回归 job 跑 456s
# （04:16:32 -> 04:24:08），旧默认 420s 低于它 ⇒ 每次绿推都先假报一次 UNVERIFIED。
# 这里抬的是**看守的等待预算**，不是判据阈值：UNVERIFIED 仍是独立状态，超时照旧不算通过。
python _test/ci_watch.py --sha "$SHA" --timeout "${CI_WATCH_TIMEOUT:-900}" 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}   # ⚠ 必须取管道首段：`$?` 在这里是 tee 的码（"退出码死在管道里"）
case $rc in
  0) echo "[push_and_watch] CI-GREEN，本轮可收口" ;;
  1) if grep -q "ENV-QUOTA(" "$LOG" && ! grep -q "RED(判红" "$LOG"; then
       # 为什么专拆这一支：电池 rc=2 也让 CI 红，而它**没有本仓可修项**。
       # 不分开写，下一轮就会去代码里找"计费导致的水红"，甚至抬判据把它洗绿。
       echo "[push_and_watch] CI-RED 但**零判红**：唯一红档是 ENV-QUOTA（上游余额/计费）"
       echo "  ⇒ 本仓无可修项，重推不会变绿；处置动作只有老大能做（充值或换 Key，只走环境变量 DEEPSEEK_KEY）"
       echo "  ⇒ 记收口时写「未验（计费阻塞）」，禁止写成 CI 全绿"
     else
       echo "[push_and_watch] CI-RED：按上面输出的「下一步指令」修，修完重推并复跑本命令"
     fi ;;
  *) echo "[push_and_watch] CI-UNVERIFIED：未拿到结论，**不得记为通过**（网络/gh/超时）" ;;
esac
exit $rc
