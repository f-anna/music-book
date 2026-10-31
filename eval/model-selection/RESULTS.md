# Elemző modell kiválasztása – mérési jegyzőkönyv

*Állapot: **lezárva, az irányt elvetettük** (2026-10-28–30). A mérés félbemaradt: a `PERT-EmoPair` nem futott le, kézi címkék nem készültek. A mérőszkripteket és az adatokat a lezáráskor töröltük, ezért a lent említett fájlok (`dump-segments`, `select_segments.py`, `run_model.py`, `compare.py`, `segments.json`, `labels.csv`, `results/`) már nem léteznek; a nevük csak a módszer leírásaként szerepel. A folytatás egy lokális LLM-mel: [`../qwen3-llamacpp/RESULTS.md`](../qwen3-llamacpp/RESULTS.md).*

## Cél

A 3. mérföldkőhöz (elemzés kész nyelvi modellel) kiválasztani azt a **feladatspecifikus, nem generatív** modellt, amely egy könyvszegmensből egymagában (hibrid megoldás nélkül) a legjobban előállítja a `MoodAnalysis` mezőit: `valence`, `arousal`, `tension`, `tags`.

Feltételek:
- lokálisan fusson a fejlesztői gépen (Intel i3-1215U, 7,7 GB RAM, ebből a WSL-nek 3,7 GB jut, nincs dedikált GPU);
- tiszta licenc;
- mért, közölt minőség;
- angol szöveg (a félév scope-ja szerint csak angol könyvek).

## Előzmény: miért nem generatív LLM?

Először kis lokális LLM-eket vizsgáltunk (Qwen3.5 2B/4B, Phi-4-mini, SmolLM3, Llama 3.2 3B). Ezek általános célú, csevegésre is képes modellek. Ezen a gépen szegmensenként percekig futnának, és a számértékeik kevésbé következetesek. A feladatspecifikus (enkóder) modellek kicsik, gyorsak, determinisztikusak, és csak a tanított kimenetet adják. Az LLM-es változat a CLAUDE.md szerint később összehasonlítási alap lehet.

## Vizsgált modellek

13 jelöltet néztünk át (a licencet, a letöltésszámot és a méretet a Hugging Face API-ból ellenőriztük, a többi adatot a modellkártyákról vettük).

