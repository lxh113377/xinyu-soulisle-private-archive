# Step 3 —— 导出官方要求的 PDF 格式（AIC 要求答辩 PPT 统一为 PDF）
#   优先用 PowerPoint 原生导出（保真度最高）；
#   若本机 COM 不可用（实测出现过 TYPE_E_CANTLOADLIBRARY），自动降级到 LibreOffice。
# 用法：powershell -ExecutionPolicy Bypass -File export_pdf.ps1
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$src  = Join-Path $here "心屿MindIsle_AIC参赛方案.pptx"
$out  = Join-Path $here "心屿MindIsle_AIC参赛方案.pdf"

if (-not (Test-Path $src)) { Write-Host "缺少 $src，请先跑 build_aic_ppt.py" ; exit 1 }
$before = if (Test-Path $out) { (Get-Item $out).LastWriteTime } else { [datetime]::MinValue }

$done = $false
try {
    $app = New-Object -ComObject PowerPoint.Application
    if ($app -ne $null -and $app.Presentations -ne $null) {
        $pres = $app.Presentations.Open($src, $true, $false, $false)   # ReadOnly
        $pres.SaveCopyAs($out, 32)                                     # 32 = ppSaveAsPDF
        $pres.Close()
        if ($app.Presentations.Count -eq 0) { $app.Quit() }
        Write-Host "通道：PowerPoint 原生导出"
        $done = $true
    }
} catch {
    Write-Host ("PowerPoint COM 不可用，原因：" + $_.Exception.Message.Split("`n")[0])
}

if (-not $done) {
    Write-Host "回退通道：LibreOffice headless"
    $soffice = @(
        "C:\Program Files\LibreOffice\program\soffice.exe",
        "C:\Program Files (x86)\LibreOffice\program\soffice.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $soffice) { Write-Host "✗ 未找到 LibreOffice，无法导出 PDF"; exit 1 }
    & $soffice --headless --norestore --convert-to pdf --outdir $here $src | Out-Null
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 2
        if ((Test-Path $out) -and ((Get-Item $out).LastWriteTime -gt $before)) { break }
    }
}

if (-not (Test-Path $out)) { Write-Host "✗ PDF 未产出"; exit 1 }
$f = Get-Item $out
Write-Host ("PDF：{0}  ({1} MB, {2})" -f $f.Name, [math]::Round($f.Length / 1MB, 2), $f.LastWriteTime)
if ($f.LastWriteTime -le $before) { Write-Host "⚠ PDF 时间戳未更新：可能仍是旧版本，请检查"; exit 3 }
Write-Host "✅ PDF 已更新"
