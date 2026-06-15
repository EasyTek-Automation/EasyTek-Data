# sap-scheduler

Daemon Python (32-bit) que executa **trabalhos SAP** sob demanda. Roda no PC do PCM (Windows).
Lê jobs da fila **`sap_jobs`** (Mongo `Cluster-EasyTek`), descobre **qual script** o job pede,
roda o script e devolve **sucesso/fracasso**.

> **Divisão de responsabilidades**
> 1. **webapp** dispara o job (manual ou agendado) → insere em `sap_jobs`.
> 2. **daemon** (genérico) vê o job, acha o **script** do tipo no `core/registry.py`, roda e marca o resultado.
> 3. **script** (auto-contido, em `trabalhos/…`) executa a tarefa no SAP e devolve `Result(ok | falha)`.
> O daemon **não conhece nenhum tipo** — só consulta o registry.

---

## Estrutura

```
sap-scheduler/
├── README.md                  ← este arquivo
├── daemon.py                  ← entrypoint (o launcher chama; deve ficar na raiz)
├── .env                       ← config (MONGO_URI, DB_NAME, SAP_JOBS_TIPOS_SUPORTADOS, pasta input…)
├── launcher.vbs               ← lançamento (tarefa agendada "SAP Job Scheduler", oculto)
├── __init__.py                ← marcador de pacote Python (necessário)
│
├── ferramentas/               ← utilitários: disparar_job.ps1/.cmd, verificar_pos_reboot.ps1
├── setup/                     ← instalação: task.xml, requirements.txt
│
├── core/                      ← MOTOR genérico do daemon (não conhece tipo)
│   ├── loop_principal.py      polling 30s + claim atômico
│   ├── executor.py            acha o script no registry, roda com retry, marca resultado
│   ├── registry.py            ← tipo → script  (ÚNICO lugar que liga tipo↔script)
│   ├── contracts.py           Result (ok|falha+fase) + Ctx (config + sessão SAP + Mongo)
│   ├── sap.py                 conecta na sessão SAP GUI aberta
│   ├── mongo.py               ops na fila sap_jobs (claim/concluido/falhou)
│   └── config logger lockfile healthcheck orfaos path_resolver kill_excel
│
├── trabalhos/                 ← os SCRIPTS, um por transação (auto-contidos)
│   ├── kpis_manut/            "KPIs Manutenção"
│   │   ├── zppprd.py          ZPPPRD   → grade ALV → &XXL → share
│   │   ├── nt0001.py          ZPP_NT0001 → grade ALV → &XXL → share
│   │   ├── _alv.py            fluxo ALV compartilhado (path→export→valida)
│   │   ├── zpp_gridcap.py     motor de export ALV (&XXL / VIA B)
│   │   └── *-sel.txt *-cols.txt   IDs/colunas de referência
│   └── custos_manut/          "Custos de Manutenção"
│       ├── custo_exec.py      KSB1 (lançamentos) → AMG_CustoLancamentos
│       ├── custo_orcado.py    ZBRCO019 (orçado, scrape) → AMG_CustoResumo
│       ├── _carga.py          carga idempotente no Mongo (delete por mês + insert)
│       └── custo_collect.py   coleta read-only (KSB1 VIA B + ZBRCO019 scrape)
│
└── old/                       ← fora da execução
    ├── codigo_antigo/         estrutura flat anterior (executor_sap, tipos, sap-gate…)
    ├── backups/               backups de .env e de versões
    ├── testes/                scripts/logs de teste
    └── RUNBOOK-antigo
```

> Pastas de código usam nome sem espaço/acento (exigência do `import`); os nomes "bonitos" estão acima.

---

## Como funciona um job (resumido)

```
loop_principal:  claim_atomico(sap_jobs, tipos ∈ SAP_JOBS_TIPOS_SUPORTADOS)
executor:        run = registry.REGISTRY[job.tipo]
                 result = run(job, ctx)          # ctx = config + sessão SAP (lazy) + Mongo
                 (retry só em fase transiente)
                 marca concluido(result.dados) | falhou(result.fase, erro)
```
Cada `trabalhos/…/<tipo>.py` tem `def run(job, ctx) -> Result`. **Sucesso** = `Result.sucesso(...)`;
**falha** = `Result.falha(fase, erro)`. O miolo de cada script é livre (ALV, scrape, etc.).

| Tipo | Script | Fonte SAP | Saída |
|---|---|---|---|
| `zppprd` | `trabalhos/kpis_manut/zppprd.py` | ZPPPRD (ALV) | xlsx → share → zpp-processor → Mongo |
| `zpp_nt0001` | `trabalhos/kpis_manut/nt0001.py` | ZPP_NT0001 (ALV) | xlsx → share → zpp-processor → Mongo |
| `custo_exec` | `trabalhos/custos_manut/custo_exec.py` | KSB1 (lê grade) | Mongo direto (`AMG_CustoLancamentos`) |
| `custo_orcado` | `trabalhos/custos_manut/custo_orcado.py` | ZBRCO019 (scrape) | Mongo direto (`AMG_CustoResumo`) |

---

## Adicionar uma transação nova
1. Criar `trabalhos/<grupo>/<tipo>.py` com `def run(job, ctx) -> Result`.
2. Registrar em `core/registry.py`: `"<tipo>": <modulo>.run`.
3. Adicionar `<tipo>` em `SAP_JOBS_TIPOS_SUPORTADOS` no `.env`.
4. Reiniciar o daemon. **O daemon não muda.**

---

## Operação

**Pré-requisito:** uma sessão SAP GUI aberta e logada (o daemon dirige ela).

**Disparar manual:**
```powershell
cd $env:USERPROFILE\sap-scheduler
.\ferramentas\disparar_job.ps1 custo_exec    # ou: zppprd | zpp_nt0001 | custo_orcado
```

**Acompanhar:**
```powershell
Get-Content "$env:USERPROFILE\sap-scheduler\logs\daemon.log" -Wait -Tail 10
```

**Reiniciar o daemon (carrega código/.env novo):**
```powershell
Stop-ScheduledTask -TaskName "SAP Job Scheduler"
Stop-Process -Id (Get-Content "$env:USERPROFILE\sap-scheduler\daemon.lock") -Force
Remove-Item "$env:USERPROFILE\sap-scheduler\daemon.lock"
Start-ScheduledTask -TaskName "SAP Job Scheduler"
```

**Agendamento automático:** o **webapp** enfileira nos horários (indicadores: ver `sap_scheduler_config`;
custo: env `CUSTOS_COLETA_HORA`). O daemon só processa.
