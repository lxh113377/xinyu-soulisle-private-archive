# MySQL local dev runner for xinyu SoulIsle (J4 persistence on a real MySQL 8.4).
#
# Why this file exists: the app already reads four env vars (XINYU_DB_URL / _DRIVER /
# _USER / _PASSWORD), so switching databases needs no code change -- but it does need a
# running server, an initialized datadir and a schema that MySQL actually accepts.
# Every step below was verified on 2026-10-12 against MySQL 8.4.9 on this machine.
#
# Dev posture (deliberate, do not ship it as-is to a public host):
#   - binds 127.0.0.1 only, never 0.0.0.0
#   - root has an EMPTY password (mysqld --initialize-insecure), so no secret is ever
#     written to disk or into a shell history line
#   - datadir lives OUTSIDE the repo (default D:\xinyu_mysql\data) to keep the repo light
#   - no Windows service is installed; this starts and stops a plain process
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File server\mysql-local.ps1 -Action Start
#   powershell -ExecutionPolicy Bypass -File server\mysql-local.ps1 -Action Serve
#   powershell -ExecutionPolicy Bypass -File server\mysql-local.ps1 -Action Status
#   powershell -ExecutionPolicy Bypass -File server\mysql-local.ps1 -Action Stop

[CmdletBinding()]
param(
  [ValidateSet("Start", "Stop", "Serve", "Status")]
  [string]$Action = "Status",
  [int]$Port = 8124,
  [int]$DbPort = 3306,
  [string]$DbName = "xinyu",
  [string]$Basedir = "C:\Program Files\MySQL\MySQL Server 8.4",
  [string]$DataDir = "D:\xinyu_mysql\data",
  [string]$JdkHome = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot",
  # Overridable so the fat-jar guard below can be drilled against a deliberately thin file.
  [string]$JarPath = ""
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Mysqld = Join-Path $Basedir "bin\mysqld.exe"
$Mysql = Join-Path $Basedir "bin\mysql.exe"
if ($JarPath -eq "") { $JarPath = Join-Path $Repo "server\target\soulisle-server.jar" }
$Jar = $JarPath
$LogDir = Join-Path $env:TEMP "xinyu-mysql-local"

function Get-MysqldProc {
  # Match on OUR datadir only, so Stop can never kill an unrelated MySQL instance.
  Get-CimInstance Win32_Process -Filter "Name='mysqld.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*$DataDir*" }
}

function Test-PortListening([int]$Number) {
  $c = Get-NetTCPConnection -LocalPort $Number -State Listen -ErrorAction SilentlyContinue
  return [bool]$c
}

function Invoke-Sql([string]$Statement) {
  # Two separate temp files: PS cannot open the SAME file as both stdout and stderr target
  # (it errors with 'being used by another process'), and `2>&1` is not an option here
  # because under $ErrorActionPreference='Stop' PS 5.1 raises a terminating
  # NativeCommandError for a native command's stderr -- i.e. "server is down" would abort
  # the script instead of being reported as a result.
  $tag = [Guid]::NewGuid().ToString("N")
  $o = Join-Path $env:TEMP "xinyu-sql-$tag.out"
  $e = Join-Path $env:TEMP "xinyu-sql-$tag.err"
  $p = Start-Process -FilePath $Mysql -NoNewWindow -Wait -PassThru `
    -ArgumentList @("-h", "127.0.0.1", "-P", "$DbPort", "-u", "root",
                    "--ssl-mode=PREFERRED", "-N", "-B", "-e", "`"$Statement`"") `
    -RedirectStandardOutput $o -RedirectStandardError $e
  $text = @()
  if (Test-Path $o) { $text += @(Get-Content -Path $o); Remove-Item $o -ErrorAction SilentlyContinue }
  if (Test-Path $e) {
    $errText = @(Get-Content -Path $e)
    if ($p.ExitCode -ne 0) { $text += $errText }
    Remove-Item $e -ErrorAction SilentlyContinue
  }
  return [pscustomobject]@{ rc = $p.ExitCode; out = $text }
}

function Test-SqlAlive {
  # Readiness must be measured by the thing we actually need (a query that answers), not by
  # a port that can look open while the server is aborting.
  return ((Invoke-Sql "SELECT 1").rc -eq 0)
}

function Wait-ServerUp([int]$TimeoutSeconds, [int]$ProcId, [string]$LogFile) {
  # Three separate witnesses, polled together: the process we launched still lives, a query
  # answers, and we never declare success from the absence of a negative.
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ($true) {
    if ($ProcId -and -not (Get-Process -Id $ProcId -ErrorAction SilentlyContinue)) {
      throw "mysqld pid=$ProcId exited before answering. Last lines of $LogFile :"
    }
    if (Test-SqlAlive) { return }
    if ((Get-Date) -gt $deadline) { throw "no answer from MySQL on $DbPort within ${TimeoutSeconds}s. Last lines of $LogFile :" }
    Start-Sleep -Milliseconds 500
  }
}

