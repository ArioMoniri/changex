<#
  ChangeX Windows preview handler — uninstaller. Run from an ELEVATED PowerShell:
    powershell -ExecutionPolicy Bypass -File uninstall.ps1
#>
[CmdletBinding()]
param(
    [string]$Dll = (Join-Path $PSScriptRoot 'ChangeXPreview.dll')
)

$ErrorActionPreference = 'Continue'
$previewIid = '{8895b1c6-b41f-4c1c-a562-0d564250836f}'

$exts = @(
    '.changex','.py','.js','.mjs','.cjs','.ts','.tsx','.jsx','.rb','.go','.rs','.php','.pl','.lua',
    '.swift','.kt','.java','.scala','.cs','.fs','.c','.h','.cc','.cpp','.cxx','.hpp','.m','.mm',
    '.sh','.bash','.zsh','.ps1','.sql','.r','.dart','.ex','.exs','.hs','.clj',
    '.json','.jsonl','.yaml','.yml','.toml','.ini','.cfg','.conf','.xml','.plist',
    '.css','.scss','.less','.md','.markdown','.diff','.patch','.gradle','.proto','.graphql'
)

foreach ($ext in $exts) {
    $key = "Registry::HKEY_CLASSES_ROOT\$ext\shellex\$previewIid"
    if (Test-Path $key) { Remove-Item -Path $key -Recurse -Force -ErrorAction SilentlyContinue }
}

$regasm = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\regasm.exe'
if ((Test-Path $regasm) -and (Test-Path $Dll)) { & $regasm /unregister "$Dll" | Write-Host }

Write-Host "ChangeX preview handler removed. Sign out/in to clear Explorer's cache." -ForegroundColor Green
