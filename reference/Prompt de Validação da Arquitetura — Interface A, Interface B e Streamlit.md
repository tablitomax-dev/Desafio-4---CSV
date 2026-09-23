# Prompt de Validação da Arquitetura — Interface A, Interface B e Streamlit

## 1. Objetivo

Quero que você faça uma **auditoria técnica da implementação atual do projeto**, comparando o que está efetivamente implementado no código com a arquitetura-alvo descrita abaixo.

A arquitetura possui três grandes componentes:

1. **Interface A — Carga dos Dados / Pipeline**
2. **Interface B — Consulta / Agente de Dados**
3. **Interface do Usuário — Streamlit**

O objetivo desta análise é determinar:

- o que já está implementado;
- o que está parcialmente implementado;
- o que está diferente da arquitetura proposta;
- o que está faltando;
- quais componentes estão redundantes ou inadequados;
- quais riscos técnicos existem;
- e quais alterações devem ser realizadas para que a implementação corresponda à arquitetura.

**IMPORTANTE:** não faça alterações no código neste primeiro momento.

Primeiro faça somente a análise e apresente um diagnóstico técnico completo.

Não presuma que algo existe apenas porque existe um nome de classe, arquivo ou função. Verifique o fluxo real de execução e as dependências entre os componentes.

---

# 2. Arquitetura-alvo

## 2.1 Interface A — Carga dos Dados

O usuário envia um arquivo `.zip` contendo um ou mais arquivos CSV de notas fiscais.

O fluxo esperado é:

```text
Usuário
   ↓
Upload ZIP
   ↓
Extração segura do ZIP
   ↓
Classificação dos CSVs
   ├── Cabeçalho / notas fiscais
   └── Itens / produtos
   ↓
Carga em STAGING
   ↓
Construção da camada CURATED
   ↓
Normalização determinística
   ↓
Validação dos relacionamentos
   ↓
Avaliação da qualidade dos dados
   ↓
Criação de VIEWS seguras
   ↓
Publicação atômica
   ↓
DatasetContext
   ↓
Interface B disponibilizada
```

O `DatasetBuilder` deve ser responsável por orquestrar esse processo.

O `DatasetContext` deve representar a unidade única de estado do dataset publicado.

---

# 3. Perguntas — Interface A / DatasetBuilder

Analise o código atual e responda:

### 3.1 Upload

1. Onde está implementado o upload do arquivo ZIP?
2. Qual componente recebe o arquivo?
3. Qual é o fluxo desde o upload até o início do processamento?
4. Existe validação de extensão, tamanho e conteúdo do arquivo?
5. Existe proteção contra arquivos malformados?

### 3.2 Segurança do ZIP

6. Onde ocorre a extração do ZIP?
7. Existe proteção explícita contra **Zip Slip / Path Traversal**?
8. Como o sistema impede que um arquivo extraído escreva fora do diretório permitido?
9. Existem validações de nomes de arquivos e diretórios?
10. Arquivos inesperados dentro do ZIP são rejeitados, ignorados ou processados?

### 3.3 Classificação dos CSVs

11. Como o sistema identifica os arquivos de cabeçalho/notas?
12. Como identifica os arquivos de itens?
13. Essa classificação é baseada no nome do arquivo, cabeçalho das colunas ou conteúdo?
14. O que acontece quando um CSV não pode ser classificado?
15. O sistema suporta múltiplos CSVs do mesmo tipo?

### 3.4 Dicionário de dados

16. Onde o dicionário de dados é criado?
17. Ele é realmente gerado automaticamente a partir dos cabeçalhos?
18. Quais metadados são armazenados?

Para cada coluna, verificar se existe:

```text
nome
tipo
descrição
origem
tabela
exemplo
nullable
```

19. Como os tipos das colunas são inferidos?
20. A inferência é determinística?
21. O dicionário é versionado?
22. O dicionário utilizado pelo agente é exatamente o mesmo schema existente no dataset?

---

# 4. Staging

23. Onde os CSVs são carregados em STAGING?
24. Qual tecnologia está sendo utilizada?
25. O staging preserva os dados originais?
26. Existe identificação da origem de cada registro?
27. Existe controle de dataset/versionamento?
28. É possível reconstruir o dataset a partir do staging?