function Show-LogTail([string]$LogFile, [int]$Lines) {
  if (Test-Path $LogFile) {
    Get-Content -Path $LogFile -Tail $Lines | ForEach-Object { Write-Output "  | $_" }
  } else {
    Write-Output "  | (no log file at $LogFile)"
  }
}

function Start-Background([string]$Exe, [string[]]$ArgList, [string]$WorkDir) {
  # Plain ShellExecute start (no -RedirectStandardOutput/-RedirectStandardError).
  # Why (measured 2026-10-12): those switches force UseShellExecute=$false, so the long-lived
  # child inherits the caller's std handles -- `powershell -File this.ps1 -Action Serve | tail`
  # then never sees EOF and hangs (measured: 249s, only released when the child was killed),
  # even though the server itself came up fine. Instead each program writes its own log
  # (mysqld: --log-error, Spring: --logging.file.name), so nothing needs our handles.
  # Elements containing spaces get quoted -- Start-Process joins the array with plain spaces
  # and would otherwise split 'C:\Program Files\...' into two arguments.
  # Name it $ArgList, never $Args: $Args is a PowerShell automatic variable and a parameter
  # with that name silently reads as empty ('Cannot validate argument on parameter ArgumentList').
  $quoted = ($ArgList | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
  return Start-Process -FilePath $Exe -ArgumentList $quoted -WorkingDirectory $WorkDir -WindowStyle Hidden -PassThru
}

function Assert-Binaries {
  foreach ($p in @($Mysqld, $Mysql)) {
    if (-not (Test-Path $p)) {
      throw "not found: $p  (pass -Basedir <path> if MySQL 8.4 sits elsewhere)"
    }
  }
}

function Action-Start {
  Assert-Binaries
  $LogFile = Join-Path $DataDir "mysqld.log"
  if (Test-SqlAlive) {
    $p = (Get-MysqldProc | Select-Object -First 1).ProcessId
    Write-Output "[mysql] already answering on 127.0.0.1:$DbPort (pid=$p) -- nothing to do"
    return
  }
  if (-not (Test-Path (Join-Path $DataDir "mysql.ibd"))) {
    Write-Output "[mysql] datadir missing or empty -> initializing (root, EMPTY password)"
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    & $Mysqld --initialize-insecure "--datadir=$DataDir" "--basedir=$Basedir"
    if ($LASTEXITCODE -ne 0) { throw "mysqld --initialize-insecure rc=$LASTEXITCODE" }
  }
  Write-Output "[mysql] starting mysqld on 127.0.0.1:$DbPort"
  # Every path value is passed as its own argv element and quoted by the helper -- an unquoted
  # basedir under 'C:\Program Files\...' gets split into extra arguments and mysqld aborts with
  # "Too many arguments (first extra is 'Files\MySQL\MySQL')".
  $p = Start-Background -Exe $Mysqld -ArgList @(
    "--datadir=$DataDir",
    "--basedir=$Basedir",
    "--log-error=$LogFile",
    "--bind-address=127.0.0.1",
    "--port=$DbPort"
  ) -WorkDir $Basedir
  try {
    Wait-ServerUp -TimeoutSeconds 60 -ProcId $p.Id -LogFile $LogFile
  } catch {
    Write-Output "[mysql] FAILED: $($_.Exception.Message)"
    Show-LogTail $LogFile 12
    throw
  }
  $mk = Invoke-Sql "CREATE DATABASE IF NOT EXISTS ``$DbName`` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
  if ($mk.rc -ne 0) { throw "CREATE DATABASE failed rc=$($mk.rc): $($mk.out -join ' ')" }
  $v = (Invoke-Sql "SELECT VERSION()").out | Select-Object -Last 1
  Write-Output "[mysql] up: version=$v db=$DbName datadir=$DataDir log=$LogFile"
  Write-Output "[mysql] tables are created by the app at boot (spring.sql.init.mode=always runs schema.sql)"
}

function Action-Stop {
  $procs = @(Get-MysqldProc)
  if ($procs.Count -eq 0) {
    Write-Output "[mysql] no mysqld owning $DataDir is running"
    return
  }
  foreach ($p in $procs) {
    Write-Output "[mysql] stopping pid=$($p.ProcessId) (matched by datadir, not by name)"
    Stop-Process -Id $p.ProcessId -Force
  }
  # InnoDB needs a clean shutdown; a plain kill is acceptable for a throwaway dev dir but
  # say so out loud instead of letting the next boot discover an unclean state by itself.
  Write-Output "[mysql] stopped. NOTE: killed, not 'fast shutdown' -- InnoDB will replay redo on next Start."
}

function Action-Serve {
  Assert-Binaries
  if (-not (Test-SqlAlive)) { throw "MySQL is not answering on $DbPort -- run -Action Start first" }
  if (-not (Test-Path $Jar)) { throw "jar missing: $Jar -- run mvn -f server/pom.xml package first" }
  $len = (Get-Item $Jar).Length
  # A repackaging failure (typically 'Unable to rename ...jar.original' while another JVM
  # holds the file) leaves a thin jar that is a valid zip and still boots as 'no main manifest'.
  # Size is the cheap first-line witness; check BOOT-INF/lib too before trusting it.
  if ($len -lt 20MB) {
    throw "jar is only $len B -- that is a THIN jar, not the fat jar. Rebuild it (see note in this script)."
  }
  $svc = @(Get-CimInstance Win32_Process -Filter "Name='java.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*soulisle-server.jar*" })
  Write-Output "[serve] jar=$len B ; existing soulisle instances=$($svc.Count)"
  if ($svc.Count -gt 0) {
    Write-Output "[serve] WARNING: another session may be using this same jar file."
    Write-Output "[serve]         Do not 'mvn package' while it lives -- Windows allows the"
    Write-Output "[serve]         in-place write but denies the repackage rename."
  }
  if (Test-PortListening $Port) { throw "port $Port is taken -- pass -Port <other>" }
  New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
  $env:XINYU_PORT = "$Port"
  # ${DbName} must be braced: PowerShell parses `$DbName?serverTimezone` as ONE variable name
  # (`?` is legal in variable names), which silently eats the database from the URL and makes
  # the driver report `Unknown database '=asia/shanghai'`.
  $env:XINYU_DB_URL = "jdbc:mysql://127.0.0.1:$DbPort/${DbName}?serverTimezone=Asia/Shanghai"
  $env:XINYU_DB_DRIVER = "com.mysql.cj.jdbc.Driver"
  $env:XINYU_DB_USER = "root"
  $env:XINYU_DB_PASSWORD = ""
  # Spring writes its own log file (console output would land in a hidden console and be lost):
  # this is also what makes the caller free to pipe our output without the app holding the pipe.
  $appLog = Join-Path $LogDir "app-$Port.log"
  if (Test-Path $appLog) { Remove-Item $appLog -ErrorAction SilentlyContinue }
  # Working directory must be the repo root: ./src/, ./_test/ and src/data/emotion-lexicon.js
  # are all resolved relative to it (project decision #2 -- serve the authoritative source).
  $p = Start-Background -Exe (Join-Path $JdkHome "bin\java.exe") `
    -ArgList @("-jar", "$Jar", "--logging.file.name=$appLog") -WorkDir $Repo
  $url = "http://127.0.0.1:$Port/api/health"
  $deadline = (Get-Date).AddSeconds(90)
  $health = $null
  while ($true) {
    if (-not (Get-Process -Id $p.Id -ErrorAction SilentlyContinue)) {
      Write-Output "[serve] FAILED: java pid=$($p.Id) exited. Tail of $appLog :"
      Show-LogTail $appLog 20
      throw "app process died during startup"
    }
    try {
      $health = (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 3).Content
      break
    } catch { }
    if ((Get-Date) -gt $deadline) {
      Write-Output "[serve] FAILED: no health answer in 90s. Tail of $appLog :"
      Show-LogTail $appLog 20
      throw "app did not answer $url"
    }
    Start-Sleep -Milliseconds 500
  }
  Write-Output "[serve] pid=$($p.Id) port=$Port log=$appLog"
  Write-Output "[serve] health: $health"
  Write-Output "[serve] prove the store is really MySQL (not the H2 default):"
  Write-Output "          Select-String -Path `"$appLog`" -Pattern 'mysql.cj.jdbc.ConnectionImpl'"
}

