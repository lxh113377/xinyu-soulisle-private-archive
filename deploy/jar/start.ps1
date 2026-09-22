#Requires -Version 5.1
# SoulIsle fat-jar launcher (Windows / PowerShell)
# Usage:
#   .\start.ps1                          # port 8080, serve ./web if present else <repo>/src
#   .\start.ps1 -Port 8123               # custom port
#   .\start.ps1 -WebRoot "D:\xinyu\web"  # explicit static root
#   .\start.ps1 -Token "my-secret"       # enable X-Xinyu-Token gate (empty = open)
param(
  [int]$Port = 8080,
  [string]$WebRoot = "",
  [string]$Token = ""
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1) locate jar: prefer a copy next to this script (standalone deploy), else repo build output
$jar = Join-Path $here "soulisle-server.jar"
if (-not (Test-Path $jar)) {
  $repo = Resolve-Path (Join-Path $here "..\..")
  $jar = Join-Path $repo "server\target\soulisle-server.jar"
}
if (-not (Test-Path $jar)) {
  Write-Error "jar not found. Build first: mvn -f server/pom.xml package"
  exit 1
}

# 2) locate static root: prefer ./web next to the script, else repo src (authoritative source)
if (-not $WebRoot) {
  $local = Join-Path $here "web"
  if (Test-Path (Join-Path $local "index.html")) {
    $WebRoot = $local
  } else {
    $repo = Resolve-Path (Join-Path $here "..\..")
    $WebRoot = Join-Path $repo "src"
  }
}
if (-not (Test-Path (Join-Path $WebRoot "index.html"))) {
  Write-Error "index.html not found under WebRoot: $WebRoot"
  exit 1
}

# 3) runtime env
$env:XINYU_WEB_ROOT = (Resolve-Path $WebRoot).Path
if ($Token) { $env:XINYU_API_TOKEN = $Token }
if (-not $env:DEEPSEEK_KEY) {
  Write-Warning "DEEPSEEK_KEY is not set -> /api/chat will fall back to offline templates."
}
if (-not $env:XINYU_EVAL_DATASET) {
  $ds = Join-Path $here "emotion-eval-dataset.json"
  if (Test-Path $ds) { $env:XINYU_EVAL_DATASET = $ds }
}

# 4) pick a JDK >= 17.
#    TRAP: on this machine the default JAVA_HOME is JDK 8, and Spring Boot 3 (class file v61)
#    silently dies with UnsupportedClassVersionError. So we PROBE the version instead of
#    trusting JAVA_HOME. Java 8 prints: java version "1.8.0_402"  -> major 1  -> rejected.
function Test-Java17 {
  param([string]$Exe)
  if (-not $Exe) { return $false }
  if (-not (Test-Path $Exe)) { return $false }
  try {
    # NOTE: `java -version` writes to STDERR. Under $ErrorActionPreference='Stop'
    # PowerShell turns that native stderr into a terminating ErrorRecord, so the
    # probe would ALWAYS fail. Route through cmd.exe so both streams come back as
    # plain text.
    $out = (& cmd /c "`"$Exe`" -version 2>&1") | Out-String
    if ($out -match 'version\s+"(\d+)') {
      return ([int]$Matches[1] -ge 17)
    }
  } catch { }
  return $false
}

$candidates = @()
if ($env:JAVA_HOME) { $candidates += (Join-Path $env:JAVA_HOME "bin\java.exe") }
$cmd = Get-Command java -ErrorAction SilentlyContinue
if ($cmd) { $candidates += $cmd.Source }
$candidates += "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot\bin\java.exe"
Get-ChildItem "C:\Program Files\Eclipse Adoptium" -Directory -Filter "jdk-17*" -ErrorAction SilentlyContinue |
  ForEach-Object { $candidates += (Join-Path $_.FullName "bin\java.exe") }
Get-ChildItem "C:\Program Files\Java" -Directory -Filter "jdk-17*" -ErrorAction SilentlyContinue |
  ForEach-Object { $candidates += (Join-Path $_.FullName "bin\java.exe") }

$java = $null
foreach ($c in ($candidates | Select-Object -Unique)) {
  if (Test-Java17 $c) { $java = $c; break }
}
if (-not $java) {
  Write-Error "No JDK >= 17 found. Install JDK 17 or set JAVA_HOME to it. Probed: $($candidates -join ', ')"
  exit 1
}
Write-Host "java    : $java (JDK>=17 verified)"

Write-Host "jar     : $jar"
Write-Host "webRoot : $env:XINYU_WEB_ROOT"
Write-Host "port    : $Port"
Write-Host "token   : $(if ($Token) { 'ON' } else { 'OFF (open)' })"
Write-Host "--- starting (Ctrl+C to stop) ---"
& $java -jar $jar --server.port=$Port
