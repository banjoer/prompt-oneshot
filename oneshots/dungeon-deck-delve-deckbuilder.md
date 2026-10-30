# Dungeon Deck Delve — Deckbuilding Crawler

**Difficulty:** hard  |  **Stack:** HTML/CSS/JS (single file, vanilla; Phaser 3 via CDN optionally allowed)  |  **Estimated time:** 3–8 h

## The Problem
Deckbuilders are economy-design problems: every card must be draftable, every fight winnable, every run recoverable. Build a 3-act Slay-lite: map, draft, relics, merchants, bosses — all offline in one file.

## Requirements
1. Run structure: 3 acts × 8-node branching map (fight/elite/rest/shop/boss), HP persists across nodes; death ends run with score (floors + kills + gold).
2. Combat: hand of 5 from draw pile, 3 energy/turn, End Turn; cards: Strike (6 dmg), Guard (5 block, decays each turn), plus ≥10 unique others (e.g. Cleave all-foes, Sear burn-over-time, Leech heal-on-hit, Haste +energy); block resets each turn; intents shown above foes.
3. ≥12 distinct foes across acts with 2+ moves each (attack/buff/debuff patterns), plus 3 act bosses with phases; status effects: Burn, Weak (-25% dmg), Frail (+25% damage taken).
4. Draft after each fight (pick 1 of 3), rest sites (heal 30% or upgrade a card), shop (buy/remove cards with gold), 8 relics with passive effects (e.g. +1 energy on first turn, heal 2 after each fight).
5. DOM/canvas hybrid UI: hand fan, piles with counts, foe row with intents, map screen, animated card play (fly-to-target + shake), turn banner.
6. Seeded RNG (`?seed=` reproduces map + draft + foe moves); pause/help overlay with full rules; WebAudio hits/coins/cards.
7. Persist best-run score + wins per act in localStorage.
8. **Sign-off:** the title screen credits line must display the date and time the solution was produced and the model/author that produced it.

## Constraints
- Single `dungeon-deck-delve.html`; vanilla preferred; ONE Phaser 3.x CDN `<script>` tag permitted as alternative renderer — no other libraries, no runtime network calls.
- All cards/foes/relics/maps inline; storage via localStorage only.
- Balance rule: starting deck (4 Strike/4 Guard/1 Sear/1 Leech) must be able to clear Act 1 with decent play.

## Sample Data / Inputs
Card inline format:
```js
{id:'cleave', name:'Cleave', cost:2, text:'Deal 4 to ALL foes.', type:'attack'}
```

## Deliverable
- `dungeon-deck-delve.html` (single file)
- Run: double-click `dungeon-deck-delve.html`, or `python3 -m http.server 8000` then open `http://localhost:8000/dungeon-deck-delve.html?seed=7`

## Done When
- [ ] 3-act branching map with all node types navigates correctly
- [ ] Energy/hand/pile/intent/block combat loop with 14+ cards works end to end
- [ ] 12+ foes + 3 phased bosses with Burn/Weak/Frail behave distinctly
- [ ] Draft/rest/shop/8-relic economy functions; death-score flow works
- [ ] Seeded runs reproduce; best scores persist; sound + help overlay work
- [ ] Title-screen sign-off with date/time + author is visible

## Stretch Goals (optional)
- Ascension modifier (+25% foe HP toggle)
- Endless mode past Act 3 with scaling
- Card-codex gallery with filter by cost/type
