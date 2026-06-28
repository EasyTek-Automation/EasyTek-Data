# verificar_pos_reboot.ps1 - rodar APOS o reboot + auto-login (TAREFA 9).
# Confirma: (1) daemon subiu sozinho apos o logon automatico; (2) self-heal armado.
# Uso:  .\verificar_pos_reboot.ps1
$root = "$env:USERPROFILE\sap-scheduler"
$log  = "$root\logs\daemon.log"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Verificacao pos-reboot (TAREFA 9)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# uptime do Windows (confirma que houve reboot recente)
$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
Write-Host "Windows ligou em: $boot  (ha $([int]((Get-Date)-$boot).TotalMinutes) min)"

# (1) daemon vivo + ultimo boot do daemon
$d = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*daemon.py*' }
if ($d) { Write-Host "[OK] daemon VIVO (PID $($d.ProcessId -join ','))" -ForegroundColor Green }
else    { Write-Host "[FALHA] daemon NAO esta rodando" -ForegroundColor Red }

$ultimoBoot = (Select-String -Path $log -Pattern 'boot iniciado' | Select-Object -Last 1).Line
Write-Host "ultimo boot do daemon no log:"
Write-Host "   $ultimoBoot"
if ($d -and $ultimoBoot -match '(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})') {
    $tboot = [datetime]::ParseExact($Matches[1], 'yyyy-MM-dd HH:mm:ss', $null)
    if ($tboot -gt $boot) { Write-Host "[OK] daemon bootou DEPOIS do Windows = subiu sozinho no logon automatico" -ForegroundColor Green }
    else { Write-Host "[ATENCAO] boot do daemon e ANTERIOR ao boot do Windows (talvez ainda nao subiu)" -ForegroundColor Yellow }
}

# SAP logado? (lembrete - precisa de humano)
$sap = Get-Process saplogon -ErrorAction SilentlyContinue
if ($sap) { Write-Host "[OK] SAP GUI aberto: $($sap.MainWindowTitle)" -ForegroundColor Green }
else { Write-Host "[LEMBRETE] SAP GUI NAO esta aberto - alguem precisa abrir e logar no mandante 040 pro job rodar" -ForegroundColor Yellow }

# (2) teste de self-heal: matar o daemon e ver se o Task Scheduler relanca em <=60s
Write-Host ""
Write-Host "--- Teste de self-heal (mata o daemon e espera relaunch automatico) ---" -ForegroundColor Cyan
$resp = Read-Host "Rodar o teste de self-heal agora? (s/N)"
if ($resp -eq 's' -or $resp -eq 'S') {
    $ws = Get-CimInstance Win32_Process -Filter "Name='wscript.exe'" | Where-Object { $_.CommandLine -like '*launcher.vbs*' }
    $baseBoots = (Select-String -Path $log -Pattern 'boot iniciado').Count
    if ($ws) { taskkill /F /T /PID $ws.ProcessId | Out-Null; Write-Host "daemon morto (wscript PID $($ws.ProcessId)); aguardando relaunch (ate 75s)..." }
    else {
        $dd = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*daemon.py*' }
        $stub = ($dd | Where-Object { $_.ParentProcessId -notin $dd.ProcessId }).ProcessId
        if ($stub) { taskkill /F /T /PID $stub | Out-Null; Write-Host "daemon morto (PID $stub); aguardando relaunch (ate 75s)..." }
    }
    $ok = $false
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Seconds 3
        if ((Select-String -Path $log -Pattern 'boot iniciado').Count -gt $baseBoots) { $ok = $true; break }
    }
    if ($ok) { Write-Host "[OK] SELF-HEAL FUNCIONA - Task Scheduler relancou o daemon sozinho!" -ForegroundColor Green }
    else { Write-Host "[FALHA] daemon NAO relancou em 75s - self-heal nao armou (LogonTrigger pode nao ter disparado)" -ForegroundColor Red }
} else {
    Write-Host "(teste de self-heal pulado)"
}

Write-Host ""
Write-Host "Fim da verificacao. Cole a saida aqui na proxima sessao do Claude se quiser que eu analise." -ForegroundColor DarkGray
