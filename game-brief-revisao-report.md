# Relatório de Revisão — `game-brief-revised-en.md` vs `game-brief-revisto.md`

Data: 2026-10-30
Ficheiro fonte (verdade): `game-brief-revisto.md` (~1034 linhas, pt-PT)
Ficheiro revisto/corrigido: `game-brief-revised-en.md` (~1036 linhas, en-GB)
Âmbito: revisão integral secção a secção, correção do EN e validação final.

## 1. Metodologia

1. **Leitura integral** dos dois ficheiros, do início ao fim (cabeçalho, notas, índice, secções 1–20).
2. **Comparação estrutural automatizada** (via script): contagem de títulos `##` (23) e `###` (53), linhas de tabela (59), bullets `*` (110), listas numeradas (62), blocos de citação e requisitos `FR-**` (22) em ambos os ficheiros.
3. **Comparação terminológica automatizada**: contagem de etiquetas de estado (`[DECIDIDO]`/`[DECIDED]` etc.), termos nucleares (impulsos→boosts, taça→trophy, cavaleiros→knights, espadas/escudos, baleia→whale, feiticeiro→wizard, exemplos 2+3, Bluey, Peppa Pig, LEGO, Minecraft) e deteção de resíduos de português e de inconsistências ortográficas (en-US vs en-GB) no ficheiro EN.
4. **Comparação semântica manual** secção a secção (1–20 + front matter): completude de parágrafos, bullets, exemplos, tabelas, notas de integração/revisor e fidelidade das nuances (derrota temporária vs permanente, boss baleia com 3 ataques, narrativa do feiticeiro, bloqueio temporário da vitória, etc.).
5. **Correção direta** do ficheiro EN e **re-verificação** automatizada pós-correção (resíduos = 0, âncoras do índice consistentes com os títulos).

## 2. Tabela comparativa por secção

