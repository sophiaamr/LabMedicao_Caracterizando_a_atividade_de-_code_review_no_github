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
| IH02 | Quanto mais tempo de revisão, mais crítico será o feedback e menos chance de ser aprovado de primeira. Quanto menos tempo, mais rápido é a aprovação. |
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

Dificuldades e desafios estiveram presentes em todas as etapas do trabalho. A coleta de dados foi especialmente desafiadora: foi preciso iterar diversas vezes até definir uma estratégia de paralelização das requisições que não ultrapassasse o rate limit da API. Mesmo reduzindo o número de PRs analisados, a geração do dataset demandou mais de 48 horas de execução.
Na análise dos dados, a complexidade também foi alta. Enfrentei dificuldades para selecionar as abordagens estatísticas mais adequadas e para implementar os procedimentos analíticos, ainda que a automação de gráficos tenha ajudado na exploração inicial.

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

## 6. Resultados & Discussões

#### RQ1 - 

<p align="center">
  <img src="GraficoRQ1.jpeg" width="480" alt="Descrição">
</p>


O tamanho por si só é um preditor fraco de feedback; alguns PRs grandes recebem muita atenção, mas a maioria (pequenos ou grandes) recebe pouco. Em termos práticos, preferir PRs menores e focados (ou quebrar PRs muito amplos) tende a favorecer revisões mais efetivas e distribuídas.

A hipotese foi parcialmente refutada, pois os dados de indicam correlação positiva fraca entre tamanho do PR e feedback total: PRs maiores têm maior chance de gerar discussões mais extensas, porém a maioria (inclusive muitos PRs grandes) recebe pouco feedback.

#### RQ2 - 

<p align="center">
  <img src="rq02.PNG" width="500" alt="Descrição">
</p>

<p align="center">
  <img src="GraficoRQ2.jpeg" width="480" alt="Descrição">
</p>

Neste gráfico, vemos que o engajamento com PRs segue uma curva em U invertido. O pico de feedback ocorre quando a análise leva de 1 a 7 dias: é quando temos mais comentários e mais participantes. PRs muito rápidos tendem a receber menos discussão, possivelmente por serem triviais, e PRs que se arrastam por mais de um mês perdem tração

Disussão: PRs que são resolvidos muito rapidamente (em menos de 1 dia) tendem a ser mudanças simples que genuinamente não requerem discussão extensiva. No entanto, é importante que as equipes verifiquem se não estão negligenciando revisões necessárias em favor da velocidade. Por outro lado, PRs que ultrapassam 1 mês de análise entram em uma zona crítica onde o feedback praticamente estagna, caindo para níveis inferiores aos dos PRs triviais

#### RQ3 - 

#### RQ4 - 

#### RQ5 - 

<p align="center">
  <img src="rq05.PNG" width="500" alt="Descrição">
</p>

O gráfico mostra que o conjunto é fortemente concentrado em PRs “Muito Pequenos” (≈45%), seguidos de Pequenos (≈24%); Médios e Grandes somam ~16% cada. Isso significa que, em termos de volume bruto de revisões, os menores inevitavelmente dominam o total simplesmente porque são muito mais numerosos.
A hipotese é refutada, pois há apenas risco ligeiramente maior de discussões longas em PRs grandes, não um crescimento consistente de revisões conforme o tamanho aumenta.

#### RQ6 - 

<p align="center">
  <img src="GraficoRQ6.jpeg" width="600" alt="Descrição">
</p>

Mais tempo não implica mais revisões. O volume de revisões tende a ser maior quando o PR é analisado entre 1 dia e 1 mês (sobretudo 1–7 dias), enquanto PRs muito rápidos e muito lentos recebem menos ciclos de revisão.
Ou seja, hipotese foi refutada

#### RQ7 - 

#### RQ8 - 




---

## 7. Conclusão

---

## 6. Referências

---
