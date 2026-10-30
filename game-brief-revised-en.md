# REVISED FINAL GAME BRIEF — Educational Tower Defense (Single-Player, 6 years old)

> Full integration of `game-brief.txt` (original brief) + `game-brief-adenda.txt` (addendum, sections 20–28, FR-13–FR-22).
> All content was originally in Portuguese (pt-PT). No detail has been removed: decisions, ideas under exploration, open points, optimisation vectors, functional requirements, themes, mechanics, whale boss, units, swords/shields, narrative and synthesis for the next agent have been preserved.

## Note on numbering (approach adopted)

- The original brief was numbered from **1 to 11**.
- The addendum was numbered from **20 to 28** (sections) and **FR-13 to FR-22** (functional requirements).
- **Approach adopted: continuous renumbering.** Sections 20–28 of the addendum were renumbered to **12–20**, keeping the content and titles unchanged. The body of the text preserves the logical order: original base first (1–11), addendum expansions afterwards (12–20).
- Correspondence table:

| Numbering in this document | Origin |
|---|---|
| 1–11 | `game-brief.txt`, sections 1–11 (original numbering preserved) |
| 12 | Addendum section 20 — Progression between levels and setting changes |
| 13 | Addendum section 21 — New level themes |
| 14 | Addendum section 22 — The whale as boss |
| 15 | Addendum section 23 — Units, classes and automatic simulation |
| 16 | Addendum section 24 — Swords, shields and level rewards |
| 17 | Addendum section 25 — Narrative notes and transition between worlds |
| 18 | Addendum section 26 — Functional requirements (consolidated FR-01–FR-22; see own note in section 18) |
| 19 | Addendum section 27 — Pending decisions (consolidated with those from the original) |
| 20 | Addendum section 28 — Updated synthesis for the next agent (expanded) |

- Requirements **FR-13–FR-22 keep their original identifiers** from the addendum. Requirements **FR-01–FR-12 did not exist with that numbering in the original** — they were **reconstructed from the minimum features and mechanics described in the original** (§§ 2, 6, 7, 8, 9, 11) and are marked as such in section 18, subject to confirmation.
- Where the original text ended in the middle of a sentence (§ 11), the cut was preserved and marked with `[original text interrupted here]`.

## Status convention

To maintain the separation required by the brief between decided, under exploration and to be validated, each relevant block ends with a label:

- **[DECIDED]** — closed point / guideline assumed by the concept.
- **[IN EXPLORATION]** — proposed idea (by the child or as a design hypothesis from the father) still without a decision.
- **[TO VALIDATE]** — hypothesis that must be tested in a prototype before becoming a requirement.

> **Tag-mapping note:** in the original Portuguese version these tags were **[DECIDIDO]**, **[EM EXPLORAÇÃO]** and **[POR VALIDAR]**, respectively. They have been translated consistently throughout this document as **[DECIDED]**, **[IN EXPLORATION]** and **[TO VALIDATE]**. The meaning and usage are unchanged.

When the original or the addendum already indicated the status explicitly, that status was kept. When the status is inferred, the label reflects the original wording ("hypothesis", "possibility", "not yet decided", "needs to be explored", etc.).

## Table of Contents

