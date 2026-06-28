# RECUPERAÇÃO / DEPLOY — daemon sap-scheduler

O daemon roda **nativo no servidor Windows do cliente** (SAP GUI Scripting, Python
32-bit). **Não containeriza** — é a exceção ao deploy por imagem do AMG. Por isso:

- **AMG_Data** versiona a **fonte** (este diretório).
- **AMG_Infra/CI** empacota um **artefato `.zip`** versionado e publica no Release (mesma
  tag das imagens). Ver `AMG_Infra` → `deploy-daemon.ps1` + hook no `up.ps1`.
- O **servidor** baixa o zip e roda nativo, **sem clonar o AMG_Data**.

> **Stateless + idempotente:** todo o dado vive no Mongo/share, nunca no PC. Crash do
> servidor = re-deploy num PC novo + restaurar `.env` + relogar SAP. **Zero perda de dado**
> — jobs `pendente` são reprocessados; a carga de custo é idempotente por mês.

---

## Deploy normal (atualização de versão)

Pelo orquestrador único (recomendado), no servidor:

```powershell
cd <AMG_Infra>
.\scripts\up.ps1 prod <tag>     # sobe containers E atualiza o daemon na mesma tag
```

O `up.ps1` chama `deploy-daemon.ps1 <tag>`, que: baixa o zip do Release da tag → extrai
para `%USERPROFILE%\sap-scheduler\` **preservando `.env`/`logs/`/`.venv/`** → atualiza a
venv (`setup/requirements.txt`) → reinicia a tarefa `"SAP Job Scheduler"`.

> O `.zip` **não** contém `.env`, `.venv`, `logs`, `daemon.lock`, `old/` (`.gitignore`).
> Esses são locais do servidor e sobrevivem ao redeploy.

---

## Recuperação do zero (PC novo / DR)

1. **Baixar a fonte** — o `.zip` do Release (`gh release download <tag> -p 'sap-scheduler-*.zip'`)
   ou clonar o AMG_Data e copiar `sap-scheduler/`. Destino: `%USERPROFILE%\sap-scheduler\`.

2. **Python 32-bit** — instalar Python 32-bit (pywin32 exige bitness igual ao SAP GUI).
   Criar venv e instalar deps:
   ```powershell
   cd $env:USERPROFILE\sap-scheduler
   py -3-32 -m venv .venv
   .\.venv\Scripts\pip install -r setup\requirements.txt
   ```

3. **Restaurar `.env`** — copiar de backup seguro (tem `MONGO_URI` com credencial). Base:
   `.env.example`. Campos críticos:
   - `MONGO_URI`, `DB_NAME` — mesmos do webapp.
   - `PASTA_INPUT_ZPP_PROCESSOR` — pasta input do zpp-processor (`docker inspect`).
   - **`SAP_JOBS_TIPOS_SUPORTADOS`** — em **produção** são os **4** tipos:
     `zppprd,zpp_nt0001,custo_exec,custo_orcado`. ⚠️ O `.env.example` lista só os 2
     primeiros; sem os de custo o daemon **não claima** as coletas de custo.

4. **Registrar a tarefa Windows** — `setup/task.xml` cria `"SAP Job Scheduler"`
   (LogonTrigger, repete a cada 1 min, single-instance). Antes de importar, **substituir
   `MADRID\cmanutencao`** pelo usuário literal do servidor (Task Scheduler não expande
   `%USERNAME%` no `<UserId>`):
   ```powershell
   schtasks /Create /TN "SAP Job Scheduler" /XML setup\task.xml /RU MADRID\<usuario>
   ```

5. **Logar no SAP** — abrir o SAP GUI e logar (sessão GM3/040). O daemon dirige a sessão
   aberta; sem login, falha na fase `conexao_sap` (e retenta — fase transiente).

6. **Subir** — `Start-ScheduledTask -TaskName "SAP Job Scheduler"`. Acompanhar:
   ```powershell
   Get-Content "$env:USERPROFILE\sap-scheduler\logs\daemon.log" -Wait -Tail 10
   ```

---

## Reverter um deploy

A versão anterior continua no Release. Re-rodar `deploy-daemon.ps1 <tag-antiga>` (ou
`up.ps1 prod <tag-antiga>`) restaura a fonte anterior. O `.env` não é tocado. Como a
carga é idempotente, reprocessar não duplica.

## Validar pós-deploy

```powershell
.\ferramentas\verificar_pos_reboot.ps1          # checa tarefa, lock, processo
.\ferramentas\disparar_job.ps1 custo_exec       # smoke: enfileira + processa 1 job
```
Sucesso = job vira `concluido` em `sap_jobs` e docs aparecem em `AMG_CustoLancamentos`.
