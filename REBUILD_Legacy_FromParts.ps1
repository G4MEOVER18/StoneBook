param(
  [string]$PartsPattern = "StoneBoock_legacy_originals.part*",
  [string]$OutFile = "StoneBoock_legacy_originals.zip"
)

$parts = Get-ChildItem -File -Filter $PartsPattern | Sort-Object Name
if (-not $parts -or $parts.Count -eq 0) {
  Write-Error "Keine Parts gefunden. Erwartet: $PartsPattern im aktuellen Ordner."
  exit 1
}

Write-Host "Baue zusammen: $OutFile"
Write-Host "Parts: " $parts.Count

$dest = [System.IO.File]::Open($OutFile, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try {
  foreach ($p in $parts) {
    Write-Host ("  + {0} ({1} bytes)" -f $p.Name, $p.Length)
    $src = [System.IO.File]::OpenRead($p.FullName)
    try {
      $src.CopyTo($dest)
    } finally {
      $src.Close()
    }
  }
} finally {
  $dest.Close()
}

Write-Host "Fertig: $OutFile"
