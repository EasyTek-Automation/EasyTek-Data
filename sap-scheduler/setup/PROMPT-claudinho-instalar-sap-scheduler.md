==============================================================
# Missao: Instalar daemon sap-scheduler no PC do PCM (servidor AMG)
==============================================================

## Contexto

Voce esta no PC do PCM no servidor AMG. Vai instalar o daemon Python 32-bit
`sap-scheduler` que executa jobs SAP via GUI Scripting e entrega `.xlsx` na
pasta `input/` do `zpp-processor` existente.

Documentacao completa: `RUNBOOK-instalacao.md` em `.dev-docs/projects/sap-scheduler/`
(ou copia local em `%USERPROFILE%\sap-scheduler\RUNBOOK\`).

Arquitetura macro:
- **Webapp** (container Docker no servidor AMG) → APScheduler agenda 2 jobs diarios
  em 00:01 BRT na collection Mongo `sap_jobs`
- **Daemon** (voce instala aqui) → polling 30s, claim atomico, executa
  `zpp_gridcap.export_grid` via SAP COM, entrega `.xlsx`
- **zpp-processor** (container existente, INTOCADO) → ingere `.xlsx`,
  popula `ZPP_Producao` / `ZPP_Paradas`
- **Home do webapp** → rodape mostra timestamp da ultima coleta

## ⚠️ Seguranca SAP 040

- Mandante 040 GM3, **read-only no SAP** (so export ALV via &XXL — sem IW32, CO11N, MIGO, sendVKey(11))
- Scripts `sap-gate/` ja revisados e ajustados (AJ-02-01 + AJ-02-02 aplicados)
- Nao modificar variants do SAP
- Daemon sem privilegio admin (Task Scheduler InteractiveToken + LeastPrivilege)
- Codigo daemon ja revisado pela equipe — nao alterar logica de coleta

## Pre-requisitos a confirmar antes de comecar

| Item | Como verificar |
|------|----------------|
| Python 3.13 32-bit instalado | `python --version` + `python -c "import struct; print(struct.calcsize('P')*8)"` deve imprimir `32` |
| SAP GUI logado em mandante 040 | Abrir SAPlogon → GM3 → mandante 040 → usuario PCM logado |
| Scripting SAP habilitado | SAP GUI: `Customize Local Layout → Options → Scripting → Enable scripting` marcado (Notify desmarcado) |
| Mongo do AMG acessivel | `mongosh "<MONGO_URI>" --eval "db.runCommand({ping:1})"` retorna `ok:1` |
| Pasta `input/` do zpp-processor gravavel | `dir <PASTA>` + `echo test > <PASTA>\teste.txt` + `del` |

Se algum falhar, parar e reportar antes de prosseguir.

## TAREFAs

### TAREFA 1 — Estrutura de pastas

```cmd
cd %USERPROFILE%
mkdir sap-scheduler
cd sap-scheduler
mkdir sap-gate logs RUNBOOK
```

**Reporte:** sucesso ou erro de criacao.

---

### TAREFA 2 — venv + dependencias

```cmd
cd %USERPROFILE%\sap-scheduler
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python .venv\Scripts\pywin32_postinstall.py -install
```

**Output esperado em `pip install`:**
```
Successfully installed pymongo-X.X.X python-dotenv-X.X.X pywin32-X.X.X pytz-X.X.X
```

**Output esperado em `pywin32_postinstall`:**
```
The pywin32 extensions were successfully registered.
```

**Reporte:** versoes instaladas + confirma pywin32 OK.

---

### TAREFA 3 — Copia dos arquivos

Pasta de origem do codigo: `<ORIGEM>` (Rodolfo informa — pode ser USB, share de rede, git clone local da branch `feature/sap-scheduler-implementation` do repo AMG_Data).

```cmd
:: Codigo do daemon (15 .py + task.xml + requirements.txt + .env.example)
xcopy /Y /I <ORIGEM>\sap-scheduler\*.py %USERPROFILE%\sap-scheduler\
xcopy /Y /I <ORIGEM>\sap-scheduler\__init__.py %USERPROFILE%\sap-scheduler\
xcopy /Y /I <ORIGEM>\sap-scheduler\requirements.txt %USERPROFILE%\sap-scheduler\
xcopy /Y /I <ORIGEM>\sap-scheduler\task.xml %USERPROFILE%\sap-scheduler\
xcopy /Y /I <ORIGEM>\sap-scheduler\healthcheck.py %USERPROFILE%\sap-scheduler\
xcopy /Y /I <ORIGEM>\sap-scheduler\.env.example %USERPROFILE%\sap-scheduler\

:: Scripts SAP (6 arquivos)
xcopy /Y /I /E <ORIGEM>\sap-scheduler\sap-gate\*.* %USERPROFILE%\sap-scheduler\sap-gate\
```

**Verificacao:**
```cmd
dir %USERPROFILE%\sap-scheduler\*.py
:: Esperado: ~14 arquivos .py (daemon.py, config.py, executor.py, etc.)

dir %USERPROFILE%\sap-scheduler\sap-gate\
:: Esperado: zpp_gridcap.py, iw_fastexport.py, *-sel.txt, *-cols.txt

findstr "AJ-02" %USERPROFILE%\sap-scheduler\sap-gate\zpp_gridcap.py
:: Esperado: 7 linhas (1× AJ-02-01 + 6× AJ-02-02)
```

**Reporte:** contagem de arquivos + verificacao das marcas AJ.

---

### TAREFA 4 — Configurar `.env`

```cmd
copy %USERPROFILE%\sap-scheduler\.env.example %USERPROFILE%\sap-scheduler\.env
notepad %USERPROFILE%\sap-scheduler\.env
```

**Editar 3 valores obrigatorios** (Rodolfo informa antes de comecar):

| Var | Valor |
|-----|-------|
| `MONGO_URI` | `mongodb://<host-mongo>:27017/?directConnection=true` |
| `DB_NAME` | `Cluster-EasyTek` (provavelmente ja default) |
| `PASTA_INPUT_ZPP_PROCESSOR` | Caminho host Windows do `input/` do zpp-processor (descobrir em TAREFA 8) |

Demais valores: aceitar defaults (POLLING_INTERVAL_SEGUNDOS=30, etc.).

**MOCK_SAP=false** em producao.

**Verificacao:**
```cmd
findstr "<MONGO_URI" %USERPROFILE%\sap-scheduler\.env
findstr "<host>" %USERPROFILE%\sap-scheduler\.env
findstr "<PASTA_INPUT" %USERPROFILE%\sap-scheduler\.env
:: Os 3 comandos devem retornar nada (placeholders removidos)
```

**Reporte:** confirma que placeholders foram substituidos.

---

### TAREFA 5 — Descobrir path do `input/` (VF-06-12)

No servidor que roda o container `zpp-processor` (talvez mesmo PC do PCM, talvez outro Windows-host):

```cmd
docker inspect <container_zpp-processor> --format "{{range .Mounts}}{{.Source}}:{{.Destination}}\n{{end}}"
```

Procurar linha que termina em `:/data/input` — o **Source** e o caminho host Windows.

Exemplo de saida:
```
C:\amg-share\zpp-input:/data/input
```

→ `PASTA_INPUT_ZPP_PROCESSOR=C:\amg-share\zpp-input`

**Teste de escrita:**
```cmd
echo teste > C:\amg-share\zpp-input\teste_claudinho.txt
del C:\amg-share\zpp-input\teste_claudinho.txt
```

Se falhar com "Acesso negado", reportar — pode precisar sysadmin liberar permissao.

**Reporte:** caminho host descoberto + teste de write passou.

---

### TAREFA 6 — Registrar Task Scheduler

```cmd
schtasks /Create /TN "SAP Job Scheduler" /XML %USERPROFILE%\sap-scheduler\task.xml /F
```

**Output esperado:**
```
SUCESSO: A tarefa agendada "SAP Job Scheduler" foi criada.
```

**Se falhar com "Acesso negado":** editar `task.xml` garantindo `<RunLevel>LeastPrivilege</RunLevel>` (nao `HighestAvailable`), salvar, repetir.

**Verificacao:**
```cmd
schtasks /Query /TN "SAP Job Scheduler" /V /FO LIST
:: Esperado: linha "Status: Ready"
```

**Reporte:** task criada + status Ready.

---

### TAREFA 7 — Primeiro disparo + verificar log

```cmd
schtasks /Run /TN "SAP Job Scheduler"
```

Aguardar 30 segundos.

```cmd
type %USERPROFILE%\sap-scheduler\logs\daemon.log
```

**Linhas esperadas:**
```
daemon: boot iniciado | pid=... versao=0.1.0-IM-D1 mock_sap=False
daemon: lockfile adquirido | pid=...
daemon: conexao Mongo OK | db=Cluster-EasyTek
daemon: indices garantidos em 'sap_jobs'
daemon: nenhum orfao detectado
daemon: loop principal iniciado | polling=30s heartbeat=3600s tipos=['zppprd', 'zpp_nt0001']
```

**Reporte:** as 6 linhas presentes. Se houver `[FATAL]`, reportar erro literal.

---

### TAREFA 8 — Healthcheck

```cmd
%USERPROFILE%\sap-scheduler\.venv\Scripts\python.exe %USERPROFILE%\sap-scheduler\healthcheck.py
```

**Output esperado:**
```
[OK] estrutura raiz: ...
[OK] subpastas presentes
[OK] venv python encontrado
[OK] deps instaladas
[OK] .env configurado (sem placeholders)
[OK] task 'SAP Job Scheduler' registrada
[OK] daemon vivo (PID ...)
[OK] log recente: daemon.log (idade=Xs)

=== HEALTHCHECK OK ===
```

Exit code 0.

**Se algum FAIL:** reportar codigo + mensagem exato.

---

### TAREFA 9 — Configurar auto-login (Opcao A do RUNBOOK)

Garante que daemon sobe apos reboot sem ninguem precisar logar.

```cmd
netplwiz
```

Na GUI que abre:
1. Selecionar o usuario PCM atual
2. **Desmarcar** "Os usuarios devem digitar nome de usuario e senha"
3. OK → janela pede senha 2× → preencher senha do usuario PCM (Rodolfo informa)
4. OK final

**Teste:** reiniciar PC manualmente (ou avisar Rodolfo pra fazer). Apos reboot, sistema deve logar automatico sem digitar senha.

**Apos login automatico (~90s):** Task Scheduler dispara o daemon. Confirmar via:
```cmd
type %USERPROFILE%\sap-scheduler\logs\daemon.log | findstr "boot iniciado"
```

Deve aparecer linha de boot recente (apos o reboot).

**Reporte:** auto-login funcionou + daemon subiu apos reboot.

**Se Opcao A nao for possivel** (politica corporativa AMG bloqueia auto-login): reportar e Rodolfo decide entre Opcao B (negociar com sysadmin "Log on as a batch job") ou C (aceitar risco).

---

### TAREFA 10 — Backup pre-update (Passo 9b)

```cmd
xcopy /E /I /Y %USERPROFILE%\sap-scheduler %USERPROFILE%\sap-scheduler-backup-%date:~6,4%%date:~3,2%%date:~0,2%
```

Cria pasta `sap-scheduler-backup-YYYYMMDD` ao lado da pasta principal.

**Reporte:** caminho da pasta de backup criada.

---

### TAREFA 11 — Teste end-to-end manual (VF-06-11 ZPPPRD)

Disparar 1 job manual via endpoint REST do webapp + observar ciclo completo.

#### 11.1 — Disparar via endpoint (webapp deve estar com nova imagem deployada)

Voce nao tem acesso ao webapp browser daqui. Pedir pro Rodolfo abrir a home e usar **uma das opcoes abaixo:**

**Opcao A — Rodolfo dispara via curl no terminal Windows com cookie de sessao:**
```cmd
curl -X POST -H "Content-Type: application/json" -b "etd_session=<cookie>" -d "{\"tipo\":\"zppprd\",\"delay_segundos\":0}" https://<webapp-url>/api/v1/sap-scheduler/trigger
```

**Opcao B — Rodolfo insere job direto no Mongo:**
```cmd
mongosh "<MONGO_URI>" --eval "db.sap_jobs.insertOne({tipo:'zppprd', parametros:{teste_manual:true}, status:'pendente', agendado_para:new Date(Date.now()-60000), criado_em:new Date(), iniciado_em:null, concluido_em:null, resultado:null, erro:null})"
```

#### 11.2 — Aguardar daemon claim (max 30s)

```cmd
type %USERPROFILE%\sap-scheduler\logs\daemon.log | findstr "[claim]"
```

Esperado:
```
[claim] job claimed | _id=... tipo=zppprd
```

#### 11.3 — Aguardar export SAP (60-120s, conforme RNF-04-01)

```cmd
type %USERPROFILE%\sap-scheduler\logs\daemon.log | findstr "[done]"
```

Esperado:
```
[done] job concluido | _id=... tipo=zppprd duracao_s=XX tamanho_bytes=XXXXXX
```

#### 11.4 — Verificar arquivo no `input/` do zpp-processor

```cmd
dir %PASTA_INPUT_ZPP_PROCESSOR%\zppprd_*.xlsx
```

Deve listar arquivo recem-criado (com timestamp atual).

#### 11.5 — Aguardar consumer ingerir (max 1h — polling 3600s default)

Apos ~1h, verificar:

**a)** Arquivo saiu de `input/`:
```cmd
dir <PASTA_INPUT>\zppprd_*.xlsx
:: Esperado: nenhum arquivo do dia (foi movido)
```

