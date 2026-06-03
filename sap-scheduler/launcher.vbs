' SAP Job Scheduler — launcher headless (Bloco I A-01).
'
' Problema (achado A-01 do cliente 02/06/2026):
'   pythonw.exe quebra porque zpp_gridcap.export_grid faz print() e
'   pythonw tem stdout=None — raise IOError em qualquer print.
'
' Solucao:
'   wscript chama python.exe (com stdout) mas em window style 0 (oculto).
'   Espera True garante single-instance — wscript so retorna quando
'   o python terminar; LogonTrigger nao relanca em paralelo.
'
' Uso (registrado em task.xml):
'   wscript //B //Nologo "%USERPROFILE%\sap-scheduler\launcher.vbs"

Option Explicit

Dim shell, profile, pyExe, daemonPy, cmd
Set shell = CreateObject("WScript.Shell")
profile = shell.ExpandEnvironmentStrings("%USERPROFILE%")
pyExe    = profile & "\sap-scheduler\.venv\Scripts\python.exe"
daemonPy = profile & "\sap-scheduler\daemon.py"

' Aspas duplas embutidas pra path com espaco em USERPROFILE
cmd = """" & pyExe & """ """ & daemonPy & """"

' Run(strCommand, intWindowStyle, bWaitOnReturn)
'   intWindowStyle = 0  -> janela oculta (sem flash de cmd preto)
'   bWaitOnReturn  = True -> wscript bloqueia ate daemon encerrar
shell.Run cmd, 0, True
