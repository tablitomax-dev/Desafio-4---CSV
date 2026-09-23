# Aprendizados — Fiscal AI (Desafio 4 I2A2)

Lições registradas durante o desenvolvimento e a bateria de 72 perguntas com
LLM real. Servem de rationale para decisões de arquitetura e para futuras
iterações.

## 1. Vazio fabricado (causa raiz de "Não encontrei dados" indevidos)

O modelo primário às vezes devolve tabela vazia (ou texto "sem dados") SEM
chamar nenhuma tool de dados. Nenhum guard anterior detectava: `_resposta_inutil`
só avalia texto; a anti-alucinação só avalia texto com números; o pipeline
converte tabela vazia em "Não encontrei dados..." mascara o problema.

**Solução**: guard determinístico `_resposta_vazia_fabricada` — se a resposta
afirma ausência de dados (tabela/gráfico vazio OU texto com frases "sem dados")
e nenhuma tool rodou nesta pergunta (`ultimo_resultado` e `ultimo_resumo` ambos
None), tenta o fallback. O vazio legítimo é preservado: quando uma tool RODOU
(mesmo devolvendo 0 linhas), `consultar` sempre seta `ultimo_resultado`.

**Métrica**: `fallback_vazio_fabricado` para observabilidade.

## 2. Fallback de modelo é a rede de segurança central

`AgenteConsulta` e `SemanticGate` usam primário (DeepSeek V4 Flash) + fallback
(gpt-5.6-luna-pro) via OpenRouter. O fallback é acionado por 4 condições:
falha de tool (UnexpectedModelBehavior), resposta inútil, números não
confiáveis (anti-alucinação) e vazio fabricado. `temperature=0.0` via
ModelSettings.

## 3. Anti-alucinação de números

Todo número citado na resposta deve vir de uma tool chamada NESTA pergunta.
`_texto_com_numero_nao_confiavel` compara números no texto contra os valores
retornados pelas tools; números sem origem confiável disparam fallback.

## 4. Não-determinismo residual do LLM

A bateria de 72 (12 sessões × 6 perguntas encadeadas) mostrou que falhas são
intermitentes: perguntas que falharam na bateria funcionaram isoladamente no
diagnóstico. O fallback reduz mas não elimina falhas. Casos residuais
documentados: S2.4/S2.6 (SQL com filtro errado retornando 0 linhas — vazio
pós-tool que o guard não cobre), S8.3/S9.2 (placeholders literais "Resposta
com os números."/"Teste" que `_resposta_inutil` não detecta).

## 5. Estado da sessão pertence à pergunta atual

`limpar_ultimo_resultado()` antes de cada pergunta evita que o fallback
reutilize dados de uma pergunta anterior (que poderiam ser de outra consulta).

## 6. Guardrails de granularidade

`validar_granularidade` bloqueia SUM/AVG de valor do cabeçalho após JOIN com
itens (evita duplicação) e COUNT(*) sem GROUP BY. `validar_sql` garante
read-only (rejeita escrita, DDL/DML e múltiplas instruções).

## 7. Catálogo expõe schema, não nomes reais de tabela

O catálogo expõe nomes canônicos (`curated.*`), mas o banco real usa
`nfs_cabecalho`/`nfs_itens`. Há divergência entre catálogo e banco — o
grounding do SQL precisa resolver essa diferença (qualificação via catalog).

## 8. Diagnóstico instrumentado > suposição

`Temp/diag_falhas.py` e `Temp/diag_falhas2.py` usam logging de SQL das tools +
delta de métricas por pergunta para identificar quando nenhuma tool rodou.
Essa abordagem provou a causa raiz do vazio fabricado com evidência, em vez de
palpite.