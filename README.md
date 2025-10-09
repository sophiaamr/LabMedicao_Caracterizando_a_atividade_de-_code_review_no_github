# 📝 Relatório Técnico de Laboratório

## 1. Informações do grupo
- **🎓 Curso:** Engenharia de Software
- **📘 Disciplina:** Laboratório de Experimentação de Software
- **🗓 Período:** 6° Período
- **👨‍🏫 Professor(a):** Prof. Wesley Dias Maciel
- **👥 Membros do Grupo:** Sophia Mendes, Thiago Andrade

---

## 2. Introdução

Este trabalho teve como objetivo caracterizar a atividade de code review em repositórios populares do GitHub, buscando compreender quais fatores influenciam o resultado final de um PR. Para isso, foram coletados dados de repositórios amplamente utilizados na plataforma, considerando apenas PRs revisados manualmente, com pelo menos uma revisão e tempo mínimo de análise de uma hora, para excluir revisões automáticas realizadas por bots ou pipelines de CI/CD.

### 2.1. Questões de Pesquisa (Research Questions – RQs)
**Questões de Pesquisa - Research Questions (RQs):**

| RQ   | Pergunta |
|------|----------|
| RQ01 | Qual a relação entre o tamanho dos PRs e o feedback final das revisões? |
| RQ02 | Qual a relação entre o tempo de análise dos PRs e o feedback final das revisões? |
| RQ03 | Qual a relação entre a descrição dos PRs e o feedback final das revisões? |
| RQ04 | Qual a relação entre as interações nos PRs e o feedback final das revisões? |
| RQ05 | Qual a relação entre o tamanho dos PRs e o número de revisões realizadas? |
| RQ06 | Qual a relação entre o tempo de análise dos PRs e o número de revisões realizadas? |
| RQ07 | Qual a relação entre a descrição dos PRs e o número de revisões realizadas? |
| RQ08 | Qual a relação entre as interações nos PRs e o número de revisões realizadas? |

### 2.2. Hipóteses Informais (Informal Hypotheses – IH)

| IH   | Descrição |
|------|-----------|
| IH01 | PR's maiores tendem a receber feedbacks mais criticos|
| IH02 | Quanto mais tempo de revisão, mais crítico será o feedback e menos chance de ser aprovado de priemeira. Quanto menos tempo, mais rápido é a aprovação. |
| IH03 | PR's com descrições mais detalhadas tem mais chance aprovações|
| IH04 | Desenvolvedores com mais experiencia tem mais chance dos PR's serem aceitos |
| IH05 | Quanto maior o PR , maior o número de revisões/rodadas necessárias até a aprovação. |
| IH06 | PRs com maior tempo de análise costumam exigir mais ciclos de revisão antes da aprovação. |
| IH07 | PR's com descrições mais detalhadas precisam de menos revisões |
| IH08 | PR's com mais discussões mais precisam de menos revisões |

---

## 3. Metodologia

Para coletar os dados da análise, foi utilizada a API REST do GitHub, que possibilitou acessar de forma organizada as informações dos repositórios e pull requests (PRs). Foram selecionados os 200 repositórios mais populares da plataforma, buscando representar projetos amplamente usados pela comunidade open source.

De cada repositório, foram extraídas as principais métricas e informações dos PRs, como número de arquivos alterados, linhas adicionadas e removidas, tempo de análise, quantidade de revisões, descrição e interações entre os participantes. Todos os dados foram reunidos em um arquivo CSV chamado Dataset, utilizado depois nas etapas de análise e visualização dos resultados.

A coleta foi automatizada com scripts em Python, utilizando ThreadPoolExecutor para realizar várias requisições ao mesmo tempo e tornar o processo mais rápido e eficiente.

---
## 4. Dificuldades
---

### 5 Métricas

#### 📊 Métricas de Laboratório - Lab Metrics (LM)
| Código | Métrica | Descrição |
|--------|---------|-----------|
| LM01 | Tamanho | número de arquivos; total de linhas adicionadas e removidas |
| LM02 | Tempo de Análise | intervalo entre a criação do PR e a última atividade (fechamento ou merge). |
| LM03 | Descrição | número de caracteres do corpo de descrição do PR (na versão markdown) |
| LM04 | Interações: | número de participantes; número de comentários. |

---

## 6. Resultados

Apresente os resultados obtidos, com tabelas e gráficos.

---

### 6.1 Gráficos

Para criar visualizações das métricas, recomenda-se utilizar como referência o projeto **Seaborn Samples**:  
- 🔗 Repositório: [Projeto Seaborn Samples](https://github.com/joaopauloaramuni/laboratorio-de-experimentacao-de-software/tree/main/PROJETOS/Projeto%20Seaborn%20Samples)

- **📊 Histograma**: `grafico_histograma.png` → distribuição de idade, PRs aceitas ou estrelas.  
- **📈 Boxplot**: `grafico_boxplot.png` → dispersão de métricas como forks, issues fechadas ou LOC.  
- **📊 Gráfico de Barras**: `grafico_barras.png` → comparação de métricas entre linguagens.  
- **🥧 Gráfico de Pizza**: `grafico_pizza.png` → percentual de repositórios por linguagem.  
- **📈 Gráfico de Linha**: `grafico_linha.png` → evolução de releases ou PRs ao longo do tempo.  
- **🔹 Scatterplot / Dispersão**: `grafico_dispersao.png` → relação entre estrelas e forks.  
- **🌡 Heatmap**: `grafico_heatmap.png` → correlação entre métricas (idade, PRs, stars, forks, issues).  
- **🔗 Pairplot**: `grafico_pairplot.png` → análise de múltiplas métricas simultaneamente.  
- **🎻 Violin Plot**: `grafico_violin.png` → distribuição detalhada de métricas por subgrupo.  
- **📊 Barras Empilhadas**: `grafico_barras_empilhadas.png` → comparação de categorias dentro de métricas.

> 💡 Dica: combine tabelas e gráficos para facilitar a interpretação e evidenciar padrões nos dados.

---

### 6.1 Discussão dos resultados

Nesta seção, compare os resultados obtidos com as hipóteses informais levantadas pelo grupo no início do experimento.

- **✅ Confirmação ou refutação das hipóteses**: identifique quais hipóteses foram confirmadas pelos dados e quais foram refutadas.  
- **❌ Explicações para resultados divergentes**: caso algum resultado seja diferente do esperado, tente levantar possíveis causas ou fatores que possam ter influenciado.  
- **🔍 Padrões e insights interessantes**: destaque tendências ou comportamentos relevantes observados nos dados que não haviam sido previstos nas hipóteses.  
- **📊 Comparação por subgrupos (opcional)**: se houver segmentação dos dados (ex.: por linguagem de programação, tamanho do repositório), discuta como os resultados se comportam em cada grupo.  

> Relacione sempre os pontos observados com as hipóteses informais definidas na introdução, fortalecendo a análise crítica do experimento.

---

## 7. Conclusão

---

## 6. Referências

---
