# *Silent Dungeon* — mundo, atos e mecânicas (seed KB)

Documento de apoio a agentes (RAG). **Fonte de verdade:** `REPO_ROOT/src/engine/schema/` (sobretudo `core.ts`, `entities.ts`) e resolução de combate em `REPO_ROOT/src/engine/combat/` (`combat.ts`, `combatStats.ts`). Se algo divergir deste resumo, prevalece o código do jogo.

Campanha por defeito: **`calvario`** (`campaignId` no estado).

---

## Estrutura de atos (`src/campaigns/calvario/scenes/`)

Pastas guiam o **capítulo** (`chapter` no frontmatter deve alinhar com o ato, ex. `act6/*` → `chapter: 6`). Resumo espacial/narrativo (sem spoil longo):

| Pasta | Função típica |
|--------|------------------|
| **act1** | Entrada na masmorra, escolha de classe (`knight` / `mage` / `cleric`), primeiros corredores e ganchos iniciais. |
| **act2** | Catacumbas e hub (`hub_catacomb`), acampamento, comerciantes, encontros selvagens, fio do Círculo / facções. |
| **act3** | Descida às profundezas, culto, eventos de corrupção, santuários e ramos laterais. |
| **act4** | Clímax político/ritual: trono, pacto, Morvayn; decisões que fecham ou abrem ramos. |
| **act5** | Arco gelo / montanha (`frost_*`), acampamento e encontros próprios do bioma. |
| **act6** | Limiar do vazio, provas, espelho, forja dimensional, hub fracturado; tom mais metafísico. |
| **act7** | Antecâmara do eremitério, bifurcação apocalipse, epílogos de encerramento. |
| **endings/** | Epílogos e variantes de fim ligadas a flags ou ramos. |
| **shared/** | Cenas reutilizáveis (navegação de exploração, juramentos, game over, pós-ato). |

Exploração selvagem e grafos de nós ligam-se a dados em `src/engine/world/exploration.ts` e a cenas com efeitos `setExploration` / `startWildEncounterFromGraph`.

---

## Personagem (líder) e atributos

O grupo é `party`: o índice **0** é o líder controlado pelo jogador; companions ocupam índices seguintes (até 3 personagens no combate — ver efeitos com `partyIndex` 0..2).

### Atributos (`str`, `agi`, `mind`, `luck`)

- **str:** força física — ataques corpo a corpo, resistências em combate.  
- **agi:** agilidade — fuga (modificador em teste 2d6 + AGI, ver encontros), iniciativa implícita na ordem de turnos.  
- **mind:** mente — magias, muitos testes narrativos (`skillCheck` / dual attr).  
- **luck:** sorte — testes de `luckCheck`, desvios de azar narrativo.

### Vitalidade e tensão

- **hp** / **maxHp:** pontos de vida.  
- **stress:** 0..4 (stress do personagem; entradas de log de combate podem referir `stress`).  
- **mana** / **maxMana:** recurso de magias do líder (classes começam com perfis diferentes).

### Valores iniciais por classe (`createPlayerCharacter` em `src/engine/core/state.ts`)

| Classe | str | agi | mind | luck | HP | mana (atual / max inicial) | Equipamento inicial (ids) |
|--------|-----|-----|------|------|-----|-----------------------------|---------------------------|
| **knight** | 12 | 9 | 7 | 8 | 18/18 | 2/2 | `rusty_sword`, `leather` |
| **mage** | 6 | 8 | 13 | 10 | 12/12 | 12/15 | `oak_staff`, `cloth_robe` |
| **cleric** | 8 | 8 | 11 | 9 | 14/14 | 8/10 | `mace`, `chain_shirt` |

**critRatio:** base por classe (cavaleiro maior); o cavaleiro pode ganhar bónus com passivo desbloqueado (fragmento Morvayn — ver `PASSIVE_UNLOCK_ITEM_ID` e `syncLeadPassiveStats` no mesmo ficheiro).

### Arquétipo narrativo `path`

Campo opcional no personagem (`path`: string ou null). Desbloqueios narrativos em `src/campaigns/calvario/classHero.ts` (ex. `knight:fallen`, `mage:dark`, `cleric:penitent`) com rótulos PT, texto de promoção e **bónus de jogo** (stats, `addResource` em fé, etc.). Não confundir `path` com `class`: a mecânica de combate continua indexada por `class`.

---

## Recursos, reputação e meta

### `resources` (início em `createInitialState`)

- **supply:** 5  
- **faith:** 3  
- **corruption:** 0  
- **gold:** 8  

Em cenas usam-se deltas via efeitos `addResource` (e condições em `resource.*` no schema). **Fé ≥ 5** liga-se a mecânica de “vida extra” preparada (`extraLifeReadyFromFaith`).

### Facções (`reputation`)

Chaves: **`vigilia`**, **`circulo`**, **`culto`**. Valores inteiros **-10..+10**. Ganhos positivos podem exigir dois passos (`factionGainPending`) salvo `directGain: true` em `addRep` — detalhe em `src/engine/schema/core.ts`.

### Progressão global (`GameState`)

- **chapter:** capítulo narrativo (alinhar com pastas `actN`).  
- **level** / **xp:** nível do líder e XP dentro do nível.  
- **day:** dia narrativo (começa em 1); avança com efeito **`{ op: advanceDay }`** (`onEnter`, `choices[].effects`, etc.).  
- **flags** / **marks:** estado booleano e marcas string para gates de cena.  
- **inventory**, **knownSpells**, **activeBuffs**, **companionFriendship**: suporte a loot, magias aprendidas, buffs temporários por cena e relação com companions.

---

## Combate (visão de sistema)

Estado em **`combat`** (`CombatStateSchema` em `entities.ts`). Modo da app: `mode` pode ser `story` | `combat` | `modal`.

### Fases do turno (`phase`)

Ordem típica: **`choose_stance`** → **`choose_target`** → **`enemy`** → **`ended`**.

1. O jogador escolhe **postura** (`StanceSchema`): **`aggressive`**, **`defensive`**, **`focus`**.  
2. Escolhe alvo (inimigo). A postura **defensiva** dá **+2 CA** ao líder durante a fase inimiga seguinte (campo `defenseStanceForEnemyTurn` guarda isso entre fases).  
3. Inimigos agem em sequência; depois novo round ou fim.

### Ordem e rondas

- **`turnOrder`:** ids dos combatentes (party + inimigos).  
- **`turnIndex`** / **`round`:** posição na ordem e número da ronda.

### Encontros (`EncounterSchema`)

- Lista de ids de inimigos (`enemies[]`).  
- **`fleeRate`:** 0..1 — probabilidade base de fuga; comentário no schema: influencia o **TN do teste 2d6 + mod(AGI)** (implementação em `combat.ts`).  
- **`playerAdvantage`**, **`enemyAdvantage`:** vantagem narrativa/mecânica no encontro.  
- **`isBoss`** + **`twists`:** bosses podem declarar gatilhos (`minRound`, HP baixo, fração de HP total) e efeitos (`combatLog`, buffs de CA/ataque, `damageAllEnemies`, etc.).

### Inimigos (`EnemyDefSchema`)

- Stats **str / agi / mind**, **hp / maxHp**, **armor**, **type:** `normal` | `undead` | `armored` | `cultist`.  
- **`armorChips`:** camadas extra para tipo `armored`.  
- **`attackStrategy`:** `random` ou `focus_leader` (com `focusLeaderWeight` opcional).  
- **`lootDrops`**, **`combatLines`**, **`critConfirm`**, **`xp`** opcionais.

### Magias (`SpellDefSchema` em `entities.ts`)

- **`spellKind`:** `damage` | `heal_self` | `buff_attack_roll` | `buff_armor_class`.  
- **`dice`:** número de d6; **`base`** somado com mod de Mente onde aplicável; **`manaCost`**, **`minLevel`**, **`classId`** ou `any`; **`learnOnly`** para magias só via narrativa.

### Log de combate

Tipos de linha incluem `attack`, `damage`, `heal`, `stance`, `stress`, `armor_break`, `crit_threat` / `fumble_threat`, etc. — útil para não contradizer a UI ao escrever copy de pós-combate.

---

## Dados de campanha (Calvário)

- **Encontros:** `src/campaigns/calvario/data/encounters.json` (ids referenciados por `encounterId` / `startCombat` nas cenas).  
- **Inimigos:** `src/campaigns/calvario/data/enemies.ts` (defs alinhadas a `EnemyDefSchema`).  
- **Itens, passivos, etc.:** outros ficheiros em `src/campaigns/calvario/data/`.

---

## Itens e equipamento (`ItemDefSchema`)

- **Slots:** `weapon`, `armor`, `relic`, `consumable`.  
- Bónus típicos: `bonusStr`, `bonusAgi`, `bonusMind`, `bonusLuck`, `armor`, `damage`.  
- Consumíveis: `restoreHp`, `restoreMana`, `stressRelief`.  
- Relíquias podem ter mecânicas especiais (ex. `corruptionDrainOnHit`).  
- **`cursed`**, **`rumor`**, **`sprite`** (ASCII) para narrativa/UI.

---

## Relação com cenas

- Ganchos de combate: `startCombat` com `encounterId`, `onVictory` / `onFlee` / `onDefeat`; `interleaveAfterCombat` para texto após o combate.  
- Condições de escolha usam `resource`, `rep`, `class`, `flag`, etc. — ver `ConditionSchema` em `core.ts`.  
- Para authoring detalhado de ficheiros `.md`, continuar a usar **`REPO_ROOT/.cursor/skills/create-scenes/SKILL.md`** quando existir.