---

# 5. Camada CURATED

29. Onde a camada CURATED é construída?
30. Quais transformações são realizadas?
31. Existe normalização de nomes de colunas?
32. Existe normalização de tipos?
33. Existe normalização de datas?
34. Existe normalização de valores monetários?
35. Existe tratamento de valores nulos?
36. Existe normalização de strings?
37. As transformações são determinísticas?
38. Uma mesma entrada gera sempre o mesmo resultado?

Explique detalhadamente as regras de transformação.

---

# 6. Relacionamento entre notas e itens

A arquitetura prevê validação dos relacionamentos através da **chave de acesso da NF-e**.

39. Qual campo representa a chave de acesso?
40. Essa chave é validada?
41. Existe relacionamento entre cabeçalho e itens?
42. O sistema identifica itens sem cabeçalho?
43. O sistema identifica cabeçalhos sem itens?
44. Existem chaves duplicadas?
45. Como inconsistências de relacionamento são tratadas?
46. Essas inconsistências impedem a publicação ou apenas geram alertas?

---

# 7. Data Quality

47. Onde ocorre a avaliação de qualidade dos dados?

Verifique se existem validações para:

- campos obrigatórios;
- tipos;
- valores nulos;
- duplicidades;
- chaves;
- relacionamentos;
- datas inválidas;
- valores monetários;
- registros órfãos;
- inconsistências entre tabelas.

48. Existe um resultado estruturado da avaliação de qualidade?
49. Existe score de qualidade?
50. A qualidade interfere na publicação do dataset?
51. Os problemas de qualidade ficam registrados para auditoria?

---

# 8. Views seguras

52. Onde as VIEWS são criadas?
53. Quais tabelas ficam expostas ao agente?
54. O agente consulta diretamente STAGING ou CURATED?
55. Existe uma camada intermediária de views seguras?
56. As views escondem colunas que não devem ser expostas?
57. Existe separação entre tabelas internas e tabelas disponíveis para consulta?

A arquitetura esperada é:

```text
STAGING
   ↓
CURATED
   ↓
SECURE VIEWS
   ↓
AGENTE
```

Verifique se o código realmente respeita esse fluxo.

---

# 9. Publicação atômica

58. Como o dataset é publicado?
59. Existe algum mecanismo de publicação atômica?
60. O usuário/agente pode consultar um dataset parcialmente carregado?
61. O sistema utiliza versionamento?
62. Existe rollback em caso de falha?
63. O dataset antigo continua disponível até que o novo esteja completamente validado?

Explique o mecanismo atual.

---

# 10. DatasetContext

O `DatasetContext` deve ser a unidade única de estado da aplicação.

Verifique:

64. Onde o `DatasetContext` é criado?
65. Quais informações ele contém?

Esperamos algo conceitualmente semelhante a:

```text
dataset_id
version
schema
schema_hash
views
status
permissions
filters
metadata
quality
```

66. Quem cria o contexto?
67. Quem atualiza o contexto?
68. Quem consome o contexto?
69. O pipeline e o agente utilizam o mesmo contexto?
70. Existe risco de o pipeline consultar um dataset e o catálogo apontar para outro?
71. Como a consistência do contexto é garantida?

---

# 11. Interface B — Consulta

Agora audite o fluxo de consulta.

A arquitetura esperada é:

```text
Pergunta em linguagem natural
          ↓
Validação do DatasetContext
          ↓
intent_gate
          ↓
Grounding
(schema + histórico + filtros)
          ↓
Gate semântico via LLM
          ↓
Agente
          ↓
SQL Grounded
          ↓
Tools
          ↓
DuckDB READ-ONLY
          ↓
Resultado
          ↓
ChartSpec
          ↓
Validação
          ↓
Texto / Tabela / Gráfico
```

---

# 12. Entrada em linguagem natural

72. Onde existe o campo para o usuário fazer perguntas em linguagem natural?
73. Como a pergunta chega ao agente?
74. Existe histórico de conversa?
75. A pergunta atual é enviada junto com o histórico?
76. O agente conhece os filtros atualmente selecionados?
77. Existe alguma transformação ou pré-processamento da pergunta antes do agente?

