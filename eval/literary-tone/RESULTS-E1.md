# Irodalmi hangvétel-osztályozó (E1) – mérési jegyzőkönyv

*Állapot: **E1 lefutott (2026-11-04), az eredmény negatív.** A tesztterv (`literary_atmosphere_model_test_plan.md`) E2 kísérlete (zero-shot ModernBERT): [`RESULTS-E2.md`](RESULTS-E2.md); az E3–E5 (kontextus-ablációk, finomhangolás) még nincs elvégezve.*

## Miért újra a feladatspecifikus irány?

A korábbi enkóderes kísérlet ([`../model-selection/RESULTS.md`](../model-selection/RESULTS.md)) két okból nem volt döntő:
- a szegmenseket **mondathatáron vágott rövid darabokra** bontottuk, és a darabok pontszámait átlagoltuk, így a hangulat kiátlagolódott;
- a modellek **érzelmeket** (GoEmotions, VAD) mértek, nem a szöveg **hangvételét/atmoszféráját**. Ez nem ugyanaz: egy szereplő érzelme nem azonos azzal, amit az olvasó a jelenetből érez.

Az új terv ezért hangvétel-osztályozót vizsgál, a részlet **egészén**, egy futtatással.

## Modell

[`Mitchins/literary-tone-classifier-v0.1`](https://huggingface.co/Mitchins/literary-tone-classifier-v0.1), revízió `afbd525d443b1b04fda2eeeb64315533427857b9`.

| | |
|---|---|
| Alap | `microsoft/deberta-v3-small` (6 réteg, 768 rejtett dim., ~141M paraméter az embeddinggel), 568 MB (fp32 safetensors) |
| Kimenet | 5 osztály, softmax (egy címke, nem multi-label): **dark, humorous, lyrical, melancholic, warm** |
| Bemenet | a kártya szerint 2048 token (`results.json`: `max_length: 2048`). A `config.json` `max_position_embeddings` értéke 512, de a DeBERTa-v3 relatív pozíciókat használ (`position_biased_input: false`), így a 2048 token technikailag működik |
| Tanítóadat | 4052 „irodalmi részlet”, a forrás nincs megadva („consolidated from 12-tone taxonomy”); validálás 406 részleten, F1-macro 0,91 |
| Licenc | MIT a `model_card.json` szerint, de a Hugging Face metaadatban nincs licenc-címke. A tanítóadat eredete ismeretlen |
| Népszerűség | 6 letöltés, 0 like (2026-11-04). Kísérleti, egyszemélyes modell |

A kártya maga írja: a „lyrical” stílus, nem hangulat; tempót / feszültséget („tense / propulsive”) nem ismer fel; a „warm” és a „melancholic” megjelent könyveken nincs tesztelve.

## Módszer

- **Szöveg:** Moby Dick (ugyanaz az EPUB és ugyanaz a kinyerés, mint az [`llm_probe.py`](../qwen3-llamacpp/llm_probe.py)-ben). A fejezetcím kimarad a bemenetből, mert a cím (pl. „Queequeg in His Coffin”) elárulná a hangulatot.
- **Részletek:** 16 kontrasztos kezdőpont: a korábbi LLM-próba 7 részlete, kiegészítve a hiányzó hangvételekkel (humor, erőszak, gyász, prédikáció, esszé). Mindegyik **négy hosszon, ugyanattól a ponttól**: 150, 300, 700 és 1500 szó (szóhatáron vágva). A tesztterv 150–350 szavas részleteket javasol; a 700 a plugin szegmensméretének mediánja; az 1500 a kártya ajánlott felső határa.
- **Futtatás:** egy hívás részletenként, darabolás és átlagolás nélkül, `torch` CPU-n, 4 szálon. Csonkolás 2048 tokennél (a legtöbb 1500 szavas bemenet belefér, a `sunset` és a `stubb_supper` 1500 szavas változata 2261, illetve 2297 token, ezeknél a vége lemaradt).
- **Várt címkék:** [`annotations.csv`](annotations.csv). **Ideiglenesek**, nem független annotátortól származnak: egy várt címke és az elfogadható alternatívák (pl. a prédikáció *dark*, de a *lyrical* is elfogadható). Az összehasonlítás csak tájékoztató; a terv szerinti két független annotátor még hiányzik.
- **Ablakos próba:** egymást követő, nem átfedő 300 szavas ablakok a 3. fejezeten (16 ablak: a sötét festmény → a fogadós tréfái, Queequeg érkezése) és a 132. fejezeten (8 ablak). Kérdés: követi-e a címke a szöveg változását?
- **Padding-próba:** a kártya minden bemenetet 2048 tokenre paddol. Három részleten összevetettük a paddolt és a paddolatlan kimenetet.

Fájlok: [`tone_probe.py`](tone_probe.py) (futtatás), [`book.py`](book.py) (EPUB → bekezdések, részletek vágása), [`results/`](results/) (`e1_passages.csv`, `e1_windows.csv`, `e1_run.json`, `e1.log`).

Futtatás:
```bash
~/.venvs/music-book-eval/bin/python tone_probe.py ../../../book_source/moby_dick.epub
```

## Eredmények

### Részletek (a legvalószínűbb címke)

| Részlet | Várt | 150 szó | 300 szó | 700 szó | 1500 szó |
|---|---|---|---|---|---|
| loomings (1. fej. eleje, ironikus) | humorous | dark 0,47 | humorous 0,84 | humorous 0,80 | humorous 0,90 |
| spouter_painting (a sötét festmény) | dark | humorous 0,74 | humorous 0,86 | humorous 0,83 | humorous 0,76 |
| spouter_landlord (a fogadós tréfái) | humorous | dark 0,34 | humorous 0,56 | humorous 0,73 | humorous 0,80 |
| sermon (Mapple atya) | dark / lyrical | **lyrical 0,75** | **lyrical 0,73** | humorous 0,34 | humorous 0,62 |
| bosom_friend (barátság) | warm | humorous 0,64 | humorous 0,83 | humorous 0,89 | humorous 0,89 |
| cetology (áltudományos) | humorous | humorous 0,45 | humorous 0,66 | humorous 0,87 | humorous 0,88 |
| sunset (Ahab monológja) | dark / lyrical | **dark 0,56** | humorous 0,78 | humorous 0,70 | humorous 0,88 |
| whiteness (a fehérség iszonyata) | dark / lyrical | humorous 0,67 | humorous 0,82 | humorous 0,85 | humorous 0,84 |
| stubb_kills (a bálna leszúrása) | dark | **dark 0,77** | **dark 0,68** | humorous 0,84 | humorous 0,89 |
| stubb_supper (Stubb és a szakács) | humorous | humorous 0,52 | humorous 0,79 | humorous 0,88 | humorous 0,83 |
| castaway (Pip) | melancholic / dark | humorous 0,81 | humorous 0,89 | humorous 0,90 | humorous 0,90 |
| squeeze (boldog) | warm / lyrical | humorous 0,68 | humorous 0,63 | humorous 0,74 | humorous 0,89 |
| coffin (Queequeg betegsége) | melancholic | humorous 0,58 | dark 0,69 | humorous 0,85 | humorous 0,88 |
| candles (tájfun) | dark | humorous 0,81 | humorous 0,88 | humorous 0,87 | humorous 0,87 |
| symphony (Ahab és Starbuck) | melancholic / lyrical, warm | **lyrical 0,79** | **lyrical 0,57** | humorous 0,57 | humorous 0,89 |
| catastrophe (a Pequod pusztulása) | dark | humorous 0,62 | humorous 0,70 | humorous 0,89 | humorous 0,75 |

| Hossz | Pontos találat | Elfogadható találat | Címkeeloszlás | Legnagyobb valószínűség: melancholic / warm |
|---|---|---|---|---|
| 150 szó | 4/16 | 6/16 | humorous 10, dark 4, lyrical 2 | 0,12 / 0,20 |
| 300 szó | 5/16 | 7/16 | humorous 12, dark 2, lyrical 2 | 0,06 / 0,23 |
| 700 szó | 4/16 | 4/16 | **humorous 16** | 0,04 / 0,23 |
| 1500 szó | 4/16 | 4/16 | **humorous 16** | 0,02 / 0,05 |

700 szó fölött a modell **minden részletre „humorous”-t ad** (0,57–0,90). A 4 „találat” csak a 4 eleve humorosnak várt részlet, nem valódi megkülönböztetés. A **melancholic és a warm egyszer sem nyer**, a melancholic valószínűsége sehol sem éri el a 0,13-at, Pip elhagyásánál és Queequeg koporsójánál sem.

### Ablakok

- **3. fejezet** (16 × 300 szó): 13 ablak humorous, 3 dark. A dark ablakok **hihető helyen** vannak: 600 szónál a kocsma („dearly sells the sailors deliriums and death… his poison”), 3900 és 4500 szónál Queequeg éjszakai érkezése és Ishmael félelme („as if it was the devil himself”). A sötét festmény és a kannibálfegyverek leírása (0–600) viszont humorous, és a dark egyszer sem erős (0,51–0,65).
- **132. fejezet** (8 × 300 szó): az első ablak (a tiszta, kék nap leírása) lyrical (0,57), a harmadik (Ahab: „the desolation of solitude”) dark (0,67), a többi humorous (0,73–0,88), köztük Ahab vallomásának folytatása (feleség, gyermek) is.

300 szavas ablakokban tehát van gyenge, de értelmes jel: a dark a sötétebb helyekre esik. Az alapállapot azonban a „humorous”, és a valószínűségek inkább egy humorous ↔ dark tengely értékeként olvashatók, mint önálló címkeként.

### Sebesség, memória

| | |
|---|---|
| Betöltés (első futás, letöltéssel) | 63 s |
| Csúcs RSS | 1328 MB (betöltés után 901 MB) |
| Futásidő (paddolás nélkül, 4 szál) | 150 szó ≈ 0,2 s · 300 ≈ 0,4 s · 700 ≈ 1,0–1,6 s · 1500 ≈ 3,7–7,5 s |
| Padding 2048 tokenre | a kimenet azonos (eltérés < 2·10⁻⁷), de **14-szer lassabb** (~5,4 s 300 szóra). A kártya mintakódját nem érdemes követni |

Sebességben és memóriában a modell bőven használható volna (a Moby Dick 347 szegmense 700 szavas bemenettel kb. 6 perc). A gond a minőség.

## Értékelés

1. **Doménváltás:** a modell a 19. századi, választékos, ironikus elbeszélői prózát a „humorous” osztályba sorolja, függetlenül a jelenet tartalmától. Feltehetően modern zsánerszövegeken tanult (a kártya Pratchett-, Weir-, Abercrombie-, King-próbákat említ); a „humorous” a legnagyobb osztály (31%), és a validálási mátrixban is a humorous ↔ dark tévesztés a leggyakoribb (12 eset).
2. **Hosszabb bemenet = rosszabb.** Rövid (150–300 szavas) részleten és ablakban van némi jel: a vérontás, Ahab monológja (150 szó), a kocsma és Queequeg éjszakai érkezése *dark*, a prédikáció és a Symphony eleje *lyrical*. Hosszabb bemenetnél ez is eltűnik, és minden „humorous” lesz. Ez ellentétes a kártya ajánlásával (500–1500 szó), és a 2048 tokenes kontextus kihasználása ellen szól.
3. **Hiányzó osztályok:** a zenéhez legfontosabb dimenziók (feszültség, nyugalom ↔ akció) nincsenek a címkék között; a melancholic és a warm ezen a könyvön gyakorlatilag nem működik.
4. **Megbízhatóság:** egyszemélyes, 6 letöltéses modell, ismeretlen tanítóadattal és bizonytalan licenccel.

**Döntés (E1):** ebben a formában a modell **nem használható** a Moby Dick hangulatkövetésére: 700 szótól konstans kimenetet ad, és a melancholic / warm osztály nem működik. Legfeljebb a rövid ablakokon mért `dark` valószínűség lehet egy gyenge kiegészítő jel („mennyire sötét”), önálló elemzőnek nem elég. A terv szerinti következő lépés az E2 (zero-shot ModernBERT-large, saját atmoszféra-címkékkel, a teljes részleten), majd az E3 kontextus-ablációja.

Összevetésül: ugyanezen a 7 közös részleten a Qwen3-4B (4. prompt) a várt sorrendet adta (lásd [`../qwen3-llamacpp/RESULTS.md`](../qwen3-llamacpp/RESULTS.md)).

## Nyitott pontok / a következő kísérletekhez

- Független kézi annotáció (legalább 2 fő) a 16 részletre; az [`annotations.csv`](annotations.csv) jelenleg csak ideiglenes elvárásokat tartalmaz.
- A tesztterv 3–5 könyvet és 120–200 részletet ír elő; ez a próba szándékosan csak a Moby Dicket használta, ezért általánosítani nem lehet belőle (más stílusú könyvön a modell működhet).
- Ha a modellre még visszatérnénk: egy modern regény néhány részlete megmutatná, hogy a hiba a doménből (19. századi próza) vagy magából a modellből adódik.
