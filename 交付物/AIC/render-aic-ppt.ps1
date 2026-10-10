# 心屿 MindIsle · AIC 答辩 PPT 渲染（PDF 格式，官方要求）
# 用法：powershell -ExecutionPolicy Bypass -File render-aic-ppt.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $here "AIC-答辩PPT.html"
$out  = Join-Path $here "心屿MindIsle-AIC-答辩PPT.pdf"

$edge = @(
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { Write-Error "未找到 Microsoft Edge"; exit 1 }

$tmp = Join-Path $here "_render_ppt_tmp.pdf"
$errLog = Join-Path $env:TEMP "xinyu-render-aic-ppt-stderr.log"
if (Test-Path $tmp) { Remove-Item $tmp -Force }
$p = Start-Process -FilePath $edge -Wait -PassThru -RedirectStandardError $errLog -ArgumentList @(
  '--headless=new', '--disable-gpu', '--no-sandbox', '--no-pdf-header-footer',
  '--run-all-compositor-stages-before-draw', '--virtual-time-budget=10000',
  "--print-to-pdf=$tmp", "$html"
)
Start-Sleep -Seconds 2
if (-not (Test-Path $tmp)) { Write-Error "PDF 渲染失败（stderr 见 $errLog）"; exit 1 }
Move-Item $tmp $out -Force
$sizeMB = [math]::Round((Get-Item $out).Length / 1MB, 2)
Write-Host "PPT PDF 已生成: $out  ($sizeMB MB)"

# 幻灯片数判据：HTML 现读 .slide 数 vs PDF 页数
$htmlSlides = ([regex]::Matches((Get-Content -Raw -Encoding UTF8 $html), 'class="slide"')).Count
$pageMarks = ([regex]::Matches([System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($out)), "/Type\s*/Page[^s]")).Count
Write-Host ("  期望张数 = {0}  PDF 页数 = {1}" -f $htmlSlides, $pageMarks)
if ($pageMarks -ne $htmlSlides) { Write-Warning "⚠ 页数与幻灯片数不一致，可能有内容溢出到额外页（检查每张 slide 是否超高）"; exit 4 }
else { Write-Host "  ✅ 每张 slide 恰好一页" }