---

# 13. Validação de contexto

78. Antes de executar uma consulta, o sistema verifica se o pipeline pertence ao mesmo dataset utilizado pelo catálogo?
79. Como essa verificação é realizada?
80. Existe `dataset_id`?
81. Existe `version`?
82. Existe `schema_hash`?
83. O que acontece quando existe inconsistência?

---

# 14. intent_gate

84. Onde está implementado o `intent_gate`?
85. Ele é executado antes do LLM?
86. Quais tipos de perguntas são bloqueados?
87. Ele bloqueia rapidamente solicitações claramente proibidas?
88. Existe risco de o usuário conseguir contornar esse gate?
89. O resultado do gate é registrado?

---

# 15. Grounding

90. Como o schema é enviado para o agente?
91. O agente recebe apenas tabelas e views permitidas?
92. O agente recebe descrições das colunas?
93. O dicionário de dados é utilizado no grounding?
94. O histórico da conversa faz parte do grounding?
95. Os filtros selecionados pelo usuário fazem parte do grounding?
96. Existe risco de o agente utilizar informações que não pertencem ao dataset atual?

---

# 16. Gate semântico via LLM

O gate deve classificar a intenção em:

```text
consulta
ambigua
maliciosa
fora_de_escopo
```

97. Onde essa classificação é realizada?
98. Qual LLM é utilizado?
99. Qual prompt é utilizado?
100. O resultado possui formato estruturado?
101. Como perguntas ambíguas são tratadas?
102. Como perguntas maliciosas são tratadas?
103. Como perguntas fora de escopo são tratadas?
104. O sistema solicita esclarecimento quando necessário?
105. Existe fallback caso o LLM falhe?

---

# 17. Geração de SQL

106. Onde o agente gera SQL?
107. O SQL é gerado exclusivamente com base no schema/grounding?
108. O agente pode inventar tabelas?
109. O agente pode inventar colunas?
110. Existe validação do SQL antes da execução?
111. O sistema permite somente `SELECT`?
112. Como são bloqueados:

```text
INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
ATTACH
COPY
EXPORT
```

113. Existem limites de execução?
114. Existe timeout?
115. Existe limite de quantidade de linhas retornadas?

---

# 18. Tools

Liste todas as tools disponíveis atualmente para o agente.

Compare com as seguintes tools esperadas:

```text
list_tables
describe_table
run_sql
sample_data
apply_filters
validate_chartspec
```

Para cada tool existente, informe:

- nome;
- localização;
- responsabilidade;
- parâmetros;
- retorno;
- permissões;
- quem pode chamá-la;
- riscos;
- se corresponde à arquitetura.

---

# 19. DuckDB

116. Onde o DuckDB é inicializado?
117. Como o agente acessa o DuckDB?
118. A conexão é realmente read-only?
119. Existe algum caminho para executar comandos de escrita?
120. Como o banco é persistido?
121. Como diferentes datasets são isolados?
122. Existe concorrência entre usuários/sessões?
123. Existe controle de lifecycle da conexão?

---

# 20. ChartSpec

A arquitetura prevê que respostas que possam ser representadas graficamente sejam convertidas em um `ChartSpec`.

124. Onde o ChartSpec é criado?
125. Qual é o schema do ChartSpec?
126. Existe validação antes da renderização?
127. O que acontece quando o ChartSpec é inválido?
128. O sistema degrada automaticamente para tabela?
129. Existe proteção contra gráficos inconsistentes com os dados?
130. A renderização é determinística?

---

# 21. Renderização da resposta

131. Como o sistema decide entre:

```text
texto
tabela
gráfico
```

132. Existe uma camada específica responsável pela renderização?
133. O mesmo resultado pode gerar diferentes representações?
134. Existe tratamento de erro amigável?
135. Como são exibidas mensagens de bloqueio, ambiguidade ou erro?

---

# 22. Interface Streamlit

Audite a interface do usuário.

Verifique a existência de:

### Filtros

