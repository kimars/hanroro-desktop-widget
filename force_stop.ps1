$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
$processes = Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -match '^(pythonw?|HanroroDesktop)\.exe$') -and (
        ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) -or
        ($_.CommandLine -and $_.CommandLine.IndexOf($root, [StringComparison]::OrdinalIgnoreCase) -ge 0)
    )
}
foreach ($process in $processes) {
    & taskkill.exe /PID $process.ProcessId /T /F 2>$null
    Write-Host ('Stopped PID ' + $process.ProcessId)
}
Start-Sleep -Milliseconds 350
Write-Host 'Hanroro Desktop stopped. You can now replace or delete its folder.'