| Secção | Estado PT | Estado EN | Observações |
|---|---|---|---|
| Cabeçalho (título + resumo de integração) | Completa | Fiel | Tradução equivalente; EN mantém referência `game-brief.txt` / adenda 20–28 e FR-13–FR-22. |
| Nota sobre a numeração + tabela de correspondência | Completa | Fiel após correção | 1 divergência média: "cenários" traduzido como "scenery changes" (falso amigo) na linha da secção 12 — corrigido para "setting changes". Restante tabela 1:1. |
| Convenção de estado | Completa | Fiel (+1 adição intencional) | EN acrescenta nota explicativa de mapeamento `[DECIDIDO]→[DECIDED]` etc. (linha 37). Adição útil de rastreabilidade, não é omissão nem erro; explica +1 em cada contagem de etiquetas e +1 blockquote. |
| Índice (1–20) | Completa | Fiel após correção | 20 entradas 1:1; âncoras em inglês coerentes com os títulos EN. 2 âncoras corrigidas (`optimisation-vectors`, `setting-changes`). |
| 1. Resumo executivo | Completa | Fiel após correção | 6 blocos + 6 bullets + princípio fundamental, todos presentes. Removidos 2 resíduos PT (`(1.º ano)`, `(taça)`). |
| 2. Conceito central do jogo | Completa | Fiel | Tabela de 3 conceitos, clarificação Capture the Flag e nota de ondas vs simulação contínua preservadas. |
| 3. Público-alvo e princípios de design | Completa | Fiel | 4 bullets de público + 7 princípios (A–G) equivalentes. |
| 4. Direção artística e identidade visual | Completa | Fiel | Direções A (Bluey/Peppa Pig) e B (LEGO/Minecraft), hipótese de independência mecânica, questão por validar e recomendação de faseamento preservadas. |
| 5. Temas, cenários e níveis (base original) | Completa | Fiel após correção | Temas A–D + tabela de reutilização + nota de integração §13 presentes. Removidos 2 resíduos (`(praça)`, `(sumo)`); "square" = tradução correta de "praça". |
| 6. Loop principal de jogabilidade | Completa | Fiel | 9 passos do loop, papel da simulação (6 bullets) e nota de integração §15 presentes. |
| 7. Mecânica educativa | Completa | Fiel | Objetivo, catálogo (letras + aritmética + outros), formatos, exemplo 2+3 com opções 4/5/6, Modos A/B, 6 impulsos, 4 opções de resposta errada + 2 diretrizes — tudo presente. |
| 8. Dificuldade dinâmica | Completa | Fiel | Cenários 8.1 (7 passos) e 8.2 (5 passos), distinção dificuldade vs impossibilidade/bloqueio (comparar em protótipo) e indicadores internos (4 bullets) preservados. |
| 9. Recompensas e progressão | Completa | Fiel | Taça (4 formas de apresentação), 5 recompensas adicionais (sumo→juice, chocolate, doces, roupas, fantasias), escolha do prémio + distinção 2 mecânicas + faseamentos presentes. |
| 10. Vetores de otimização | Completa | Fiel após correção | Tabela de 10 vetores 1:1 + 5 prioridades. Ortografia `optimization`→`optimisation` (6 ocorrências, incl. âncora). |
| 11. Âmbito do primeiro protótipo | Completa | Fiel | Tabela de 12 funcionalidades 1:1; corte a meio de frase + nota do revisor preservados e assinalados. |
| 12. Progressão entre níveis | Completa | Fiel após correção | 12.1–12.3 presentes (níveis, continuidade dos cavaleiros, feiticeiro como elemento narrativo). "scenery"→"setting" no título; removido resíduo `(gruta)`. |
| 13. Catálogo consolidado de temas | Completa | Fiel | Tabela de 6 temas (castelo, montanha, gruta, barcos/lago, baleia, praça) com conceitos, elementos e estados 1:1; nota anti-duplicação presente. |
| 14. A baleia como boss | Completa | Fiel | Conceito, ambiente/progressão furtiva (por validar), 3 ataques (jatos de água, puxar pelos pés, criaturas auxiliares — raias/peixes), integração educativa como reutilização (decidido), condição de vitória em aberto — tudo preservado. |
| 15. Unidades, classes e simulação | Completa | Fiel | Não-controlo individual (decidido), capacidade/circulação, derrota temporária vs perda permanente (proposta atual sem decisão definitiva), classes futuras não aprovadas — preservados. |
| 16. Espadas, escudos e recompensas | Completa | Fiel | 4 papéis possíveis, recompensa de nível, efeitos mecânicos por validar, preservação da mecânica (decidido) — presentes. |
| 17. Notas de narrativa | Completa | Fiel após correção | Viagem entre realidades, continuidade, 5 questões em aberto para o próximo agente + prioridade (decidido). Removidos 2 resíduos `(feiticeiro)`; "wizard" = tradução correta. |
| 18. Requisitos funcionais (FR-01–FR-22) | Completa | Fiel | 22/22 requisitos presentes; nota de origem (FR-01–FR-12 reconstruídos, FR-13–FR-22 transcrição) e origens por parágrafo (§§) preservadas. |
| 19. Decisões pendentes | Completa | Fiel | 11 pontos do original + 10 da adenda, todos presentes com referências (§) corretas. |
| 20. Síntese para o próximo agente | Completa | Fiel | 8 parágrafos 1:1, incluindo núcleo por validar, 6 mundos, baleia, unidades, espadas/escudos, narrativa aberta e faseamento (decidido). |

## 3. Divergências encontradas (antes da correção)

**Críticas: 0.** Nenhuma secção, parágrafo, tabela, bullet, exemplo, requisito FR-01–FR-22, decisão pendente ou etiqueta de estado em falta. Contagens estruturais idênticas (títulos 23/53, tabelas 59, bullets 110, numeradas 62, FRs 22, etiquetas 47/41/21 PT = 47/41/21 EN em conteúdo — o +1 aparente no EN deve-se apenas à nota explicativa de mapeamento, que cita as 3 etiquetas).

**Médias: 1 tipo (3 ocorrências).**

| # | Divergência | Local (EN, antes) | Impacto |
|---|---|---|---|
| M1 | "cenários" traduzido como **"scenery changes"** (falso amigo; *scenery* = paisagem, não "cenário de jogo") | Tabela de correspondência (L16), índice + âncora (L54), título §12 (L634) | Terminologia errada em 3 pontos de navegação; o resto do documento usa "setting(s)" (~20x). Sem perda de conteúdo, mas inconsistente num conceito nuclear. |

**Menores: 3 tipos (~22 ocorrências).**

