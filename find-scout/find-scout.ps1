# find-scout.ps1 - locate a Dronetag Scout admin page on the wired network.
# ASCII only on purpose: non-ASCII literals get mangled on some Windows shells.
# Read-only: never changes IP settings, adapters or the device.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File find-scout.ps1 [-NoSweep]

param([switch]$NoSweep)

$OUI      = '2C-CF-67'          # Dronetag
$FALLBACK = '192.168.100.100'   # Scout falls back here ~60 s after DHCP fails

function Test-ScoutHttps([string]$ip) {
    # Scout answers 401 (nginx Basic Auth) with X-DRONETAG-PRODUCT: Scout.
    $h = & curl.exe -k -s -I --connect-timeout 3 --max-time 5 "https://$ip/" 2>$null
    if (-not $h) { return $null }
    if (-not ($h -match '(?i)^X-DRONETAG-PRODUCT:\s*Scout')) { return $null }
    $realm = ($h | Select-String '(?i)realm="([^"]*)"').Matches | Select-Object -First 1
    $serial = if ($realm) { ($realm.Groups[1].Value -split '\s+')[-1] } else { '' }
    $masked = if ($serial.Length -ge 4) { ('*' * ($serial.Length - 4)) + $serial.Substring($serial.Length - 4) } else { '?' }
    [pscustomobject]@{ IP = $ip; SerialMasked = $masked.ToUpper() }
}

function Get-OuiNeighbors {
    Get-NetNeighbor -AddressFamily IPv4 -EA SilentlyContinue |
        Where-Object { $_.LinkLayerAddress -like "$OUI*" } |
        Select-Object IPAddress, LinkLayerAddress, State, ifIndex
}

# --- 1. wired adapters -------------------------------------------------------
$wired = Get-NetAdapter -Physical -EA SilentlyContinue |
    Where-Object { $_.PhysicalMediaType -eq '802.3' }
"== Wired adapters"
if (-not $wired) { "  (none found)" }
foreach ($a in $wired) {
    $ips = (Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -EA SilentlyContinue |
        ForEach-Object { "$($_.IPAddress)/$($_.PrefixLength)" }) -join ', '
    "  [{0}] {1}  status={2}  ip={3}" -f $a.ifIndex, $a.InterfaceDescription, $a.Status, $ips
}
$up = @($wired | Where-Object Status -eq 'Up')
if (-not $up) {
    "RESULT: NO_LINK"
    "  No wired adapter is Up. Check the cable, the PoE injector power, and that the laptop is on the injector's LAN/DATA port (not PoE/OUT)."
    exit 2
}

# --- 2. candidates from the neighbor table -----------------------------------
$cands = [System.Collections.Generic.List[string]]::new()
foreach ($n in Get-OuiNeighbors) { if (-not $cands.Contains($n.IPAddress)) { $cands.Add($n.IPAddress) } }
"== Neighbors with Dronetag MAC: " + ($(if ($cands.Count) { $cands -join ', ' } else { '(none)' }))

# --- 3. verify ---------------------------------------------------------------
function Resolve-Found($list) {
    $hits = @()
    foreach ($ip in $list) { $r = Test-ScoutHttps $ip; if ($r) { $hits += $r } }
    $hits
}
$found = @(Resolve-Found $cands)

# --- 4. sweep the wired /24s to warm ARP, then retry -------------------------
if (-not $found -and -not $NoSweep) {
    $nets = foreach ($a in $up) {
        Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -EA SilentlyContinue |
            Where-Object { $_.IPAddress -notlike '169.254.*' } |
            ForEach-Object { ($_.IPAddress -split '\.')[0..2] -join '.' }
    }
    $nets = @($nets | Select-Object -Unique)
    if ($nets) {
        "== Sweeping " + (($nets | ForEach-Object { "$_.0/24" }) -join ', ') + " ..."
        $tasks = foreach ($net in $nets) { foreach ($i in 1..254) {
            (New-Object System.Net.NetworkInformation.Ping).SendPingAsync("$net.$i", 400)
        } }
        try { [System.Threading.Tasks.Task]::WaitAll([System.Threading.Tasks.Task[]]@($tasks)) } catch {}
        # ARP resolves even when Scout ignores ICMP, so re-read the table.
        $more = @(Get-OuiNeighbors | Where-Object { $_.State -ne 'Unreachable' } |
            ForEach-Object IPAddress | Where-Object { -not $cands.Contains($_) })
        "== New Dronetag neighbors after sweep: " + ($(if ($more) { $more -join ', ' } else { '(none)' }))
        $found = @(Resolve-Found $more)
    }
}

# --- 5. factory fallback -----------------------------------------------------
if (-not $found) {
    "== Trying factory fallback $FALLBACK"
    $found = @(Resolve-Found @($FALLBACK))
    if (-not $found) {
        $on100 = Get-NetIPAddress -AddressFamily IPv4 -EA SilentlyContinue | Where-Object { $_.IPAddress -like '192.168.100.*' }
        if (-not $on100) { "  Laptop has no 192.168.100.x address, so the fallback is unreachable from here." }
    }
}

# --- result ------------------------------------------------------------------
if ($found) {
    foreach ($f in $found) {
        "RESULT: FOUND https://$($f.IP)/   serial=$($f.SerialMasked)"
    }
    exit 0
}
"RESULT: NOT_FOUND"
exit 1
