# Hangulatelemzés lokális LLM-mel (Qwen3-4B + llama.cpp) – tesztjegyzőkönyv

*2026-10-31. Előzmény: a feladatspecifikus enkóder modellek vizsgálata, lásd [`../model-selection/RESULTS.md`](../model-selection/RESULTS.md).*

## Összefoglaló

A **Qwen3-4B-Instruct-2507** (Q4_K_M kvantálás, llama.cpp `llama-server`, JSON-séma korlátozással) négy prompt-iteráció után **prototípusnak alkalmas** a `MoodAnalysis` előállítására:

- a JSON mind a 24 megválaszolt kérésnél érvényes volt;
- a valence, az arousal és a tension a végső változatban a teljes 1–5 skálát használja, és a 7 tesztrészlet sorrendje egyezik a várt hangulattal;
- a modell rövid, szövegre épülő indoklást ad.

Gyenge pontok:
- **sebesség:** szegmensenként kb. 1–3 perc ezen a gépen;
- **memória:** a WSL 5 GB-jából kb. 3 GB-ot foglal, mellette swapolás;
- **tagválasztás:** érzékeny a prompt apró változásaira;
- **confidence:** a modell nem tudja megítélni, ezért kivettük a kimenetből.

## Miért ez a megközelítés?

Az előző körben vizsgált feladatspecifikus modellekkel ezek voltak a gondok:
- a VAD-regresszorok (vad-bert) és a GoEmotions a skálák csak 4–5%-át használták, és egymással is gyengén egyeztek;
- a zero-shot DeBERTa szegmensenként 4–5 perc felett volt;
- egyik sem adta egymagában a teljes sémát (tension, tagek, indoklás).

Egy instrukciókövető LLM a teljes sémát egy hívásban adja, a llama.cpp nyelvtan-korlátozása pedig garantálja a JSON szerkezetét. Ez egyezik a CLAUDE.md 3. mérföldkövének eredeti tervével („LLM structured output, HTTP-n”).

## Környezet

