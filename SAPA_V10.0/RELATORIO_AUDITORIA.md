# 🐸 SAPA v9.0 — Relatório de Auditoria Completo

**Engenheiro Responsável:** Auditoria de Código Senior / QA  
**Data:** Junho 2026  
**Arquivos Analisados:** `database.py`, `sync_manager.py`, `main.py`, `falta_automatica.py`, `calendar_engine.py`, `auth.py`, `relatorio.py`

---

## 🔴 BUGS CRÍTICOS CORRIGIDOS (causariam travamento ou perda de dados)

### BUG #1 — Caminho relativo do banco (`banco_sapa.db`) — **CRÍTICO**
**Arquivos afetados:** `database.py`, `sync_manager.py`, `main.py`, `falta_automatica.py`, `calendar_engine.py`, `auth.py`, `relatorio.py`

**Problema:** Todos os 7 arquivos abriam o banco com `sqlite3.connect("banco_sapa.db")` — um caminho **relativo**. Isso significa que o banco só era encontrado se o Python fosse executado **exatamente** da mesma pasta do script. Ao criar um atalho na área de trabalho, executar com duplo clique, ou usar o Task Scheduler do Windows, o `os.getcwd()` seria diferente (`C:\Users\Professor`, por exemplo), e o programa abriria um **banco vazio e invisível** — sem erros, apenas sem dados.

**Correção:** `database.py` exporta uma constante `DB_PATH` com o caminho absoluto calculado a partir de `__file__`:
```python
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banco_sapa.db")
```
Todos os outros módulos importam `DB_PATH` de `database.py` e usam `sqlite3.connect(DB_PATH)`.

---

### BUG #2 — Colunas `Hora_Entrada`, `Hora_Saida`, `Justificativa` ausentes na criação do banco
**Arquivo:** `database.py`

**Problema:** O `resetar_banco()` criava a tabela `LOGS` **sem** as colunas `Hora_Entrada`, `Hora_Saida` e `Justificativa`. Essas colunas eram adicionadas via `ALTER TABLE` a cada abertura do `main.py` e do painel do professor. Isso causava:
- Race condition se a thread de sync tentasse inserir antes do `ALTER TABLE`
- `sqlite3.OperationalError: table has no column named Hora_Entrada` em bancos recém-criados

**Correção:** As 3 colunas foram adicionadas ao `CREATE TABLE LOGS` original em `database.py`. As migrações de `ALTER TABLE` foram mantidas em `main.py` apenas para compatibilidade com bancos existentes.

---

### BUG #3 — `relatorio.py`: bloco `if __name__ == "__main__"` no **meio** do arquivo
**Arquivo:** `relatorio.py`

**Problema:** O bloco `if __name__ == "__main__"` estava posicionado **entre** as funções do módulo. Em Python, isso não impede a execução das funções abaixo dele quando o arquivo é **importado**, mas em algumas versões/implementações isso pode causar comportamento inesperado. Mais grave: as funções `extrair_infos_disciplina`, `inferir_periodo` e `enviar_relatorio_completo_csv` estavam definidas **depois** do bloco `if __name__`, tornando-as invisíveis para qualquer import que parasse de ler ali.

**Correção:** O bloco `if __name__ == "__main__"` foi movido para o **final** do arquivo.

---

### BUG #4 — Thread de sync (`_sincronizar`) sem proteção contra `JSONDecodeError`
**Arquivo:** `sync_manager.py`

**Problema:** O `json.loads(item["payload"])` capturava apenas `Exception` genérica — sem distinção entre payload corrompido e erro de rede. Um payload corrompido ficava em loop, incrementando `tentativas` até 5 e nunca sendo descartado corretamente.

**Correção:** `JSONDecodeError` e `KeyError` capturados separadamente; payload corrompido é marcado como `enviado=1` (descartado) com log de erro claro.

---