**b)** Arquivo em `output/` (sucesso) OU em `rejected/` (falha):
```cmd
dir <PASTA_OUTPUT>\zppprd_*.xlsx
dir <PASTA_REJECTED>\zppprd_*.xlsx
```

**c)** Collection `ZPP_Producao` no Mongo ganhou docs novos:
```cmd
mongosh "<MONGO_URI>" --eval "print('docs hoje: ' + db.ZPP_Producao.countDocuments({fininotif: {$gte: new Date(new Date().setHours(0,0,0,0))}}))"
```

**Reporte:** status final do arquivo (output/rejected) + contagem de docs em `ZPP_Producao`.

**Se arquivo foi pra `rejected/`:** consultar log do consumer pra entender motivo:
```cmd
docker logs <container_zpp-processor> 2>&1 | findstr "rejected"
```

Comum:
- "tipo de planilha nao reconhecido" → schema diferente; reportar como bug do daemon
- "nenhum registro pertence ao mes de referencia" → regra de mes do consumer; **dados do dia funcionarao**, dados antigos rejeitados. **Aceitavel se primeiro ciclo manual usar dados de outro dia**.

---

### TAREFA 12 — Confirmar filtros ZPP_NT0001 via SAP Script Recording (IM-G3)

Os filtros do ZPP_NT0001 (transacao de paradas) estao como **placeholder** em
`%USERPROFILE%\sap-scheduler\tipos.py:_args_zpp_nt0001`. Voce vai gravar a sessao
SAP real pra extrair os IDs corretos.

