#!/usr/bin/env bash
# push 后必取 CI 回执的一条命令（把"记得去查"从人身上挪到脚本上）。
# 用法：bash _test/push_and_watch.sh [remote] [branch]     默认 origin main
#        XINYU_PUSH_REFS="v1.7.0" 可带上 tag（切版那一轮必须同推分支与 tag，否则 G12 在 CI 上判红）
# 退出码 = ci_watch 的退出码：0 全绿 / 1 有红 / 2 未验证（无 run、超时、gh 不可用）
set -u
REMOTE="${1:-origin}"; BRANCH="${2:-main}"
EXTRA=()
[ -n "${XINYU_PUSH_REFS:-}" ] && EXTRA=($XINYU_PUSH_REFS)
if ! git push "$REMOTE" "$BRANCH" "${EXTRA[@]}"; then
    # r82/r83 两次实测：共享 `.gitconfig` 里 `http.proxy=http://127.0.0.1:7897`，而该代理时常没起
    # ⇒ push 报 `Failed to connect to github.com port 443 via 127.0.0.1`，同一时刻 curl 直连全 200。
    # 处置只对这**一条命令**内联关掉代理——改共享配置属他人可见状态，不在这里做。
    # 首推仍正常优先：真需要代理的网络里第二试也会失败，不会把「必须走代理」这件事掩盖掉。
    echo "[push_and_watch] 首推失败 ⇒ 试一次内联关代理（仅本条命令，不动 ~/.gitconfig）"
    git push -c http.proxy= -c https.proxy= "$REMOTE" "$BRANCH" "${EXTRA[@]}" \
      || { echo "PUSH-FAILED ⇒ 不进入 CI 判定（先按「域名×时刻」测直连再判是谁的锅）"; exit 1; }
fi
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
