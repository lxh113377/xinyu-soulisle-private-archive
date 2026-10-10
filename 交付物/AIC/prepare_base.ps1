# Step 1 —— 从「用户的原稿」重建中间底座
#   复制原稿 → 用 PowerPoint 原生 Duplicate 复制用户第 14 页版式若干份追加到末尾
#   这样做的好处：背景图、卡片样式、字体、页码位置 100% 继承用户的视觉，不会走样。
# 用法：powershell -ExecutionPolicy Bypass -File prepare_base.ps1
$ErrorActionPreference = "Stop"
$here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$src   = "c:\Users\37533\Desktop\workspace\项目\陪聊\交付物\提交包\心屿MindIsle_参赛方案.pptx"
$base  = Join-Path $here "_build_base.pptx"
$dups  = 4          # 需要新增的页数（与 build_aic_ppt.py 的 NEW_SLIDES 条数一致）
$tplNo = 14         # 用作版式模板的用户原页号

if (-not (Test-Path $src)) { Write-Error "找不到用户原稿：$src"; exit 1 }
Copy-Item $src $base -Force

$pp = New-Object -ComObject PowerPoint.Application
try {
    $pres = $pp.Presentations.Open($base, $false, $false, $false)
    $tpl  = $pres.Slides.Item($tplNo)
    for ($i = 0; $i -lt $dups; $i++) {
        $d = $tpl.Duplicate(1)
        $d.MoveTo($pres.Slides.Count)
    }
    $pres.Save()
    Write-Host ("底座就绪：{0} 页（20 用户页 + {1} 版式页）" -f $pres.Slides.Count, $dups)
    $pres.Close()
} finally {
    # 只退出自己打开的实例：先确认没有别的文档被打开
    try { if ($pp.Presentations.Count -eq 0) { $pp.Quit() } } catch { }
}
Write-Host "下一步：python build_aic_ppt.py"
