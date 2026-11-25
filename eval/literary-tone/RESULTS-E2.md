# Zero-shot atmoszféra-címkék (E2) – mérési jegyzőkönyv

*Állapot: **E2 lefutott (2026-11-04).** A tesztterv (`literary_atmosphere_model_test_plan.md`) E2 kísérlete: zero-shot ModernBERT, csak a célrészlet (C0), saját atmoszféra-címkékkel. Az E1 (hangvétel-osztályozó): [`RESULTS-E1.md`](RESULTS-E1.md). Az E3–E5 még nincs elvégezve.*

## Modell

[`MoritzLaurer/ModernBERT-large-zeroshot-v2.0`](https://huggingface.co/MoritzLaurer/ModernBERT-large-zeroshot-v2.0), revízió `a51e07b524299e309dd2b88d48b0cfa2bd9ec598`.

| | |
|---|---|
| Alap | `answerdotai/ModernBERT-large` (28 réteg, 1024 rejtett dim., ~395M paraméter), 792 MB (bf16 safetensors), CPU-n fp32-ben futtatva |
| Feladat | NLI (`entailment` / `not_entailment`): a részlet a premissza, egy címkéből képzett mondat a hipotézis |
| Bemenet | 8192 token (`max_position_embeddings`). A kártya szerint a tanítóadat még nem használja ki a hosszú kontextust („preparing a newer version… to make full use of the 8k context window”) |
| Tanítóadat | a `zeroshot-v2.0` sorozat keveréke (33 adathalmaz, NLI és osztályozási feladatok). A „-c” nélküli változat nem kereskedelmi licencű adatokat is tartalmaz; maguk a súlyok Apache-2.0 alattiak |
| Közölt mérés | átlag 0,85 pontosság / 0,83 F1-macro 28 feladaton; irodalmi szövegen nincs mérés |
| Népszerűség | 12 798 letöltés (2026-11-04) |
| ONNX | a repóban van ONNX export (fp32, fp16, int8, q4 stb.), Rust oldali futtatáshoz jól jöhet |

## Módszer

- **Részletek:** ugyanaz a 16 Moby Dick-részlet és kinyerés, mint az E1-ben ([`tone_probe.py`](tone_probe.py) `PASSAGES`), fejezetcím nélkül; hosszak: **150, 300, 700 szó** ugyanattól a ponttól. Az 1500 szót kihagytuk: az E1-ben a hosszabb bemenet csak rontott, és itt egy 700 szavas részlet is ~50 s.
- **Címkék** (a tesztterv 10 atmoszféra-címkéje): ominous, suspenseful, mysterious, melancholic, warm and cozy, peaceful, hopeful, oppressive, whimsical, wondrous.
- **Hipotézis-sablonok:** `v1` = „The atmosphere of this passage is {}.” (fő futás, mindhárom hosszon); `v2` = „This passage creates a {} atmosphere.” (csak 300 szón, a megfogalmazás hatásának ellenőrzésére).
- **Pontozás (multi-label):** címkénként külön modellfuttatás; a pontszám a P(entailment) az (entailment, not_entailment) softmaxából (mint a zero-shot pipeline `multi_label=True` módja). Az egycímkés nézetet (az entailment-logitok softmaxa a címkék között) is mentettük (`single:*` oszlopok), de nem értékeltük.
- **Várt címkék:** [`annotations_e2.csv`](annotations_e2.csv), részletenként 1–3 címke a 10-ből. **Ideiglenesek**, nem független annotátortól; a „hopeful” egyik részletnél sem szerepel, ezért azt nem lehet értékelni.
- **Értékelés küszöb nélkül** ([`analyze_e2.py`](analyze_e2.py)), mert a terv szerint a küszöböket külön validációs adaton kellene hangolni, ilyen pedig nincs:
  - **AP (average precision) címkénként:** a 16 részletet a címke pontszáma szerint rangsorolva mennyire kerülnek előre a várt részletek (1,0 = mind elöl). A véletlen szint ≈ a pozitívak aránya (átlagosan 0,24);
  - **top-1 találat:** a legmagasabb pontszámú címke a várt címkék között van;
  - **top-3 felidézés:** a várt címkék hányada a top 3-ban;
  - **szórás:** a címke pontszámának szórása a részletek között (mennyire különbözteti meg őket).
- **Ablakos próba:** egymást követő 300 szavas ablakok a 3. (16 ablak) és a 132. fejezettől (8 ablak; a 7. ablak már a 133. fejezet eleje), `v1` sablonnal.
- 4 szál, CPU (i3-1215U, WSL 5 GB).

Fájlok: [`zeroshot_probe.py`](zeroshot_probe.py), [`analyze_e2.py`](analyze_e2.py), [`annotations_e2.csv`](annotations_e2.csv), [`results/`](results/) (`e2_passages.csv`, `e2_windows.csv`, `e2_run.json`, `e2.log`).

Futtatás:
```bash
~/.venvs/music-book-eval/bin/python zeroshot_probe.py ../../../book_source/moby_dick.epub
python3 analyze_e2.py
```

## Eredmények

### Összesítve

| Futás | Átlagos AP | Véletlen szint | Top-1 találat | Top-3 felidézés |
|---|---|---|---|---|
| v1, 150 szó | 0,56 | 0,24 | 7/16 | 0,48 |
| **v1, 300 szó** | **0,68** | 0,24 | 6/16 | 0,41 |
| v1, 700 szó | 0,67 | 0,24 | 6/16 | 0,34 |
| v2, 300 szó | 0,65 | 0,24 | 7/16 | 0,38 |

### Címkénként

| Címke | Várt részletek | AP 150 | AP 300 | AP 700 | AP v2 300 | Szórás (v1 300) |
|---|---|---|---|---|---|---|
| ominous | 7 | 0,63 | 0,69 | 0,59 | 0,68 | 0,43 |
| suspenseful | 3 | 0,78 | **0,92** | 0,53 | 0,87 | 0,40 |
| mysterious | 2 | 0,58 | 0,83 | 0,83 | 0,75 | 0,37 |
| melancholic | 5 | 0,55 | 0,49 | 0,75 | 0,57 | 0,23 |
| warm and cozy | 2 | 0,50 | 0,61 | 0,70 | 0,60 | 0,27 |
| peaceful | 3 | 0,64 | **1,00** | **1,00** | 0,92 | 0,26 |
| hopeful | 0 | – | – | – | – | – |
| oppressive | 6 | 0,55 | 0,63 | 0,68 | 0,55 | 0,36 |
| whimsical | 4 | 0,37 | 0,50 | 0,67 | 0,37 | 0,26 |
| wondrous | 3 | 0,44 | 0,46 | 0,31 | 0,51 | 0,36 |

Egy címkénél 2–7 várt részlet van, így egyetlen részlet helycseréje 0,1–0,3-mal is mozgathatja az AP-t. A számok iránymutatók.

### Részletenként (v1, 300 szó, a 3 legmagasabb címke)

| Részlet | Várt | Top 3 (P(entailment)) |
|---|---|---|
| loomings | whimsical, melancholic | wondrous 0,78 · whimsical 0,76 · mysterious 0,18 |
| spouter_painting | ominous, mysterious, oppressive | mysterious 0,99 · suspenseful 0,92 · ominous 0,64 |
| spouter_landlord | whimsical | ✗ melancholic 0,91 · oppressive 0,85 · suspenseful 0,62 |
| sermon | ominous, oppressive | suspenseful 0,98 · wondrous 0,74 · ominous 0,58 |
| bosom_friend | warm and cozy, peaceful | ✗ mysterious 0,94 · whimsical 0,69 · wondrous 0,21 |
| cetology | whimsical | ✗ suspenseful 0,99 · mysterious 0,98 · wondrous 0,36 |
| sunset | ominous, oppressive, melancholic | mysterious 0,99 · suspenseful 0,97 · ominous 0,93 |
| whiteness | mysterious, ominous, wondrous | mysterious 0,99 · wondrous 0,82 · suspenseful 0,78 |
| stubb_kills | suspenseful, oppressive | suspenseful 0,99 · ominous 0,98 · mysterious 0,36 |
| stubb_supper | whimsical | ✗ ominous 0,98 · suspenseful 0,95 · oppressive 0,95 |
| castaway | melancholic, ominous | ✗ warm and cozy 0,68 · whimsical 0,23 · wondrous 0,16 |
| squeeze | peaceful, warm and cozy, wondrous | **peaceful 0,99 · wondrous 0,94 · warm and cozy 0,90** |
| coffin | melancholic, oppressive | suspenseful 0,99 · ominous 0,98 · oppressive 0,96 |
| candles | suspenseful, ominous, wondrous | ominous 1,00 · suspenseful 1,00 · mysterious 0,85 |
| symphony | melancholic, peaceful | wondrous 0,99 · whimsical 0,71 · peaceful 0,55 |
| catastrophe | suspenseful, ominous, oppressive | suspenseful 1,00 · ominous 0,99 · mysterious 0,45 |

- A **castaway** első 300 szava Pip vidám, élénk jellemét írja le, a vízbe ugrás később jön. A „warm and cozy” így a célrészletre talán helyes, és a várt címke a hibás erre a vágásra. Ez a terv „a hangulat a részlet végén” szabályának fontosságát mutatja.
- **A humort nem ismeri fel:** Stubb és a szakács (stubb_supper) ominous/oppressive, a fogadós tréfái melancholic/oppressive, a cetológia suspenseful/mysterious.
- **A „suspenseful” és a „mysterious” gyűjtőcímke:** 0,9 fölött van a részletek felénél, köztük a száraz cetológiánál is. (Hasonlóan a Qwen „mysterious” tagjéhez.)
- **A pontszámok telítődnek:** sok címke 0,95–0,999. A sorrend értelmes, de abszolút küszöbként (pl. 0,5) használhatatlan; a terv szerinti kalibráció kellene.

### Hossz és megfogalmazás

- **300 szó a legjobb.** 150 szónál zajosabb (átlagos AP 0,56). 700 szónál a rangsor megmarad (0,67), de a top-3 felidézés 0,41 → 0,34-re esik, mert a suspenseful/mysterious szinte mindenhol 0,97–0,99, és kiszorítja a többit. Az E1-hez hasonló kiátlagolódás tehát itt is van, csak gyengébb.
- **A megfogalmazás számít, de nem döntően:** a `v2` sablon átlaga 0,65 (a `v1`-é 0,68), a whimsical viszont 0,50 → 0,37, a mysterious 0,83 → 0,75 lett. Sablonhangolással (és címkeleírásokkal) valószínűleg javítható, de ezt csak külön validációs adaton szabad.

### Ablakok (300 szó)

**3. fejezet:**

| Ablak (szó) | Tartalom | Top 2 |
|---|---|---|
| 0–900 | festmény, kannibálfegyverek, a kocsma („deliriums and death”) | mysterious / ominous → ominous / oppressive ✓ |
| 900–1200 | a fogadós tréfái a harpunásról | ✗ ominous 0,86 · melancholic 0,82 |
| 1500–1800 | a matrózok isznak, ugrálnak | wondrous 0,95 · whimsical 0,95 ✓ |
| 3300–3600 | a fogadós komikus története a nagy ágyról | suspenseful 0,99 · mysterious 0,97 (whimsical 0,93) |
| 4500–4800 | Queequeg éjjel megérkezik, Ishmael fél | ominous 1,00 · mysterious 1,00 (oppressive 0,95) ✓ |

**132. fejezet → 133. eleje:**

| Ablak (szó) | Tartalom | Top 2 |
|---|---|---|
| 0–600 | tiszta, kék nap | wondrous 0,99 · peaceful 0,90 / warm and cozy 0,89 ✓ |
| 600–900 | Ahab: „the desolation of solitude” | oppressive 0,97 · ominous 0,97 · melancholic 0,95 ✓ |
| 900–1200 | Ahab: „let me look into a human eye… the bright hearth-stone” | whimsical 0,98 · warm and cozy 0,94 (részben ✓) |
| 1200–2100 | Starbuck könyörgése, Ahab elutasítja, Fedallah | mysterious / suspenseful / ominous |
| 2100–2400 | 133. fej.: „There she blows!”, üldözés | suspenseful 1,00 · ominous 0,97 ✓ |

Az E1-gyel szemben (ott szinte minden ablak „humorous” volt) a címkék **követik a szöveg váltásait**: a nyugodt nap → Ahab sivársága → melegség → üldözés váltások jól látszanak. A humoros ablakokat itt is csak részben ismeri fel.

### Sebesség, memória

| | |
|---|---|
| Betöltés | 118 s az első alkalommal (letöltéssel), utána 8 s |
| Csúcs RSS | 2281 MB (fp32) |
| Idő részletenként, 10 címkével (medián) | 150 szó: 8,9 s · 300 szó: 22 s · 700 szó: 52 s |
| Kiugrások | 75–257 s, amikor a WSL swapolt (1 GB swap foglalt, közben más is futott) |

- A költség a **címkék számával arányos**: az NLI-modell a részletet és a hipotézist együtt olvassa, ezért a részlet feldolgozása címkénként megismétlődik, nem gyorsítótárazható.
- A Moby Dick 347 szegmense 700 szóval és 10 címkével kb. **5 óra** ezen a gépen. Ez nagyjából a Qwen3-4B sebessége (50–100 s / szegmens), tehát a zero-shot modell **nem gyorsabb** az LLM-nél. Gyorsítási lehetőségek: kevesebb címke, 300 szavas bemenet, a repóban lévő int8 ONNX változat (minőségét újra mérni kell).

## Összevetés

| | E1 hangvétel-osztályozó | **E2 zero-shot ModernBERT** | Qwen3-4B (llama.cpp) |
|---|---|---|---|
| Megkülönbözteti a részleteket? | nem, 700 szótól minden „humorous” | igen, átlagos AP 0,68 (véletlen 0,24) | igen, a 7 közös részlet sorrendje egyezik a várttal |
| Közös címkék AP-je (melancholic / warm, 300 szó) | 0,38 / 0,58 | 0,49 / 0,61 | – |
| Közös címkék AP-je (700 szó) | 0,55 / 0,50 | 0,75 / 0,70 | – |
| Feszültség | nincs ilyen kimenet | „suspenseful”, de gyűjtőcímke | `tension` 1–5, a teljes skálán |
| Humor | mindenre ezt mondja | nem ismeri fel | a viharnál felismerte (Stubb éneke) |
| Idő / 700 szó | ~1 s | ~52 s (10 címke) | 50–100 s |
| Memória | 1,3 GB | 2,3 GB | 2,7 GB |

## Értékelés

1. **Az E2 használható jelet ad**, az E1 nem. A nyugodt/meleg ↔ sötét/feszült tengely jól szétválik (peaceful AP 1,00, suspenseful 0,92), és 300 szavas ablakokban a címkék a szöveggel együtt változnak.
2. **A gyengeségek rendszerszerűek:** a humor (whimsical) gyenge, a suspenseful/mysterious gyűjtőcímke, a pontszámok telítődnek, a hosszabb bemenet laposít.
3. **A sebesség a fő akadály:** címkénként egy modellfuttatás, így nagyjából olyan lassú, mint a Qwen3-4B, miközben a kimenete kevesebbet ad (nincs valence/arousal skála, nincs indoklás).
4. **Az eredmény bizonytalan:** 16 részlet, ideiglenes címkék, egy könyv. A terv szerinti (több könyv, két annotátor, könyvenkénti felosztás) értékelés nélkül a számok csak irányt mutatnak.

**Döntés (E2):** a zero-shot ModernBERT jobb az E1-nél, de **nem váltja ki a Qwen3-4B-t**: hasonló sebesség mellett gyengébb és szegényebb a kimenete. A terv szerinti E3-at (hosszabb előzmény) nem érdemes erőltetni, mert a hosszabb bemenet már a célrészletnél is laposított, és a költséget többszörözné.

A legígéretesebb folytatás az **E5 (finomhangolás)**, desztillációval: a Qwen3-4B (4. prompt) címkézzen offline néhány ezer szegmenst több Gutenberg-regényből, és erre egy ModernBERT-base tanuljon (valence/arousal/tension regresszió + tag multi-label fej), egyetlen futtatással szegmensenként. A kézi annotáció (több könyv, két annotátor) ekkor a független tesztkészlet lesz.

## Nyitott pontok

- A „hopeful” nem értékelhető (nincs várt részlet); a következő annotációban kell rá példa.
- A terv kontrolljai közül a **célrészlet-csere** (target sensitivity) olcsó, és megmutatná, hogy a modell valóban a célrészletet olvassa; az E3-mal együtt érdemes elvégezni, ha arra sor kerül.
- Az egycímkés nézetet (`single:*` oszlopok) nem értékeltük.
