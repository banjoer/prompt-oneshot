# GAME BRIEF FINAL REVISTO — Tower Defense Educativo (Single-Player, 6 anos)

> Integração integral de `game-brief.txt` (brief original) + `game-brief-adenda.txt` (adenda, secções 20–28, FR-13–FR-22).
> Todo o conteúdo em português (pt-PT). Nenhum detalhe foi eliminado: decisões, ideias em exploração, pontos em aberto, vetores de otimização, requisitos funcionais, temas, mecânicas, boss baleia, unidades, espadas/escudos, narrativa e síntese para o próximo agente foram preservados.

## Nota sobre a numeração (abordagem adotada)

- O brief original estava numerado de **1 a 11**.
- A adenda estava numerada de **20 a 28** (secções) e **FR-13 a FR-22** (requisitos funcionais).
- **Abordagem adotada: renumeração contínua.** As secções 20–28 da adenda foram renumeradas para **12–20**, mantendo o conteúdo e os títulos inalterados. O corpo do texto preserva a ordem lógica: base original primeiro (1–11), expansões da adenda depois (12–20).
- Tabela de correspondência:

| Numeração neste documento | Origem |
|---|---|
| 1–11 | `game-brief.txt`, secções 1–11 (numeração original preservada) |
| 12 | Adenda secção 20 — Progressão entre níveis e mudança de cenários |
| 13 | Adenda secção 21 — Novos temas de níveis |
| 14 | Adenda secção 22 — A baleia como boss |
| 15 | Adenda secção 23 — Unidades, classes e simulação automática |
| 16 | Adenda secção 24 — Espadas, escudos e recompensas de nível |
| 17 | Adenda secção 25 — Notas de narrativa e transição entre mundos |
| 18 | Adenda secção 26 — Requisitos funcionais (consolidados FR-01–FR-22; ver nota própria na secção 18) |
| 19 | Adenda secção 27 — Decisões pendentes (consolidadas com as do original) |
| 20 | Adenda secção 28 — Síntese atualizada para o próximo agente (expandida) |

- Os requisitos **FR-13–FR-22 conservam os seus identificadores originais** da adenda. Os requisitos **FR-01–FR-12 não existiam com essa numeração no original** — foram **reconstruídos a partir das funcionalidades mínimas e mecânicas descritas no original** (§§ 2, 6, 7, 8, 9, 11) e estão assinalados como tal na secção 18, sujeitos a confirmação.
- Onde o texto original terminava a meio de uma frase (§ 11), o corte foi preservado e assinalado com `[texto original interrompido aqui]`.

## Convenção de estado

Para manter a separação exigida pelo brief entre decidido, em exploração e por validar, cada bloco relevante termina com uma etiqueta:

- **[DECIDIDO]** — ponto fechado / diretriz assumida pelo conceito.
- **[EM EXPLORAÇÃO]** — ideia proposta (pela criança ou como hipótese de design do pai) ainda sem decisão.
- **[POR VALIDAR]** — hipótese que tem de ser testada em protótipo antes de se tornar requisito.

Quando o original ou a adenda já indicavam explicitamente o estado, esse estado foi mantido. Quando o estado é inferido, a etiqueta reflete a formulação original ("hipótese", "possibilidade", "ainda não está decidido", "precisa de ser explorado", etc.).

## Índice

