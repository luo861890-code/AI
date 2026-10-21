# Download SRTM 90m elevation tiles around Wuhan (AWS Open Data, parallel range fetch).
# Usage: powershell -ExecutionPolicy Bypass -File tools/download_srtm_wuhan.ps1
$ErrorActionPreference = 'Stop'

$BaseUrl = 'https://elevation-tiles-prod.s3.amazonaws.com/skadi'
$DestDir = Join-Path $PSScriptRoot '..\backend\data\dem'
$DestDir = [System.IO.Path]::GetFullPath($DestDir)
New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

# 1x1 degree tiles covering Wuhan admin bbox (lat N29-N31, lon E113-E115)
$Tiles = @(
    @{ Lat = 'N29'; Lon = 'E113' },
    @{ Lat = 'N29'; Lon = 'E114' },
    @{ Lat = 'N29'; Lon = 'E115' },
    @{ Lat = 'N30'; Lon = 'E113' },
    @{ Lat = 'N30'; Lon = 'E114' },
    @{ Lat = 'N30'; Lon = 'E115' },
    @{ Lat = 'N31'; Lon = 'E113' },
    @{ Lat = 'N31'; Lon = 'E114' },
    @{ Lat = 'N31'; Lon = 'E115' }
)

$Chunks = 6

function Get-Tile {
    param($Lat, $Lon)
    $name = "$Lat$Lon"
    $url = "$BaseUrl/$Lat/$name.hgt.gz"
    $final = Join-Path $DestDir "$name.hgt.gz"
    $work = "$final.parts"
    $hgt = $final -replace '\.gz$', ''
    if ((Test-Path $hgt) -and (Test-Path $final)) {
        Write-Host "[$name] already present, skip."
        return
    }

    # get remote file size
    $len = [int64]0
    for ($i = 0; $i -lt 5; $i++) {
        $h = curl.exe -sI $url
        $m = $h | Select-String -Pattern 'Content-Length:\s*(\d+)'
        if ($m) { $len = [int64]$m.Matches[0].Groups[1].Value; break }
        Start-Sleep -Seconds 3
    }
    if ($len -le 0) { throw "cannot get size for $name" }

    Write-Host "[$name] total $len bytes, $Chunks parallel chunks ..."
    New-Item -ItemType Directory -Force -Path $work | Out-Null

    $chunkSize = [math]::Ceiling($len / $Chunks)
    $jobs = @()
    for ($c = 0; $c -lt $Chunks; $c++) {
        $start = $c * $chunkSize
        $end = [math]::Min($len - 1, $start + $chunkSize - 1)
        if ($start -gt $len - 1) { break }
        $part = Join-Path $work ("part_{0:D2}.bin" -f $c)
        $jobs += Start-Job -ScriptBlock {
            param($u, $p, $s, $e)
            curl.exe -s -L --retry 4 --connect-timeout 15 --max-time 900 -r "$s-$e" -o $p $u
        } -ArgumentList $url, $part, $start, $end
    }

    $deadline = (Get-Date).AddMinutes(15)
    while ($jobs | Where-Object { $_.State -eq 'Running' }) {
        if ((Get-Date) -gt $deadline) {
            $jobs | Stop-Job -ErrorAction SilentlyContinue
            throw "[$name] download timeout"
        }
        Start-Sleep -Seconds 5
    }
    $fail = $jobs | Where-Object { $_.State -ne 'Completed' }
    if ($fail) { $jobs | Remove-Job -Force -ErrorAction SilentlyContinue; throw "[$name] chunk job failed" }

    # merge chunks
    $out = [System.IO.File]::Open($final, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    try {
        for ($c = 0; $c -lt $Chunks; $c++) {
            $part = Join-Path $work ("part_{0:D2}.bin" -f $c)
            if (Test-Path $part) {
                $bytes = [System.IO.File]::ReadAllBytes($part)
                $out.Write($bytes, 0, $bytes.Length)
            }
        }
    } finally {
        $out.Close()
    }
    $jobs | Remove-Job -Force -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue

    $got = (Get-Item $final).Length
    if ($got -ne $len) {
        Remove-Item -Force $final -ErrorAction SilentlyContinue
        throw "[$name] size mismatch: $got/$len"
    }
    Write-Host "[$name] done ($got bytes)"

    # extract .hgt.gz -> .hgt (python gzip, reliable on Windows)
    if (-not (Test-Path $hgt)) {
        $py = @"
import gzip, sys
src = sys.argv[1]; dst = src[:-3]
with gzip.open(src, 'rb') as fi, open(dst, 'wb') as fo:
    fo.write(fi.read())
"@
        $tmpPy = Join-Path $env:TEMP 'extract_hgt.py'
        Set-Content -Path $tmpPy -Value $py -Encoding UTF8
        & 'D:\python\py3.12.8\python.exe' $tmpPy $final
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $hgt)) { throw "[$name] extract failed" }
    }
    Write-Host "[$name] extracted -> $hgt"
}

foreach ($t in $Tiles) {
    Get-Tile -Lat $t.Lat -Lon $t.Lon
}

Write-Host 'All SRTM tiles ready:'
Get-ChildItem $DestDir -Filter '*.hgt' | Select-Object Name, Length
