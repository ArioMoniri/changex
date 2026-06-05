<#
  ChangeX Windows preview handler — installer.

  Registers the COM preview handler (ChangeXPreview.dll) and associates it with the
  Explorer preview pane for .changex journals and common source-code extensions. Run from
  an ELEVATED PowerShell:  powershell -ExecutionPolicy Bypass -File install.ps1

  Requires the ChangeX engine on PATH:  pip install -U "changex[preview]"
#>
[CmdletBinding()]
param(
    [string]$Dll = (Join-Path $PSScriptRoot 'ChangeXPreview.dll')
)

$ErrorActionPreference = 'Stop'
$clsid = '{D3A1B2C4-5E6F-47A8-9B0C-1D2E3F4A5B6C}'
$previewIid = '{8895b1c6-b41f-4c1c-a562-0d564250836f}'   # IID_IPreviewHandler

# File extensions to preview with ChangeX (the redline for .changex, syntax-highlighted code
# for the rest). Adjust to taste — these are the "full set".
$exts = @(
    '.changex',
    '.py','.js','.mjs','.cjs','.ts','.tsx','.jsx','.rb','.go','.rs','.php','.pl','.lua',
    '.swift','.kt','.java','.scala','.cs','.fs','.c','.h','.cc','.cpp','.cxx','.hpp','.m','.mm',
    '.sh','.bash','.zsh','.ps1','.sql','.r','.dart','.ex','.exs','.hs','.clj',
    '.json','.jsonl','.yaml','.yml','.toml','.ini','.cfg','.conf','.xml','.plist',
    '.css','.scss','.less','.md','.markdown','.diff','.patch','.gradle','.proto','.graphql'
)

if (-not (Test-Path $Dll)) { throw "ChangeXPreview.dll not found at $Dll" }

# Locate regasm (64-bit .NET Framework).
$regasm = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\regasm.exe'
if (-not (Test-Path $regasm)) { throw "regasm.exe not found ($regasm)" }

Write-Host "Registering COM server..." -ForegroundColor Cyan
& $regasm /codebase "$Dll" | Write-Host

Write-Host "Associating extensions with the ChangeX preview handler..." -ForegroundColor Cyan
foreach ($ext in $exts) {
    $key = "Registry::HKEY_CLASSES_ROOT\$ext\shellex\$previewIid"
    New-Item -Path $key -Force | Out-Null
    Set-ItemProperty -Path $key -Name '(default)' -Value $clsid
}

Write-Host "`nDone. Open Explorer, enable the Preview pane (Alt+P), and select a .changex or code file." -ForegroundColor Green
Write-Host "If a preview doesn't appear, sign out/in (Explorer caches preview handlers)."