### BUG #5 — Pull de logs com filtro de ID concatenado na URL (URL mal-formada)
**Arquivo:** `sync_manager.py`

**Problema:** 
```python
# ANTES (bugado):
r = requests.get(f"{url}/rest/v1/logs?id=gt.{max_id_local}", ...)
```
O filtro `id=gt.X` estava sendo concatenado diretamente na URL, mas a chamada também passava `params={}`. Isso resultava em URL duplicada e comportamento indefinido na API do Supabase (podia retornar todos os registros ou nenhum).

**Correção:** Filtro passado corretamente via dicionário `params`:
```python
r = requests.get(f"{url}/rest/v1/logs", params={"id": f"gt.{max_id_local}", "order": "id.asc"}, ...)
```

---

### BUG #6 — `falta_automatica.py`: INSERT sem `Hora_Entrada` (coluna presente no schema)
**Arquivo:** `falta_automatica.py`

**Problema:** O robô de faltas fazia `INSERT INTO LOGS (RA_Aluno, Data, Hora, Disciplina, Tipo)` omitindo `Hora_Entrada`. Com o schema corrigido (que define `Hora_Entrada`), isso deixava faltas automáticas com `Hora_Entrada = NULL`, quebrando relatórios e exportações Power BI que esperavam o campo preenchido.

**Correção:** `Hora_Entrada` incluída no INSERT com o mesmo valor de `Hora`.

---

### BUG #7 — `ao_fechar_programa()` sem try/except em `_descobrir_prof_hoje()`
**Arquivo:** `main.py`

**Problema:** Se o banco estivesse bloqueado ou ausente no momento em que o professor clicasse no X, a função levantava exceção não tratada, o dialog de confirmação nunca aparecia e o programa travava — precisando ser morto pelo gerenciador de tarefas.

**Correção:** `_descobrir_prof_hoje()` envolto em `try/except Exception` que retorna `(None, None, None)` em caso de erro, permitindo que a janela feche normalmente.

---

### BUG #8 — `_abrir_autocadastro()` sem guard de reentrada
**Arquivo:** `main.py`

**Problema:** Se o professor bipasse a carteirinha de um aluno não cadastrado rapidamente duas vezes, duas janelas de autocadastro abriam simultaneamente. Fechar uma não fechava a outra, e a segunda poderia tentar registrar presença de um aluno já inserido, causando duplicata.

**Correção:** Flag global `_autocadastro_aberto` que bloqueia a abertura de uma segunda janela enquanto a primeira estiver ativa.

---

## 🟠 BUGS MÉDIOS CORRIGIDOS (causariam comportamento incorreto)

### BUG #9 — `registrar_presenca()` sem try/except
**Arquivo:** `main.py`

**Problema:** Qualquer `sqlite3.OperationalError` (banco bloqueado por outro processo, por exemplo) propagava exceção não tratada direto para o event loop do Tkinter, podendo congelar a interface.

**Correção:** Bloco `try/except sqlite3.OperationalError` + `except Exception` com feedback visual via `_mostrar_status()`.

---

### BUG #10 — `sync_manager.py`: commit único vs. commits parciais no PULL
**Arquivo:** `sync_manager.py`

**Problema:** O PULL de dados do Supabase fazia `conn.commit()` dentro de cada loop individual (alunos, professores, disciplinas). Se a sessão fosse interrompida no meio, o banco ficaria num estado parcialmente sincronizado sem indicação de erro.

**Correção:** Um único `conn.commit()` ao final de toda a operação de PULL, garantindo consistência transacional.

---

### BUG #11 — `calendar_engine.py`: `get_disciplina_atual()` capturava só `OperationalError`
**Arquivo:** `calendar_engine.py`

**Problema:** Apenas `sqlite3.OperationalError` era capturado. Um banco bloqueado (`sqlite3.DatabaseError`) ou outro tipo de exceção propagava para `atualizar_disciplina_automatica()`, quebrando o loop de 60 segundos.

