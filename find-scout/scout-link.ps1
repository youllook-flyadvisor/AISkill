# scout-link.ps1 - temporarily give the wired adapter a 192.168.100.x address
# so a Scout sitting on its fallback 192.168.100.100 becomes reachable.
# ASCII only on purpose: non-ASCII literals get mangled on some Windows shells.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scout-link.ps1 -Action status|add|remove
#
# add/remove need admin rights. When not elevated, the script relaunches itself
# through the normal Windows UAC prompt, so the user only has to click "Yes".
# The address is put in ActiveStore only, so it disappears on reboot anyway.
# Never touches the execution policy, DHCP, gateway, DNS or Wi-Fi.

param(
    [ValidateSet('status', 'add', 'remove')][string]$Action = 'status',
    [switch]$Elevated,
    [string]$OutFile,
    [string]$StateFile
)

$NET   = '192.168.100'
$SCOUT = "$NET.100"
if (-not $StateFile) { $StateFile = Join-Path $env:LOCALAPPDATA 'find-scout\scout-link.state' }

function Get-WiredUp {
    @(Get-NetAdapter -Physical -EA SilentlyContinue |
        Where-Object { $_.PhysicalMediaType -eq '802.3' -and $_.Status -eq 'Up' })
}

function Get-LinkIPs($adapters) {
    foreach ($a in $adapters) {
        Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -EA SilentlyContinue |
            Where-Object { $_.IPAddress -like "$NET.*" }
    }
}

function Test-Admin {
    $p = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# --- status: read-only ---------------------------------------------------------
if ($Action -eq 'status') {
    $up = Get-WiredUp
    if (-not $up) { "RESULT: NO_LINK"; exit 2 }
    foreach ($a in $up) { "  [{0}] {1}" -f $a.ifIndex, $a.InterfaceDescription }
    $ips = @(Get-LinkIPs $up)
    if ($ips) { "RESULT: HAS_IP " + (($ips | ForEach-Object IPAddress) -join ', '); exit 0 }
    "RESULT: NO_IP"
    exit 1
}

# --- not elevated: relaunch through UAC and relay the output --------------------
if (-not (Test-Admin)) {
    if ($Elevated) { "RESULT: FAILED not elevated"; exit 1 }
    $out = Join-Path $env:TEMP ("scout-link-{0}.txt" -f [guid]::NewGuid())
    $argv = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
        '-File', "`"$PSCommandPath`"", '-Action', $Action, '-Elevated',
        '-OutFile', "`"$out`"", '-StateFile', "`"$StateFile`"")
    try {
        Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList $argv -EA Stop
    } catch {
        "RESULT: CANCELLED (the Windows permission prompt was declined)"
        exit 3
    }
    if (Test-Path $out) { Get-Content $out; Remove-Item $out -Force -EA SilentlyContinue }
    else { "RESULT: FAILED no output from elevated process" }
    exit 0
}

# --- elevated work ---------------------------------------------------------------
function Write-Out([string]$line) {
    if ($OutFile) { Add-Content -Path $OutFile -Value $line } else { $line }
}

if ($Action -eq 'add') {
    $up = Get-WiredUp
    if (-not $up) { Write-Out "RESULT: NO_LINK"; exit 2 }
    $have = @(Get-LinkIPs $up)
    if ($have) { Write-Out ("RESULT: ALREADY " + (($have | ForEach-Object IPAddress) -join ', ')); exit 0 }

    $a = $up[0]
    $ip = $null
    foreach ($i in 10..30) {
        $cand = "$NET.$i"
        if ($cand -eq $SCOUT) { continue }
        if (-not (Test-Connection -ComputerName $cand -Count 1 -Quiet -EA SilentlyContinue)) { $ip = $cand; break }
    }
    if (-not $ip) { Write-Out "RESULT: FAILED no free address in $NET.10-30"; exit 1 }

    try {
        New-NetIPAddress -InterfaceIndex $a.ifIndex -IPAddress $ip -PrefixLength 24 -PolicyStore ActiveStore -EA Stop | Out-Null
    } catch {
        Write-Out "RESULT: FAILED $($_.Exception.Message)"; exit 1
    }
    New-Item -ItemType Directory -Force (Split-Path $StateFile) | Out-Null
    Set-Content -Path $StateFile -Value "$($a.ifIndex) $ip" -Encoding ascii
    Write-Out ("RESULT: ADDED {0} on [{1}] {2}" -f $ip, $a.ifIndex, $a.InterfaceDescription)
    exit 0
}

if ($Action -eq 'remove') {
    # Prefer what this script added; otherwise any 192.168.100.x on a wired adapter
    # (e.g. one the user added by hand earlier). The SKILL asks the user before this.
    $targets = @()
    if (Test-Path $StateFile) {
        $idx, $ip = (Get-Content $StateFile -TotalCount 1) -split ' '
        $targets = @(Get-NetIPAddress -InterfaceIndex $idx -IPAddress $ip -EA SilentlyContinue)
    }
    if (-not $targets) {
        $wired = @(Get-NetAdapter -Physical -EA SilentlyContinue | Where-Object PhysicalMediaType -eq '802.3')
        $targets = @(Get-LinkIPs $wired | Where-Object { $_.PrefixOrigin -eq 'Manual' })
    }
    if (-not $targets) { Write-Out "RESULT: NOTHING_TO_REMOVE"; Remove-Item $StateFile -EA SilentlyContinue; exit 0 }

    $done = @()
    foreach ($t in $targets) {
        try {
            Remove-NetIPAddress -InterfaceIndex $t.InterfaceIndex -IPAddress $t.IPAddress -Confirm:$false -EA Stop
            $done += $t.IPAddress
        } catch {
            Write-Out "  could not remove $($t.IPAddress): $($_.Exception.Message)"
        }
    }
    Remove-Item $StateFile -EA SilentlyContinue
    if ($done) { Write-Out ("RESULT: REMOVED " + (($done | Select-Object -Unique) -join ', ')) }
    else { Write-Out "RESULT: FAILED" }
    exit 0
}