1. [Resumo executivo](#1-resumo-executivo)
2. [Conceito central do jogo](#2-conceito-central-do-jogo)
3. [Público-alvo e princípios de design](#3-público-alvo-e-princípios-de-design)
4. [Direção artística e identidade visual](#4-direção-artística-e-identidade-visual)
5. [Temas, cenários e níveis (base original)](#5-temas-cenários-e-níveis-base-original)
6. [Loop principal de jogabilidade](#6-loop-principal-de-jogabilidade)
7. [Mecânica educativa: desafios que proporcionam impulsos](#7-mecânica-educativa-desafios-que-proporcionam-impulsos)
8. [Dificuldade dinâmica e momentos de intervenção educativa](#8-dificuldade-dinâmica-e-momentos-de-intervenção-educativa)
9. [Recompensas e progressão](#9-recompensas-e-progressão)
10. [Vetores de otimização do produto](#10-vetores-de-otimização-do-produto)
11. [Âmbito sugerido para o primeiro protótipo](#11-âmbito-sugerido-para-o-primeiro-protótipo)
12. [Progressão entre níveis e mudança de cenários](#12-progressão-entre-níveis-e-mudança-de-cenários)
13. [Catálogo consolidado de temas de níveis](#13-catálogo-consolidado-de-temas-de-níveis)
14. [A baleia como boss](#14-a-baleia-como-boss)
15. [Unidades, classes e simulação automática](#15-unidades-classes-e-simulação-automática)
16. [Espadas, escudos e recompensas de nível](#16-espadas-escudos-e-recompensas-de-nível)
17. [Notas de narrativa e transição entre mundos](#17-notas-de-narrativa-e-transição-entre-mundos)
18. [Requisitos funcionais consolidados (FR-01–FR-22)](#18-requisitos-funcionais-consolidados-fr-01fr-22)
19. [Decisões pendentes consolidadas](#19-decisões-pendentes-consolidadas)
20. [Síntese para o próximo agente](#20-síntese-para-o-próximo-agente)

---

## 1. Resumo executivo

A ideia é criar um jogo single-player para uma criança de 6 anos, no primeiro ano de escolaridade, que combina mecânicas de Tower Defense com a sensação de competição e progressão de Capture the Flag. **[DECIDIDO]**

O jogo deverá ser divertido, visualmente apelativo e suficientemente simples para uma criança desta idade compreender. Ao mesmo tempo, deverá incorporar desafios educativos que influenciem diretamente o desenrolar da partida. **[DECIDIDO — diretriz]**

A ideia diferenciadora é que a aprendizagem não seja uma atividade separada do jogo. Em vez disso, resolver pequenos desafios educativos permite obter vantagens concretas dentro do jogo, como reforçar defesas, ganhar velocidade, ultrapassar o adversário ou conquistar a taça. **[DECIDIDO — princípio diferenciador]**

O resultado pretendido não é apenas um Tower Defense com elementos educativos. É um jogo em que a criança sente que está a competir, a tomar decisões e a tentar conquistar um prémio, enquanto pratica competências adequadas à sua idade. **[DECIDIDO — intenção de experiência]**

O conceito deve ser suficientemente flexível para suportar diferentes temas visuais, personagens, cenários e recompensas, mantendo uma base comum de mecânicas. **[DECIDIDO — diretriz de arquitetura]**

### 1.1. Visão do produto

Criar um jogo de estratégia acessível, com personagens adoráveis, objetivos claros, progressão visual e desafios educativos integrados na jogabilidade. **[DECIDIDO]**

A criança deverá conseguir:

* Compreender rapidamente o objetivo de cada partida.
* Perceber se está a ganhar, a perder ou se está perto de conseguir vencer.
* Tomar decisões simples que influenciem o resultado.
* Resolver desafios educativos para obter vantagens no jogo.
* Sentir que o seu conhecimento e as suas decisões contribuem para a vitória.
* Receber recompensas concretas e visualmente apelativas.

### 1.2. Princípio fundamental

A aprendizagem deve ser uma mecânica de jogo, não uma interrupção da experiência de jogo. **[DECIDIDO]**

Os desafios educativos devem ter consequências percetíveis no mundo do jogo. Uma resposta correta deverá proporcionar uma vantagem que a criança consiga compreender, observar e associar à sua ação. **[DECIDIDO]**

---

## 2. Conceito central do jogo

### 2.1. Género e mecânicas

O jogo combina três conceitos: **[DECIDIDO]**

| Conceito | Papel no jogo |
|---|---|
| Tower Defense | Base estratégica: defender uma posição, gerir unidades e resistir a ataques. |
| Capture the Flag | Objetivo competitivo: avançar para conquistar o objetivo do adversário antes que este consiga vencer. |
| Educational Game | Camada educativa: resolver desafios para obter vantagens estratégicas. |

A referência a Capture the Flag descreve sobretudo a experiência e o objetivo competitivo, não necessariamente uma implementação literal das regras tradicionais desse género. **[DECIDIDO — clarificação]**

O jogo deverá ser single-player. A competição pode ser simulada através de um adversário controlado pelo jogo, sem necessidade de multiplayer. **[DECIDIDO]**

### 2.2. A experiência pretendida

A criança observa uma batalha entre duas forças.

Tem de proteger a sua posição, ultrapassar as defesas adversárias e aproximar-se de um objetivo final, como uma grande taça.

Ao longo da partida, a situação evolui. A criança consegue perceber visualmente quem está em vantagem e se a vitória está próxima.

Quando precisa de ajuda para inverter uma situação desfavorável, ou quando está prestes a conquistar o prémio, podem surgir desafios educativos que permitem obter um impulso.

A partida termina quando uma das forças consegue atingir o objetivo definido para o nível.

A recompensa pode ser uma taça, um objeto especial ou outra conquista adequada ao tema.

> **Nota de design:** ainda não está decidido se o jogo decorrerá em ondas discretas, com pausas entre elas, ou como uma simulação contínua. Esta decisão deve permanecer em aberto durante a fase inicial de prototipagem. **[POR VALIDAR]**

---

## 3. Público-alvo e princípios de design

### 3.1. Público-alvo inicial **[DECIDIDO]**

* Crianças de aproximadamente 6 anos.
* Crianças no primeiro ano de escolaridade.
* Jogadores com capacidade limitada para interpretar interfaces complexas e regras estratégicas abstratas.
* Jogadores que beneficiam de feedback visual imediato e objetivos concretos.

O jogo será inicialmente concebido para uma criança, embora possa posteriormente ser adaptado a outras idades.

### 3.2. Princípios de design **[DECIDIDO — como diretrizes]**

**A. Clareza**

A criança deve compreender o que está a acontecer sem precisar de ler instruções longas.

**B. Feedback visual**

A vantagem de cada lado deve ser visível através das posições das unidades, do progresso no cenário e da proximidade ao objetivo.

**C. Recompensas concretas**

As vitórias devem produzir resultados que a criança compreenda: ganhar uma taça, desbloquear um elemento ou escolher uma recompensa.

**D. Aprendizagem integrada**

As perguntas educativas devem ter consequências na batalha, evitando a sensação de que a criança foi retirada do jogo para fazer um exercício escolar.

**E. Autonomia**

A criança deverá ter oportunidades para decidir quando utilizar determinados impulsos, em vez de depender exclusivamente de intervenções automáticas do jogo.

**F. Dificuldade adaptável**

O jogo deve poder criar situações desafiantes sem tornar a experiência frustrante ou exigir que a criança compreenda sistemas estratégicos complexos.

**G. Flexibilidade temática**

Os temas visuais e narrativos podem variar sem obrigar a reconstruir toda a lógica do jogo.

---

## 4. Direção artística e identidade visual

Foram identificadas duas referências visuais principais, que não precisam de ser mutuamente exclusivas. **[DECIDIDO]**

### 4.1. Direção A — Personagens fofas e coloridas **[EM EXPLORAÇÃO]**

Referências de estilo: a simplicidade visual e o carácter amigável de séries infantis como Bluey e Peppa Pig.

Características pretendidas:

* Personagens expressivas e simpáticas.
* Formas arredondadas.
* Cores vivas.
* Animações fáceis de interpretar.
* Cenários acolhedores e imaginativos.
* Conflitos apresentados de forma lúdica, sem violência gráfica.

Estas referências servem apenas para comunicar a direção artística pretendida, não para reproduzir personagens, recursos gráficos ou propriedade intelectual de terceiros.

### 4.2. Direção B — Construção estilizada **[EM EXPLORAÇÃO]**

Referências de estilo: a linguagem visual de LEGO e Minecraft.

Características pretendidas:

* Formas geométricas simples.
* Objetos que parecem construídos com blocos.
* Cenários modulares.
* Elementos fáceis de reconhecer.
* Potencial para construir, modificar ou expandir estruturas.
* Identidade visual simples e legível.

Também aqui se pretende inspiração estilística, não uma cópia dos jogos ou das marcas de referência.

### 4.3. Decisão de arquitetura visual

Uma hipótese importante é manter a mecânica central independente da direção artística. **[EM EXPLORAÇÃO — hipótese de arquitetura]**

Assim, o mesmo sistema de jogo poderá suportar:

* Uma versão com personagens fofas e cenários coloridos.
* Uma versão com blocos de construção e estruturas geométricas.
* Outros temas futuros, se o conceito justificar essa expansão.

Ainda não está decidido se estas direções serão apresentadas como temas dentro do mesmo jogo ou como jogos distintos que partilham a mesma base técnica. **[POR VALIDAR]**

Recomendação inicial: prototipar primeiro uma única direção artística. A segunda deve ser acrescentada quando a mecânica central estiver suficientemente validada. **[DECIDIDO — recomendação de faseamento]**

---

## 5. Temas, cenários e níveis (base original)

A conversa sugere que cada nível possa introduzir um tema diferente, mantendo as regras fundamentais do jogo. **[EM EXPLORAÇÃO]**

Os temas podem alterar o cenário, as personagens, as estruturas, o objetivo visual e as recompensas, sem necessariamente alterar a mecânica central. **[DECIDIDO — princípio]**

### 5.1. Tema A — Castelos e cavaleiros **[DECIDIDO como conceito inicial; detalhes POR VALIDAR]**

Elementos possíveis:

* Dois castelos ou posições opostas.
* Uma rainha ou outras personagens.
* Cavaleiros.
* Espadas e escudos.
* Uma grande taça como objetivo final.
* Uma batalha visualmente simples e divertida.

Este tema constitui uma das primeiras ideias apresentadas pela criança.

### 5.2. Tema B — Barcos e lago **[EM EXPLORAÇÃO]**

Elementos possíveis:

* Um lago.
* Barcos de cada lado.
* Personagens a lutar.
* Espadas e outros elementos visuais adaptados ao cenário.
* Um objetivo ou prémio situado junto de um dos barcos ou numa zona central.

A ideia original incluía barcos, um lago, uma batalha e uma taça especial.

A implementação exata ainda está por definir. **[POR VALIDAR]**

### 5.3. Tema C — Montanhas **[EM EXPLORAÇÃO]**

Foi sugerida a possibilidade de criar um nível de Tower Defense num ambiente de montanha.

Este cenário poderá utilizar o mesmo sistema de defesa e progressão, mas com um ambiente visual distinto.

### 5.4. Tema D — Praça, cavaleiros e recompensas **[EM EXPLORAÇÃO]**

Outra ideia envolve cavaleiros numa praça e recompensas como:

* Um sumo.
* Um chocolate.
* Um doce.
* Uma roupa ou fantasia.

Neste contexto, o prémio pode ser apresentado como algo que a personagem recebe ou escolhe depois de vencer.

### 5.5. Princípio de reutilização **[DECIDIDO — como princípio; tabela abaixo é proposta, não definição final]**

Os temas devem ser tratados, sempre que possível, como configurações de uma mesma estrutura de jogo.

Por exemplo:

| Elemento | Tema do castelo | Tema do lago |
|---|---|---|
| Posição a proteger | Castelo | Barco ou posição junto ao lago |
| Unidades | Cavaleiros | Personagens ou unidades temáticas |
| Progressão | Avanço em direção ao castelo adversário | Avanço em direção ao objetivo adversário |
| Objetivo final | Conquistar a taça | Conquistar a taça |
| Impulsos educativos | Melhorias de defesa ou ataque | Melhorias adaptadas ao cenário |
| Recompensa | Taça ou prémio | Taça ou prémio |

Esta tabela é uma proposta de organização, não uma definição final das mecânicas de cada tema.

> **Nota de integração:** o catálogo de temas foi alargado pela adenda (montanha detalhada, gruta, baleia/boss, ambiente aquático). Ver secção 13 (catálogo consolidado). A presente secção preserva o estado original das ideias.

---

## 6. Loop principal de jogabilidade

O loop principal deverá ser suficientemente simples para uma criança compreender e suficientemente flexível para acomodar desafios educativos. **[DECIDIDO — diretriz]**

### 6.1. Loop proposto **[EM EXPLORAÇÃO — hipótese inicial a validar em protótipos]**

1. Iniciar um nível. A criança encontra um cenário, um adversário e um objetivo claro.
2. Observar a batalha. As unidades avançam, atacam e defendem.
3. Acompanhar o progresso. A criança consegue perceber qual dos lados está em vantagem.
4. Reagir a uma situação. O jogo pode introduzir uma oportunidade ou necessidade de obter um impulso.
5. Resolver um desafio educativo. A criança responde a uma pergunta ou completa uma atividade simples.
6. Receber um impulso. Uma resposta correta proporciona uma vantagem dentro da batalha.
7. Continuar a partida. A vantagem obtida altera o estado do jogo.
8. Conquistar o objetivo. A criança ganha a partida ao cumprir a condição de vitória.
9. Receber uma recompensa. O jogo apresenta a taça ou outro prémio associado ao nível.

Este loop é uma hipótese inicial de design e deverá ser validado através de protótipos. **[POR VALIDAR]**

### 6.2. O papel da simulação

Um dos pontos mais importantes da conversa é que o jogo não deve ser apenas uma simulação automática de uma batalha engraçada. **[DECIDIDO]**

A simulação deve transmitir uma sensação real de competição e progresso.

A criança precisa de perceber que:

* As coisas estão a acontecer.
* O adversário representa um desafio.
* As suas ações podem alterar o resultado.
* Pode estar perto de ganhar ou de perder.
* Existe uma razão para tomar decisões.
* A vitória depende, pelo menos em parte, das suas escolhas e da sua aprendizagem.

O equilíbrio entre simulação automática e controlo direto da criança ainda precisa de ser explorado. **[POR VALIDAR]**

> **Nota de integração:** a adenda clarifica que as unidades **não são controladas individualmente** — são unidades da simulação e a criança decide ao nível do jogo (impulsos, elementos estratégicos). Ver secção 15.

---

## 7. Mecânica educativa: desafios que proporcionam impulsos

Esta é uma das funcionalidades mais importantes e diferenciadoras do conceito. **[DECIDIDO]**

### 7.1. Objetivo

Integrar pequenas atividades educativas na progressão da batalha, de modo que a criança possa utilizar os conhecimentos que está a desenvolver na escola para obter vantagens concretas. **[DECIDIDO]**

Os desafios deverão ser adequados ao primeiro ano de escolaridade. **[DECIDIDO]**

### 7.2. Tipos de desafio considerados **[EM EXPLORAÇÃO — catálogo não fechado]**

**Letras e leitura inicial**

* Reconhecer uma letra.
* Identificar uma letra apresentada no ecrã.
* Escolher a letra que corresponde a uma pergunta.
* Distinguir letras visualmente semelhantes, quando apropriado.

**Aritmética básica**

* Contar objetos.
* Resolver somas simples.
* Resolver subtrações simples.
* Escolher o resultado correto entre algumas opções.

**Outros conceitos simples**

Poderão ser acrescentados futuramente outros conteúdos adequados à idade, desde que sejam compatíveis com o ritmo do jogo.

Não é necessário decidir agora o catálogo completo de desafios. **[POR VALIDAR]**

### 7.3. Formato dos desafios **[EM EXPLORAÇÃO]**

Foram considerados formatos semelhantes a:

* Flashcards.
* Minicards.
* Pequenos minijogos.

Uma carta poderá apresentar uma pergunta, uma imagem e várias respostas possíveis.

Por exemplo:

Pergunta: Quanto é 2 + 3?

* 4
* 5
* 6

Ao responder corretamente, a criança recebe um impulso que altera a batalha.

Este é apenas um exemplo ilustrativo, não uma decisão sobre o formato final da interface. **[POR VALIDAR]**

### 7.4. Os desafios podem surgir de duas formas **[EM EXPLORAÇÃO — hipótese a validar; protótipo deve incluir ambas se viável]**

**Modo A — Desafio automático**

O jogo apresenta espontaneamente um desafio educativo num momento específico da partida.

Por exemplo:

* Quando a defesa começa a ceder.
* Quando o adversário está em vantagem.
* Quando surge uma oportunidade de melhorar uma unidade.
* Quando a criança se aproxima do objetivo final.

**Modo B — Desafio iniciado pela criança**

A criança pode decidir recorrer a um desafio educativo para tentar obter uma vantagem.

Por exemplo, pode optar por tentar resolver uma conta para conseguir reforçar as suas defesas ou acelerar o avanço das suas unidades.

Esta opção introduz uma decisão estratégica: utilizar o impulso no momento presente ou continuar a batalha sem recorrer a ele.

### 7.5. Relação entre resposta e consequência **[EM EXPLORAÇÃO]**

A resposta correta deverá ter uma consequência clara no jogo. **[DECIDIDO — princípio]**

Possíveis recompensas:

* Reforçar uma defesa.
* Aumentar temporariamente a força de uma unidade.
* Acelerar o avanço.
* Ganhar tempo.
* Recuperar uma posição desfavorável.
* Obter uma vantagem decisiva perto do objetivo final.

A relação exata entre cada tipo de desafio e cada impulso ainda está por definir. **[POR VALIDAR]**

### 7.6. O que acontece quando a resposta está errada? **[POR VALIDAR — em aberto]**

Este ponto continua em aberto.

Algumas opções a testar:

* A criança não recebe o impulso, mas pode continuar a jogar.
* Recebe uma pista e tem oportunidade de tentar novamente.
* O jogo apresenta a resposta correta de forma simples.
* O desafio reaparece mais tarde, permitindo praticar novamente.

A experiência não deve transformar um erro numa penalização desproporcionada. **[DECIDIDO — diretriz]**

O objetivo é criar uma associação positiva entre aprender, tentar novamente e melhorar o desempenho no jogo. **[DECIDIDO — diretriz]**

---

## 8. Dificuldade dinâmica e momentos de intervenção educativa

O pai introduziu um requisito particularmente importante: a dificuldade não deve ser apenas uma consequência passiva do estado do jogo. **[DECIDIDO — requisito]**

O sistema deverá poder criar situações em que os desafios educativos se tornam relevantes para a progressão. **[DECIDIDO — intenção]**

### 8.1. Dificuldade superior à capacidade atual da personagem **[EM EXPLORAÇÃO — hipótese]**

Uma possibilidade é que, em certos momentos, a situação da batalha se torne demasiado difícil para a configuração atual da criança.

Isto cria uma necessidade de recorrer a um impulso educativo.

Por exemplo:

1. A criança está a defender o castelo.
2. O adversário começa a ganhar terreno.
3. A defesa existente já não é suficiente.
4. Surge uma oportunidade para obter um impulso através de um desafio educativo.
5. A criança resolve o desafio.
6. O impulso melhora a situação da batalha.
7. A criança volta a sentir que tem hipóteses de vencer.

A dificuldade serve, assim, para dar relevância à aprendizagem.

### 8.2. Intervenção perto da vitória **[EM EXPLORAÇÃO — hipótese]**

A mesma lógica poderá ser utilizada quando a criança está prestes a ganhar.

Por exemplo:

1. A criança aproxima-se da taça.
2. O adversário consegue criar um último obstáculo.
3. A criança precisa de uma vantagem adicional.
4. Surge um desafio educativo.
5. Ao resolvê-lo, recebe o impulso necessário para conquistar o prémio.

A intenção é que a aprendizagem faça parte dos momentos mais importantes da partida.

### 8.3. Distinção entre dificuldade e impossibilidade **[POR VALIDAR — comparar as duas abordagens em prototipagem]**

É importante distinguir uma situação desafiante de uma situação em que a vitória está artificialmente bloqueada.

A ideia discutida inclui a possibilidade de a mecânica impedir temporariamente a vitória até surgir uma oportunidade de resolver um desafio educativo.

Esta abordagem precisa de ser explorada cuidadosamente.

Se o jogo impedir repetidamente uma vitória que a criança considera merecida, poderá parecer injusto ou imprevisível.

Uma alternativa é criar situações em que o desafio educativo representa uma oportunidade real de superar um obstáculo, sem tornar obrigatória uma resposta correta para todas as vitórias.

Estas duas abordagens devem ser comparadas durante a prototipagem.

### 8.4. A criança não precisa de conhecer os números internos **[DECIDIDO — diretriz]**

O sistema poderá utilizar indicadores internos de progresso para determinar quando apresentar um desafio.

Por exemplo, poderá considerar:

* A proximidade ao objetivo.
* O estado das defesas.
* A vantagem relativa entre os dois lados.
* O tempo que falta para um dos lados vencer.

A criança não precisa de ver percentagens ou métricas técnicas. Basta receber sinais visuais simples que comuniquem a situação.

---

## 9. Recompensas e progressão

A recompensa é um elemento central do conceito original apresentado pela criança. **[DECIDIDO]**

### 9.1. A taça como objetivo principal **[DECIDIDO como conceito; implementação POR VALIDAR]**

A grande taça especial é a primeira recompensa claramente identificada.

Deverá funcionar como um símbolo visual da vitória e da conclusão do nível.

Pode ser apresentada através de:

* Uma animação de conquista.
* Uma celebração das personagens.
* Um ecrã de vitória.
* Uma taça que fica disponível na coleção da criança.

Estas são possibilidades de implementação a validar.

### 9.2. Recompensas adicionais **[EM EXPLORAÇÃO — não implementar todas no primeiro protótipo]**

Foram mencionadas recompensas concretas, como:

* Sumo.
* Chocolate.
* Doces.
* Roupas.
* Fantasias.

Estas recompensas podem ser representadas dentro do jogo, por exemplo através de uma loja, de uma praça ou de um sistema de personalização.

Não é necessário implementar todas no primeiro protótipo. **[DECIDIDO — faseamento]**

### 9.3. Escolha da recompensa **[EM EXPLORAÇÃO]**

Uma possibilidade é permitir que a criança escolha o prémio depois de vencer.

Isto acrescenta uma pequena decisão à experiência e pode reforçar a sensação de autonomia.

Contudo, é importante distinguir duas mecânicas diferentes:

* A recompensa que assinala a vitória.
* A recompensa que permite personalizar ou evoluir a personagem.

O primeiro protótipo poderá limitar-se à taça, acrescentando outras recompensas mais tarde. **[DECIDIDO — faseamento]**

> **Nota de integração:** a adenda acrescenta recompensas temáticas por nível (espadas, escudos e outros elementos do tema). Ver secção 16 e FR-22.

---

## 10. Vetores de otimização do produto

Esta secção identifica os critérios que deverão orientar as decisões de design e desenvolvimento. **[DECIDIDO — como quadro de avaliação]**

Não são requisitos já validados. São hipóteses de otimização que devem ser transformadas em critérios observáveis durante os testes.

| Vetor | Objetivo | Como avaliar |
|---|---|---|
| Diversão | A criança quer continuar a jogar. | Interesse, envolvimento e vontade de repetir. |
| Compreensão | A criança percebe o objetivo e o estado da batalha. | Capacidade de explicar o que está a acontecer. |
| Agência | As ações da criança influenciam o resultado. | Capacidade de associar decisões a consequências. |
| Aprendizagem | Os desafios ajudam a praticar competências escolares. | Desempenho nos desafios e retenção em tentativas posteriores. |
| Integração pedagógica | Os desafios parecem fazer parte do jogo. | Reação da criança aos desafios e continuidade do envolvimento. |
| Equilíbrio | O jogo é desafiante sem ser excessivamente frustrante. | Frequência de vitórias, derrotas e pedidos de ajuda. |
| Clareza visual | O estado do jogo é compreensível sem explicações extensas. | Capacidade de identificar quem está em vantagem. |
| Autonomia | A criança consegue tomar decisões simples. | Utilização voluntária dos impulsos e escolhas de recompensa. |
| Reutilização | Novos temas podem ser adicionados sem reconstruir a mecânica. | Esforço necessário para implementar um novo cenário. |
| Simplicidade técnica | O protótipo permite testar rapidamente as hipóteses. | Tempo de implementação e facilidade de alteração das regras. |

### 10.1. Prioridades sugeridas **[DECIDIDO — ordem sugerida para o primeiro protótipo]**

Para o primeiro protótipo, sugere-se a seguinte ordem:

**Prioridade 1 — Validar a diversão e a compreensão.**

A criança deve perceber a batalha, compreender o objetivo e querer continuar a jogar.

**Prioridade 2 — Validar o impacto dos desafios educativos.**

É necessário perceber se resolver um desafio e obter um impulso cria uma experiência satisfatória.

**Prioridade 3 — Validar a dificuldade dinâmica.**

O jogo deve conseguir criar momentos em que a intervenção educativa seja útil, sem parecer injusto.

**Prioridade 4 — Validar a arquitetura temática.**

Só depois de a mecânica central funcionar deverá ser necessário investir na possibilidade de reutilizar o sistema em vários cenários.

**Prioridade 5 — Expandir recompensas e progressão.**

Novos prémios, personalização e sistemas de progressão podem ser introduzidos quando a experiência principal estiver validada.

---

## 11. Âmbito sugerido para o primeiro protótipo

O objetivo do primeiro protótipo não deverá ser construir o jogo completo. **[DECIDIDO]**

Deverá ser demonstrar que a combinação de Tower Defense, competição visual e desafios educativos funciona para a criança. **[DECIDIDO]**

### 11.1. Funcionalidades mínimas **[EM EXPLORAÇÃO — proposta inicial]**

| Funcionalidade | Proposta inicial |
|---|---|
| Modo de jogo | Single-player. |
| Cenário | Um único cenário de castelo. |
| Adversário | Controlado pelo jogo. |
| Unidades | Um conjunto pequeno de unidades simples. |
| Mecânica de batalha | Defesa e avanço em direção ao objetivo adversário. |
| Objetivo | Conquistar uma taça. |
| Indicador de progresso | Feedback visual sobre a vantagem de cada lado. |
| Desafios educativos | Um conjunto reduzido de perguntas sobre letras ou aritmética básica. |
| Impulsos | Uma ou duas vantagens associadas às respostas corretas. |
| Ativação dos desafios | Pelo menos uma oportunidade automática e uma oportunidade iniciada pela criança, se viável. |
| Dificuldade | Uma situação em que um impulso educativo ajuda a recuperar uma posição desfavorável. |
| Recompensa | Animação simples de vitória e apresentação da taça. |

Esta proposta não implica que todas as funcionalidades tenham de estar presentes na primeira versão técnica. A seleção final *[texto original interrompido aqui]*

> **Nota do revisor:** o ficheiro `game-brief.txt` termina a meio desta frase. O conteúdo foi transcrito exatamente até ao ponto de interrupção. A seleção final das funcionalidades do primeiro protótipo fica registada como decisão pendente (ver secção 19).

---

## 12. Progressão entre níveis e mudança de cenários

*(Adenda secção 20. Todas as ideias e requisitos previamente registados mantêm-se; esta secção acrescenta os novos conceitos discutidos. As ideias propostas pela criança continuam a ser tratadas como inputs criativos importantes; as interpretações técnicas do pai são hipóteses de design a validar.)*

### 12.1. Progressão por níveis **[EM EXPLORAÇÃO — ideia proposta pela criança]**

A criança propôs que, depois de concluir um nível, o jogo avance para o nível seguinte. A passagem de um nível para outro poderá também introduzir uma mudança de cenário.

Por exemplo:

* O jogador começa num castelo.
* Depois de vencer, avança para um novo nível.
* O cenário muda para uma montanha, uma gruta ou outro ambiente.
* Os cavaleiros continuam a ser essencialmente os mesmos.
* O objetivo competitivo mantém-se, mas os elementos visuais, os adversários e os prémios podem mudar.

A ideia é proporcionar uma sensação de aventura e descoberta sem obrigar a criança a aprender novamente todas as regras em cada nível.

### 12.2. Continuidade das personagens **[EM EXPLORAÇÃO — decisão conceptual importante, detalhes por definir]**

Uma decisão conceptual importante é que os cavaleiros podem manter-se ao longo dos vários temas, mesmo quando o cenário e a identidade visual mudam.

Isto permite preservar a continuidade da experiência.

Os cavaleiros são as unidades do jogador; os diferentes ambientes representam etapas de uma aventura mais abrangente.

Ainda não está decidido se os cavaleiros terão atributos persistentes, se serão apenas visualmente consistentes ou se poderão evoluir entre níveis. **[POR VALIDAR]**

### 12.3. Mudança de tema e de identidade visual **[EM EXPLORAÇÃO]**

A progressão poderá alternar entre diferentes estilos e ambientes:

* Um mundo de castelos e cavaleiros.
* Um cenário de montanha.
* Uma gruta.
* Um ambiente aquático.
* Outros mundos imaginativos que venham a ser definidos.

As referências estilísticas previamente discutidas continuam válidas: personagens infantis e coloridas, estética de blocos inspirada em LEGO ou Minecraft e outras variações visuais adequadas à idade.

Foi também sugerida a possibilidade de uma personagem, como um feiticeiro, servir de elemento narrativo que conduz os cavaleiros através de diferentes épocas, mundos ou realidades.

Esta ideia fica registada como uma possibilidade narrativa, sem necessidade de definir já a história. **[POR VALIDAR — ver também secção 17]**

---

## 13. Catálogo consolidado de temas de níveis

*(Adenda secção 21, fundida com os Temas A–D da secção 5. Os temas não têm necessariamente de representar géneros de jogo diferentes; podem ser variações do mesmo sistema de batalha. A prioridade é manter a mecânica principal reconhecível, introduzindo diferenças visuais e desafios específicos em cada ambiente.)*

| Tema | Conceito | Elementos específicos | Estado |
|---|---|---|---|
| Castelo | Batalha entre posições fortificadas. | Cavaleiros, espadas, escudos e taça. (Ver § 5.1: dois castelos/posições opostas, rainha ou outras personagens, cavaleiros, espadas e escudos, grande taça, batalha simples e divertida. Primeira ideia da criança.) | Conceito inicial. **[DECIDIDO como ponto de partida]** |
| Montanha | Novo cenário de batalha. | Terreno montanhoso e possíveis obstáculos. (Ver § 5.3: mesmo sistema de defesa e progressão com ambiente visual distinto.) | Ideia proposta. **[EM EXPLORAÇÃO]** |
| Gruta | Batalha num ambiente fechado. | Uma casa ou fortificação dos cavaleiros, com espadas e escudos como elementos de interesse. | Ideia em exploração. **[EM EXPLORAÇÃO]** |
| Barcos e lago | Batalha num ambiente aquático. | Barcos, água e unidades adaptadas ao cenário. (Ver § 5.2: lago, barcos de cada lado, personagens a lutar, espadas adaptadas, objetivo/prémio junto a um barco ou zona central; taça especial. Implementação exata por definir.) | Ideia proposta anteriormente. **[EM EXPLORAÇÃO]** |
| Baleia | Nível aquático com um adversário especialmente poderoso. | Baleia, jatos de água, peixes adversários e ataques que afetam as unidades. | Novo conceito desenvolvido pela criança. **[EM EXPLORAÇÃO — detalhado na secção 14]** |
| Praça, cavaleiros e recompensas | Cavaleiros numa praça com prémios quotidianos. | Sumo, chocolate, doce, roupa ou fantasia como prémio recebido/escolhido após vencer. (Origem: § 5.4.) | Ideia em exploração. **[EM EXPLORAÇÃO]** |

> **Nota de integração:** esta tabela consolida o Tema A–D originais (§ 5) com os cinco temas listados na adenda, sem duplicar entradas (castelo, montanha e barcos/lago existiam em ambos; gruta e baleia são novidades da adenda; praça transita do original).

---

## 14. A baleia como boss

*(Adenda secção 22.)*

### 14.1. Conceito **[EM EXPLORAÇÃO — nova proposta da criança]**

A baleia deixa de ser apenas um elemento decorativo de um cenário aquático.

A nova proposta é que seja um boss, ou seja, um adversário particularmente poderoso que constitui o principal desafio de um dos níveis.

A baleia deverá ser uma presença central na batalha, com ataques e comportamentos próprios.

O jogador continua a utilizar o sistema habitual de unidades e progressão, mas enfrenta um adversário que exige mais esforço para ultrapassar.

### 14.2. Ambiente e progressão até à baleia **[EM EXPLORAÇÃO]**

O nível poderá decorrer num ambiente aquático.

As unidades dos cavaleiros avançam pela água ou por um percurso associado ao cenário, enquanto a baleia e outras criaturas marinhas tentam impedir o seu progresso.

A ideia da criança inclui a possibilidade de os cavaleiros avançarem disfarçados ou parcialmente submersos, criando uma sensação de aproximação furtiva ao adversário.

Não está decidido como esta ideia será traduzida em mecânicas concretas. **[POR VALIDAR]**

### 14.3. Ataques e comportamentos da baleia **[EM EXPLORAÇÃO — propostas de design, efeitos por definir]**

Foram identificadas três ideias específicas:

**A. Jatos de água**

A baleia lança jatos de água que afetam as unidades do jogador e podem interromper ou dificultar o seu avanço.

**B. Puxar as unidades pelos pés**

A baleia pode puxar os cavaleiros para baixo, como se os agarrasse debaixo de água.

A ideia é criar uma animação visualmente expressiva, que comunique que as unidades estão em perigo.

**C. Criaturas marinhas auxiliares**

Outros animais, como raias ou peixes, podem funcionar como adversários associados à baleia.

Estas criaturas poderão ajudar a atrasar, desviar ou neutralizar temporariamente as unidades do jogador.

Todos estes comportamentos são propostas de design. A sua implementação e os seus efeitos exatos na batalha ainda estão por definir. **[POR VALIDAR]**

### 14.4. Relação com as mecânicas educativas **[EM EXPLORAÇÃO — possibilidade de integração, não regra decidida]**

O boss poderá utilizar o mesmo sistema de desafios educativos já previsto para os restantes níveis.

Por exemplo, quando a baleia coloca as unidades em desvantagem, o jogo poderá apresentar um desafio de matemática ou de reconhecimento de letras. Uma resposta correta poderá proporcionar um impulso que permita recuperar terreno.

Esta é uma possibilidade de integração, não uma regra já decidida.

A baleia não deverá exigir necessariamente um sistema educativo diferente: poderá ser uma nova aplicação das mecânicas centrais. **[DECIDIDO — como diretriz de reutilização]**

### 14.5. Condição de vitória **[POR VALIDAR — em aberto]**

O objetivo do nível poderá ser ultrapassar a baleia, neutralizar a sua capacidade de impedir o avanço ou alcançar o objetivo que ela protege.

A condição exata de vitória ainda está em aberto.

O mais importante é que o boss represente um desafio percetivelmente maior do que os adversários habituais, sem exigir que a criança aprenda um conjunto inteiramente novo de regras. **[DECIDIDO — diretriz]**

---

## 15. Unidades, classes e simulação automática

*(Adenda secção 23. Clarifica uma distinção importante introduzida pelo pai.)*

### 15.1. As unidades não são controladas individualmente **[DECIDIDO — clarificação]**

Os cavaleiros e restantes personagens que participam na batalha são unidades da simulação.

A criança não precisa de controlar cada personagem individualmente.

Em vez disso, observa o desenrolar da batalha e toma decisões ao nível do jogo, como utilizar impulsos educativos ou gerir outros elementos estratégicos que venham a ser definidos.

As unidades avançam, combatem, recuam e são afetadas pelos adversários através das regras internas da simulação.

A experiência deve transmitir a sensação de uma batalha em curso, sem exigir microgestão individual dos personagens.

### 15.2. Capacidade e circulação de unidades **[EM EXPLORAÇÃO]**

O jogo poderá ter uma capacidade definida de unidades em campo.

As unidades entram na batalha, avançam, combatem e podem ser derrotadas ou retiradas temporariamente.

Quando isso acontece, a simulação pode representar visualmente o seu regresso à posição inicial, a recuperação ou a substituição por outra unidade.

Esta representação é importante porque permite à criança perceber que a batalha está a evoluir e que existem consequências para os acontecimentos no terreno.

### 15.3. Derrota de uma unidade não significa necessariamente perda permanente **[EM EXPLORAÇÃO — proposta atual favorece derrota temporária; sem decisão definitiva]**

A conversa sugere que, quando um cavaleiro é derrotado, poderá voltar ao início do percurso ou reaparecer mais tarde.

A intenção é que a criança veja a unidade a sair da batalha e perceba que deixou temporariamente de contribuir para o avanço.

Não está decidido se a unidade regressará automaticamente, se precisará de algum tempo para recuperar ou se será substituída por outra. **[POR VALIDAR]**

A distinção fundamental é entre:

* Derrota temporária: a unidade deixa de contribuir para a batalha durante algum tempo, mas pode regressar.
* Perda permanente: a unidade deixa de estar disponível para o resto da partida ou para níveis posteriores.

A proposta atual favorece a primeira abordagem, por ser mais simples e potencialmente menos frustrante para o público-alvo.

Não se considera, contudo, uma decisão definitiva sobre o sistema de unidades.

### 15.4. Classes diferentes de unidades **[EM EXPLORAÇÃO — possibilidades de design, não classes aprovadas]**

Foi também identificada a possibilidade de existirem classes diferentes de unidades.

Estas classes poderão ter características próprias, como resistência, velocidade ou capacidade de ataque.

Por exemplo, numa fase futura, o jogo poderá distinguir entre unidades mais resistentes e unidades mais rápidas.

Estes exemplos são possibilidades de design, não classes já aprovadas.

O objetivo será introduzir variedade suficiente para tornar a simulação interessante, sem criar complexidade excessiva para uma criança de 6 anos.

---

## 16. Espadas, escudos e recompensas de nível

*(Adenda secção 24. Ideia sugerida pela criança: um nível em que as espadas e os escudos assumem um papel importante, associado a um castelo ou a uma gruta onde os cavaleiros disputam estes elementos.)*

### 16.1. Papel das espadas e dos escudos **[EM EXPLORAÇÃO — interpretação por fechar]**

As espadas e os escudos poderão funcionar como:

* Elementos visuais associados às unidades.
* Objetos conquistados durante a batalha.
* Indicadores de progressão.
* Recompensas atribuídas depois de vencer um nível.

A interpretação exata ainda não está fechada. **[POR VALIDAR]**

### 16.2. Recompensas específicas **[EM EXPLORAÇÃO]**

Uma possibilidade é que, ao vencer este nível, a criança receba espadas e escudos como recompensa.

Estes elementos poderão depois integrar a progressão visual dos cavaleiros ou servir como indicadores de conquista.

Não está decidido se terão efeitos mecânicos permanentes ou se serão apenas recompensas visuais. **[POR VALIDAR]**

### 16.3. Preservar a mecânica principal **[DECIDIDO — diretriz]**

Mesmo que um nível passe a ter espadas e escudos como elementos centrais, a estrutura da partida deverá continuar a ser reconhecível.

O jogador observa a batalha, acompanha o progresso, utiliza as oportunidades disponíveis e procura cumprir o objetivo do nível.

A mudança de tema não deverá obrigar a redefinir todo o sistema de jogo.

---

## 17. Notas de narrativa e transição entre mundos

*(Adenda secção 25. A narrativa não precisa de ser fechada nesta fase; registam-se as ideias para o próximo agente.)*

### 17.1. Uma aventura através de diferentes realidades **[EM EXPLORAÇÃO — possibilidade]**

Uma possibilidade é que os cavaleiros viajem entre diferentes mundos, épocas ou ambientes.

Um personagem, como um feiticeiro, poderá funcionar como elemento de ligação entre essas realidades.

A transição poderá justificar a passagem de um castelo para uma montanha, de uma gruta para um cenário aquático ou para qualquer outro ambiente que venha a ser acrescentado.

### 17.2. Continuidade apesar da mudança de cenário **[EM EXPLORAÇÃO]**

Os mesmos cavaleiros poderão aparecer nos vários níveis, mantendo a identidade do jogador.

O cenário muda, mas a criança continua a acompanhar a mesma aventura.

Esta abordagem poderá tornar a progressão mais coerente e ajudar a criança a reconhecer as personagens de nível para nível.

### 17.3. Liberdade para desenvolver a narrativa posteriormente **[POR VALIDAR — oportunidades para o próximo agente]**

Não é necessário decidir já:

* Quem é o feiticeiro.
* Como funcionam as viagens entre mundos.
* Porque é que os cavaleiros têm de enfrentar diferentes adversários.
* Como se relacionam os vários cenários.
* Qual é a história completa da baleia.

Estes elementos devem ser transmitidos ao próximo agente como oportunidades de desenvolvimento narrativo.

A prioridade nesta fase continua a ser definir a estrutura da experiência e as mecânicas essenciais. **[DECIDIDO]**

---

## 18. Requisitos funcionais consolidados (FR-01–FR-22)

> **Nota de origem:** o brief original não numerava requisitos funcionais; descrevia funcionalidades mínimas (§ 11.1) e mecânicas (§§ 2, 6–9). Os FR-01–FR-12 abaixo são **reconstruídos fielmente a partir desse texto** e estão sujeitos a confirmação — não devem ser lidos como numeração histórica. Os **FR-13–FR-22 são transcrição literal da adenda** (secção 26). Estes requisitos são preliminares; a sua inclusão não significa que todos tenham de ser implementados no primeiro protótipo.

### 18.1. Requisitos da base original (FR-01–FR-12, reconstruídos)

**FR-01 — Modo single-player com adversário simulado**

O jogo deverá suportar um modo single-player em que o adversário é controlado pelo jogo, sem necessidade de multiplayer. (Origem: §§ 2.1, 11.1.)

**FR-02 — Defesa e avanço competitivo**

O sistema deverá suportar defesa de uma posição e avanço das unidades em direção ao objetivo adversário. (Origem: §§ 2.1, 6.1, 11.1.)

**FR-03 — Indicador visual de progresso/vantagem**

O jogo deverá apresentar feedback visual sobre a vantagem de cada lado e a proximidade ao objetivo, sem expor percentagens ou métricas técnicas à criança. (Origem: §§ 3.2-B, 8.4, 11.1.)

**FR-04 — Desafios educativos (letras e aritmética)**

O jogo deverá apresentar um conjunto de desafios adequados ao 1.º ano (reconhecimento de letras; contagem, somas e subtrações simples com escolha entre opções), em formato de flashcards/minicards ou pequenos minijogos. (Origem: §§ 7.2, 7.3, 11.1.)

**FR-05 — Dupla ativação dos desafios (automática + iniciativa da criança)**

O sistema deverá suportar desafios apresentados automaticamente pelo jogo em momentos específicos e desafios solicitados pela criança para tentar obter uma vantagem. (Origem: §§ 7.4, 11.1.)

**FR-06 — Impulsos de batalha por resposta correta**

Uma resposta correta deverá produzir uma vantagem percetível na batalha (ex.: reforçar defesa, aumentar força temporariamente, acelerar avanço, ganhar tempo, recuperar posição desfavorável, vantagem decisiva perto do objetivo). (Origem: §§ 7.5, 11.1.)

**FR-07 — Tratamento não-punitivo de respostas erradas**

O sistema deverá tratar respostas erradas sem penalização desproporcionada (ex.: sem impulso mas com continuidade do jogo; pista com nova tentativa; apresentação simples da resposta; reaparecimento posterior do desafio). Mecanismo exato por validar. (Origem: § 7.6.)

**FR-08 — Dificuldade dinâmica com intervenção educativa**

O sistema deverá poder criar situações em que um impulso educativo ajuda a recuperar uma posição desfavorável e intervir em momentos próximos da vitória, distinguindo desafio legítimo de bloqueio artificial da vitória. (Origem: §§ 8.1–8.3, 11.1.)

**FR-09 — Condição de vitória e fim de partida**

A partida deverá terminar quando uma das forças atinge o objetivo definido para o nível (ex.: conquistar a taça). (Origem: §§ 2.2, 6.1.)

**FR-10 — Recompensa principal com celebração**

A vitória deverá desencadear a apresentação da taça (animação de conquista, celebração, ecrã de vitória e/ou registo em coleção) e suportar a escolha do prémio pela criança. (Origem: §§ 9.1, 9.3, 11.1.)

**FR-11 — Recompensas adicionais e personalização (diferidas)**

A arquitetura deverá prever recompensas adicionais (sumo, chocolate, doces, roupas, fantasias) representadas em loja/praça/sistema de personalização, a introduzir após validação da experiência principal. (Origem: §§ 9.2, 9.3, 10.1-P5.)

**FR-12 — Arquitetura temática reutilizável**

A mecânica central deverá ser independente da direção artística, permitindo suportar temas/cenários distintos (personagens fofas, blocos de construção, outros) como configurações do mesmo sistema. (Origem: §§ 4.3, 5.5, 10.1-P4.)

### 18.2. Requisitos da adenda (FR-13–FR-22, transcrição)

**FR-13 — Progressão entre níveis**

O jogo deverá permitir avançar para novos níveis após a conclusão dos anteriores.

**FR-14 — Variação temática**

Os níveis poderão apresentar diferentes ambientes e identidades visuais, mantendo uma base de mecânicas comum.

**FR-15 — Continuidade das unidades**

O jogo deverá permitir manter uma identidade consistente para as unidades do jogador ao longo de diferentes cenários, se essa abordagem for confirmada.

**FR-16 — Simulação automática de unidades**

As unidades deverão atuar de acordo com as regras da simulação, sem exigir controlo individual direto por parte da criança.

**FR-17 — Gestão do estado das unidades**

O sistema deverá representar o estado das unidades, incluindo a sua entrada em campo, participação na batalha e eventual derrota ou retirada temporária.

**FR-18 — Possibilidade de recuperação das unidades**

O sistema poderá permitir que unidades derrotadas regressem à batalha, evitando que todas as derrotas impliquem perdas permanentes.

**FR-19 — Classes de unidades**

A arquitetura deverá permitir introduzir classes diferentes de unidades, caso a variedade de funções se revele necessária.

**FR-20 — Boss fights**

O jogo deverá poder incluir adversários especiais com comportamentos distintos dos adversários comuns.

**FR-21 — Comportamentos específicos de boss**

Um boss poderá ter ataques ou habilidades próprias, como jatos de água, captura temporária de unidades ou apoio de criaturas auxiliares.

**FR-22 — Recompensas temáticas**

Os níveis poderão atribuir recompensas específicas, como espadas, escudos ou outros elementos associados ao respetivo tema.

---

## 19. Decisões pendentes consolidadas

*(Consolida os pontos em aberto do original com as 10 questões da adenda secção 27. O próximo agente deverá considerá-las gradualmente, com prioridade para as que influenciam o loop central e a complexidade técnica.)*

### 19.1. Pontos em aberto do brief original

1. Ondas discretas com pausas vs. simulação contínua — decisão a manter em aberto na prototipagem inicial. (§ 2.2)
2. Direções artísticas como temas do mesmo jogo vs. jogos distintos com base técnica comum. (§ 4.3)
3. Catálogo completo de desafios educativos — não fechar já. (§ 7.2)
4. Formato final da interface dos desafios (flashcard, minicard, minijogo). (§ 7.3)
5. Mapeamento exato entre tipo de desafio e tipo de impulso. (§ 7.5)
6. Consequência de resposta errada (sem impulso / pista + nova tentativa / mostrar resposta / reaparecer mais tarde). (§ 7.6)
7. Bloqueio temporário da vitória até ao desafio educativo vs. desafio como oportunidade não-obrigatória — comparar em protótipo. (§ 8.3)
8. Equilíbrio entre simulação automática e controlo direto da criança. (§ 6.2)
9. Apresentação concreta da taça (animação, celebração, ecrã, coleção). (§ 9.1)
10. Escolha do prémio pela criança; distinção entre recompensa de vitória e recompensa de personalização/evolução. (§ 9.3)
11. Seleção final das funcionalidades da primeira versão técnica do protótipo (frase original interrompida). (§ 11.1)

### 19.2. Decisões pendentes acrescentadas pela adenda

1. Progressão: os níveis serão sequenciais ou haverá escolhas entre diferentes cenários?
2. Unidades: as unidades regressam automaticamente depois de serem derrotadas?
3. Classes: quais são as diferenças mínimas entre classes, caso venham a existir?
4. Boss: a baleia deve ser derrotada, ultrapassada ou apenas impedida de bloquear o objetivo?
5. Ataques especiais: os ataques da baleia afetam a saúde, a posição, a velocidade ou apenas o estado visual das unidades?
6. Espadas e escudos: são recompensas visuais, recursos de jogo ou melhorias permanentes?
7. Narrativa: como se justificam as transições entre mundos?
8. Estilo visual: os temas podem alternar entre estéticas muito diferentes ou deverão manter uma identidade gráfica comum?
9. Dificuldade: como garantir que o sistema de unidades e os bosses continuam compreensíveis para uma criança de 6 anos?
10. Integração educativa: os desafios educativos poderão ajudar a recuperar unidades, contrariar ataques especiais ou obter vantagens contra bosses?

---

## 20. Síntese para o próximo agente

O jogo é uma experiência single-player para uma criança de 6 anos (1.º ano de escolaridade), baseada numa simulação de batalha que combina mecânicas de Tower Defense com um objetivo competitivo inspirado em Capture the Flag. A referência a Capture the Flag descreve a experiência competitiva, não uma implementação literal das regras tradicionais. **[DECIDIDO]**

O jogador acompanha unidades (cavaleiros e outras personagens) que combatem e avançam automaticamente segundo as regras da simulação — sem microgestão individual. O objetivo é conquistar uma taça ou outro prémio, utilizando decisões estratégicas simples (quando pedir/usar impulsos, que recompensa escolher) e desafios educativos (letras, contagem, somas e subtrações simples) que proporcionam vantagens reais na batalha. A aprendizagem é uma mecânica de jogo, não uma interrupção: cada resposta correta tem uma consequência visível que a criança compreende e associa à sua ação; cada erro é tratado sem penalização desproporcionada, com pista, nova tentativa ou reaparição posterior. **[DECIDIDO — núcleo a validar no protótipo]**

A experiência poderá decorrer em diferentes mundos — castelo, montanha, gruta, barcos/lago, nível da baleia, praça — mantendo a mecânica principal reconhecível e variando cenário, adversários e prémios. Os mesmos cavaleiros poderão acompanhar a criança ao longo dos níveis, preservando continuidade e identidade do jogador; está por definir se terão atributos persistentes, consistência apenas visual ou evolução entre níveis. A progressão por níveis (sequencial e/ou com escolha de cenários) deve dar sensação de aventura sem obrigar a reaprender as regras. **[EM EXPLORAÇÃO]**

A baleia é a proposta de boss para o nível aquático: presença central com jatos de água, capacidade de puxar unidades para baixo (animação expressiva de perigo) e apoio de criaturas marinhas auxiliares (raias, peixes) que atrasam, desviam ou neutralizam temporariamente as unidades. Os cavaleiros poderão avançar disfarçados ou parcialmente submersos (aproximação furtiva — tradução mecânica por definir). A integração educativa segue o sistema geral (desafio → impulso para recuperar terreno); a condição de vitória do nível (derrotar, ultrapassar ou neutralizar o bloqueio da baleia) está em aberto, mas o boss deve ser percetivelmente mais desafiante sem exigir um novo conjunto de regras. **[EM EXPLORAÇÃO]**

As unidades entram em campo até uma eventual capacidade definida, avançam, combatem e podem ser derrotadas ou retiradas temporariamente — com representação visual do regresso à posição inicial, recuperação ou substituição. A proposta atual favorece a derrota temporária (regresso à batalha) por ser mais simples e menos frustrante; o regresso automático, o tempo de recuperação e a substituição estão por decidir. Classes futuras (ex.: resistente vs. rápida, com diferenças de resistência/velocidade/ataque) são previstas na arquitetura mas não aprovadas. **[EM EXPLORAÇÃO]**

As espadas e os escudos — associados a um castelo ou gruta com casa/fortificação dos cavaleiros — poderão ser elementos visuais, objetos conquistados, indicadores de progressão ou recompensas de nível que integram a progressão visual dos cavaleiros; está por decidir se têm efeitos mecânicos permanentes ou são apenas visuais. A estrutura da partida mantém-se reconhecível em todos os temas. Para além da taça (com animação, celebração, ecrã de vitória e coleção), o catálogo de recompensas inclui sumo, chocolate, doces, roupas e fantasias, possivelmente via loja/praça/personalização e com escolha pela criança — a introduzir após validação do núcleo. **[EM EXPLORAÇÃO]**

A narrativa (cavaleiros a viajar entre mundos/épocas/realidades, possivelmente conduzidos por um feiticeiro) permanece aberta: identidade do feiticeiro, lógica das viagens, motivação dos confrontos, relação entre cenários e história da baleia são oportunidades de desenvolvimento posterior, não requisitos atuais. **[POR VALIDAR]**

A prioridade continua a ser validar um nível jogável (cenário de castelo, single-player, adversário simulado, poucas unidades, 1–2 impulsos, ativação automática + por iniciativa da criança, indicador visual de vantagem, taça como recompensa) que combine batalha legível, progressão visual, desafios educativos integrados e recompensas concretas — medido pelos vetores de otimização (diversão e compreensão primeiro; impacto educativo e dificuldade dinâmica depois; arquitetura temática e expansão de recompensas por último). Os novos temas, os bosses, as classes de unidades e a narrativa deverão expandir essa base, e não obrigar a criar um sistema de jogo inteiramente diferente para cada cenário. **[DECIDIDO — faseamento]**
