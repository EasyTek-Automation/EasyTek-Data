"""sap-scheduler daemon — serviço Python 32-bit que executa jobs SAP via GUI Scripting.

Roda no PC do PCM no servidor AMG. Lê jobs `pendente` da collection `sap_jobs`
do Mongo do AMG; executa via `sap-gate/zpp_gridcap.py`; entrega `.xlsx` na pasta
`input/` do `zpp-processor` existente.

Documentação completa: `.dev-docs/projects/sap-scheduler/05-design.md` (DS-04).
"""