| Modell | Kimenet | Licenc | Közölt mérés | Döntés |
|---|---|---|---|---|
| [`edsi-umd/PERT-EmoPair`](https://huggingface.co/edsi-umd/PERT-EmoPair) | V, A, D (abszolút) | CC-BY-4.0 | Pearson V 0,83, A 0,86 | **kiválasztva** |
| [`MoritzLaurer/deberta-v3-base-zeroshot-v2.0`](https://huggingface.co/MoritzLaurer/deberta-v3-base-zeroshot-v2.0) | tetszőleges címkék (NLI) | MIT | 28 osztályozási feladaton | **kiválasztva** |
| [`SamLowe/roberta-base-go_emotions`](https://huggingface.co/SamLowe/roberta-base-go_emotions) | 28 érzelem (multi-label) | MIT | F1 ≈ 0,54 | **kiválasztva** |
| [`RobroKools/vad-bert`](https://huggingface.co/RobroKools/vad-bert) | V, A, D | MIT | nincs | **kiválasztva** |
| [`chrlukas/stories-emotion-c4`](https://huggingface.co/chrlukas/stories-emotion-c4) | V, A (történetek) | nincs megadva, „csak demó” | CCC 0,82 / 0,71 | tartalék |
| [`edsi-umd/Reward-EmoPair`](https://huggingface.co/edsi-umd/Reward-EmoPair) | V; A és D relatív | CC-BY-4.0 | párokon 82–85% | elvetve: ugyanaz az adat, mint a PERT-nél |
| [`j-hartmann/emotion-english-distilroberta-base`](https://huggingface.co/j-hartmann/emotion-english-distilroberta-base) | 7 érzelem | nincs licenc-címke | 66% | elvetve |
| [`cirimus/modernbert-base-go-emotions`](https://huggingface.co/cirimus/modernbert-base-go-emotions) | 28 érzelem | MIT | hasonló a GoEmotionshöz | elvetve: elavult |
| [`cardiffnlp/twitter-roberta-base-emotion-multilabel-latest`](https://huggingface.co/cardiffnlp/twitter-roberta-base-emotion-multilabel-latest) | 11 érzelem | nincs licenc-címke | F1 0,55 / 0,72 | elvetve |
| [`siebert/sentiment-roberta-large-english`](https://huggingface.co/siebert/sentiment-roberta-large-english) | csak pozitív/negatív | nincs licenc-címke | 93% | elvetve: egyedül túl kevés |
| [`bhadresh-savani/distilbert-base-uncased-emotion`](https://huggingface.co/bhadresh-savani/distilbert-base-uncased-emotion) | 6 érzelem | Apache-2.0 | – | elvetve |
| [`RuiSumida/LUFY`](https://huggingface.co/RuiSumida/LUFY) | V, A | MIT | nincs | elvetve: 128 tokenre vág |
| NRC VAD lexikon | V, A, D szavanként | ellenőrizendő | – | később, összehasonlítási alapnak |

Kész, letölthető **feszültség-modellt nem találtunk**. A `tension` mindenhol származtatott érték.

A négy kiválasztott modell négy különböző megközelítést képvisel:
1. **PERT-EmoPair:** a legjobban mért VAD-regresszor (nagy modell, RoBERTa-large).
2. **vad-bert:** ugyanaz a feladat kis modellel (BERT-base), a „nagy vagy kicsi” kérdéshez.
3. **Zero-shot DeBERTa:** az egyetlen, amely a teljes sémát lefedi a saját címkéinkkel.
4. **GoEmotions:** kategóriás megközelítés, a V/A/tension egy fix táblázatból jön.

## Elvégzett lépések

1. **Környezet.** Python 3.12-es virtuális környezet `uv`-vel, a repón kívül: `~/.venvs/music-book-eval`. A `/tmp` memóriában lévő fájlrendszer (tmpfs), ezért oda nem kerülhetett. Telepítve: `torch` 2.14.1, `transformers` 4.57.6, `sentencepiece`, `protobuf`, `psutil`.
   - A PyTorch saját, csak CPU-s csomagforrását a jogosultság-ellenőrző letiltotta, ezért a szabványos PyPI-csomag került fel. Ez a CUDA-könyvtárakat is tartalmazza, így a környezet 5,4 GB lett, de a futás csak CPU-t használ.
   - A modellek a Hugging Face alapértelmezett gyorsítótárába töltődnek le (`~/.cache/huggingface`).
2. **Szegmensek.** A `dump-segments` kis Rust program a plugin saját [`epub.rs`](../../crates/tauri-plugin-soundtrack/src/epub.rs)-ét használja (`#[path]`-szal beemelve), így pontosan ugyanazok a szegmensek jönnek ki, mint az appban (Moby Dick: 347 szegmens).
3. **Kiválasztás.** A `select_segments.py` 20 szándékosan változatos szegmenst választott ki: humor, prédikáció, barátság, baljóslat, Ahab monológjai, vadászat, száraz ismeretterjesztés, erőszak, gyász, vihar, katasztrófa. Ez a `segments.json`-ba került, összesen 14 073 szó. A kiválasztott szegmensek (a plugin szegmentálásával): #13, #29, #35, #44, #59, #81, #101, #105, #108, #115, #133, #160, #173, #184, #234, #249, #287, #301, #322, #339. A jegyzetek a szegmensek *tartalmát* írják le, nem címkék.
4. **Futtatás.** A `run_model.py` egyszerre egy modellt futtat, külön folyamatban, hogy a memóriamérés tiszta legyen:
   - a szegmenst mondathatáron vágott darabokra bontja (a darabméret a modell bemeneti korlátjához igazodik, lásd lent);
   - darabonként pontoz, majd szóhossz szerint súlyozott átlagot számol;
   - méri a betöltési időt, a szegmensenkénti időt és a folyamat csúcs-memóriáját (RSS);
   - az eredményt a `results/<modell>.json`-ba írja.
5. **Összesítés.** A `compare.py` Markdown-táblázatokat készített: sebesség, az értékek szórása, a modellek egymás közti egyezése (Spearman), és a kézi címkékkel való egyezés (ez utóbbi a címkék hiányában nem futott).
6. **Kézi címkézés előkészítése.** Egy `labels.csv` sablon (szegmensenként valence, arousal és tension 1–5 skálán) és egy olvasásra szánt `segments.md` készült; kitöltésre nem került sor.

### Modellenkénti beállítások

| Modell | Darabméret | Hogyan lesz belőle V / A / T / tag |
|---|---|---|
| PERT-EmoPair | 120 szó (a kártya szerint 256 tokenre vág, ebből kb. 70 a prompt) | V, A, D közvetlenül (a kártya prompt-sablonjával); T és tag nincs |
| vad-bert | 300 szó | V, A, D közvetlenül (EmoBank-skála, kb. 1–5); T és tag nincs |
| Zero-shot | 300 szó | `"The mood of this passage is {}."`: V = 2·P(pleasant) − 1 a (pleasant, unpleasant) párból; A = P(agitated) az (agitated, calm) párból; T = P(tense) a (tense, relaxed) párból. Tagek: `"This passage conveys {}."`, multi-label, 16 ideiglenes tag (calm, cheerful, humorous, tender, melancholic, grief, solemn, mysterious, ominous, fear, suspense, anger, violence, chaos, triumph, contemplative). |
| GoEmotions | 300 szó | 28 valószínűség. V és A: a címkék valószínűséggel súlyozott átlaga egy **kézzel összeállított** Russell-féle koordinátatáblázat alapján (`GOEMOTIONS_VA`). T: fear + nervousness + 0,6·anger + 0,3·(annoyance, disgust), legfeljebb 1. Tagek: a címkék közvetlenül. |

A GoEmotions V/A/T-táblázata saját becslés, tehát ennél a modellnél a leképezés is befolyásolja az eredményt, nem csak a modell.

## Eredmények (eddig: vad-bert, GoEmotions)

### Sebesség és memória

| Modell | Betöltés (s) | s / szegmens | s / 1000 szó | Csúcs RSS (MB) |
|---|---|---|---|---|
| vad-bert | 31,4 | 3,05 átlag, 1,80 medián | 4,34 | 1407 |
| GoEmotions | 45,0 | 1,45 átlag, 1,37 medián | 2,06 | 1351 |
| Zero-shot | – | **> 4,5 perc** (1,5 óra után sem végzett a 20 szegmenssel, leállítottuk) | – | ~1100 futás közben |
| PERT-EmoPair | – | nincs lefuttatva | – | – |

- 4 szálon, CPU-n mérve. A betöltési idő az első futásnál a letöltést is tartalmazza.
- A vad-bert átlagát egyetlen kiugró érték húzza fel (#115: 22 s, a többi 1,2–3,5 s). Ez valószínűleg a gép terheléséből adódott, nem a szövegből; ismételt futtatással ellenőrizhető.
- A zero-shot lassúságának oka, hogy darabonként 22 külön modellfuttatás kell (3 pár × 2 és 16 tag), szegmensenként tehát kb. 45–65. Ez hosszabb, mint egy kb. 700 szavas szegmens elolvasása (kb. 3 perc), így ezen a gépen gyakorlatban nem használható. Utána egy 3 szegmenses részhalmazon pontos mérést indítottunk, de az eredményét az irány elvetése előtt nem értékeltük ki, és a fájl a törléssel elveszett.

### Mennyire különbözteti meg a szegmenseket? (szórás)

| Modell | Dimenzió | min | max | szórás | szórás / skála |
|---|---|---|---|---|---|
| vad-bert | valence | 2,60 | 3,16 | 0,157 | 0,039 |
| vad-bert | arousal | 3,18 | 3,80 | 0,186 | 0,047 |
| GoEmotions | valence | −0,30 | +0,18 | 0,106 | 0,053 |
| GoEmotions | arousal | 0,27 | 0,42 | 0,050 | 0,050 |
| GoEmotions | tension | 0,01 | 0,17 | 0,037 | 0,037 |

Mindkét modell **nagyon szűk sávban** mozog: a teljes skála kb. 4–5%-át használja ki. A zenei leképezéshez ez önmagában nem kizáró ok (a szegmensek közötti relatív különbség is vezérelhet), de a modellek rangsora is csak gyengén egyezik egymással:

| Spearman | valence | arousal |
|---|---|---|
| vad-bert ↔ GoEmotions | +0,28 | +0,30 |

### Megfigyelések szegmensenként

- **GoEmotions:**
  - A szegmensek 61%-át átlagosan „neutral”-nak tartja (0,27–0,84). Ez a V/A-átlagot a semleges pont felé húzza, ezért ilyen szűk a sáv.
  - A leggyakoribb nem semleges címkék a confusion, curiosity és realization. Ezek a Reddit-adatra jellemzők, és az irodalmi szöveg hangulatát rosszul írják le.
  - Helyes találatok: #249 (Pip, a Castaway) sadness 0,44, a legnegatívabb valence; #115 (A bálna fehérsége) fear 0,12, a legmagasabb tension.
  - Gyanús: a vihar (#301) *amusement* 0,27 és pozitív valence; a végső katasztrófa (#339) desire 0,17 és pozitív valence.
- **vad-bert:**
  - A legmagasabb arousal a Sunset (#105, 3,80) és a katasztrófa (#339, 3,77), ez hihető.
  - A valence viszont alig mozog: a Queequeg koporsója (#287, 2,60) és a katasztrófa (#339, 2,62) a legalacsonyabb, a Symphony (#322) pedig a legmagasabb (3,15), ami vitatható.

## Lezárás

Az irányt a mérés befejezése előtt elvetettük, mert az addigi eredmények alapján egyik feladatspecifikus modell sem felelt meg:
- a két lefutott modell (vad-bert, GoEmotions) a skálák csak 4–5%-át használta ki, és egymással is gyengén egyezett (Spearman ≈ 0,3);
- a zero-shot DeBERTa, az egyetlen, amely a teljes sémát lefedte volna, ezen a gépen szegmensenként több mint 4,5 percig dolgozott;
- egyik modell sem adta egymagában a `tension`-t, a tageket és az indoklást.

Nem készült el: a PERT-EmoPair futtatása, a zero-shot 3 szegmenses mérésének kiértékelése és a kézi címkézés.

A folytatás egy lokális, instrukciókövető LLM (Qwen3-4B-Instruct-2507, llama.cpp), JSON-séma korlátozással: [`../qwen3-llamacpp/RESULTS.md`](../qwen3-llamacpp/RESULTS.md).

A repón kívül megmaradt a Python-környezet (`~/.venvs/music-book-eval`, 5,4 GB) és a letöltött modellek (`~/.cache/huggingface/hub`, 1,7 GB). Ezek törölhetők, ha erre az irányra nem térünk vissza.