1. [Executive summary](#1-executive-summary)
2. [Core game concept](#2-core-game-concept)
3. [Target audience and design principles](#3-target-audience-and-design-principles)
4. [Art direction and visual identity](#4-art-direction-and-visual-identity)
5. [Themes, settings and levels (original base)](#5-themes-settings-and-levels-original-base)
6. [Main gameplay loop](#6-main-gameplay-loop)
7. [Educational mechanic: challenges that grant boosts](#7-educational-mechanic-challenges-that-grant-boosts)
8. [Dynamic difficulty and moments of educational intervention](#8-dynamic-difficulty-and-moments-of-educational-intervention)
9. [Rewards and progression](#9-rewards-and-progression)
10. [Product optimisation vectors](#10-product-optimisation-vectors)
11. [Suggested scope for the first prototype](#11-suggested-scope-for-the-first-prototype)
12. [Progression between levels and setting changes](#12-progression-between-levels-and-setting-changes)
13. [Consolidated catalogue of level themes](#13-consolidated-catalogue-of-level-themes)
14. [The whale as boss](#14-the-whale-as-boss)
15. [Units, classes and automatic simulation](#15-units-classes-and-automatic-simulation)
16. [Swords, shields and level rewards](#16-swords-shields-and-level-rewards)
17. [Narrative notes and transition between worlds](#17-narrative-notes-and-transition-between-worlds)
18. [Consolidated functional requirements (FR-01–FR-22)](#18-consolidated-functional-requirements-fr-01fr-22)
19. [Consolidated pending decisions](#19-consolidated-pending-decisions)
20. [Synthesis for the next agent](#20-synthesis-for-the-next-agent)

---

## 1. Executive summary

The idea is to create a single-player game for a 6-year-old child, in the first year of schooling, that combines Tower Defense mechanics with the feeling of competition and progression of Capture the Flag. **[DECIDED]**

The game should be fun, visually appealing and simple enough for a child of this age to understand. At the same time, it should incorporate educational challenges that directly influence the course of the match. **[DECIDED — guideline]**

The differentiating idea is that learning is not an activity separated from the game. Instead, solving small educational challenges provides concrete advantages within the game, such as reinforcing defences, gaining speed, overtaking the opponent or conquering the trophy. **[DECIDED — differentiating principle]**

The intended result is not just a Tower Defense with educational elements. It is a game in which the child feels that they are competing, making decisions and trying to conquer a prize, while practising age-appropriate skills. **[DECIDED — experience intent]**

The concept should be flexible enough to support different visual themes, characters, settings and rewards, while keeping a common base of mechanics. **[DECIDED — architecture guideline]**

### 1.1. Product vision

To create an accessible strategy game, with adorable characters, clear objectives, visual progression and educational challenges integrated into the gameplay. **[DECIDED]**

The child should be able to:

* Quickly understand the objective of each match.
* Perceive whether they are winning, losing or close to winning.
* Make simple decisions that influence the outcome.
* Solve educational challenges to obtain advantages in the game.
* Feel that their knowledge and decisions contribute to victory.
* Receive concrete and visually appealing rewards.

### 1.2. Fundamental principle

Learning must be a game mechanic, not an interruption of the game experience. **[DECIDED]**

Educational challenges must have perceptible consequences in the game world. A correct answer should provide an advantage that the child can understand, observe and associate with their action. **[DECIDED]**

---

## 2. Core game concept

### 2.1. Genre and mechanics

The game combines three concepts: **[DECIDED]**

| Concept | Role in the game |
|---|---|
| Tower Defense | Strategic base: defending a position, managing units and resisting attacks. |
| Capture the Flag | Competitive objective: advancing to conquer the opponent's objective before they manage to win. |
| Educational Game | Educational layer: solving challenges to obtain strategic advantages. |

The reference to Capture the Flag describes above all the experience and the competitive objective, not necessarily a literal implementation of the traditional rules of that genre. **[DECIDED — clarification]**

The game should be single-player. Competition can be simulated through an opponent controlled by the game, with no need for multiplayer. **[DECIDED]**

### 2.2. The intended experience

The child observes a battle between two forces.

They must protect their position, overcome the opposing defences and approach a final objective, such as a large trophy.

Throughout the match, the situation evolves. The child can visually perceive who has the advantage and whether victory is near.

When they need help to turn around an unfavourable situation, or when they are about to conquer the prize, educational challenges may appear that allow them to obtain a boost.

The match ends when one of the forces manages to reach the objective defined for the level.

The reward can be a trophy, a special object or another conquest appropriate to the theme.

> **Design note:** it is not yet decided whether the game will take place in discrete waves, with pauses between them, or as a continuous simulation. This decision should remain open during the initial prototyping phase. **[TO VALIDATE]**

---

## 3. Target audience and design principles

### 3.1. Initial target audience **[DECIDED]**

* Children of approximately 6 years old.
* Children in the first year of schooling.
* Players with limited ability to interpret complex interfaces and abstract strategic rules.
* Players who benefit from immediate visual feedback and concrete objectives.

The game will initially be designed for one child, although it may later be adapted to other ages.

### 3.2. Design principles **[DECIDED — as guidelines]**

**A. Clarity**

The child must understand what is happening without needing to read long instructions.

**B. Visual feedback**

Each side's advantage must be visible through the positions of the units, progress in the setting and proximity to the objective.

**C. Concrete rewards**

Victories must produce outcomes that the child understands: winning a trophy, unlocking an element or choosing a reward.

**D. Integrated learning**

Educational questions must have consequences in the battle, avoiding the feeling that the child was taken out of the game to do a school exercise.

**E. Autonomy**

The child should have opportunities to decide when to use certain boosts, rather than relying exclusively on automatic interventions by the game.

**F. Adaptable difficulty**

The game must be able to create challenging situations without making the experience frustrating or requiring the child to understand complex strategic systems.

**G. Thematic flexibility**

Visual and narrative themes may vary without forcing the entire game logic to be rebuilt.

---

## 4. Art direction and visual identity

Two main visual references were identified, which do not need to be mutually exclusive. **[DECIDED]**

### 4.1. Direction A — Cute and colourful characters **[IN EXPLORATION]**

Style references: the visual simplicity and friendly character of children's series such as Bluey and Peppa Pig.

Intended characteristics:

* Expressive and friendly characters.
* Rounded shapes.
* Vivid colours.
* Easy-to-interpret animations.
* Welcoming and imaginative settings.
* Conflicts presented in a playful way, without graphic violence.

These references serve only to communicate the intended art direction, not to reproduce characters, graphic assets or third-party intellectual property.

### 4.2. Direction B — Stylized construction **[IN EXPLORATION]**

Style references: the visual language of LEGO and Minecraft.

Intended characteristics:

* Simple geometric shapes.
* Objects that look built from blocks.
* Modular settings.
* Easy-to-recognize elements.
* Potential to build, modify or expand structures.
* Simple and legible visual identity.

Here too the intent is stylistic inspiration, not a copy of the referenced games or brands.

### 4.3. Visual architecture decision

An important hypothesis is to keep the core mechanic independent of the art direction. **[IN EXPLORATION — architecture hypothesis]**

Thus, the same game system could support:

* A version with cute characters and colourful settings.
* A version with building blocks and geometric structures.
* Other future themes, if the concept justifies that expansion.

It is not yet decided whether these directions will be presented as themes within the same game or as distinct games sharing the same technical base. **[TO VALIDATE]**

Initial recommendation: prototype first a single art direction. The second should be added when the core mechanic is sufficiently validated. **[DECIDED — phasing recommendation]**

---

## 5. Themes, settings and levels (original base)

The conversation suggests that each level may introduce a different theme, while keeping the fundamental rules of the game. **[IN EXPLORATION]**

Themes may change the setting, characters, structures, visual objective and rewards, without necessarily changing the core mechanic. **[DECIDED — principle]**

### 5.1. Theme A — Castles and knights **[DECIDED as initial concept; details TO VALIDATE]**

Possible elements:

* Two castles or opposite positions.
* A queen or other characters.
* Knights.
* Swords and shields.
* A large trophy as the final objective.
* A visually simple and fun battle.

This theme constitutes one of the first ideas presented by the child.

### 5.2. Theme B — Boats and lake **[IN EXPLORATION]**

Possible elements:

* A lake.
* Boats on each side.
* Characters fighting.
* Swords and other visual elements adapted to the setting.
* An objective or prize located next to one of the boats or in a central zone.

The original idea included boats, a lake, a battle and a special trophy.

The exact implementation is still to be defined. **[TO VALIDATE]**

### 5.3. Theme C — Mountains **[IN EXPLORATION]**

The possibility of creating a Tower Defense level in a mountain environment was suggested.

This setting could use the same defence and progression system, but with a distinct visual environment.

### 5.4. Theme D — Square, knights and rewards **[IN EXPLORATION]**

Another idea involves knights in a square and rewards such as:

* Juice.
* A chocolate.
* A sweet/candy.
* Clothing or a costume.

In this context, the prize can be presented as something the character receives or chooses after winning.

### 5.5. Reuse principle **[DECIDED — as principle; table below is a proposal, not a final definition]**

Themes should be treated, whenever possible, as configurations of the same game structure.

For example:

| Element | Castle theme | Lake theme |
|---|---|---|
| Position to protect | Castle | Boat or position by the lake |
| Units | Knights | Characters or thematic units |
| Progression | Advance towards the opposing castle | Advance towards the opposing objective |
| Final objective | Conquer the trophy | Conquer the trophy |
| Educational boosts | Defence or attack improvements | Improvements adapted to the setting |
| Reward | Trophy or prize | Trophy or prize |

This table is a proposal for organisation, not a final definition of the mechanics of each theme.

> **Integration note:** the theme catalogue was extended by the addendum (detailed mountain, cave, whale/boss, aquatic environment). See section 13 (consolidated catalogue). This section preserves the original state of the ideas.

---

## 6. Main gameplay loop

The main loop should be simple enough for a child to understand and flexible enough to accommodate educational challenges. **[DECIDED — guideline]**

### 6.1. Proposed loop **[IN EXPLORATION — initial hypothesis to validate in prototypes]**

1. Start a level. The child encounters a setting, an opponent and a clear objective.
2. Observe the battle. Units advance, attack and defend.
3. Track progress. The child can perceive which side has the advantage.
4. React to a situation. The game may introduce an opportunity or need to obtain a boost.
5. Solve an educational challenge. The child answers a question or completes a simple activity.
6. Receive a boost. A correct answer provides an advantage within the battle.
7. Continue the match. The advantage obtained changes the state of the game.
8. Conquer the objective. The child wins the match by fulfilling the victory condition.
9. Receive a reward. The game presents the trophy or other prize associated with the level.

This loop is an initial design hypothesis and should be validated through prototypes. **[TO VALIDATE]**

### 6.2. The role of simulation

One of the most important points of the conversation is that the game should not be merely an automatic simulation of a funny battle. **[DECIDED]**

The simulation must convey a real sense of competition and progress.

The child needs to perceive that:

* Things are happening.
* The opponent represents a challenge.
* Their actions can change the outcome.
* They may be close to winning or losing.
* There is a reason to make decisions.
* Victory depends, at least in part, on their choices and learning.

The balance between automatic simulation and direct control by the child still needs to be explored. **[TO VALIDATE]**

> **Integration note:** the addendum clarifies that units **are not controlled individually** — they are simulation units and the child decides at the game level (boosts, strategic elements). See section 15.

---

## 7. Educational mechanic: challenges that grant boosts

This is one of the most important and differentiating features of the concept. **[DECIDED]**

### 7.1. Objective

To integrate small educational activities into the progression of the battle, so that the child can use the knowledge they are developing at school to obtain concrete advantages. **[DECIDED]**

Challenges should be appropriate for the first year of schooling. **[DECIDED]**

### 7.2. Types of challenge considered **[IN EXPLORATION — non-closed catalogue]**

**Letters and early reading**

* Recognizing a letter.
* Identifying a letter shown on the screen.
* Choosing the letter that corresponds to a question.
* Distinguishing visually similar letters, when appropriate.

**Basic arithmetic**

* Counting objects.
* Solving simple additions.
* Solving simple subtractions.
* Choosing the correct result from a few options.

**Other simple concepts**

Other age-appropriate content may be added in the future, provided it is compatible with the pace of the game.

There is no need to decide now the complete catalogue of challenges. **[TO VALIDATE]**

### 7.3. Challenge format **[IN EXPLORATION]**

Formats similar to the following were considered:

* Flashcards.
* Minicards.
* Small minigames.

A card may present a question, an image and several possible answers.

For example:

Question: What is 2 + 3?

* 4
* 5
* 6

By answering correctly, the child receives a boost that changes the battle.

This is only an illustrative example, not a decision on the final interface format. **[TO VALIDATE]**

### 7.4. Challenges can appear in two ways **[IN EXPLORATION — hypothesis to validate; prototype should include both if feasible]**

**Mode A — Automatic challenge**

The game spontaneously presents an educational challenge at a specific moment of the match.

For example:

* When the defence starts to give way.
* When the opponent has the advantage.
* When an opportunity arises to upgrade a unit.
* When the child approaches the final objective.

**Mode B — Child-initiated challenge**

The child may decide to use an educational challenge to try to obtain an advantage.

For example, they may choose to try to solve a sum to reinforce their defences or accelerate the advance of their units.

This option introduces a strategic decision: using the boost at the present moment or continuing the battle without resorting to it.

### 7.5. Relationship between answer and consequence **[IN EXPLORATION]**

A correct answer should have a clear consequence in the game. **[DECIDED — principle]**

Possible rewards:

* Reinforcing a defence.
* Temporarily increasing the strength of a unit.
* Accelerating the advance.
* Gaining time.
* Recovering an unfavourable position.
* Obtaining a decisive advantage near the final objective.

The exact relationship between each type of challenge and each boost is still to be defined. **[TO VALIDATE]**

### 7.6. What happens when the answer is wrong? **[TO VALIDATE — open]**

This point remains open.

Some options to test:

* The child does not receive the boost, but can continue playing.
* They receive a hint and have the opportunity to try again.
* The game presents the correct answer in a simple way.
* The challenge reappears later, allowing them to practise again.

The experience must not turn a mistake into a disproportionate penalty. **[DECIDED — guideline]**

The objective is to create a positive association between learning, trying again and improving performance in the game. **[DECIDED — guideline]**

---

## 8. Dynamic difficulty and moments of educational intervention

The father introduced a particularly important requirement: difficulty should not be merely a passive consequence of the state of the game. **[DECIDED — requirement]**

The system should be able to create situations in which educational challenges become relevant to progression. **[DECIDED — intent]**

### 8.1. Difficulty above the character's current capability **[IN EXPLORATION — hypothesis]**

One possibility is that, at certain moments, the battle situation becomes too difficult for the child's current configuration.

This creates a need to resort to an educational boost.

For example:

1. The child is defending the castle.
2. The opponent starts gaining ground.
3. The existing defence is no longer sufficient.
4. An opportunity arises to obtain a boost through an educational challenge.
5. The child solves the challenge.
6. The boost improves the battle situation.
7. The child feels once again that they have a chance of winning.

Difficulty thus serves to give relevance to learning.

### 8.2. Intervention near victory **[IN EXPLORATION — hypothesis]**

The same logic could be used when the child is about to win.

For example:

1. The child approaches the trophy.
2. The opponent manages to create a final obstacle.
3. The child needs an additional advantage.
4. An educational challenge appears.
5. By solving it, they receive the boost needed to conquer the prize.

The intent is for learning to be part of the most important moments of the match.

### 8.3. Distinction between difficulty and impossibility **[TO VALIDATE — compare both approaches in prototyping]**

It is important to distinguish a challenging situation from a situation in which victory is artificially blocked.

The idea discussed includes the possibility of the mechanic temporarily preventing victory until an opportunity arises to solve an educational challenge.

This approach needs to be explored carefully.

If the game repeatedly prevents a victory that the child considers deserved, it may seem unfair or unpredictable.

An alternative is to create situations in which the educational challenge represents a real opportunity to overcome an obstacle, without making a correct answer mandatory for every victory.

These two approaches should be compared during prototyping.

### 8.4. The child does not need to know the internal numbers **[DECIDED — guideline]**

The system may use internal progress indicators to determine when to present a challenge.

For example, it may consider:

* Proximity to the objective.
* State of the defences.
* Relative advantage between the two sides.
* Time remaining before one side wins.

The child does not need to see percentages or technical metrics. They only need to receive simple visual signals that communicate the situation.

---

## 9. Rewards and progression

The reward is a central element of the original concept presented by the child. **[DECIDED]**

### 9.1. The trophy as main objective **[DECIDED as concept; implementation TO VALIDATE]**

The large special trophy is the first clearly identified reward.

It should function as a visual symbol of victory and level completion.

It can be presented through:

* A conquest animation.
* A celebration of the characters.
* A victory screen.
* A trophy that becomes available in the child's collection.

These are implementation possibilities to validate.

### 9.2. Additional rewards **[IN EXPLORATION — do not implement all in the first prototype]**

Concrete rewards were mentioned, such as:

* Juice.
* Chocolate.
* Sweets/candy.
* Clothes.
* Costumes.

These rewards can be represented within the game, for example through a shop, a square or a customisation system.

There is no need to implement all of them in the first prototype. **[DECIDED — phasing]**

### 9.3. Choice of reward **[IN EXPLORATION]**

One possibility is to allow the child to choose the prize after winning.

This adds a small decision to the experience and may reinforce the sense of autonomy.

However, it is important to distinguish two different mechanics:

* The reward that marks victory.
* The reward that allows customising or evolving the character.

The first prototype may be limited to the trophy, adding other rewards later. **[DECIDED — phasing]**

> **Integration note:** the addendum adds thematic rewards per level (swords, shields and other theme elements). See section 16 and FR-22.

---

## 10. Product optimisation vectors

This section identifies the criteria that should guide design and development decisions. **[DECIDED — as evaluation framework]**

They are not already-validated requirements. They are optimisation hypotheses that must be turned into observable criteria during testing.

| Vector | Objective | How to evaluate |
|---|---|---|
| Fun | The child wants to keep playing. | Interest, engagement and willingness to repeat. |
| Comprehension | The child perceives the objective and the state of the battle. | Ability to explain what is happening. |
| Agency | The child's actions influence the outcome. | Ability to associate decisions with consequences. |
| Learning | Challenges help practise school skills. | Performance on challenges and retention in later attempts. |
| Pedagogical integration | Challenges feel like part of the game. | Child's reaction to challenges and continuity of engagement. |
| Balance | The game is challenging without being excessively frustrating. | Frequency of victories, defeats and requests for help. |
| Visual clarity | The state of the game is understandable without extensive explanations. | Ability to identify who has the advantage. |
| Autonomy | The child can make simple decisions. | Voluntary use of boosts and reward choices. |
| Reuse | New themes can be added without rebuilding the mechanic. | Effort required to implement a new setting. |
| Technical simplicity | The prototype allows quickly testing the hypotheses. | Implementation time and ease of changing the rules. |

### 10.1. Suggested priorities **[DECIDED — suggested order for the first prototype]**

For the first prototype, the following order is suggested:

**Priority 1 — Validate fun and comprehension.**

The child must perceive the battle, understand the objective and want to keep playing.

**Priority 2 — Validate the impact of educational challenges.**

It is necessary to perceive whether solving a challenge and obtaining a boost creates a satisfying experience.

**Priority 3 — Validate dynamic difficulty.**

The game must be able to create moments in which educational intervention is useful, without seeming unfair.

**Priority 4 — Validate the thematic architecture.**

Only after the core mechanic works should it be necessary to invest in the possibility of reusing the system in various settings.

**Priority 5 — Expand rewards and progression.**

New prizes, customisation and progression systems can be introduced when the main experience is validated.

---

## 11. Suggested scope for the first prototype

The objective of the first prototype should not be to build the complete game. **[DECIDED]**

It should be to demonstrate that the combination of Tower Defense, visual competition and educational challenges works for the child. **[DECIDED]**

### 11.1. Minimum features **[IN EXPLORATION — initial proposal]**

| Feature | Initial proposal |
|---|---|
| Game mode | Single-player. |
| Setting | A single castle setting. |
| Opponent | Controlled by the game. |
| Units | A small set of simple units. |
| Battle mechanic | Defence and advance towards the opposing objective. |
| Objective | Conquering a trophy. |
| Progress indicator | Visual feedback on each side's advantage. |
| Educational challenges | A reduced set of questions on letters or basic arithmetic. |
| Boosts | One or two advantages associated with correct answers. |
| Challenge activation | At least one automatic opportunity and one child-initiated opportunity, if feasible. |
| Difficulty | A situation in which an educational boost helps recover an unfavourable position. |
| Reward | Simple victory animation and presentation of the trophy. |

This proposal does not imply that all features must be present in the first technical version. The final selection *[original text interrupted here]*

> **Reviewer note:** the `game-brief.txt` file ends in the middle of this sentence. The content was transcribed exactly up to the point of interruption. The final selection of features for the first technical version of the prototype is recorded as a pending decision (see section 19).

---

## 12. Progression between levels and setting changes

*(Addendum section 20. All previously recorded ideas and requirements remain; this section adds the newly discussed concepts. Ideas proposed by the child continue to be treated as important creative inputs; the father's technical interpretations are design hypotheses to validate.)*

### 12.1. Level-based progression **[IN EXPLORATION — idea proposed by the child]**

The child proposed that, after completing a level, the game advance to the next level. Moving from one level to another may also introduce a change of setting.

For example:

* The player starts in a castle.
* After winning, they advance to a new level.
* The setting changes to a mountain, a cave or another environment.
* The knights essentially remain the same.
* The competitive objective is maintained, but the visual elements, opponents and prizes may change.

The idea is to provide a sense of adventure and discovery without forcing the child to relearn all the rules in each level.

### 12.2. Character continuity **[IN EXPLORATION — important conceptual decision, details to be defined]**

An important conceptual decision is that the knights may persist across the various themes, even when the setting and visual identity change.

This allows preserving continuity of the experience.

The knights are the player's units; the different environments represent stages of a broader adventure.

It is not yet decided whether the knights will have persistent attributes, whether they will be only visually consistent, or whether they may evolve between levels. **[TO VALIDATE]**

### 12.3. Theme and visual identity changes **[IN EXPLORATION]**

Progression may alternate between different styles and environments:

* A world of castles and knights.
* A mountain setting.
* A cave.
* An aquatic environment.
* Other imaginative worlds to be defined.

The previously discussed style references remain valid: colourful children's characters, LEGO- or Minecraft-inspired block aesthetics and other age-appropriate visual variations.

The possibility was also suggested that a character, such as a wizard, could serve as a narrative element leading the knights through different eras, worlds or realities.

This idea is recorded as a narrative possibility, with no need to define the story yet. **[TO VALIDATE — see also section 17]**

---

## 13. Consolidated catalogue of level themes

*(Addendum section 21, merged with Themes A–D from section 5. Themes do not necessarily have to represent different game genres; they can be variations of the same battle system. The priority is to keep the main mechanic recognizable, introducing visual differences and specific challenges in each environment.)*

| Theme | Concept | Specific elements | Status |
|---|---|---|---|
| Castle | Battle between fortified positions. | Knights, swords, shields and trophy. (See § 5.1: two castles/opposite positions, queen or other characters, knights, swords and shields, large trophy, simple and fun battle. Child's first idea.) | Initial concept. **[DECIDED as starting point]** |
| Mountain | New battle setting. | Mountainous terrain and possible obstacles. (See § 5.3: same defence and progression system with distinct visual environment.) | Proposed idea. **[IN EXPLORATION]** |
| Cave | Battle in an enclosed environment. | A house or fortification of the knights, with swords and shields as elements of interest. | Idea under exploration. **[IN EXPLORATION]** |
| Boats and lake | Battle in an aquatic environment. | Boats, water and units adapted to the setting. (See § 5.2: lake, boats on each side, characters fighting, adapted swords, objective/prize next to a boat or central zone; special trophy. Exact implementation to be defined.) | Previously proposed idea. **[IN EXPLORATION]** |
| Whale | Aquatic level with an especially powerful opponent. | Whale, water jets, opposing fish and attacks that affect the units. | New concept developed by the child. **[IN EXPLORATION — detailed in section 14]** |
| Square, knights and rewards | Knights in a square with everyday prizes. | Juice, chocolate, sweet/candy, clothing or costume as prize received/chosen after winning. (Origin: § 5.4.) | Idea under exploration. **[IN EXPLORATION]** |

> **Integration note:** this table consolidates the original Themes A–D (§ 5) with the five themes listed in the addendum, without duplicating entries (castle, mountain and boats/lake existed in both; cave and whale are new from the addendum; square carries over from the original).

---

## 14. The whale as boss

*(Addendum section 22.)*

### 14.1. Concept **[IN EXPLORATION — new proposal from the child]**

The whale ceases to be merely a decorative element of an aquatic setting.

The new proposal is that it be a boss, that is, a particularly powerful opponent that constitutes the main challenge of one of the levels.

The whale should be a central presence in the battle, with its own attacks and behaviours.

The player continues to use the usual system of units and progression, but faces an opponent that requires more effort to overcome.

### 14.2. Environment and progression towards the whale **[IN EXPLORATION]**

The level may take place in an aquatic environment.

The knight units advance through the water or along a path associated with the setting, while the whale and other sea creatures try to prevent their progress.

The child's idea includes the possibility of the knights advancing disguised or partially submerged, creating a sense of stealthy approach to the opponent.

It is not decided how this idea will be translated into concrete mechanics. **[TO VALIDATE]**

### 14.3. Whale attacks and behaviours **[IN EXPLORATION — design proposals, effects to be defined]**

Three specific ideas were identified:

**A. Water jets**

The whale launches water jets that affect the player's units and may interrupt or hinder their advance.

**B. Pulling units by the feet**

The whale may pull the knights down, as if grabbing them from underwater.

The idea is to create a visually expressive animation that communicates that the units are in danger.

**C. Auxiliary sea creatures**

Other animals, such as rays or fish, may function as opponents associated with the whale.

These creatures may help to delay, divert or temporarily neutralize the player's units.

All these behaviours are design proposals. Their implementation and exact effects in battle are still to be defined. **[TO VALIDATE]**

### 14.4. Relationship with educational mechanics **[IN EXPLORATION — integration possibility, not a decided rule]**

The boss may use the same system of educational challenges already foreseen for the other levels.

For example, when the whale puts the units at a disadvantage, the game may present a maths or letter-recognition challenge. A correct answer may provide a boost that allows recovering ground.

This is an integration possibility, not an already-decided rule.

The whale should not necessarily require a different educational system: it may be a new application of the core mechanics. **[DECIDED — as reuse guideline]**

### 14.5. Victory condition **[TO VALIDATE — open]**

The objective of the level may be to overcome the whale, neutralize its ability to prevent the advance, or reach the objective it protects.

The exact victory condition is still open.

The most important thing is that the boss represents a perceptibly greater challenge than the usual opponents, without requiring the child to learn an entirely new set of rules. **[DECIDED — guideline]**

---

## 15. Units, classes and automatic simulation

*(Addendum section 23. Clarifies an important distinction introduced by the father.)*

### 15.1. Units are not controlled individually **[DECIDED — clarification]**

The knights and other characters participating in the battle are simulation units.

The child does not need to control each character individually.

Instead, they observe the course of the battle and make decisions at the game level, such as using educational boosts or managing other strategic elements to be defined.

Units advance, fight, retreat and are affected by opponents through the internal rules of the simulation.

The experience must convey the feeling of an ongoing battle, without requiring individual micromanagement of the characters.

### 15.2. Unit capacity and circulation **[IN EXPLORATION]**

The game may have a defined capacity of units on the field.

Units enter the battle, advance, fight and may be defeated or temporarily withdrawn.

When this happens, the simulation may visually represent their return to the starting position, recovery or replacement by another unit.

This representation is important because it allows the child to perceive that the battle is evolving and that there are consequences to events on the terrain.

### 15.3. Defeat of a unit does not necessarily mean permanent loss **[IN EXPLORATION — current proposal favours temporary defeat; no definitive decision]**

The conversation suggests that, when a knight is defeated, they may return to the start of the path or reappear later.

The intent is for the child to see the unit leaving the battle and perceive that it has temporarily stopped contributing to the advance.

It is not decided whether the unit will return automatically, whether it will need some time to recover, or whether it will be replaced by another. **[TO VALIDATE]**

The fundamental distinction is between:

* Temporary defeat: the unit stops contributing to the battle for some time, but may return.
* Permanent loss: the unit is no longer available for the rest of the match or for later levels.

The current proposal favours the first approach, as it is simpler and potentially less frustrating for the target audience.

It is not considered, however, a definitive decision on the unit system.

### 15.4. Different unit classes **[IN EXPLORATION — design possibilities, not approved classes]**

The possibility was also identified that there may be different classes of units.

These classes may have their own characteristics, such as resistance, speed or attack capability.

For example, at a future stage, the game may distinguish between more resistant units and faster units.

These examples are design possibilities, not already-approved classes.

The objective will be to introduce enough variety to make the simulation interesting, without creating excessive complexity for a 6-year-old child.

---

## 16. Swords, shields and level rewards

*(Addendum section 24. Idea suggested by the child: a level in which swords and shields take an important role, associated with a castle or a cave where the knights compete for these elements.)*

### 16.1. Role of swords and shields **[IN EXPLORATION — interpretation to be closed]**

Swords and shields may function as:

* Visual elements associated with the units.
* Objects conquered during the battle.
* Progress indicators.
* Rewards granted after winning a level.

The exact interpretation is not yet closed. **[TO VALIDATE]**

### 16.2. Specific rewards **[IN EXPLORATION]**

One possibility is that, upon winning this level, the child receives swords and shields as a reward.

These elements may then integrate the visual progression of the knights or serve as conquest indicators.

It is not decided whether they will have permanent mechanical effects or whether they will be merely visual rewards. **[TO VALIDATE]**

### 16.3. Preserving the core mechanic **[DECIDED — guideline]**

Even if a level comes to have swords and shields as central elements, the structure of the match should remain recognizable.

The player observes the battle, tracks progress, uses the available opportunities and seeks to fulfil the level objective.

A change of theme should not force redefining the entire game system.

---

## 17. Narrative notes and transition between worlds

*(Addendum section 25. The narrative does not need to be closed at this stage; ideas are recorded for the next agent.)*

### 17.1. An adventure through different realities **[IN EXPLORATION — possibility]**

One possibility is that the knights travel between different worlds, eras or environments.

A character, such as a wizard, may function as a linking element between these realities.

The transition may justify the passage from a castle to a mountain, from a cave to an aquatic setting or to any other environment to be added.

### 17.2. Continuity despite setting change **[IN EXPLORATION]**

The same knights may appear in the various levels, maintaining the player's identity.

The setting changes, but the child continues to follow the same adventure.

This approach may make progression more coherent and help the child recognize the characters from level to level.

### 17.3. Freedom to develop the narrative later **[TO VALIDATE — opportunities for the next agent]**

There is no need to decide yet:

* Who the wizard is.
* How travel between worlds works.
* Why the knights must face different opponents.
* How the various settings relate to each other.
* What the complete story of the whale is.

These elements should be passed to the next agent as opportunities for narrative development.

The priority at this stage remains defining the structure of the experience and the essential mechanics. **[DECIDED]**

---

## 18. Consolidated functional requirements (FR-01–FR-22)

> **Origin note:** the original brief did not number functional requirements; it described minimum features (§ 11.1) and mechanics (§§ 2, 6–9). FR-01–FR-12 below are **faithfully reconstructed from that text** and are subject to confirmation — they should not be read as historical numbering. **FR-13–FR-22 are literal transcription of the addendum** (section 26). These requirements are preliminary; their inclusion does not mean that all must be implemented in the first prototype.

### 18.1. Requirements from the original base (FR-01–FR-12, reconstructed)

**FR-01 — Single-player mode with simulated opponent**

The game should support a single-player mode in which the opponent is controlled by the game, with no need for multiplayer. (Origin: §§ 2.1, 11.1.)

**FR-02 — Competitive defence and advance**

The system should support defence of a position and advance of units towards the opposing objective. (Origin: §§ 2.1, 6.1, 11.1.)

**FR-03 — Visual progress/advantage indicator**

The game should present visual feedback on each side's advantage and proximity to the objective, without exposing percentages or technical metrics to the child. (Origin: §§ 3.2-B, 8.4, 11.1.)

**FR-04 — Educational challenges (letters and arithmetic)**

The game should present a set of challenges appropriate for the 1st year (letter recognition; counting, simple additions and subtractions with choice among options), in flashcard/minicard format or small minigames. (Origin: §§ 7.2, 7.3, 11.1.)

**FR-05 — Dual activation of challenges (automatic + child-initiated)**

The system should support challenges presented automatically by the game at specific moments and challenges requested by the child to try to obtain an advantage. (Origin: §§ 7.4, 11.1.)

**FR-06 — Battle boosts for correct answers**

A correct answer should produce a perceptible advantage in battle (e.g.: reinforcing defence, temporarily increasing strength, accelerating advance, gaining time, recovering an unfavourable position, decisive advantage near the objective). (Origin: §§ 7.5, 11.1.)

**FR-07 — Non-punitive treatment of wrong answers**

The system should treat wrong answers without disproportionate penalty (e.g.: no boost but game continuity; hint with new attempt; simple presentation of the answer; later reappearance of the challenge). Exact mechanism to be validated. (Origin: § 7.6.)

**FR-08 — Dynamic difficulty with educational intervention**

The system should be able to create situations in which an educational boost helps recover an unfavourable position and intervene at moments close to victory, distinguishing legitimate challenge from artificial blocking of victory. (Origin: §§ 8.1–8.3, 11.1.)

**FR-09 — Victory condition and end of match**

The match should end when one of the forces reaches the objective defined for the level (e.g.: conquering the trophy). (Origin: §§ 2.2, 6.1.)

**FR-10 — Main reward with celebration**

Victory should trigger the presentation of the trophy (conquest animation, celebration, victory screen and/or record in collection) and support the choice of prize by the child. (Origin: §§ 9.1, 9.3, 11.1.)

**FR-11 — Additional rewards and customisation (deferred)**

The architecture should foresee additional rewards (juice, chocolate, sweets/candy, clothes, costumes) represented in a shop/square/customisation system, to be introduced after validation of the main experience. (Origin: §§ 9.2, 9.3, 10.1-P5.)

**FR-12 — Reusable thematic architecture**

The core mechanic should be independent of the art direction, allowing support for distinct themes/settings (cute characters, building blocks, others) as configurations of the same system. (Origin: §§ 4.3, 5.5, 10.1-P4.)

### 18.2. Requirements from the addendum (FR-13–FR-22, transcription)

**FR-13 — Progression between levels**

The game should allow advancing to new levels after completion of previous ones.

**FR-14 — Thematic variation**

Levels may present different environments and visual identities, while keeping a common base of mechanics.

**FR-15 — Unit continuity**

The game should allow maintaining a consistent identity for the player's units across different settings, if that approach is confirmed.

**FR-16 — Automatic unit simulation**

Units should act according to the rules of the simulation, without requiring direct individual control by the child.

**FR-17 — Unit state management**

The system should represent the state of units, including their entry onto the field, participation in battle and eventual defeat or temporary withdrawal.

**FR-18 — Possibility of unit recovery**

The system may allow defeated units to return to battle, avoiding that all defeats imply permanent losses.

**FR-19 — Unit classes**

The architecture should allow introducing different classes of units, should variety of functions prove necessary.

**FR-20 — Boss fights**

The game should be able to include special opponents with behaviours distinct from common opponents.

**FR-21 — Specific boss behaviours**

A boss may have its own attacks or abilities, such as water jets, temporary capture of units or support from auxiliary creatures.

**FR-22 — Thematic rewards**

Levels may grant specific rewards, such as swords, shields or other elements associated with the respective theme.

---

## 19. Consolidated pending decisions

*(Consolidates the open points from the original with the 10 questions from addendum section 27. The next agent should consider them gradually, with priority for those influencing the central loop and technical complexity.)*

### 19.1. Open points from the original brief

1. Discrete waves with pauses vs. continuous simulation — decision to keep open in initial prototyping. (§ 2.2)
2. Art directions as themes of the same game vs. distinct games with common technical base. (§ 4.3)
3. Complete catalogue of educational challenges — do not close yet. (§ 7.2)
4. Final interface format of challenges (flashcard, minicard, minigame). (§ 7.3)
5. Exact mapping between challenge type and boost type. (§ 7.5)
6. Consequence of wrong answer (no boost / hint + new attempt / show answer / reappear later). (§ 7.6)
7. Temporary blocking of victory until the educational challenge vs. challenge as non-mandatory opportunity — compare in prototype. (§ 8.3)
8. Balance between automatic simulation and direct control by the child. (§ 6.2)
9. Concrete presentation of the trophy (animation, celebration, screen, collection). (§ 9.1)
10. Choice of prize by the child; distinction between victory reward and customisation/evolution reward. (§ 9.3)
11. Final selection of features for the first technical version of the prototype (original sentence interrupted). (§ 11.1)

### 19.2. Pending decisions added by the addendum

1. Progression: will levels be sequential or will there be choices between different settings?
2. Units: do units return automatically after being defeated?
3. Classes: what are the minimum differences between classes, should they come to exist?
4. Boss: should the whale be defeated, overtaken or merely prevented from blocking the objective?
5. Special attacks: do the whale's attacks affect health, position, speed or only the visual state of units?
6. Swords and shields: are they visual rewards, game resources or permanent upgrades?
7. Narrative: how are transitions between worlds justified?
8. Visual style: can themes alternate between very different aesthetics or should they keep a common graphic identity?
9. Difficulty: how to ensure that the unit system and bosses remain understandable for a 6-year-old child?
10. Educational integration: may educational challenges help recover units, counter special attacks or obtain advantages against bosses?

---

## 20. Synthesis for the next agent

The game is a single-player experience for a 6-year-old child (1st year of schooling), based on a battle simulation that combines Tower Defense mechanics with a competitive objective inspired by Capture the Flag. The reference to Capture the Flag describes the competitive experience, not a literal implementation of the traditional rules. **[DECIDED]**

The player follows units (knights and other characters) that fight and advance automatically according to the rules of the simulation — without individual micromanagement. The objective is to conquer a trophy or other prize, using simple strategic decisions (when to request/use boosts, which reward to choose) and educational challenges (letters, counting, simple additions and subtractions) that provide real advantages in battle. Learning is a game mechanic, not an interruption: each correct answer has a visible consequence that the child understands and associates with their action; each mistake is treated without disproportionate penalty, with a hint, new attempt or later reappearance. **[DECIDED — core to validate in the prototype]**

The experience may take place in different worlds — castle, mountain, cave, boats/lake, whale level, square — keeping the main mechanic recognizable and varying setting, opponents and prizes. The same knights may accompany the child across levels, preserving continuity and player identity; it is to be defined whether they will have persistent attributes, merely visual consistency or evolution between levels. Level progression (sequential and/or with choice of settings) should give a sense of adventure without forcing the rules to be relearned. **[IN EXPLORATION]**

The whale is the boss proposal for the aquatic level: central presence with water jets, ability to pull units down (expressive animation of danger) and support from auxiliary sea creatures (rays, fish) that delay, divert or temporarily neutralize units. Knights may advance disguised or partially submerged (stealth approach — mechanical translation to be defined). Educational integration follows the general system (challenge → boost to recover ground); the victory condition of the level (defeating, overtaking or neutralizing the whale's block) is open, but the boss must be perceptibly more challenging without requiring a new set of rules. **[IN EXPLORATION]**

Units enter the field up to a possible defined capacity, advance, fight and may be defeated or temporarily withdrawn — with visual representation of return to the starting position, recovery or replacement. The current proposal favours temporary defeat (return to battle) as it is simpler and less frustrating; automatic return, recovery time and replacement are to be decided. Future classes (e.g.: resistant vs. fast, with differences in resistance/speed/attack) are foreseen in the architecture but not approved. **[IN EXPLORATION]**

Swords and shields — associated with a castle or cave with a house/fortification of the knights — may be visual elements, objects conquered, progress indicators or level rewards that integrate the visual progression of the knights; it is to be decided whether they have permanent mechanical effects or are merely visual. The match structure remains recognizable across all themes. Beyond the trophy (with animation, celebration, victory screen and collection), the reward catalogue includes juice, chocolate, sweets/candy, clothes and costumes, possibly via shop/square/customisation and with choice by the child — to be introduced after validation of the core. **[IN EXPLORATION]**

The narrative (knights travelling between worlds/eras/realities, possibly led by a wizard) remains open: identity of the wizard, logic of travel, motivation for confrontations, relationship between settings and story of the whale are opportunities for later development, not current requirements. **[TO VALIDATE]**

The priority remains validating a playable level (castle setting, single-player, simulated opponent, few units, 1–2 boosts, automatic + child-initiated activation, visual advantage indicator, trophy as reward) that combines legible battle, visual progression, integrated educational challenges and concrete rewards — measured by the optimisation vectors (fun and comprehension first; educational impact and dynamic difficulty afterwards; thematic architecture and reward expansion last). New themes, bosses, unit classes and narrative should expand that base, and not force the creation of an entirely different game system for each setting. **[DECIDED — phasing]**
