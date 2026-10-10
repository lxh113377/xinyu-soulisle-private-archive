# 心屿 MindIsle · AIC 作品方案 PDF 渲染
# 用途：改完 AIC-作品方案.html 或替换 img/ 截图后，重新出 PDF。
# 用法：powershell -ExecutionPolicy Bypass -File render-aic-pdf.ps1
# 依赖：Microsoft Edge headless 打印。硬约束：AIC 要求 PDF ≤ 10M。
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $here "AIC-作品方案.html"
$out  = Join-Path $here "心屿MindIsle-AIC-作品方案.pdf"

$edge = @(
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { Write-Error "未找到 Microsoft Edge"; exit 1 }
if (-not (Test-Path $html)) { Write-Error "缺少 $html"; exit 1 }

# 先渲染临时文件、成功后替换（禁止先删旧 PDF）
$tmp = Join-Path $here "_render_tmp.pdf"
$errLog = Join-Path $env:TEMP "xinyu-render-aic-stderr.log"
if (Test-Path $tmp) { Remove-Item $tmp -Force }
$p = Start-Process -FilePath $edge -Wait -PassThru -RedirectStandardError $errLog -ArgumentList @(
  '--headless=new', '--disable-gpu', '--no-sandbox', '--no-pdf-header-footer',
  '--run-all-compositor-stages-before-draw', '--virtual-time-budget=15000',
  "--print-to-pdf=$tmp", "$html"
)
Start-Sleep -Seconds 2
if (-not (Test-Path $tmp)) { Write-Error "PDF 渲染失败（stderr 见 $errLog，退出码 $($p.ExitCode)）"; exit 1 }
Move-Item $tmp $out -Force

$sizeMB = [math]::Round((Get-Item $out).Length / 1MB, 2)
Write-Host "PDF 已生成: $out"
Write-Host ("  大小 = {0} MB" -f $sizeMB)
if ($sizeMB -gt 10) { Write-Warning "⚠ 超过官方硬约束 10M，必须压缩"; exit 2 }
else { Write-Host "  ✅ 满足 ≤10M 硬约束" }

# 图片数判据：HTML 现读 <figure> 数 vs PDF 内嵌图数，数不出来判不可信
$htmlFigures = ([regex]::Matches((Get-Content -Raw -Encoding UTF8 $html), '<figure')).Count
if ($htmlFigures -lt 1) { Write-Error "HTML 里数不到 <figure>"; exit 1 }
$bytes = [System.IO.File]::ReadAllBytes($out)
$text = [System.Text.Encoding]::ASCII.GetString($bytes)
$imgs = ([regex]::Matches($text, "/Subtype\s*/Image")).Count
Write-Host ("  图数期望（HTML <figure>）= {0}  PDF 内嵌 = {1}" -f $htmlFigures, $imgs)
if ($imgs -lt $htmlFigures) { Write-Warning "⚠ 只嵌入 $imgs 张图，HTML 声明 $htmlFigures 张"; exit 3 }
else { Write-Host "  ✅ 图片全部嵌入（$imgs/$htmlFigures）" }
