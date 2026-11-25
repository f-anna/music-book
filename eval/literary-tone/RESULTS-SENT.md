# Mondatszintű pontozás feladatspecifikus modellekkel – mérési jegyzőkönyv

*Állapot: **lefutott (2026-11-18).** Hat feladatspecifikus (nem zero-shot) modell, ugyanazon a 16 Moby Dick-részleten, mint az E1/E2 ([`RESULTS-E1.md`](RESULTS-E1.md), [`RESULTS-E2.md`](RESULTS-E2.md)). A zero-shot modelleket (DeBERTa, ModernBERT) a lassúságuk miatt nem vettük újra.*

## Kérdés

A korábbi enkóderes mérés ([`../model-selection/RESULTS.md`](../model-selection/RESULTS.md)) két modellje (vad-bert, GoEmotions) a skála csak 4–5%-át használta. Két lehetséges ok:
1. **a módszer:** 120–300 szavas darabok pontszámának átlaga a semleges pont felé húz;
2. **a modellek:** rövid, nem irodalmi szövegen tanultak (EmoBank, Reddit).

Ezért **mondatonként** pontozunk, és a részlet összesítését (átlag, percentilisek, a szélsőséges mondatok aránya) külön vizsgáljuk. A régi két modell mellé négy újat vettünk fel, mindegyik szépirodalmon vagy történeteken tanult, vagy a korábbi mérésből maradt ki.

## Modellek