| Elem | Érték |
|---|---|
| Gép | Intel i3-1215U (2 P- és 4 E-mag, 8 szál, AVX2), 7,7 GB RAM, nincs dedikált GPU |
| WSL | Ubuntu 26.04, WSL 2.7.14; `.wslconfig`: `memory=5GB`, `autoMemoryReclaim=gradual` (az alapértelmezett 3,7 GB helyett) |
| llama.cpp | forrásból fordítva (`~/tools/llama.cpp`, commit `5047748`, 2026-10-30, 0.8.0-dev): `cmake -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF`, `-j 2`, csak a `llama-server` és a `llama-cli`. A v0.8.0 kiadáshoz nem volt kész Linuxos bináris. |
| Modell | `unsloth/Qwen3-4B-Instruct-2507-GGUF`, `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (2,5 GB, Apache-2.0), `~/models`. A „2507 Instruct” a gondolkodás (thinking) nélküli változat. Hivatalos Qwen GGUF ehhez nincs, az unsloth kvantálása a legelterjedtebb. |
| Szerver | `llama-server -m … -c 4096 -t 4 --host 127.0.0.1 --port 8080` (1–2. kör), később **`-c 2048`** (a 2. kör vége, a 3. és a 4. kör) |
| Kérés | `/v1/chat/completions`, `temperature: 0`, `seed: 42`, `max_tokens: 300`, `response_format: {type: json_schema, …}` |

A mérőszkript a [`llm_probe.py`](llm_probe.py), és csak a Python szabványkönyvtárát használja. A részleteket közvetlenül az EPUB-ból vágja ki (a fejezetcímtől vagy egy megadott mondattól kb. 700 szót, bekezdéshatáron), nem a plugin szegmentálójával; egy prompt- és sebességpróbához ez elég. A mappában lévő szkript a **végleges (4.) promptot és sémát** tartalmazza a 7 részlettel. A korábbi körök promptja és sémája az „Iterációk” részben van leírva.

Futtatás (a `llama-server` fusson a `127.0.0.1:8080` címen):
```bash
python3 eval/qwen3-llamacpp/llm_probe.py <moby_dick.epub>
```

A körök nyers kimenete a [`logs/`](logs/) mappában van (`round1.log` … `round4.log`, `round2-contrast.log`). A `round2-contrast.log` és a `round4.log` végén egy-egy Python-hibaüzenet áll: ott a `llama-server` futás közben leállt (lásd „Negatívumok”). A hiányzó részleteket egy újraindítás után futtattuk le, ezek eredménye a hibaüzenet után, ugyanabban a fájlban van.

## Tesztrészletek (Moby Dick)

| Részlet | Kezdete | Várt hangulat |
|---|---|---|
| Spouter-Inn | Ch. 3 eleje | a fogadó sötét, nyomasztó festményének leírása; a fejezet humora csak később jön |
| Pip | Ch. 93 (The Castaway) eleje | szomorú, rémisztő |
| Vihar | Ch. 119 (The Candles) eleje | feszült, közben Stubb ironikus éneke |
| A Squeeze of the Hand | Ch. 94 eleje | boldog, szinte eufórikus |
| A Bosom Friend | Ch. 10 eleje | meleg, nyugodt (barátság születése) |
| The Symphony | Ch. 132 eleje | gyengéd, melankolikus |
| Katasztrófa | Ch. 135, „Almost simultaneously, with a mighty volition…” | eszeveszett akció, a hajó pusztulása |

## Iterációk

### 1. kör: 0–1 tört skálák
Séma: `valence` −1..1, `arousal` és `tension` 0..1, `confidence` 0..1, tagek 1–3 db a 16 elemes listából, `rationale` ≤ 240 karakter. A prompt csak a tartományok végpontjait írta le.

| Részlet | V | A | T | Conf. | Tagek |
|---|---|---|---|---|---|
| Spouter-Inn | 0,1 | 0,8 | 0,9 | 0,9 | mysterious, ominous, suspense |
| Pip | 0,2 | 0,8 | 0,9 | 0,9 | suspense, fear, melancholic |
| Vihar | 0,2 | 0,8 | 0,9 | 0,9 | suspense, humorous, grief |

**Felfedezés:** az arousal, a tension és a confidence mindháromnál azonos, a valence mindháromnál pozitív (Pipnél kifejezetten hibás). A kis modell a finom számskálán néhány „kedvenc” értékre ragad. Az indoklások viszont már ekkor pontosak voltak.

### 2. kör: 1–5 egész skála leírt fokozatokkal + kalibráció
Változás: a V/A/T 1–5 `enum`, minden fokozat megnevezett jelentéssel; a kalibrációs utasítás szerint a legtöbb szakasz a 2–4 tartományban van, szélső érték csak egyértelmű esetben jár, és a skálák függetlenek.

| Részlet | V | A | T | Tagek |
|---|---|---|---|---|
| Spouter-Inn | 2 | 4 | 4 | mysterious, ominous, suspense |
| Pip | 2 | 4 | 4 | melancholic, suspense, fear |
| Vihar | 3 | 4 | 4 | suspense, humorous, mysterious |

**Felfedezések:**
- A valence megmozdult (Pip helyesen negatív), az arousal és a tension viszont 4/4 maradt.
- **A tesztanyag volt túl egyforma:** mindhárom részlet sötét és feszült. Ezért kontrasztos részletekkel bővítettük (lásd lent).
- A `confidence` 9-et és 8-at adott, holott a sémában 0–1 a tartomány. **A llama.cpp a számok `minimum`/`maximum` határait nem kényszeríti ki, csak az `enum`-ot.**
- A 240 karakteres `maxLength` egyszer mondat közepén vágta el az indoklást.

Ugyanez a prompt a kontrasztos részleteken:

| Részlet | V | A | T | Tagek |
|---|---|---|---|---|
| A Squeeze of the Hand | 5 | 3 | 1 | tender, cheerful, contemplative |
| A Bosom Friend | 3 | 2 | 2 | tender, contemplative, melancholic |
| The Symphony | 3 | 2 | 3 | melancholic, contemplative, solemn |
| Katasztrófa | 2 | 5 | 5 | suspense, fear, mysterious |

**Felfedezés:** a skálák mozognak, a modell tehát nem ragadt be. Kiadja az 5-ös arousalt és tensiont is, amikor kell.

### 3. kör: tagdefiníciók, rövid indoklás, confidence 1–5
Változás: minden tag egysoros definíciót kapott (például *mysterious: the unknown, enigma, the uncanny; not merely dark*); a prompt a domináns érzést leíró tageket kéri; az indoklás legfeljebb 20 szó, a séma korlátja 400 karakter; a confidence 1–5 `enum`, leírt fokozatokkal.

| Részlet | V | A | T | Tagek | Conf. |
|---|---|---|---|---|---|
| Spouter-Inn | 2 | 4 | 4 | mysterious, ominous, suspense | 5 |
| Pip | 2 | 4 | 4 | melancholic, ominous, suspense | 5 |
| Vihar | 4 | 4 | 3 | humorous, contemplative, suspense | 5 |
| A Squeeze of the Hand | 5 | 3 | 1 | tender, calm, cheerful | 5 |
| A Bosom Friend | 3 | 2 | 2 | contemplative, melancholic, solemn | 5 |
| The Symphony | 3 | 2 | 2 | melancholic, contemplative, tender | 5 |
| Katasztrófa | 1 | 5 | 5 | grief, fear, suspense | 5 |

**Felfedezések:**
- Az indoklások rövidek és teljesek lettek.
- A „mysterious” túlhasználata csökkent.
- **A confidence mindig 5**, akkor is, ha az indoklás maga mondja, hogy a hangulat vegyes. A modell ezt nem tudja megbízhatóan megítélni.
- A Bosom Friend továbbra is semleges valence-t (3) és „melancholic” taget kapott.

### 4. kör (végleges): confidence nélkül, „affectionate” a valence 4-es fokozatában

| Részlet | V | A | T | Tagek | Indoklás (részlet) |
|---|---|---|---|---|---|
| Spouter-Inn | 2 | 4 | 4 | mysterious, ominous, suspense | „eerie mystery, unsettling imagery…” |
| Pip | 2 | 4 | 4 | melancholic, suspense, mysterious | „dread and foreboding… Pip's traumatic accident” |
| Vihar | 3 | 4 | 4 | mysterious, humorous, suspense | „dark, stormy imagery with a sudden shift into playful, ironic singing” |
| A Squeeze of the Hand | **5** | 3 | **1** | cheerful, tender, contemplative | „deeply peaceful, affectionate, and warm” |
| A Bosom Friend | **4** | **2** | 2 | tender, calm, solemn | „quiet observation and deep, unspoken affection” |
| The Symphony | 3 | **2** | 3 | melancholic, tender, suspense | „melancholic reflection on isolation, loss” |
| Katasztrófa | 2 | **5** | **5** | suspense, fear, mysterious | „intense action, dread, and a sense of inevitable doom” |

**Felfedezések:**
- Az „affectionate” elérte a célját: a Bosom Friend valence-e 3-ról 4-re nőtt, a tagjai „tender, calm” lettek.
- A confidence elhagyása a skálákat nem rontotta. A tagek közül viszont a „mysterious” két helyen visszakerült, és a vihar visszaállt a 2. kör értékeire. **A tagválasztás érzékeny a prompt apró változásaira, a skálák sokkal kevésbé.**

## Sebesség

Másodperc szegmensenként (falióra-idő; bemenet kb. 900–1400 token, kimenet kb. 85–120 token):

| Kör | Spouter-Inn | Pip | Vihar | Squeeze | Bosom Friend | Symphony | Katasztrófa |
|---|---|---|---|---|---|---|---|
| 1. | 196\* | 67 | 96 | – | – | – | – |
| 2. | 240\* | 51 | 82 | 147\* | 49 | 60 | 102\* |
| 3. | 72 | 61 | 119 | 99 | 57 | 60 | 62 |
| 4. | 131 | 81 | 138 | 82 | 196\* | 61 | 172 |

\* az első kérés egy (újra)indítás vagy hosszabb szünet után

- **Meleg állapotban kb. 50–100 s**, a medián kb. 70 s.
- A bemenet feldolgozása jó esetben 20–27 token/s, a válasz írása 5–7 token/s.
- **Kiugrások 2–4 percig:** az első kérés után, és amikor a rendszer swapol. Ilyenkor a bemenet feldolgozása 7–9 token/s-re, a válasz írása akár 1 token/s-re esik.
- Az azonos rendszerprompt előtagját a llama.cpp gyorsítótárazza (a második kéréstől a bemenet kb. 100–300 tokennel rövidebb).
- Összevetésként: egy kb. 700 szavas szegmens elolvasása kb. 3 perc. A meleg sebesség tehát belefér, a kiugrások nem mindig.

## Memória
- A `llama-server` kb. 2,6–2,9 GB-ot foglal (RSS). Mellette a WSL 5 GB-jából 1 GB swap folyamatosan foglalt volt.
- A `-c 4096` → `-c 2048` váltás kb. 300 MB-tal csökkentette a kontextus memóriaigényét. Egy kb. 1,5k tokenes kéréshez (prompt + szegmens + válasz) a 2048 elég.
- **Az első betöltés kb. 4,5 percig tartott** (a súlyok átrendezése a CPU-hoz, szűk memória mellett). Az újraindítás utáni betöltés gyorsabb volt.

## Pozitívumok
- **Teljes séma egy hívásban:** valence, arousal, tension, tagek és indoklás.
- **Garantált szerkezet:** a JSON-séma (`enum`-okkal) mind a 24 megválaszolt kérésnél érvényes kimenetet adott; a tagek mindig a zárt listából jöttek.
- **A skálák kihasználtsága:** a végső változatban V 2–5, A 2–5, T 1–5; a 7 részlet sorrendje egyezik a várt hangulattal (nyugodt → feszült).
- **Szövegértés:** az indoklások konkrétak (Pip balesete, Stubb ironikus éneke, a barátság). Egyik enkóder modell sem tudott ilyet.
- **Determinisztikus:** `temperature 0` és rögzített seed mellett ugyanarra a promptra ugyanaz jön, ez a cache-hez szükséges.
- **Cserélhető:** a `llama-server` OpenAI-kompatibilis API-ja miatt ugyanaz a kliens felhős API-val is működne.
- **Licenc:** Qwen3 Apache-2.0, llama.cpp MIT.

## Negatívumok és buktatók
- **Lassú és ingadozó:** 1–3 perc szegmensenként. Kötelező a cache (SQLite), a következő szegmens előre elemzése, és az, hogy lapozáskor ne várjunk a modellre. Egy teljes könyv előfeldolgozása órákig tartana.
- **Szűkös memória:** a gép 7,7 GB-jából a WSL-nek 5 GB jár, ebből a modell kb. 3 GB. A swap okozza a kiugrásokat. A Tauri-app egyidejű futtatása tovább szűkít.
- **A szerver a terminállal együtt leállt** (két mérés is félbeszakadt). Megoldás: `nohup … &`, később a Tauri-app indítsa sidecarként.
- **A llama.cpp nem kényszeríti ki a számok `minimum`/`maximum` határait**, csak az `enum`-ot. Ezért egész skálák `enum`-mal, és a backendben tartomány-validálás.
- **A confidence használhatatlan** (mindig 8–9 vagy 5). A végső sémában nincs. A backend állítja be: 1 érvényes válasznál, 0 hibánál.
- **A tagválasztás instabil** a prompt apró változásaira; a „mysterious” hajlamos gyűjtőkategóriává válni. A katasztrófánál a „violence”/„chaos” helyett „fear”/„mysterious” jött.
- **A modell a részlet egészét nézi:** a Spouter-Inn első 700 szava a sötét festményről szól, ezért „baljós”, a fejezet humora később jön. Ez valójában helyes, de mutatja, hogy a szegmentálás határozza meg az eredményt.
- **Kis minta:** 7 részlet, kézi címkék nélkül, csak a várt hangulattal összevetve. A további hangolás ezen a mintán túlillesztés lenne.

## A végleges (4.) prompt és séma

Rendszerprompt:
```
You rate the mood of a passage from a novel, to drive adaptive background music. Judge the emotional atmosphere the reader experiences, not the plot. Rate each scale with an integer from 1 to 5:
valence: 1 = grief, despair, horror; 2 = sad, gloomy, unpleasant; 3 = neutral or mixed; 4 = pleasant, warm, affectionate, amusing; 5 = joyful, elated.
arousal: 1 = still, sleepy; 2 = quiet, reflective; 3 = moderate activity; 4 = lively, agitated; 5 = frantic, violent action.
tension: 1 = relaxed, safe; 2 = slight unease; 3 = noticeable suspense; 4 = strong suspense or threat; 5 = extreme danger, climax.
Calibration: most passages of a novel sit in the middle of the scales (2-4). Use 1 or 5 only when the passage clearly and strongly calls for it, and rate each scale independently of the others.
tags: the 1-3 tags that best describe the dominant feeling, from this list only:
- calm: peaceful, nothing is happening
- cheerful: light, happy, good spirits
- humorous: comic, ironic, playful
- tender: affection, friendship, intimacy
- melancholic: wistful sadness, longing
- grief: loss, mourning, death of someone close
- solemn: grave, dignified, religious or ceremonial
- mysterious: the unknown, enigma, the uncanny; not merely dark
- ominous: foreboding, a sense that something bad will happen
- fear: characters are afraid, terror
- suspense: uncertain outcome, the reader holds their breath
- anger: rage, defiance, hostility
- violence: physical struggle, killing, injury
- chaos: confusion, disorder, things falling apart
- triumph: victory, exultation, pride
- contemplative: reflection, philosophy, inner thought
rationale: one sentence of at most 20 words. Answer with JSON only.
```
A felhasználói üzenet a szegmens szövege.

JSON-séma (`response_format.json_schema.schema`):
```json
{
  "type": "object",
  "properties": {
    "rationale": {"type": "string", "maxLength": 400},
    "valence": {"enum": [1, 2, 3, 4, 5]},
    "arousal": {"enum": [1, 2, 3, 4, 5]},
    "tension": {"enum": [1, 2, 3, 4, 5]},
    "tags": {"type": "array", "items": {"enum": ["calm", "cheerful", "humorous", "tender", "melancholic", "grief", "solemn", "mysterious", "ominous", "fear", "suspense", "anger", "violence", "chaos", "triumph", "contemplative"]}, "minItems": 1, "maxItems": 3}
  },
  "required": ["rationale", "valence", "arousal", "tension", "tags"],
  "additionalProperties": false
}
```
Az indoklás szándékosan az első mező: a modell előbb megfogalmazza a hangulatot, és csak utána pontoz.

## Következtetés és következő lépések
1. **Döntés:** az első `MoodAnalyzer` implementáció a Qwen3-4B-Instruct-2507 + `llama-server` legyen, a fenti 4. prompttal (`prompt_version = 4`). A backend az 1–5 értékeket a `MoodVector` skáláira képezi le (valence: −1..1, arousal és tension: 0..1).
2. **Plugin-kód:**
   - `analysis/` (trait és `LlamaCppAnalyzer`, `reqwest`, validálás, újrapróbálás);
   - `store.rs` (SQLite, kulcs: `(book_hash, seg_index, model_id, prompt_version)`);
   - bekötés a `report_location`-be: cache-ből vagy a modelltől, a következő szegmens előre elemzésével.
3. **Később:**
   - a tag-lista véglegesítése a zenei leképezéssel együtt (4. mérföldkő);
   - kézi címkék nagyobb mintán (10–20 szegmens) és egyezésmérés;
   - a Qwen3-1.7B kipróbálása tartaléknak, ha a sebesség vagy a memória nem elég;
   - a `llama-server` indítása sidecarként.