#### 12.1 — Habilitar Script Recording

No SAP GUI: `Customize Local Layout (Alt+F12) → Script Recording and Playback`.

Janela abre. Clicar **Record**.

#### 12.2 — Executar fluxo manual no SAP

1. Digitar transacao `zpp_nt0001` no campo de comando do SAP
2. Pressionar Enter
3. Preencher os filtros que o relatorio de paradas usa:
   - Centro: `BR02`
   - Data inicio / data fim: ontem (dd.mm.yyyy)
   - Variant: a que o cliente AMG usa pra paradas (Rodolfo informa)
   - Qualquer outro campo necessario (perguntar pro PCM)
4. Pressionar F8 (executar)
5. Aguardar grid carregar
6. Clicar **Stop** na janela de recording

#### 12.3 — Inspecionar `.vbs` gerado

Janela mostra `Script in process` → clicar **Save As** → salvar como `nt0001_record.vbs`.

Abrir o `.vbs` com Notepad. Procurar linhas tipo:
```vbs
session.findById("wnd[0]/usr/ctxtP_WERKS").Text = "BR02"
session.findById("wnd[0]/usr/ctxtS_DATE-LOW").Text = "01.06.2026"
session.findById("wnd[0]/usr/ctxtS_DATE-HIGH").Text = "01.06.2026"
session.findById("wnd[0]/usr/ctxtP_VARI").Text = "<variant>"
```