| Rövid név | Modell | Kimenet | Tanítóadat | Licenc |
|---|---|---|---|---|
| vadbert | [`RobroKools/vad-bert`](https://huggingface.co/RobroKools/vad-bert) (BERT-base) | V, A, D (EmoBank, kb. 1–5) | EmoBank | MIT |
| goemotions | [`SamLowe/roberta-base-go_emotions`](https://huggingface.co/SamLowe/roberta-base-go_emotions) | 28 érzelem (multi-label); V/A/T saját táblázatból | Reddit | MIT |
| pert | [`edsi-umd/PERT-EmoPair`](https://huggingface.co/edsi-umd/PERT-EmoPair) (RoBERTa-large) | V (kb. 1–5), A és D (0 körül, kb. −1..1) | EmoPair | CC-BY-4.0 |
| fiction | [`fpianz/sentiment-fiction`](https://huggingface.co/fpianz/sentiment-fiction) (RoBERTa-large) | neg/neu/pos → V = p(pos) − p(neg) | 13,9 ezer kézzel címkézett **szépirodalmi** mondat | MIT |
| emolit | [`lrei/roberta-large-emolit`](https://huggingface.co/lrei/roberta-large-emolit) | 38 érzelem (multi-label) | **Gutenberg**-mondatok, félig felügyelt | MIT |
| stories | [`chrlukas/stories-emotion-c4`](https://huggingface.co/chrlukas/stories-emotion-c4) (DeBERTa-v3-large) | V, A (0–1), mondatonként, ±4 mondat kontextussal | főleg gyerektörténetek | **nincs megadva, „csak demó”** |

- A PERT-EmoPair saját fejet használ (a modellkártya `RoBERTaForVAD` osztálya), a súlyok hiánytalanul betöltődtek. A kártya a teljes promptolt szöveget 256 tokenre vágja, ami egy hosszú mondatnál a `<mask>`-os promptot vágná le; ezért mi a mondatot vágjuk, a prompt mindig megmarad.
- A stories a mondat utáni `[SEP]` tokenen jósol; a bemenet a mondat és a két oldalán 4–4 mondat, `[SEP]`-pel elválasztva (a modell repójának `src/data.py`-ja szerint).
- A GoEmotions V/A-táblázata a törölt régi táblázat **újraalkotása**, nem azonos vele. A T mindkét érzelem-modellnél: fear + nervousness + 0,6·anger + 0,3·(annoyance + disgust), legfeljebb 1.

## Módszer

- **Részletek:** a 16 E1/E2-részlet ([`tone_probe.py`](tone_probe.py) `PASSAGES`), ugyanattól a kezdőponttól, de **mondathatáron** vágva, amint elérte a 700 szót (700–786 szó); a 300 szavas változat ennek az eleje. A fejezetcímek kimaradnak.
- **Mondatokra bontás:** szabályalapú ([`sentence_probe.py`](sentence_probe.py) `split_sentences`): mondatvégi jel (+ záró idézőjel), szóköz, nagybetű / nyitó idézőjel; rövidítések kivéve. Ehhez a [`book.py`](book.py) új `block_paragraphs` függvénye kell: a Gutenberg-XHTML a `<p>`-n belül is tör sort, és a régi `paragraphs` ezeket külön „bekezdésnek” vette (az E1/E2-t ez nem érintette, mert ott csak a szavakat fűztük össze). Összesen 496 mondat a részletekben, 330 az ablakokban. Csonkolás: modellenként 1–6 mondat (pl. a „whiteness” 467 szavas mondata).
- **Összesítés részletenként:** szóhosszal súlyozott **átlag**, **p10**, **p90**, valamint a szélsőséges mondatok szóaránya: **−low** (a modell összes mondatának alsó negyedébe eső mondatok aránya, negálva, hogy a nagyobb érték mindenhol „pozitívabb / izgatottabb / feszültebb” legyen) és **high** (a felső negyed).
- **Régi módszer** (vad-bert, GoEmotions): ugyanaz a 700 szavas részlet kb. 300 szavas, mondathatáron vágott darabokban, súlyozott átlaggal.
- **Várt értékek:** [`annotations_vat.csv`](annotations_vat.csv), részletenként V/A/T 1–5 (a Qwen-prompt fokozataival). **Ideiglenesek**, nem független annotátortól; 16 részletnél |ρ| ≥ 0,50 kell a p < 0,05-höz. Összevetésül a Qwen3-4B (4. prompt) a 7 közös részleten.
- **Címkék:** a GoEmotions és az EmoLit érzelmeit egy kézzel írt leképezés (`ATMOSPHERE` az [`analyze_sentences.py`](analyze_sentences.py)-ben) összegzi az E2 atmoszféra-címkéire; értékelés átlagos precizitással (AP), mint az E2-ben.
- **Ablakok:** a 3. és a 132. fejezet 300 szavas ablakai (mint az E1/E2-ben), modellenként z-pontszámmal.
- Minden modell külön folyamatban, 4 szálon, CPU-n (WSL, 3,8 GB RAM + swap).

Fájlok: [`sentence_probe.py`](sentence_probe.py), [`analyze_sentences.py`](analyze_sentences.py), [`annotations_vat.csv`](annotations_vat.csv), [`results/`](results/) (`sent_<modell>.csv` mondatonként, `sent_<modell>.json`, `sent_analysis.md` a teljes táblázatokkal, `sent.log`).

```bash
~/.venvs/music-book-eval/bin/python sentence_probe.py ../../../book_source/moby_dick.epub   # mind a 6, kb. 1 óra (letöltéssel)
python3 analyze_sentences.py
```

## Eredmények

### Sebesség, memória (16 × ~700 szó)

| Modell | Betöltés (s) | Csúcs RSS (MB) | s / 1000 szó | s / 700 szavas részlet |
|---|---|---|---|---|
| vadbert | 1 | 1250 | 3,0 | 2,2 |
| goemotions | 4 | 1185 | 3,2 | 2,3 |
| fiction | 71* | 1998 | 12,1 | 8,7 |
| emolit | 85* | 2162 | 12,8 | 9,2 |
| pert | 78* | 2234 | 20,2 | 14,5 |
| stories | 135* | 2018 | **117,5** | **84,7** |

\* első futás, letöltéssel. A stories azért lassú, mert minden mondatot a 8 szomszédjával együtt olvas újra (kb. 9-szeres munka), DeBERTa-large-dzsal; ez a Qwen3-4B sebessége (50–100 s / szegmens).

### Skálakihasználás (a részletátlagok terjedelme / a skála szélessége, 700 szó)

| | V | A | T |
|---|---|---|---|
| vadbert | 0,08 | 0,11 | – |
| goemotions | 0,09 | 0,11 | 0,13 |
| pert | 0,10 | 0,27 | – |
| fiction | **0,36** | – | – |
| stories | **0,49** | **0,34** | – |
| emolit | – | – | 0,23 |

A régi mérésben a szórás/skála 0,04–0,05 volt; ugyanez itt vad-bertnél 0,02–0,03, a fictionnél 0,09, a storiesnál 0,10–0,11 ([`results/sent_analysis.md`](results/sent_analysis.md)).

### Spearman ρ az ideiglenes V/A/T értékekkel (16 részlet, 700 szó)

| Modell.dim | átlag | p10 | p90 | −low | high | Qwen (7 részlet, átlag) |
|---|---|---|---|---|---|---|
| vadbert.V | +0,45 | +0,56 | +0,25 | +0,45 | +0,22 | +0,77 |
| vadbert.A | +0,44 | +0,23 | +0,38 | +0,37 | +0,45 | +0,36 |
| pert.V | +0,50 | +0,43 | +0,05 | **+0,73** | +0,30 | +0,86 |
| pert.A | +0,62 | +0,31 | **+0,83** | +0,24 | +0,71 | +0,64 |
| fiction.V | +0,41 | +0,59 | +0,15 | +0,49 | +0,13 | +0,77 |
| stories.V | +0,57 | **+0,69** | +0,57 | +0,68 | +0,47 | +0,67 |
| stories.A | +0,63 | +0,29 | **+0,82** | +0,42 | +0,62 | +0,54 |
| goemotions.V | +0,34 | +0,56 | +0,11 | +0,12 | +0,04 | +0,80 |
| goemotions.A | +0,09 | +0,06 | +0,36 | −0,14 | −0,03 | −0,37 |
| goemotions.T | +0,33 | +0,20 | +0,57 | +0,18 | +0,17 | +0,00 |
| emolit.T | +0,57 | +0,18 | +0,57 | +0,39 | **+0,67** | +0,85 |

A 300 szavas változat szinte mindenhol gyengébb (pl. pert.A átlag +0,55, emolit.T átlag +0,28), a stories kivételével (V +0,58, A +0,60).

### Régi módszer (darabok átlaga) vs. mondatszint

| Modell.dim | darab: terjedelem / skála | mondat-átlag: terjedelem / skála | darab: ρ | mondat-átlag: ρ | mondat, legjobb összesítés: ρ |
|---|---|---|---|---|---|
| vadbert.V | 0,13 | 0,08 | +0,50 | +0,45 | +0,56 (p10) |
| vadbert.A | 0,16 | 0,11 | +0,36 | +0,44 | +0,45 (high) |
| goemotions.V | 0,26 | 0,09 | +0,32 | +0,34 | +0,56 (p10) |
| goemotions.A | 0,12 | 0,11 | +0,21 | +0,09 | +0,36 (p90) |
| goemotions.T | 0,18 | 0,13 | +0,48 | +0,33 | +0,57 (p90) |

**A régi két modell gyengesége nem a módszerből jön.** A mondatonkénti átlag nem tágítja a skálát (a darabos átlag terjedelme még nagyobb is), és a rangsor sem lesz jobb. Csak a percentilisek javítanak valamennyit (+0,1–0,2), de ez minden modellnél így van.

### Egyezés a modellek között (a részletátlagok Spearman ρ-ja)

- **V:** vadbert, pert, fiction, stories egymással +0,65–0,90; a GoEmotions mindegyikkel csak +0,41–0,60.
- **A:** vadbert, pert, stories egymással +0,85–0,90; a GoEmotions +0,22–0,40.

A régi mérés +0,28–0,30-as vad-bert ↔ GoEmotions egyezése itt +0,60 / +0,40; a V/A-regresszorok viszont egymással erősen egyeznek, tehát **közös jelet mérnek**, és a GoEmotions lóg ki.

### Atmoszféra-címkék (E2 címkék, érzelem-leképezéssel), átlagos AP

| | átlag 700 | p90 700 | átlag 300 | p90 300 | véletlen |
|---|---|---|---|---|---|
| goemotions | 0,48 | 0,43 | 0,49 | 0,51 | 0,24 |
| **emolit** | **0,59** | 0,54 | 0,53 | **0,65** | 0,24 |
| *(E2 zero-shot ModernBERT, összevetésül)* | *0,67* | | *0,68* | | |

Az EmoLit erős címkéi: peaceful 0,92 (300 szó, p90: 1,00), melancholic 0,86, ominous 0,80, warm and cozy 0,70. **A humor (whimsical) mindkét modellnél a véletlen szintjén van** (0,20–0,28), mint az E2-ben, és a wondrous is gyenge (0,21–0,28).

### Ablakok

Minden modell ugyanazt a két ablakot találja a legsötétebbnek és legfeszültebbnek: a 132. fejezetben Ahab „desolation of solitude” vallomását (600 szó: V z = −2,0..−2,5, emolit.T +2,5), a 3. fejezetben Queequeg éjszakai érkezését (4500 szó: V −2,1..−2,5, A +1,3..+2,8, T +2,5..+3,7). A nyugodt nap (132. fej., 0 szó) mindenhol pozitív V és alacsony A. **Hibák:** a 3. fejezet 2700. szavánál a fogadós tréfáját a harpunásról, aki „a fejét árulja”, minden modell szó szerint veszi (negatív V, magas A és T); a 132. fejezet végén az üldözés („There she blows!”, 2100 szó) egyik modellnél sem ad magas arousalt.

## Értékelés modellenként

| Modell | Döntés | Indok |
|---|---|---|
| **pert** (PERT-EmoPair) | **megtartjuk** (V, A) | A legjobb használható V/A-modell: A ρ +0,62 (átlag) / +0,83 (p90), V +0,73 (−low); a Qwennel +0,86 (V), +0,64 (A). Licenc tiszta (CC-BY-4.0). 14,5 s / szegmens. Hátrány: általános (EmoBank-szerű) adat, a V-skála szűk (10%), a humort szó szerint veszi. |
| **emolit** | **megtartjuk** (T, tagek) | Az egyetlen jól működő feszültség-jel (ρ +0,57 / +0,67, a Qwennel +0,85) és a legjobb tag-modell (AP 0,59–0,65; peaceful, melancholic, ominous jó). Szépirodalmon tanult, MIT, 9 s / szegmens. Hátrány: whimsical és wondrous gyenge, a gold F1 csak 0,59. |
| stories | **elvetjük** (a termékhez); összevetési alapnak marad | A rangsorban a legjobb V (ρ +0,57 / +0,69) és a pert szintjén lévő A (+0,63 / +0,82), a legszélesebb skálával – a kontextus tehát segít. De **nincs licenc („csak demó”)**, és **84,7 s / szegmens**, ami a Qwen3-4B sebessége, kevesebb kimenettel. |
| fiction | **elvetjük** | A V-skálát jól kihasználja (36%), de a rangsora nem jobb a vad-bertnél (+0,41 átlag, +0,59 p10), és a pert/stories mögött marad; a többi V-modellel +0,78–0,90-re egyezik, tehát nem ad új információt. A tágabb skála egyszerű átskálázással a pertből is elérhető. Kis felhasználói bázis. |
| vadbert | **elvetjük** | Mondatszinten is szűk (8–11%), a rangsora gyengébb a pertnél, amellyel erősen egyezik (+0,86 / +0,89), tehát ugyanazt méri rosszabbul. Egyetlen előnye a sebesség (2 s / szegmens). |
| goemotions | **elvetjük** | Az arousal nem működik (ρ +0,09, a Qwennel −0,37), a T gyengébb az EmoLitnél, a címkéi AP-je (0,48) is alatta van; a többi modellel gyengén egyezik. A Reddit-címkék (confusion, curiosity) irodalmi szövegre nem illenek. |

**Összesítve:** a **pert + emolit** páros adja a teljes sémát (V, A, T, tagek), kb. **24 s / 700 szavas szegmens** alatt, ami 2–4-szer gyorsabb a Qwen3-4B-nél (50–100 s), kb. 2,2 GB memóriával (egymás után futtatva). Indoklást nem ad, a humort nem ismeri fel, és az akciójelenetet az ablakpróbában nem emelte ki. A Qwen3-4B helyett ezért nem, de **LLM nélküli összehasonlítási alapnak** (dolgozat) és a desztilláció (E5) ellenőrzésére alkalmas.

## Bizonytalanságok

- **A várt értékek ideiglenesek** (egy, nem független annotáló), egy könyv, 16 részlet. Egy-két részlet helycseréje 0,1–0,2-vel mozgatja a ρ-t.
- **Az összesítést az adatok ismeretében választottuk** (p10 a V-hez, p90 / high az A-hoz és a T-hez). Ez illesztés, nem független mérés; egy új könyvön előre rögzített összesítéssel kell ellenőrizni.
- A GoEmotions V/A-táblázata és az érzelem → atmoszféra leképezés saját, kézzel írt; ezek is befolyásolják az eredményt.
- A PERT arousal-skálája nem dokumentált (megfigyelt tartomány −0,78..0,82); a terjedelmet −1..1 skálához viszonyítottuk. A rangsort ez nem érinti.

## Következő lépések

- Ha az LLM nélküli ág marad: a pert + emolit összesítésének (p10 / p90 / high) **rögzítése**, és ellenőrzés egy második könyvön, független kézi címkékkel.
- Az E5-ös desztillációs tervben a pert és az emolit a „tanítás nélküli” alapvonal: a desztillált ModernBERT-nek ezeket kell felülmúlnia.