| # | Divergência | Local (EN, antes) | Impacto |
|---|---|---|---|
| m1 | **Resíduos bilingues** entre parênteses: `(1.º ano)` (L68), `(taça)` (L72), `(praça)` (L267), `(sumo)` (L269), `(gruta)` (L646), `(feiticeiro)` (L674, L861) — 7 ocorrências | §§ 1, 5.4, 12.1, 12.3, 17.1 | Ruído de tom impróprio num PRD em inglês; inconsistentes (a maioria dos termos já estava traduzida sem glosa). |
| m2 | **Ortografia americana misturada** num documento de resto britânico (`defence` 14x, `behaviour` 5x, `colour` 4x, `catalogue` 9x, `travelling`, `favour` 8x, `practising`): `optimization` 6x (L4, L52×2, L560, L564, L1036), `customization` 6x (L539, L601, L935, L937, L1002, L1032), `organization` 1x (L291), `customizing` 1x (L552) — 14 ocorrências | §§ 10 (título/âncora), 10.1, 18, 19, 20, cabeçalho | Inconsistência de registo. (Nota: "Tower Defense" mantido — é nome próprio do género.) |
| m3 | **"A juice"** (substantivo incontável com artigo) + inconsistência com a lista de §9.2 ("Juice.") | §5.4 (L269, mesma linha de m1) | Gramática/consistência interna. PT "Um sumo" está corretamente vertido como "Juice". |

## 4. Correções aplicadas ao ficheiro EN

Todas as edições foram intra-linha (sem alterar a numeração de linhas):

| Correção | Secção | Linha(s) EN |
|---|---|---|
| `scenery changes` → `setting changes` (3x) | Nota de numeração, índice, §12 | 16, 54, 634 |
| `scenery-changes` → `setting-changes` (âncora do índice) | Índice | 54 |
| Removido ` (1.º ano)` | §1 | 68 |
| Removido ` (taça)` | §1 | 72 |
| Removido ` (praça)` | §5.4 | 267 |
| `A juice (sumo).` → `Juice.` | §5.4 | 269 |
| Removido ` (gruta)` | §12.1 | 646 |
| Removido ` (feiticeiro)` (2x) | §12.3, §17.1 | 674, 861 |
| `optimization` → `optimisation` (6x, incl. âncora `#10-product-optimisation-vectors`) | Cabeçalho, índice, §10, §20 | 4, 52, 560, 564, 1036 |
| `customization` → `customisation` (6x) | §§ 9.2, 9.3, 10.1, 18, 19, 20 | 539, 601, 935, 937, 1002, 1032 |
| `organization` → `organisation` (1x) | §5.5 | 291 |
| `customizing` → `customising` (1x) | §9.3 | 552 |

**Verificação pós-correção:** resíduos PT = 0, `scenery`/`optimization`/`customization`/`organization` = 0, `Tower Defense` (nome próprio) intacto (7x), âncoras do índice (`#10-product-optimisation-vectors`, `#12-progression-between-levels-and-setting-changes`) coincidentes com os títulos, fidelidade terminológica confirmada (boosts 31 = impulsos 31; trophy 27 = taça 27; knights 32 = cavaleiros 32; Bluey/Peppa/LEGO/Minecraft/2+3 1:1).

## 5. Veredicto final

**A versão inglesa está validada: é fiel e completa.** Após as correções acima, o `game-brief-revised-en.md` reproduz integralmente o `game-brief-revisto.md`:

- Todas as secções (1–20), parágrafos, bullets, exemplos, tabelas e notas presentes, sem omissões.
- FR-01 a FR-22 todos presentes e fiéis, com notas de origem e referências (§§) preservadas.
- Decisões pendentes (11 + 10), síntese, pontos em aberto e vetores de otimização sem omissões.
- Etiquetas de estado corretamente mapeadas em todo o documento: `[DECIDIDO]→[DECIDED]`, `[EM EXPLORAÇÃO]→[IN EXPLORATION]`, `[POR VALIDAR]→[TO VALIDATE]`.
- Nomes próprios, exemplos (2+3, Bluey, LEGO, etc.) e nuances (derrota temporária vs permanente, baleia com 3 ataques, espadas/escudos, narrativa do feiticeiro, bloqueio temporário da vitória) preservados.
- Tom e terminologia consistentes e adequados a PRD em inglês (en-GB; "Tower Defense" preservado como nome próprio do género); estrutura Markdown, hierarquia, numeração e tabelas equivalentes.
- Nada falta. Nenhum novo brief foi criado; apenas revisão, correção e este relatório.
