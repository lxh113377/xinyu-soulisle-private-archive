# 心屿 SoulIsle · 应用方案 PDF 重新渲染
#
# 用途：改完 application-plan.html 或替换 img/ 下的截图后，重新出 PDF。
# 用法（在本目录执行）：
#   powershell -ExecutionPolicy Bypass -File render-pdf.ps1
#
# 依赖：Microsoft Edge（用其 headless 打印能力）。机器上没有 pandoc / wkhtmltopdf /
#       weasyprint / reportlab，Edge 是本机唯一可用且中文字体表现正常的一条路。
# 硬约束：官方要求应用方案 PDF ≤20 页，脚本末尾会校验页数并告警。

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $here "application-plan.html"
$out  = Join-Path $here "心屿SoulIsle-应用方案.pdf"

$edge = @(
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $edge) { Write-Error "未找到 Microsoft Edge，无法渲染 PDF"; exit 1 }
if (-not (Test-Path $html)) { Write-Error "缺少 $html"; exit 1 }

# 先渲染到临时文件、成功后再替换：禁止先删旧 PDF 再渲染（渲染中断 = 交付物丢失）。
# Edge 的无害 stderr 噪音（如 QQBrowser 提示）必须走 Start-Process 重定向到文件，
# 禁用 `2>&1 | Out-Null` —— EAP=Stop 下它会变成终止性 ErrorRecord 中断渲染。
$tmp = Join-Path $here "_render_tmp.pdf"
$errLog = Join-Path $env:TEMP "xinyu-render-edge-stderr.log"
if (Test-Path $tmp) { Remove-Item $tmp -Force }
$p = Start-Process -FilePath $edge -Wait -PassThru -RedirectStandardError $errLog -ArgumentList @(
  '--headless=new', '--disable-gpu', '--no-sandbox', '--no-pdf-header-footer',
  '--run-all-compositor-stages-before-draw', '--virtual-time-budget=15000',
  "--print-to-pdf=$tmp", "$html"
)
Start-Sleep -Seconds 2

if (-not (Test-Path $tmp)) { Write-Error "PDF 渲染失败（Edge 未产出文件，stderr 见 $errLog，退出码 $($p.ExitCode)）"; exit 1 }
Move-Item $tmp $out -Force

$text  = [System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($out))
$pages = ([regex]::Matches($text, "/Type\s*/Page[^s]")).Count
$imgs  = ([regex]::Matches($text, "/Subtype\s*/Image")).Count

Write-Host "PDF 已生成: $out"
Write-Host ("  页数 = {0}   图片 = {1}   大小 = {2:N0} KB" -f $pages, $imgs, ((Get-Item $out).Length / 1KB))
if ($pages -gt 20) { Write-Warning "⚠️ 页数 $pages 已超过官方硬约束 20 页，必须精简内容" }
else { Write-Host "  ✅ 满足 ≤20 页硬约束" }
if ($imgs -lt 8) { Write-Warning "⚠️ 只嵌入 $imgs 张图（预期 8 张），检查 img/ 下截图是否缺失" }
