<#
  ChangeX Windows preview handler — installer.

  Registers the COM preview handler (ChangeXPreview.dll) and associates it with the
  Explorer preview pane for ChangeX's own .changex journals ONLY — your code/Markdown/etc.
  stay with their own preview handlers, so there are no conflicts. (Upgrading from an older
  build also unregisters the code/text extensions previous versions used to claim.) Run from
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

# ChangeX previews ONLY its own .changex journals. Code/Markdown/JSON/etc. are deliberately
# left to your dedicated preview handlers, so ChangeX never fights them for a file type.
$exts = @('.changex')

# Code/text extensions earlier builds used to claim. We UNREGISTER these on (re)install so an
# upgrade cleanly hands them back to whatever previewer the user actually wants for them.
$legacyExts = @(
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
    # (1) Explorer preview pane (Alt+P) via the COM handler.
    $key = "Registry::HKEY_CLASSES_ROOT\$ext\shellex\$previewIid"
    New-Item -Path $key -Force | Out-Null
    Set-ItemProperty -Path $key -Name '(default)' -Value $clsid

    # (2) Reliable right-click "Preview with ChangeX" → opens the HTML in the default browser
    #     (the cross-platform engine; works even without the preview pane).
    $verb = "Registry::HKEY_CLASSES_ROOT\SystemFileAssociations\$ext\shell\ChangeXPreview"
    New-Item -Path $verb -Force | Out-Null
    Set-ItemProperty -Path $verb -Name 'MUIVerb' -Value 'Preview with ChangeX'
    New-Item -Path "$verb\command" -Force | Out-Null
    Set-ItemProperty -Path "$verb\command" -Name '(default)' -Value 'cmd /c changex preview "%1" --open'
}

Write-Host "Releasing legacy code/text associations (handing them back to your own previewers)..." -ForegroundColor Cyan
foreach ($ext in $legacyExts) {
    $key = "Registry::HKEY_CLASSES_ROOT\$ext\shellex\$previewIid"
    if (Test-Path $key) { Remove-Item -Path $key -Recurse -Force -ErrorAction SilentlyContinue }
    $verb = "Registry::HKEY_CLASSES_ROOT\SystemFileAssociations\$ext\shell\ChangeXPreview"
    if (Test-Path $verb) { Remove-Item -Path $verb -Recurse -Force -ErrorAction SilentlyContinue }
}

Write-Host "`nDone." -ForegroundColor Green
Write-Host "  • Preview pane: open Explorer, press Alt+P, select a .changex journal."
Write-Host "  • Or right-click a .changex file → 'Preview with ChangeX' (opens in your browser)."
Write-Host "If the preview pane stays blank, use the right-click option (or sign out/in — Explorer caches handlers)."