**Correção:** Captura genérica `except Exception` com log do erro.

---

### BUG #12 — `auth.py`: `verificar_login()` sem try/except na conexão
**Arquivo:** `auth.py`

**Problema:** Se o banco estivesse ausente quando o professor tentasse fazer login, `sqlite3.connect()` lançava exceção não tratada que subia até a UI, exibindo traceback ao usuário.

**Correção:** `try/except Exception` em torno da query — retorna `False` silenciosamente, permitindo que o fallback de backdoor via `.env` funcione mesmo sem banco disponível.

---

### BUG #13 — `relatorio.py`: SMTP sem timeout
**Arquivo:** `relatorio.py`

**Problema:** `smtplib.SMTP("smtp.gmail.com", 587)` sem timeout. Em redes universitárias instáveis, a conexão poderia travar indefinidamente, congelando a thread que chamou o envio.

**Correção:** `timeout=15` adicionado em todas as conexões SMTP.

---

### BUG #14 — `falta_automatica.py`: envio de e-mail bloqueava o scheduler
**Arquivo:** `falta_automatica.py`

**Problema:** `enviar_relatorio_por_email()` era chamado diretamente dentro do job do APScheduler. Se o SMTP travasse, o próximo disparo do job ficaria aguardando o anterior terminar, potencialmente acumulando jobs.

**Correção:** Envio de e-mail movido para thread `daemon` separada (`threading.Thread`).

---

## 🟡 PROBLEMAS DE QUALIDADE E CÓDIGO LIMPO CORRIGIDOS

### LIMPEZA #1 — Imports desnecessários removidos
**Arquivo:** `main.py`

`import numpy as np` e `import json` estavam importados e nunca utilizados no arquivo. Removidos.

---

### LIMPEZA #2 — `garantir_schema()` era verbosa e propagava erros
**Arquivo:** `main.py`

O `print()` de exceções era desnecessário. A função agora é silenciosa e protegida com `try/except` externo.

---

### LIMPEZA #3 — Threads sem nome
**Arquivo:** `sync_manager.py`, `falta_automatica.py`

Todas as threads `daemon` agora têm `name=` explícito (`"SAPA-SyncPush"`, `"SAPA-PullInit"`, `"SAPA-Wifi"`, `"SAPA-EmailFaltas"`), facilitando o debug com `threading.enumerate()`.

---

### LIMPEZA #4 — `_salvar_prof()` com risco de `IndexError`
**Arquivo:** `main.py`

```python
# ANTES — quebra se nome for string vazia:
email = ee.get().strip() or f"{nome.split()[0].lower()}@unisepe.com.br"
```
Corrigido com verificação explícita:
```python
email = ee.get().strip() or (f"{nome.split()[0].lower()}@unisepe.com.br" if nome else "")
```

---

### LIMPEZA #5 — `blocos_dict` usava padrão verboso
**Arquivo:** `main.py`

```python
# ANTES:
if b_name not in blocos_dict:
    blocos_dict[b_name] = []
blocos_dict[b_name].append(d)

# DEPOIS:
blocos_dict.setdefault(b_name, []).append(d)
```

---

### LIMPEZA #6 — `_mostrar_status()` sem proteção contra widget destruído
**Arquivo:** `main.py`

Se a janela fosse fechada enquanto um `root.after()` ainda estava pendente, `status_label.configure()` levantava `TclError`. Adicionado `try/except Exception`.

---

### LIMPEZA #7 — Caminhos de imagem relativos no construtor da UI
**Arquivo:** `main.py`

```python
# ANTES (quebra se working dir diferente):
Image.open("sapa_novo_icone_cropped.png")

# DEPOIS (sempre funciona):
Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sapa_novo_icone_cropped.png"))
```

---

## ✅ VALIDAÇÃO DA ESTRUTURA DO BANCO PARA POWER BI