**Extrair os IDs SAP** (entre aspas em `findById("...")`) e os valores (sem o `.Text`).

#### 12.4 — Atualizar `tipos.py`

Editar `%USERPROFILE%\sap-scheduler\tipos.py`. Achar funcao `_args_zpp_nt0001`. Substituir os elementos placeholder da lista `set` pelos IDs reais extraidos do `.vbs`:

```python
def _args_zpp_nt0001(path_xlsx: str, agora_brt: datetime) -> SimpleNamespace:
    ontem = agora_brt - timedelta(days=1)
    return SimpleNamespace(
        tx="zpp_nt0001",
        set=[
            "wnd[0]/usr/ctxtP_WERKS=BR02",
            # <-- COLAR IDs REAIS AQUI, mantendo formato "id=valor"
            # Trocar datas estaticas por dinamicas usando f-string:
            f"wnd[0]/usr/ctxtS_DATE-LOW={_ddmmaaaa(ontem)}",
            f"wnd[0]/usr/ctxtS_DATE-HIGH={_ddmmaaaa(ontem)}",
            "wnd[0]/usr/ctxtP_VARI=<variant_real>",
        ],
        no_f8=False,
        kill_excel=False,
        ctx_code="&XXL",
        save_dir=str(path_xlsx).rsplit("\\", 1)[0],
        fname=str(path_xlsx).rsplit("\\", 1)[-1],
    )
```