136. Filtro de UF?
137. Filtro de natureza da operação?
138. Filtro de período?
139. Os filtros são realmente aplicados às consultas?
140. Os filtros são enviados para o contexto do agente?
141. As métricas também respeitam os filtros?

### Pergunta em linguagem natural

142. Existe campo de entrada para pergunta?
143. O campo envia a pergunta para o agente?
144. Existe indicação de processamento?
145. O usuário consegue fazer perguntas consecutivas?

### Histórico

146. O histórico da conversa é exibido?
147. O histórico pertence à sessão correta?
148. O histórico é enviado ao agente?
149. Existe mecanismo para limpar/iniciar uma nova conversa?

---

# 23. Métricas de faturamento

Identifique todas as métricas atualmente implementadas.

Para cada métrica informe:

```text
nome
fórmula
origem dos dados
SQL utilizado
filtros aplicados
componente responsável
```

Verifique especialmente:

- faturamento total;
- número de notas fiscais;
- ticket médio;
- número de clientes;
- outras métricas existentes.

Confirme se as métricas usam exatamente o mesmo dataset/contexto utilizado pelo agente.

---

# 24. Segurança

Faça uma auditoria específica de segurança.

Verifique:

1. Zip Slip
2. Path Traversal
3. SQL Injection
4. Prompt Injection
5. acesso indevido a datasets
6. acesso a tabelas não autorizadas
7. comandos DuckDB perigosos
8. DDL/DML
9. vazamento de schema
10. vazamento de dados
11. ausência de timeout
12. consultas excessivamente grandes
13. ausência de limites
14. isolamento entre sessões
15. isolamento entre datasets

Para cada risco encontrado, classifique:

```text
CRÍTICO
ALTO
MÉDIO
BAIXO
```

e explique o motivo.

---

# 25. Observabilidade e auditoria

Verifique se existe logging para:

- upload;
- processamento do dataset;
- erros de ingestão;
- qualidade dos dados;
- publicação;
- perguntas do usuário;
- classificação do intent;
- SQL gerado;
- tools utilizadas;
- tempo de execução;
- resultado;
- erros;
- bloqueios de segurança.

Indique quais informações devem ser adicionadas caso não existam.

---

# 26. Testes

Verifique a existência de testes para:

### Pipeline

- ZIP válido;
- ZIP inválido;
- Zip Slip;
- CSV inválido;
- classificação de arquivos;
- schema;
- staging;
- curated;
- relacionamentos;
- qualidade;
- publicação atômica.

### Agente

- pergunta válida;
- pergunta ambígua;
- pergunta maliciosa;
- pergunta fora de escopo;
- prompt injection;
- SQL inválido;
- SQL perigoso;
- tabela inexistente;
- coluna inexistente;
- timeout;
- resultado vazio.

### Interface

- upload;
- filtros;
- pergunta;
- histórico;
- métricas;
- gráfico;
- fallback para tabela;
- mensagens de erro.

Informe quais desses testes existem e quais estão faltando.

---

# 27. Matriz de conformidade

Ao final da análise, crie uma matriz:

| Componente | Arquitetura esperada | Implementação atual | Status | Evidência | Gap |
|---|---|---|---|---|---|
| Upload ZIP | Sim | ? | ✅/⚠️/❌ | arquivo/função | descrição |
| Anti Zip Slip | Sim | ? | | | |
| Classificação CSV | Sim | ? | | | |
| Staging | Sim | ? | | | |
| Curated | Sim | ? | | | |
| Normalização | Sim | ? | | | |
| Relacionamentos | Sim | ? | | | |
| Data Quality | Sim | ? | | | |
| Secure Views | Sim | ? | | | |
| Publicação atômica | Sim | ? | | | |
| DatasetContext | Sim | ? | | | |
| intent_gate | Sim | ? | | | |
| Grounding | Sim | ? | | | |
| Gate semântico | Sim | ? | | | |
| SQL Grounded | Sim | ? | | | |
| Tools | Sim | ? | | | |
| DuckDB read-only | Sim | ? | | | |
| ChartSpec | Sim | ? | | | |
| Streamlit | Sim | ? | | | |
| Filtros | Sim | ? | | | |
| Pergunta em linguagem natural | Sim | ? | | | |
| Histórico | Sim | ? | | | |
| Métricas | Sim | ? | | | |
| Segurança | Sim | ? | | | |
| Testes | Sim | ? | | | |

