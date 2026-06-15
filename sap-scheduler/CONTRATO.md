# CONTRATO — coleções compartilhadas daemon ↔ webapp

O daemon `sap-scheduler` e o webapp se comunicam **só pelo Mongo** (`Cluster-EasyTek`).
Não há API entre eles. Este arquivo é a **fonte única da verdade** do schema dessas
coleções. Os dois lados (daemon e `webapp/src/custos/` + `webapp/src/sap_scheduler/`)
devem bater com o que está aqui. **Qualquer mudança de schema atualiza este arquivo.**

> Convivência: o daemon **co-localiza** a fonte no AMG_Data justamente para que webapp
> e daemon partam deste mesmo documento e não divirjam (drift). Ver `README.md` para a
> arquitetura do daemon e os tipos de job.

---

## 1. `sap_jobs` — a fila (webapp ENFILEIRA, daemon CONSOME)

Webapp insere (`webapp/src/custos/sap_jobs.py`, `webapp/src/sap_scheduler/`):

```jsonc
{
  "tipo": "custo_exec",            // zppprd | zpp_nt0001 | custo_exec | custo_orcado
  "parametros": { ... },           // payload livre por tipo (ver nota de drift abaixo)
  "status": "pendente",            // pendente → executando → concluido | falhou
  "agendado_para": <Date UTC>,     // claim só quando <= now
  "criado_em": <Date UTC>,
  "iniciado_em": null,             // daemon seta no claim
  "concluido_em": null,            // daemon seta no fim
  "resultado": null,               // dados de sucesso (duracao_segundos, tamanho_bytes, tentativas)
  "erro": null                     // {mensagem, tipo_excecao, fase, traceback_resumido?}
}
```

Daemon claima atômico (`core/mongo.py` → `claim_atomico`):
`status="pendente" AND agendado_para<=now AND tipo ∈ SAP_JOBS_TIPOS_SUPORTADOS`,
ordenado por `agendado_para` (FIFO), seta `status="executando" + iniciado_em`.

**Índices:** `(status, agendado_para)`, `(tipo, concluido_em desc)`, `(tipo, agendado_para)` unique (dedup).

---

## 2. `AMG_CustoLancamentos` — lançamentos (daemon `custo_exec` GRAVA, webapp LÊ no drill)

1 doc por lançamento (`custo_collect.collect_lancamentos` → `_carga.gravar`):

```jsonc
{
  "mes_referencia": "2026-05",     // STRING "YYYY-MM"  ← convenção obrigatória
  "data_lancamento": <Date>,       // BSON Date         ← convenção obrigatória
  "conta": "33102101",
  "centro_custo": "...",
  "valor": 1234.56,                // float (sinal à direita do SAP → negativo = crédito)
  "descritor": "...",              // texto do pedido (EBTXT) ou do material
  "tipo_doc": "...", "no_documento": "...", "pedido_compra": "...",
  "fonte": "sap"                   // daemon = "sap"; seed local = "csv"
}
```

Webapp lê (`webapp/src/custos/leitura.py`) por `mes_referencia` + opcional `centro_custo`.
**Índices:** `(mes_referencia, conta, data_lancamento)`, `(centro_custo)`.

---

## 3. `AMG_CustoResumo` — orçado×executado (daemon `custo_orcado` GRAVA, webapp LÊ no gráfico)

1 doc por conta × mês (`custo_collect.collect_resumo` → `_carga.gravar`):

```jsonc
{
  "conta": "33102101", "conta_desc": "...",
  "subgrupo": "G0341", "grupo": "GT340",
  "mes_referencia": "2026-05",     // STRING "YYYY-MM"
  "orcado": 73076.67,              // float (coluna Plan ZBRCO019)
  "executado": 229824.96,          // float (coluna Real ZBRCO019)
  "total_oficial_geral": ...,      // executado da linha GERAL GT340
  "fonte": "sap"
}
```

**Índice:** `(mes_referencia, conta)`.

---

## 4. Convenções inquebráveis (já nos morderam)

- `mes_referencia` = **`"YYYY-MM"`** string. Com `MM.YYYY` o gráfico do 1º nível vem **vazio**.
- datas = **BSON Date** (não string). Com data string o **drill por dia** vem vazio.
- **Carga idempotente:** o daemon faz `delete_many({mes_referencia ∈ janela, fonte:"sap"}) + insert_many`.
  Rodar 2× não duplica. **Só apaga `fonte:"sap"`** — não toca docs de outra fonte.

---

## 5. Drifts conhecidos (auditados em 2026-06-15 na importação da fonte)

Pré-existentes; documentados para não viram surpresa. Nenhum quebra produção hoje.

1. **`parametros.janela` é ignorado pelo daemon.** O webapp grava
   `parametros.janela.{inicio,fim,meses}` no job, mas `custo_exec.run`/`custo_orcado.run`
   **recalculam** a janela via `custo_collect.janela_dois_meses(agora)`. Benigno: as duas
   implementações são algebricamente idênticas (mês corrente + anterior até D-1, BR-09).

2. **Regra da janela (BR-09) duplicada** em dois lugares: `webapp/src/custos/sap_jobs.py`
   (`janela_dois_meses`) e `sap-scheduler/trabalhos/custos_manut/custo_collect.py`
   (`janela_dois_meses`). Mudar a regra exige editar os dois. Consolidar é o alvo futuro.

3. **A leitura do webapp NÃO filtra `fonte`.** `webapp/src/custos/leitura.py` agrega por
   `mes_referencia` sem distinguir `fonte`. Como a idempotência do daemon só apaga
   `fonte:"sap"`, se um mês tiver **`csv` (seed) E `sap` (daemon) ao mesmo tempo**, a
   leitura **soma os dois → valores dobrados**. **Dormente:** produção só tem `sap`; o seed
   (`fonte:"csv"`) é âncora local/dev. Só dispara se rodarem o seed em produção. Mitigação
   futura: a leitura preferir `sap` quando existir, ou garantir exclusão mútua por mês.
