# 探测本机 PowerPoint COM 是否可用（2026-10-09 中途失效过一次）
$ErrorActionPreference = "Continue"
try {
    $app = New-Object -ComObject PowerPoint.Application
    if ($null -eq $app) { "COM: 对象为 null"; exit 1 }
    if ($null -eq $app.Presentations) { "COM: Presentations 不可用（类型库加载失败）"; exit 1 }
    "COM: 可用，版本 " + $app.Version + "，已打开文档 " + $app.Presentations.Count
    if ($app.Presentations.Count -eq 0) { $app.Quit() }
} catch {
    "COM: 异常 -> " + $_.Exception.Message.Split("`n")[0]
}