Use:

- ✅ **Implementado**
- ⚠️ **Parcialmente implementado**
- ❌ **Não implementado**
- 🔍 **Não foi possível confirmar**

---

# 28. Análise de arquitetura

Depois da matriz, responda objetivamente:

### A. O desenho arquitetural corresponde ao código atual?

Responda:

```text
SIM
PARCIALMENTE
NÃO
```

Explique.

### B. Quais são os 10 maiores gaps?

Ordene por prioridade.

### C. Quais componentes do código atual não aparecem na arquitetura?

Explique se devem:

- permanecer;
- ser incorporados ao desenho;
- ser removidos;
- ou ser refatorados.

### D. Quais componentes aparecem no desenho, mas não existem no código?

Liste todos.

### E. Existem responsabilidades duplicadas?

Identifique classes, módulos ou componentes que estejam fazendo a mesma coisa.

### F. Existem responsabilidades que deveriam estar separadas?

Identifique possíveis problemas de acoplamento.

---

# 29. Fluxo real versus fluxo desejado

Apresente dois fluxos.

## Fluxo REAL

Mostre exatamente como o sistema funciona hoje:

```text
Componente A
   ↓
Componente B
   ↓
Componente C
   ↓
...
```

Não simplifique.

## Fluxo DESEJADO

Mostre como deveria funcionar para corresponder à arquitetura:

```text
Upload
   ↓
DatasetBuilder
   ↓
Staging
   ↓
Curated
   ↓
Validation
   ↓
Secure Views
   ↓
Atomic Publish
   ↓
DatasetContext
   ↓
Agent
   ↓
DuckDB
   ↓
Response
```

Depois destaque as diferenças.

---

# 30. Proposta de correção

Somente depois de concluir toda a auditoria, apresente uma proposta de implementação.

Divida em:

## Fase 1 — Correções críticas

Segurança e integridade.

## Fase 2 — Pipeline

DatasetBuilder, staging, curated, validação e publicação.

## Fase 3 — DatasetContext

Estado, versionamento e consistência.

## Fase 4 — Agente

Intent gate, grounding, LLM gate, SQL, tools e DuckDB.

## Fase 5 — Interface

Streamlit, filtros, perguntas em linguagem natural, histórico e métricas.

## Fase 6 — Visualização

ChartSpec, validação e fallback.

## Fase 7 — Testes

Unitários, integração, segurança e end-to-end.

---

# 31. Regras importantes para esta análise

Siga estas regras:

1. **Não altere o código ainda.**
2. Não diga que algo está implementado apenas porque existe uma classe ou função com o nome esperado.
3. Rastreie o fluxo real de execução.
4. Sempre que possível, cite:
   - arquivo;
   - classe;
   - função;
   - linha aproximada;
   - dependência.
5. Diferencie claramente:
   - implementado;
   - parcialmente implementado;
   - apenas planejado;
   - não implementado.
6. Identifique contradições entre módulos.
7. Identifique responsabilidades duplicadas.
8. Identifique componentes que estão sendo utilizados de maneira diferente da arquitetura.
9. Não proponha refatoração antes de concluir a auditoria.
10. Não faça alterações no código nesta etapa.

---

# 32. Resultado esperado

Ao terminar, entregue exatamente nesta ordem:

1. **Resumo executivo**
2. **Fluxo real identificado**
3. **Fluxo esperado**
4. **Matriz de conformidade**
5. **Gaps encontrados**
6. **Riscos de segurança**
7. **Problemas de arquitetura**
8. **Componentes faltantes**
9. **Componentes redundantes**
10. **Testes existentes**
11. **Testes faltantes**
12. **Top 10 prioridades de correção**
13. **Plano de implementação por fases**
14. **Conclusão: quanto a implementação atual corresponde ao desenho arquitetural**

Por fim, dê uma nota de aderência arquitetural de:

```text
0% a 100%
```

e explique como chegou a essa nota.

**Não faça nenhuma alteração no código até que eu analise e aprove esse diagnóstico.**