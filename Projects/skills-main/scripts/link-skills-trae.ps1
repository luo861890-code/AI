# link-skills-trae.ps1
#
# Link this repo's promoted skills (engineering + productivity buckets) into
# Trae's global skills directory using directory junctions, so Trae auto-
# discovers and loads them.
#
# This is the Windows/Trae counterpart of scripts/link-skills.sh:
#   - Junctions (not symlinks) => no admin rights needed.
#   - Each skill is a junction into this repo, so `git pull` updates them live.
#   - Re-run only after adding/renaming/removing a skill.
#
# Usage (Windows PowerShell 5.1 or PowerShell 7):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\link-skills-trae.ps1
#
# Optional env var:
#   $env:TRAE_SKILLS_DIR  override the default Trae global skills directory
#
# Note: this script only creates/refreshes junctions. If a skill is removed
# from the repo, remove its leftover junction under the skills dir by hand.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$Repo   = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Skills = Join-Path $Repo 'skills'
$Dest   = if ($env:TRAE_SKILLS_DIR) { $env:TRAE_SKILLS_DIR } else { Join-Path $env:USERPROFILE '.trae-cn\skills' }

if (-not (Test-Path $Dest)) { New-Item -ItemType Directory -Path $Dest | Out-Null }

# Promoted skills (kept in sync with .claude-plugin/plugin.json's skills array)
$SkillList = @(
  'engineering\ask-matt',
  'engineering\diagnosing-bugs',
  'engineering\grill-with-docs',
  'engineering\triage',
  'engineering\improve-codebase-architecture',
  'engineering\setup-matt-pocock-skills',
  'engineering\tdd',
  'engineering\to-spec',
  'engineering\to-tickets',
  'engineering\wayfinder',
  'engineering\implement',
  'engineering\prototype',
  'engineering\research',
  'engineering\domain-modeling',
  'engineering\codebase-design',
  'engineering\code-review',
  'engineering\resolving-merge-conflicts',
  'productivity\grill-me',
  'productivity\grilling',
  'productivity\handoff',
  'productivity\teach',
  'productivity\writing-great-skills'
)

function Get-JunctionTarget([string]$path) {
  # Returns the target path of a junction, or $null if not a junction.
  try {
    $item = Get-Item -LiteralPath $path -Force
    if ($item.LinkType -eq 'Junction') {
      if ($item.Target) { return ($item.Target | Select-Object -First 1) }
      # PS 5.1 fallback: resolve the reparse point via .NET
      return [System.IO.Path]::GetFullPath((cmd /c dir /al `"$path`" | Select-String '\[.*\]').Matches.Value.Trim('[]'))
    }
  } catch { }
  return $null
}

$ok = 0; $fail = 0; $skipped = 0
foreach ($rel in $SkillList) {
  $name = Split-Path $rel -Leaf
  $src  = Join-Path $Skills $rel
  $tgt  = Join-Path $Dest $name

  if (-not (Test-Path (Join-Path $src 'SKILL.md'))) {
    Write-Warning "missing SKILL.md, skipping: $src"; $skipped++; continue
  }

  $srcResolved = (Resolve-Path $src).Path
  $existingTarget = Get-JunctionTarget $tgt

  if ($existingTarget) {
    if ((Resolve-Path $existingTarget).Path -eq $srcResolved) {
      Write-Output "skip $name (already linked)"; $skipped++; continue
    }
    [System.IO.Directory]::Delete($tgt, $false)
  } elseif (Test-Path -LiteralPath $tgt) {
    $item = Get-Item -LiteralPath $tgt -Force
    if ($item.PSIsContainer) {
      Write-Warning "target is a real directory (not a junction), skipping to avoid overwrite: $tgt"; $fail++; continue
    } else {
      Remove-Item -LiteralPath $tgt -Force
    }
  }

  try {
    New-Item -ItemType Junction -Path $tgt -Target $src -ErrorAction Stop | Out-Null
    Write-Output "OK   $name -> $src"; $ok++
  } catch {
    Write-Warning "failed $name : $_"; $fail++
  }
}

Write-Output ""
Write-Output ("done: ok {0}, skipped {1}, failed {2}  (dest: {3})" -f $ok, $skipped, $fail, $Dest)
