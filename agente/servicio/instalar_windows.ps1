# Windows: registra el agente como tarea programada que arranca al iniciar sesión y se reinicia si falla.
# Ejecutar en PowerShell como el usuario que usa Ollama:  powershell -ExecutionPolicy Bypass -File instalar_windows.ps1
$dir = Split-Path -Parent $PSScriptRoot
$py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command python.exe).Source }
$accion = New-ScheduledTaskAction -Execute $py -Argument "`"$dir\agente_stq.py`"" -WorkingDirectory $dir
$disparador = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$ajustes = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "Agente STQ" -Action $accion -Trigger $disparador -Settings $ajustes -Force
Start-ScheduledTask -TaskName "Agente STQ"
Write-Host "Listo. Para verlo: Programador de tareas > 'Agente STQ'. Para quitarlo: Unregister-ScheduledTask 'Agente STQ'"