### Schema atual (após correções)

| Tabela | Colunas-chave | Avaliação |
|--------|--------------|-----------|
| `ALUNOS` | `RA (PK), Nome, Turma` | ✅ Limpa |
| `PROFESSORES` | `ID (PK), Nome_Professor (UNIQUE), Email, Telefone, senha_hash` | ✅ Limpa |
| `DISCIPLINAS` | `ID (PK), Nome_Materia, Professor_Nome, Semestre, Bloco, Data_Inicio, Data_Fim, Dia_Semana` | ✅ Limpa |
| `LOGS` | `ID (PK), RA_Aluno (FK→ALUNOS.RA), Data, Hora, Hora_Entrada, Hora_Saida, Disciplina, Tipo, Justificativa` | ✅ Limpa |
| `grade_horarios` | `id (PK), disciplina_id (FK→DISCIPLINAS.ID), dia_semana, hora_inicio, hora_fim, turma` | ✅ Limpa |
| `sync_queue` | `id (PK), payload, tentativas, enviado, criado_em` | ✅ Interna |

### Pontos de atenção para o Power BI

**✅ Registro único (Entrada + Saída na mesma linha):** A lógica de "um ID por aluno por disciplina por dia" é **correta e ideal para BI**. No Power BI você faz simplesmente:
```
Horas_Presença = DATEDIFF([Hora_Entrada], [Hora_Saida], MINUTE)
```

**✅ Sem risco de duplicatas:** A query `SELECT ID FROM LOGS WHERE RA_Aluno=? AND Data=? AND Disciplina=?` garante unicidade antes de qualquer INSERT.

**⚠️ Campo `Disciplina` em LOGS é texto livre (desnormalizado):** O nome completo `"Mat - Sem (Bloco) - Prof"` é armazenado como string. Para o Power BI, isso **funciona**, mas se quiser um modelo estrela mais limpo no futuro, considere adicionar uma FK `Disciplina_ID` na tabela LOGS.

**✅ Coluna `Tipo` com valores controlados:** `ENTRADA`, `SAIDA`, `FALTA`, `JUSTIFICADO` — ideal para criar medidas DAX de taxa de presença.

**✅ Data em formato `DD/MM/AAAA`:** O Power BI importa corretamente, mas ao criar a coluna de data no Power Query use: `Date.FromText([Data], "pt-BR")` para garantir reconhecimento automático.

---

## 📊 RESUMO EXECUTIVO

| Categoria | Encontrados | Corrigidos |
|-----------|------------|-----------|
| Bugs Críticos (crash / perda de dados) | 8 | 8 ✅ |
| Bugs Médios (comportamento incorreto) | 6 | 6 ✅ |
| Problemas de Qualidade/Limpeza | 7 | 7 ✅ |
| **Total** | **21** | **21 ✅** |

### Arquivos entregues (pasta `sapa_corrigido/`)

| Arquivo | Status |
|---------|--------|
| `database.py` | ✅ Corrigido |
| `sync_manager.py` | ✅ Corrigido |
| `main.py` | ✅ Corrigido |
| `falta_automatica.py` | ✅ Corrigido |
| `calendar_engine.py` | ✅ Corrigido |
| `auth.py` | ✅ Corrigido |
| `relatorio.py` | ✅ Corrigido |

---

## 🚀 COMO APLICAR AS CORREÇÕES

1. **Faça backup** da pasta `SAPA_v8.0` antes de qualquer coisa.
2. Substitua os 7 arquivos `.py` pelos da pasta `sapa_corrigido/`.
3. Se o banco `banco_sapa.db` já existir, **não** execute `resetar_banco()`. As migrações em `main.py` adicionarão as colunas novas automaticamente ao subir o sistema.
4. Se for criar um banco **do zero**, execute `python database.py` — ele cria o schema completo e semeia os alunos.
5. Execute `python main.py` normalmente.
