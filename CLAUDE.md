# Book Soundtrack – hangulatkövető háttérzene e-book olvasóhoz

Egyetemi projekt. Egy e-book olvasóhoz készülő funkció, amely az olvasott szöveg aktuális hangulatához igazodó háttérzenét szólaltat meg előre elkészített, rétegezett zenei stemek keverésével.

## Technológiai stack

- **Host olvasó:** [FolioReader](https://github.com/bastonta/FolioReader) fork ([f-anna/folioreader-study-project](https://github.com/f-anna/folioreader-study-project)), submodule-ként a `hosts/folioreader` mappában (Tauri v2 + React 19 + TypeScript + Foliate.js, Rust backend sqlx/SQLite-tal). Asztali és Android platformra.
- **Saját backend:** Rust, egyetlen Tauri v2 pluginként (`tauri-plugin-soundtrack`).
- **Saját frontend:** TypeScript/React csomagok (reader adapter, később UI).
- **Audio:** még nyitott kérdés: Rust oldalon `kira` crate, vagy frontendben Web Audio API / Tone.js.

## Jelenlegi állapot

- [x] FolioReader forkolva (`f-anna/folioreader-study-project`).
- [x] Saját repó létrehozva (`music-book`, ág: `master`, még nincs első commit).
- [x] A fork submodule-ként felvéve: `hosts/folioreader`.
  - A stage-elt submodule-mutató még a régi `588f22a`-ra mutat, a kicsekkolt állapot viszont `7afb0e9` (a PR #1 merge-e). Az első commit előtt: `git add hosts/folioreader`.
- [x] Gyökér `package.json` (npm workspaces: `packages/*`) és `.gitignore`.
- [x] **`packages/adapter-foliate`** kész: `createFoliateAdapter()` → `attach(view, bookSource)` / `detach()` + `ReaderAdapter` eventek. Részletek lent, az 1. mérföldkőnél.
- [~] **A ReadingContext lecserélése a forkban** (ág: `replace-reading-context`, még nincs commitolva/PR-ezve):
  - `src/context/ReadingContext.tsx` törölve, az `App.tsx`-ből a Provider kivéve. A `RequireAuth` wrapper a könyvtárnézet (`/`) elől **szándékosan ki van véve** (vele nem lehetett helyi könyvet megnyitni); a `/profile` route-on megmarad.
  - Új `src/soundtrack.ts`: az adapter példánya; DEV módban `console.debug`-ra írja az eseményeket (ez váltja a korábbi kiírást, később a plugin felé továbbít).
  - `vite.config.ts`: `server.forwardConsole` (`error`, `warn`, `debug`), így a WebView `console.debug` sorai (pl. `[soundtrack] location {...}`) a `npm run tauri dev` termináljában is megjelennek. Enélkül a Vite csak AI-ügynökből indítva továbbít, kézzel indítva semmit.
  - `FoliateReader.tsx`: csak `soundtrackAdapter.attach(view, bookSource)` a view létrehozásakor és `detach()` a cleanupban.
  - `package.json`: `"adapter-foliate": "file:../../packages/adapter-foliate"` (a `package-lock.json` kézzel frissítve).
  - Kipróbálva (WSL, `npm run tauri dev`, Moby Dick EPUB): a könyvnyitás, a hash, a kezdő pozíció és a lapozásonkénti locatorok megjelennek a terminálban, duplikátum nélkül. Hátravan: commit, PR.
- [ ] Plugin és Cargo workspace még nincs.

## Félév scope (önlab)

Négy lépés, végponttól végpontig működve:

1. **Kontextus megszerzése:** olvasási pozíció és a hozzá tartozó szöveg (szegmens) a backendben.
2. **Elemzés:** a szegmens szövegének elemzése **kész nyelvi modellel** (saját modell tanítása nincs a scope-ban).
3. **Strukturált kimenet:** fix sémájú, validált JSON (`MoodAnalysis`, lásd lent), SQLite-ban cache-elve.
4. **Zenei rétegek vezérlése:** a strukturált kimenetből leképezés a stemek hangerejére, alap simítással.

**Nincs a scope-ban** (a „Később” részbe tartozik): gördülő story state és snapshotok, könyvprofil és fejezet-alapvonal, előretekintés, leitmotívumok, felhasználói teszt, Android-specifikus finomhangolás.

### Fork munkafolyamat

A fork `main` ága az integrációs ág (nincs külön `soundtrack-integration` ág). A változtatások feature ágon készülnek (pl. `create-reading-context`), és PR-rel kerülnek a fork `main`-jébe.

---

## Architektúra – meghozott döntések

### Rétegek

```
Foliate.js <foliate-view> (relocate event)
        │  adapter.attach(view, bookSource)   ← a fork csak ennyit hív
        ▼
[Reader adapter]          frontend, olvasóspecifikus → saját Locator
        │  reportLocation()
        ▼
[tauri-plugin-soundtrack] integráció: commandok, eventek, állapot, vezénylés
        │
        ├─▶ epub       EPUB megnyitása, szegmentálás, Locator → szegmens
        ├─▶ store      SQLite cache: elemzések, story state snapshotok, könyvprofil
        ├─▶ analysis   MoodAnalyzer trait + implementációk
        ├─▶ director   simítás, hiszterézis, állapotgép, előretekintés
        └─▶ audio      stem-keverés (Rust) VAGY event a frontend audio felé
```

### Alapelvek

1. **Olvasófüggetlenség (port & adapter).** A saját kód soha nem függ közvetlenül a FolioReadertől vagy a Foliate.js-től. Minden olvasóhoz egy vékony adapter tartozik, amely a `ReaderAdapter` interfészt valósítja meg.
2. **Saját pozíció-modell.** CFI és FolioReader-azonosító nem kerülhet a saját adatbázisba és a backend logikába. Saját `Locator`-t használunk (a Readium Locator modell mintájára). A könyv azonosítója a **fájltartalom hash-e**.
3. **A szöveget a backend nyeri ki.** A Rust plugin maga nyitja meg az EPUB-ot (pl. `epub` vagy `rbook` crate), és determinisztikusan szegmentál. Az olvasó csak a pozíciót jelenti. Így a szegmentálás független a tördeléstől, és lehetséges az előre-elemzés.
4. **Folytonos hangulatvektor mint köztes reprezentáció.** `MoodVector { valence, arousal, tension, tags, confidence }` (Russell-féle valence–arousal modell + feszültség). Az elemző nem tud a zenéről, a zenei rész nem tud a szövegről.
5. **Hierarchikus kontextus, három időskálán:**
   | Szint | Tartalom | Zenei szerep |
   |---|---|---|
   | Könyv | műfaj, korszak, alaphangulat, szereplők | hangszerelés, paletta |
   | Fejezet / jelenet | helyszín, szereplők, konfliktus, ív | stem-szett, hangnem, alap-intenzitás |
   | Lokális | aktuális oldal hangulata | rétegek hangereje, szűrők |
   - A lokális hangulat a jelenet-alapvonalhoz képest értendő: `mood = baseline.lerp(local, 0.4 * confidence)`.
   - **Gördülő story state:** az elemző az előző állapotot és az új szegmenst kapja, és mindkettőt visszaadja (új hangulat + frissített állapot). A kontextus mérete így korlátos.
   - **Snapshotok** szegmensenként SQLite-ban, hogy ugráskor (TOC, scrubber, könyvjelző) folytatható legyen.
   - **Háttér-worker prioritási sorral:** az aktuális pozíció környéke előre kerül.
   - **Előretekintés:** a rendező a következő pár szegmenst is látja, így a zene anticipálhat (pl. feszültség felépítése tetőpont előtt). A UI-ban nem jelenhet meg spoiler.
   - **LLM nélküli változat:** több időállandójú EMA a lokális hangulatvektorokon (összehasonlítási alap a dolgozathoz).
   - *Ez a pont (a lokális szint kivételével) a félév scope-ján kívül esik.*
6. **Adaptív zene, játékaudió-technikákkal.** Vertikális rétegezés (4–6 szinkron stem, a hangerőt a hangulat vezérli) + horizontális váltás (szettcsere crossfade-del, ütemhatáron). A remegés ellen exponenciális simítás, hiszterézis, minimális tartózkodási idő és a gyors lapozás felismerése.
7. **Egyetlen plugin, belső modulokkal.** A plugin nem önálló réteg, hanem a Tauri-integráció: commandokat fogad, a `setup`-ban létrehozza a komponenseket, vezényli a folyamatot, és eventekkel visszajelez. A belső modularitást Rust modulok, később crate-ek adják, nem több plugin.
8. **Modulszabály:** a pluginon belül **csak a `lib.rs` és a `commands.rs` importálhat `tauri`-t.** Minden más modul tiszta Rust, így később gond nélkül kiemelhető külön crate-be (pl. CLI-hez, kiértékeléshez).

### Strukturált kimenet (félév, vázlat)

Az elemző kimenete. A modell JSON-schema / structured output módban adja vissza, a backend validálja (serde + tartomány-ellenőrzés). Hibás kimenetnél újrapróbálás, végül `confidence = 0`.

```json
{
  "valence": -0.4,          // -1..1
  "arousal": 0.7,           // 0..1
  "tension": 0.8,           // 0..1
  "tags": ["suspense", "night"],   // FIX szókészletből, nem szabad szöveg
  "confidence": 0.75,       // 0..1
  "rationale": "..."        // rövid indoklás, csak debughoz és a dolgozathoz
}
```

- A `tags` zárt listából jön (pl. 10–20 elem). Csak így képezhető le determinisztikusan stemekre.
- A zenei leképezés **adatvezérelt**: stem-szettenként egy config (pl. `assets/stems/<set>/mapping.json`), amely megadja, hogy melyik stem hangereje hogyan függ az `arousal`/`tension`/`valence` értékektől és a tagektől. Így a zenei rész kód nélkül hangolható.

### Kulcs típusok (vázlat)

```ts
// Megvalósítva: packages/adapter-foliate/src/types.ts
export interface Locator {
  bookId: string;          // fájltartalom SHA-256 hash
  href: string;            // spine elem / fejezetfájl
  sectionIndex: number;    // spine index
  progression: number;     // 0..1 a fejezeten belül (közelítő)
  totalProgression?: number;
  text?: { highlight?: string };   // a látható szöveg eleje → pontos pozíció a backendben
}

export interface LocationEvent {
  locator: Locator;
  chapterTitle?: string;
  isJump: boolean;         // ugrás (TOC, link, keresés) vs. lapozás
  visibleText?: string;    // opcionális, csak ellenőrzésre
}

export interface ReaderAdapter {
  onLocationChanged(cb: (e: LocationEvent) => void): Unsubscribe;
  onBookOpened(cb: (e: { bookId: string; data: Blob }) => void): Unsubscribe;  // FolioReaderben a forrás File/Blob, nem mindig fájlútvonal
  onBookClosed(cb: () => void): Unsubscribe;
}
```

```rust
#[async_trait]
pub trait MoodAnalyzer: Send + Sync {
    async fn analyze(&self, text: &str, ctx: &SegmentContext) -> Result<MoodVector>;
}

#[async_trait]
pub trait ContextualAnalyzer {
    async fn analyze(&self, segment: &str, prev: &StoryState, book: &BookProfile)
        -> Result<(MoodVector, StoryState)>;
}

pub struct StoryState {
    pub location: Option<String>,
    pub present_characters: Vec<String>,
    pub active_conflict: Option<String>,
    pub arc_phase: ArcPhase,        // Building, Climax, Resolution, Calm
    pub scene_summary: String,
    pub scene_baseline: MoodVector,
}
```

### A plugin API-ja (tervezett)

- **Commandok:** `open_book(bytes)` (raw body; a plugin hash-el, és az app data mappába cache-eli az EPUB-ot, a `bookId` = hash), `report_location(location)`, `close_book()`, `set_settings(enabled, volume, intensity)`, `get_debug_state()`
- **Eventek:** `soundtrack://mood-changed`, `soundtrack://mix-changed` (frontend audio esetén), `soundtrack://analysis-progress`

### Adatbázis (vázlat, saját SQLite fájl)

```sql
CREATE TABLE segment_analysis (
  book_hash   TEXT,
  seg_index   INTEGER,
  cfi_start   TEXT,   -- TODO: CFI helyett saját reprezentáció (spine index + karakter-offset), lásd 2. alapelv
  cfi_end     TEXT,
  mood_json   TEXT,
  state_json  TEXT,   -- StoryState snapshot a szegmens UTÁN
  PRIMARY KEY (book_hash, seg_index)
);
CREATE TABLE book_profile (book_hash TEXT PRIMARY KEY, profile_json TEXT);
```

---

## Repó-szerkezet

### Kezdeti (a `hosts/` már kész, a többit most kell létrehozni)

```
music-book/
├── Cargo.toml                         # Rust workspace
├── package.json                       # npm workspaces
├── crates/
│   └── tauri-plugin-soundtrack/       # generált plugin váz
│       └── src/
│           ├── lib.rs                 # init, setup, state  (tauri OK)
│           ├── commands.rs            # vékony továbbhívás  (tauri OK)
│           ├── models.rs              # Locator, LocationEvent, MoodVector
│           ├── epub.rs
│           ├── analysis/mod.rs
│           ├── store.rs
│           └── director.rs
├── packages/
│   └── adapter-foliate/               # foliate-view relocate → Locator  ✔ kész
└── hosts/
    └── folioreader/                   # git submodule (f-anna/folioreader-study-project, main)  ✔ kész
```

### Célállapot (csak akkor bontsuk tovább, ha szükséges)

```
crates/   soundtrack-core, soundtrack-epub, soundtrack-analysis, soundtrack-director,
          soundtrack-store, soundtrack-cli, tauri-plugin-soundtrack
packages/ soundtrack-types (tauri-specta / ts-rs generált), soundtrack-ui,
          audio-engine-web (ha frontend audio), adapter-foliate, adapter-fake
assets/stems/
hosts/folioreader/
```

Az `adapter-fake` egy .txt fájlt lapozó teszt-olvasó: lehetővé teszi a fejlesztést a FolioReader nélkül, az automatizált teszteket, és bizonyítja az olvasó cserélhetőségét.

---

## Következő lépések

### 1. mérföldkő – Walking skeleton

Cél: lapozás → adapter → plugin command → a Rust terminálban megjelenik a `Locator`. Nincs elemzés, nincs zene, de minden réteg a helyén van.

- [x] Új repó (`music-book`) és a fork felvétele submodule-ként (`hosts/folioreader`).
- [x] A „current context” kód a fork `main`-jén (`ReadingContext`, PR #1); lecserélve adapterre (`replace-reading-context` ág).
- [ ] Submodule-mutató frissítése (`git add hosts/folioreader`), első commit a fő repóban.
- [ ] Gyökér `Cargo.toml`:
  ```toml
  [workspace]
  resolver = "2"
  members = ["crates/*"]
  exclude = ["hosts/folioreader/src-tauri"]   # nélküle a FolioReader build hibát dob
  ```
- [x] Gyökér `package.json` (`workspaces: ["packages/*"]`; a plugin JS része majd ide kerül: `crates/tauri-plugin-soundtrack`). A gyökérben lévő `workspaces` mező a Vite `server.fs.allow` miatt is kell, különben a dev szerver nem szolgálja ki a forkon kívüli csomag fájljait.
- [ ] Plugin váz generálása a `crates/` mappában: `npx @tauri-apps/cli plugin new soundtrack` (a generált tartalom CLI-verziónként eltérhet). A `ping` példacommand átnevezése `report_location`-re, a `build.rs` `COMMANDS` listájának frissítése.
- [ ] `models.rs`: `Locator`, `LocationEvent` (serde).
- [ ] `guest-js/index.ts`: `reportLocation()` → `invoke('plugin:soundtrack|report_location', { location })`.
- [x] `packages/adapter-foliate` (`src/index.ts`, `src/types.ts`; build lépés nincs, a `exports` közvetlenül a `.ts` forrásra mutat):
  - A `<foliate-view>` `relocate` eventjére maga iratkozik fel; `attach`-ot a `view.open()` **előtt** kell hívni, így a kezdő pozíció is kimegy.
  - `bookId` = a `bookSource` (File/Blob/URL) SHA-256 hash-e; a locator-eventek megvárják. `onBookOpened` a hash-t és a Blobot adja (ebből lesz majd az `open_book(bytes)`).
  - `href` = `book.sections[index].id`, `progression` a `page/pages`-ből (a paginator képletével), `totalProgression` = a Foliate `fraction`, `text.highlight` = a látható szöveg első 200 karaktere (normalizált whitespace), `isJump` = `reason` ∈ {`navigation`, `anchor`}.
  - Azonos helyre küldött ismételt relocate (pl. átméretezés) kiszűrve; `detach()` után a késve beérkező eventek eldobva.
- [~] ReadingContext lecserélése a forkban (lásd „Jelenlegi állapot”). Kipróbálva. Hátra van: commit, PR a fork `main`-jébe, submodule-mutató frissítése.
- [ ] `src/soundtrack.ts` a forkban: a DEV kiírás helyett `adapter.onLocationChanged(e => reportLocation(e))` és `onBookOpened(e => openBook(e.data))`, ha a plugin kész.
- [ ] Bekötés a forkba:
  - `hosts/folioreader/src-tauri/Cargo.toml`: `tauri-plugin-soundtrack = { path = "../../../crates/tauri-plugin-soundtrack" }`
  - `hosts/folioreader/package.json`: ~~`"adapter-foliate": "file:../../packages/adapter-foliate"`~~ (kész), `"tauri-plugin-soundtrack-api": "file:../../crates/tauri-plugin-soundtrack"`
  - `lib.rs`: `.plugin(tauri_plugin_soundtrack::init())`
  - `src-tauri/capabilities/*.json`: `"soundtrack:default"` hozzáadása a `permissions` listához
- [ ] Teszt: `cd hosts/folioreader && npm run tauri dev`, lapozás, és a locator megjelenik a Rust konzolon.

### 2. mérföldkő – Szöveg a backendben

- [ ] `open_book(bytes)` command: a könyvazonosító a tartalom hash-e, az EPUB cache-elése az app data mappába.
- [ ] `epub.rs`: EPUB megnyitása, spine bejárása, bekezdéshatárokra igazított, kb. 300–800 szavas szegmensek.
- [ ] Locator → szegmens leképezés (spine index + a `text.highlight` fuzzy keresése a fejezet szövegében → karakter-offset → szegmens). Lapozáskor az aktuális szegmens szövegének kiírása.

### 3. mérföldkő – Elemzés kész nyelvi modellel, strukturált kimenet

- [ ] `MoodAnalysis` séma véglegesítése (mezők, tartományok, zárt tag-lista).
- [ ] `MoodAnalyzer` trait + első implementáció: LLM structured output (JSON schema) módban, HTTP-n (`reqwest`). Az API-kulcs ne kerüljön a repóba.
- [ ] Validálás, újrapróbálás, `confidence` kezelése.
- [ ] SQLite cache (`store.rs`): `(book_hash, seg_index, model_id, prompt_version)` → kimenet.
- [ ] Opcionális második implementáció összehasonlításhoz: kész érzelem-osztályozó vagy NRC VAD lexikon.
- [ ] Kézzel címkézett ground truth néhány fejezetre, és egy egyszerű metrika (pl. korreláció a valence/arousal értékekkel).

### 4. mérföldkő – Zenei rétegek vezérlése

- [ ] **Döntés:** frontend (Web Audio / Tone.js, ajánlott a prototípushoz) vagy Rust (`kira`).
- [ ] 1–2 stem-szett beszerzése (4–6 szinkron, loopolható stem, licenc rendben). Ezt a 1–3. mérföldkővel **párhuzamosan** érdemes elkezdeni.
- [ ] Engine: szinkron indítás, rétegenkénti hangerő, crossfade.
- [ ] Előbb **kézi csúszkákkal** vezérelve, utána a `mapping.json` alapján a `MoodAnalysis`-ből.

### 5. mérföldkő – Összekötés

- [ ] Pozíció → szegmens → elemzés (cache) → leképezés → audio, végponttól végpontig.
- [ ] Alap simítás (exponenciális) és minimális tartózkodási idő. A gyors lapozásnál az elemzés debounce-olása.
- [ ] Egyszerű előre-elemzés: a következő 1–2 szegmens háttérben.
- [ ] Debug nézet: aktuális szegmens, `MoodAnalysis`, stem-hangerők (a dolgozat ábráihoz is).

### Később

- [ ] Hiszterézis, állapotgép, háttér-worker prioritási sorral.
- [ ] Hierarchikus kontextus: könyvprofil → fejezet-alapvonal → story state snapshotokkal → előretekintés.
- [ ] Leitmotívumok (szereplőhöz/helyszínhez rendelt motívum-stem).
- [ ] UI: be/ki kapcsoló, hangerő, intenzitás, debug overlay (spoilermentesen).
- [ ] `adapter-fake` és automatizált tesztek.
- [ ] Felhasználói teszt random zenés kontrollcsoporttal.
- [ ] Elemzők összehasonlítása (LLM vs. lokális modell vs. lexikon vs. EMA).

---

## Nyitott kérdések

- Hol szól a zene: Rust (`kira`) vagy frontend (Web Audio)? Android WebView audio megbízhatósága?
- Melyik kész modell legyen? (Felhőalapú LLM API vs. lokális, pl. Ollama, vs. kész osztályozó.) Milyen nyelvűek a tesztkönyvek? Magyar szöveghez LLM vagy multilingual modell kell.
- Honnan lesznek a stemek, és milyen licenccel?

## Ismert buktatók

- **Cargo workspace:** a `hosts/folioreader/src-tauri` legyen `exclude`-olva, különben a FolioReader build hibát dob.
- **Capabilities:** ha a `soundtrack:default` hiányzik, a hívás „not allowed” hibát ad.
- **Fejlesztői környezet (WSL):** Node az nvm-ből (`~/.nvm`, LTS), Rust a rustup-ból (`~/.cargo`), a Tauri Linux-függőségei apt-tal telepítve. A Windows-os `node.exe`/`npm`-et ne használd a WSL-es repóra: a symlinkeknél (`file:` függőség) elbukik. Ha a `which npm` a `/mnt/c/...` útvonalat adja, nincs betöltve az nvm. A WSLg alatt megjelenő `libEGL` / `MESA ZINK` warningok ártalmatlanok. Ha az ablak üres marad: `WEBKIT_DISABLE_DMABUF_RENDERER=1`.
- **Submodule:** módosítás után két commit kell. Először a submodule-on belül (feature ág → PR → fork `main`), utána a fő repóban a submodule-mutató frissítése (`git add hosts/folioreader`). Klónozás: `git clone --recurse-submodules`.
- **Fork-diff minimális maradjon:** a forkban csak a plugin regisztrációja, a capability bejegyzés, az `adapter.attach()` hívás és a UI felcsatolása legyen. Egyetlen szándékos kivétel: a `RequireAuth` wrapper eltávolítása a könyvtárnézet elől (`App.tsx`). Ne tegyük vissza, mert vele Folio szerver / bejelentkezés nélkül nem lehet helyi könyvet megnyitni. A „Browse” nézet szerver nélkül `Server URL not configured` hibát ad, ez várt viselkedés.
- **A régi ReadingContext problémái** (ezért cseréltük adapterre): az első pozíciónál (`previousLocation === null`) nem megy ki event, így a kezdő pozíció elveszik. A `clearLocation()` a `locationRef`-et nem nullázza. Mivel a `FoliateReader` maga is fogyasztja a contextet, minden `relocate` újrarendereli a teljes olvasókomponenst. A `fraction` a teljes könyvre vonatkozik, a `tocItem.href` pedig TOC-horgony, nem spine elem.
- **Hosszú spine elemek:** a Gutenberg-féle EPUB-okban egy spine elem több fejezetet is tartalmazhat (a Moby Dickben a tartalomjegyzék, az ETYMOLOGY és az EXTRACTS is ugyanabban a fájlban van). A `progression` ezért durva; a szegmens megtalálásához a `text.highlight` alapú keresés kell (2. mérföldkő).
- **React StrictMode (dev):** a view-t létrehozó effect kétszer fut le, ezért induláskor egy `book closed` jön a `book opened` előtt. Ez várt viselkedés, az első, eldobott attach hash-e nem megy ki.
- **Tauri verzió-eltérés warning:** `tauri-plugin-opener (v2.7.1) : @tauri-apps/plugin-opener (v2.6.0)`. Nem tőlünk jön: a `Cargo.lock` gitignore-olva van, ezért a friss build újabb crate-et old fel. Javítás: az npm csomagot `^2.7`-re emelni (külön commitban).
- **A könyvforrás File/Blob:** a FolioReader `bookSource`-a nem mindig fájlútvonal (Androidon főleg nem), ezért az `open_book` bájtokat kap, nem útvonalat.