function Action-Status {
  $mp = @(Get-MysqldProc)
  Write-Output ("[status] mysqld owning {0}: {1}" -f $DataDir, (($mp | ForEach-Object { $_.ProcessId }) -join ","))
  # Report 'answers' (a query that works), not 'port looks open' -- the two diverge while a
  # server is starting or aborting, which is exactly when a wrong reading costs the most.
  $answers = $false
  if (Test-Path $Mysql) { $answers = Test-SqlAlive }
  Write-Output ("[status] MySQL answers on 127.0.0.1:{0} : {1}" -f $DbPort, $answers)
  if ($answers) {
    Write-Output ("[status] version : " + ((Invoke-Sql "SELECT VERSION()").out | Select-Object -Last 1))
    $t = (Invoke-Sql "SELECT table_name FROM information_schema.tables WHERE table_schema='$DbName'").out
    Write-Output ("[status] tables in $DbName : " + (($t | Where-Object { $_ }) -join ","))
    $i = (Invoke-Sql "SELECT CONCAT(table_name,'.',index_name) FROM information_schema.statistics WHERE table_schema='$DbName' GROUP BY table_name,index_name").out
    Write-Output ("[status] indexes          : " + (($i | Where-Object { $_ }) -join ","))
  }
  if (Test-Path $Jar) {
    Write-Output ("[status] jar : {0} ({1} B)" -f $Jar, (Get-Item $Jar).Length)
  } else {
    Write-Output ("[status] jar : MISSING at $Jar")
  }
  $svc = @(Get-CimInstance Win32_Process -Filter "Name='java.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*soulisle-server.jar*" })
  foreach ($s in $svc) { Write-Output ("[status] soulisle pid={0} cmdline={1}" -f $s.ProcessId, $s.CommandLine) }
}

switch ($Action) {
  "Start"  { Action-Start }
  "Stop"   { Action-Stop }
  "Serve"  { Action-Serve }
  "Status" { Action-Status }
}