Salvar.

#### 12.5 — Reiniciar daemon + disparar job ZPP_NT0001 manual

```cmd
:: 1. Achar PID do daemon
type %USERPROFILE%\sap-scheduler\daemon.lock
:: 2. Matar
taskkill /F /PID <PID>
:: 3. Aguardar Task Scheduler relancar (~60s) — OU forcar:
schtasks /Run /TN "SAP Job Scheduler"
:: 4. Confirmar boot
type %USERPROFILE%\sap-scheduler\logs\daemon.log | findstr "boot"
:: 5. Disparar job manual
mongosh "<MONGO_URI>" --eval "db.sap_jobs.insertOne({tipo:'zpp_nt0001', parametros:{teste_g3:true}, status:'pendente', agendado_para:new Date(Date.now()-60000), criado_em:new Date(), iniciado_em:null, concluido_em:null, resultado:null, erro:null})"
:: 6. Aguardar 2min
:: 7. Conferir log
type %USERPROFILE%\sap-scheduler\logs\daemon.log | findstr "[done]"
```

**Reporte:** IDs SAP extraidos do `.vbs` + sucesso/falha do job `zpp_nt0001` + se falhou, em qual fase.

---

### TAREFA 13 — Backup final + propagar AJ pra mestre

Apos tudo funcionar:

