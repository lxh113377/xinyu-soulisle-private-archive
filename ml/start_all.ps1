# 心屿 · 一键演示启动（Java 业务服务 + Python 模型服务）
# 用法：powershell -File ml\start_all.ps1
# 判据：/api/health 与 /health 双 UP 才算起成功（脚本内自验），随后打印验收样例。
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$ml = Join-Path $root "ml"

# JDK 17（系统默认 JDK 8，必须显式切）
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"

# 本地模型腿接线：Java 侧通过该环境变量开启三级路由（留空 = 行为与旧双路一致）
$env:XINYU_EMOTION_MODEL_URL = "http://127.0.0.1:8300"
$env:XINYU_EMOTION_ROUTE = "auto"

Write-Host "[1/3] 启动 Python 模型服务 (127.0.0.1:8300)..."
$modelProc = Start-Process -FilePath "$ml\.venv\Scripts\python.exe" `
    -ArgumentList "`"$ml\server.py`"" -WorkingDirectory $root -PassThru -WindowStyle Hidden

Write-Host "[2/3] 启动 Java 业务服务 (127.0.0.1:8123)..."
$jar = Join-Path $root "server\target\soulisle-server.jar"
# ⚠️ model-url 必须走命令行参数：实测 Start-Process 子进程对 $env: 环境变量继承不可靠
# （2026-10-09 一手：env 设了但 Spring 读到空 → 恒走 legacyRoute）
$javaProc = Start-Process -FilePath "$env:JAVA_HOME\bin\java.exe" `
    -ArgumentList "-jar", "`"$jar`"", "--server.port=8123", `
        "--xinyu.emotion.model-url=http://127.0.0.1:8300", "--xinyu.emotion.route=auto" `
    -WorkingDirectory $root -PassThru -WindowStyle Hidden

function Wait-Up($url, $name, $sec) {
    for ($i = 0; $i -lt $sec * 2; $i++) {
        try {
            $r = Invoke-RestMethod -Uri $url -TimeoutSec 2
            if ($r.status -eq "UP") { Write-Host "  $name UP"; return $true }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    Write-Host "  $name 未在 ${sec}s 内 UP"; return $false
}

Write-Host "[3/3] 健康检查..."
$ok1 = Wait-Up "http://127.0.0.1:8300/health" "model-service" 40
$ok2 = Wait-Up "http://127.0.0.1:8123/api/health" "java-service" 40
if (-not ($ok1 -and $ok2)) {
    Write-Host "启动失败：model=$ok1 java=$ok2（进程 model=$($modelProc.Id) java=$($javaProc.Id)）"
    exit 1
}

Write-Host "双服务 UP。验收样例："
$demo = @{ text = "明天要答辩，紧张得睡不着" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8123/api/emotion" -Method Post -Body $demo -ContentType "application/json; charset=utf-8" |
    ConvertTo-Json -Depth 4
Write-Host "停止：Stop-Process -Id $($modelProc.Id), $($javaProc.Id)"
