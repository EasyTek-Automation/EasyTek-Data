# SAP Job Scheduler - dispara job manualmente (Bloco I A-04 fallback).
#
# Util enquanto o endpoint REST /api/v1/sap-scheduler/trigger nao esta
# operacional em todos os clientes. Insere doc 'pendente' em sap_jobs
# com agendado_para = now - 60s (daemon claim no proximo polling 30s).
#
# Uso:
#   .\disparar_job.ps1 zppprd
#   .\disparar_job.ps1 zpp_nt0001
#
# Pre-requisitos:
#   - venv do daemon ativo em %USERPROFILE%\sap-scheduler\.venv
#   - .env do daemon configurado (MONGO_URI, DB_NAME)
#   - SAP GUI aberto e logado

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("zppprd", "zpp_nt0001")]
    [string]$tipo
)

$ErrorActionPreference = "Stop"

$root = "$env:USERPROFILE\sap-scheduler"
$venvPython = "$root\.venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "ERRO: venv nao encontrada em $venvPython" -ForegroundColor Red
    Write-Host "Rode a instalacao primeiro (RUNBOOK-instalacao.md)." -ForegroundColor Yellow
    exit 1
}

Write-Host "Disparando job '$tipo' em sap_jobs..." -ForegroundColor Cyan

# Insert direto na fila via pymongo
# `agendado_para = now - 60s` (truncado pro minuto) garante claim imediato
$pyScript = @"
import sys
sys.path.insert(0, r'$root')
from datetime import datetime, timedelta
import config as cfg_mod
import pymongo

cfg = cfg_mod.load()
client = pymongo.MongoClient(cfg.mongo_uri, serverSelectionTimeoutMS=5000)
db = client[cfg.db_name]
agendado = (datetime.utcnow() - timedelta(seconds=60)).replace(second=0, microsecond=0)
doc = {
    'tipo': '$tipo',
    'parametros': {'disparo_manual': True},
    'status': 'pendente',
    'agendado_para': agendado,
    'criado_em': datetime.utcnow(),
    'iniciado_em': None,
    'concluido_em': None,
    'resultado': None,
    'erro': None,
}
try:
    result = db.sap_jobs.insert_one(doc)
    print(f'OK | _id={result.inserted_id} agendado_para={agendado.isoformat()}')
except pymongo.errors.DuplicateKeyError:
    print('DEDUP | ja existe job com mesma chave (tipo, agendado_para). Tente em 1 min.')
except Exception as e:
    print(f'ERRO | {type(e).__name__}: {e}')
    sys.exit(1)
"@

$tmpFile = "$env:TEMP\disparar_job_$($tipo)_$([guid]::NewGuid().Guid.Substring(0,8)).py"
$pyScript | Out-File -FilePath $tmpFile -Encoding utf8

try {
    & $venvPython $tmpFile
} finally {
    Remove-Item $tmpFile -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Acompanhe execucao em:" -ForegroundColor Yellow
Write-Host "  $root\logs\daemon.log" -ForegroundColor Yellow
Write-Host "Comando: Get-Content `"$root\logs\daemon.log`" -Wait -Tail 10" -ForegroundColor Yellow