```cmd
:: Backup pos-config
xcopy /E /I /Y %USERPROFILE%\sap-scheduler %USERPROFILE%\sap-scheduler-backup-pos-config-%date:~6,4%%date:~3,2%%date:~0,2%

:: Copiar zpp_gridcap.py + tipos.py atualizados de volta pro Rodolfo:
:: (USB ou share de rede)
copy %USERPROFILE%\sap-scheduler\sap-gate\zpp_gridcap.py <DESTINO>\zpp_gridcap-validado.py
copy %USERPROFILE%\sap-scheduler\tipos.py <DESTINO>\tipos-validado.py
```

Rodolfo vai propagar AJ-02-01/02 + IDs ZPP_NT0001 reais pra cópia mestre em
`.dev-docs/development/SAP Integration/sap-gate/` em proximo SDD.

**Reporte:** backup criado + arquivos validados copiados.

---

## Entregaveis (reportar ao Rodolfo no fim)

1. **Healthcheck OK?** Output completo do `healthcheck.py`
2. **VF-06-11 ZPPPRD passou?** Arquivo foi pra `output/` ou `rejected/`? Se rejected, qual motivo?
3. **VF-06-11 ZPP_NT0001 passou?** Idem
4. **IDs SAP extraidos pro ZPP_NT0001:** lista completa do `set` montado
5. **Auto-login configurado?** Opcao A/B/C adotada
6. **Daemon sobe apos reboot?** Confirmado via log timestamp
7. **Caminho host de `<PASTA_INPUT_ZPP_PROCESSOR>`:** valor preenchido no `.env`
8. **Algum erro nao previsto?** Stack trace + arquivo de log relevante

## Fatos conhecidos (referencia)

- Daemon usa Python **3.13 32-bit** (nao 64) — exigido pelo `pywin32` + SAPlogon
- Modo `MOCK_SAP=true` so em dev/CI; em prod deve ser `false`
- Polling 30s default — daemon le `sap_jobs` a cada 30s
- Heartbeat 3600s — log "alive" a cada hora em ocioso
- Lockfile em `%USERPROFILE%\sap-scheduler\daemon.lock` com PID — single-instance
- Task Scheduler `LogonTrigger` + repeat 1min — relanca apos crash em <=60s
- Sem privilegio admin em nenhuma etapa exceto **opcao B** (alternativa, requer sysadmin)
- Webapp ja tem rodape na home mostrando timestamp da ultima coleta — sinaliza problema visualmente
- 8 fases de erro classificadas em BR-06: conexao_sap / navegacao / export_alv / salvamento / validacao_arquivo / kill_excel / mongo_update / desconhecido

## Quando reportar pra mim (Rodolfo)

**Reporte imediato** se:
- Algum pre-requisito falhar (TAREFA 0)
- `pywin32_postinstall.py` falhar (TAREFA 2)
- Marcas AJ-02 ausentes no `zpp_gridcap.py` (TAREFA 3)
- `MONGO_URI` recusa conexao (TAREFA 7 falha)
- Healthcheck retorna FAIL em qualquer numero
- VF-06-11 ZPPPRD vai pra `rejected/` por motivo diferente de "regra de mes" (TAREFA 11)
- SAP Script Recording nao gera `.vbs` valido (TAREFA 12)

**Reporte final** apos TAREFA 13 completar — entregaveis 1-8 acima.

---

**Diretrizes finais:**
- Nao alterar codigo Python do daemon a menos que seja `tipos.py:_args_zpp_nt0001` (TAREFA 12)
- Nao alterar variants do SAP em hipotese alguma
- Em caso de duvida, parar e reportar
- Logs em `%USERPROFILE%\sap-scheduler\logs\daemon.log` — primeiro lugar a olhar em qualquer problema
