# 1. Criar branch específica
git checkout -b feature/bife-[numero]

# 2. Fazer checkpoint
git add .
git commit -m "checkpoint: before starting bife [numero]"

# 3. Anotar estado atual
echo "Branch: feature/bife-[numero]
Data: $(date)
Último commit antes: $(git log -1 --oneline)" > bife-[numero]-checkpoint.txt

##########################################################

# Commits pequenos e frequentes
git add [arquivos modificados]
git commit -m "[tipo]: [descrição curta]"

# Tipos:
# - feat: nova funcionalidade
# - refactor: refatoração
# - fix: correção
# - docs: documentação

###########################################################

# 1. Testar TUDO manualmente
# Ver seção de testes de cada bife

# 2. Se tudo OK:
git add .
git commit -m "feat: complete bife [numero] - ..."
git push
git checkout main
git pull
git merge feature/bife-[numero]
git push origin main
git branch -d feature/bife-[numero]
git push origin --delete feature/bife-[numero]

# 3. Se algo deu errado:
git checkout main  # Volta para versão estável
git branch -D feature/bife-[numero]  # Descarta mudanças
```

---

## 📈 Progresso Geral
```
🥩 Bife 1: [  0%] Reorganizar Estrutura
🥩 Bife 2: [  0%] Melhorar Header
🥩 Bife 3: [  0%] Criar Home
🥩 Bife 4: [  0%] Separar Energia
🥩 Bife 5: [  0%] Criar Alarmes
🥩 Bife 6: [  0%] Limpar e Documentar

Total: [  0%] Completo

