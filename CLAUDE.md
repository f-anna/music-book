# Book Soundtrack – hangulatkövető háttérzene e-book olvasóhoz

Egyetemi projekt. Egy e-book olvasóhoz készülő funkció, amely az olvasott szöveg aktuális hangulatához igazodó háttérzenét szólaltat meg előre elkészített, rétegezett zenei stemek keverésével.

## Technológiai stack

- **Host olvasó:** [FolioReader](https://github.com/bastonta/FolioReader) fork ([f-anna/folioreader-study-project](https://github.com/f-anna/folioreader-study-project)), submodule-ként a `hosts/folioreader` mappában (Tauri v2 + React 19 + TypeScript + Foliate.js, Rust backend sqlx/SQLite-tal). Asztali és Android platformra.
- **Saját backend:** Rust, egyetlen Tauri v2 pluginként (`tauri-plugin-soundtrack`).
- **Saját frontend:** TypeScript/React csomagok (reader adapter, később UI).
- **EPUB (backend):** `rbook` (konténer: spine, manifest, TOC, metadata) + `scraper` (XHTML → szöveg). Indoklás a 2. mérföldkőnél.
- **Audio:** még nyitott kérdés: Rust oldalon `kira` crate, vagy frontendben Web Audio API / Tone.js.

## Jelenlegi állapot

- [x] FolioReader forkolva (`f-anna/folioreader-study-project`).
- [x] Saját repó létrehozva (`music-book`, ág: `master`, remote: `f-anna/music-book`). Első commit: `ef2bb5d`.
- [x] A fork submodule-ként felvéve: `hosts/folioreader`, a mutató a fork `main`-jén lévő `4468c36`-ra (PR #3 merge) mutat.
- [x] Gyökér `package.json` (npm workspaces: `packages/*`, `crates/tauri-plugin-soundtrack`) és `.gitignore`.
- [x] **`packages/adapter-foliate`** kész: `createFoliateAdapter()` → `attach(view, bookSource)` / `detach()` + `ReaderAdapter` eventek. Részletek lent, az 1. mérföldkőnél.
- [x] **A ReadingContext lecserélése a forkban** (PR #2, `replace-reading-context` → fork `main`, merge: `f352369`):
  - `src/context/ReadingContext.tsx` törölve, az `App.tsx`-ből a Provider kivéve. A `RequireAuth` wrapper a könyvtárnézet (`/`) elől **szándékosan ki van véve** (vele nem lehetett helyi könyvet megnyitni); a `/profile` route-on megmarad.
  - Új `src/soundtrack.ts`: az adapter példánya; DEV módban `console.debug`-ra írja az eseményeket (ez váltja a korábbi kiírást, később a plugin felé továbbít).
  - `vite.config.ts`: `server.forwardConsole` (`error`, `warn`, `debug`), így a WebView `console.debug` sorai (pl. `[soundtrack] location {...}`) a `npm run tauri dev` termináljában is megjelennek. Enélkül a Vite csak AI-ügynökből indítva továbbít, kézzel indítva semmit.
  - `FoliateReader.tsx`: csak `soundtrackAdapter.attach(view, bookSource)` a view létrehozásakor és `detach()` a cleanupban.
  - `package.json`: `"adapter-foliate": "file:../../packages/adapter-foliate"` (a `package-lock.json` kézzel frissítve).
  - Kipróbálva (WSL, `npm run tauri dev`, Moby Dick EPUB): a könyvnyitás, a hash, a kezdő pozíció és a lapozásonkénti locatorok megjelennek a terminálban, duplikátum nélkül.
- [x] Gyökér `Cargo.toml` workspace és **`crates/tauri-plugin-soundtrack`** váz (a generátorból, `--no-example`, mobil projektek nélkül):
  - Commandok: `open_book` (raw body), `close_book`, `report_location(location: LocationEvent)`; `eprintln!`-nel írnak a konzolra (`[soundtrack] ...`). Logger (pl. `tauri-plugin-log`) még nincs. Részletek a 2. mérföldkőnél.
  - A generált `desktop.rs`/`mobile.rs` szétválasztás és az `error.rs` törölve: a logika minden platformon tiszta Rust, a `mobile.rs` pedig egy nem létező Android osztályt (`ExamplePlugin`) regisztrált volna. Ha kell, visszajön.
  - JS API (`tauri-plugin-soundtrack-api`): build lépés és rollup nélkül, az `exports` a `guest-js/index.ts`-re mutat (mint az adapternél). A `@tauri-apps/api` peer dependency; a hostban `resolve.dedupe` oldja fel.
  - A `guest-js` saját `Locator`/`LocationEvent` típusokat definiál (a plugin nem függhet az olvasóspecifikus adaptertől); szerkezetileg egyeznek az adapterével.
- [x] **Bekötés a forkba** (PR #3, `add-soundtrack-plugin` → fork `main`, merge: `4468c36`): `Cargo.toml` path-függőség, `.plugin(tauri_plugin_soundtrack::init())`, `soundtrack:default` a `default.json` capabilityben, `tauri-plugin-soundtrack-api` file-függőség (`npm install`-lal), `vite.config.ts`: `resolve.dedupe: ["@tauri-apps/api"]`, `src/soundtrack.ts`: `onLocationChanged` → `reportLocation`. A `tsc`, a `vite build` és a `cargo build` lefut. Kipróbálva (WSL, Moby Dick): a locatorok lapozásonként megjelennek a Rust konzolon.

- [ ] **`isJump` javítása** (fork, ág: `forward-relocate-reason`, commit `819d3f4`, még nincs push/PR): a `reason` továbbadása a Foliate view `relocate` eventjében. Kipróbálva (WSL, Moby Dick): lapozás → `jump=false`, csúszka/TOC/„következő fejezet” → `jump=true`. Hátra van: push, PR a fork `main`-jébe, majd a submodule-mutató frissítése a fő repóban.
- [x] **EPUB crate döntés** (2. mérföldkő eleje): `rbook` a konténerhez, `scraper` a szöveghez; a spine-indexelés egyezése a Foliate-tel kipróbálva. Kód még nem került a pluginba.

## Félév scope (önlab)

Négy lépés, végponttól végpontig működve:

1. **Kontextus megszerzése:** olvasási pozíció és a hozzá tartozó szöveg (szegmens) a backendben.
2. **Elemzés:** a szegmens szövegének elemzése **kész nyelvi modellel** (saját modell tanítása nincs a scope-ban).
3. **Strukturált kimenet:** fix sémájú, validált JSON (`MoodAnalysis`, lásd lent), SQLite-ban cache-elve.
4. **Zenei rétegek vezérlése:** a strukturált kimenetből leképezés a stemek hangerejére, alap simítással.

**Nyelv:** csak angol nyelvű könyvekkel dolgozunk (tesztkönyv pl. a Moby Dick). Többnyelvűség nincs a scope-ban.

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
3. **A szöveget a backend nyeri ki.** A Rust plugin maga nyitja meg az EPUB-ot (`rbook` crate), és determinisztikusan szegmentál. Az olvasó csak a pozíciót jelenti. Így a szegmentálás független a tördeléstől, és lehetséges az előre-elemzés.
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

### Kezdeti (a `hosts/`, a `packages/adapter-foliate`, a plugin váza és az `epub.rs` kész; az `analysis/`, `store.rs`, `director.rs` még hiányzik)

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
│           ├── epub.rs                # EPUB → szakaszok, szegmensek, Locator → szegmens
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
- [x] A „current context” kód a fork `main`-jén (`ReadingContext`, PR #1); lecserélve adapterre (PR #2).
- [x] Submodule-mutató frissítése, első commit a fő repóban (`ef2bb5d`).
- [x] Gyökér `Cargo.toml`:
  ```toml
  [workspace]
  resolver = "2"
  members = ["crates/*"]
  exclude = ["hosts/folioreader/src-tauri"]   # nélküle a FolioReader build hibát dob
  ```
- [x] Gyökér `package.json` (`workspaces: ["packages/*"]`; a plugin JS része majd ide kerül: `crates/tauri-plugin-soundtrack`). A gyökérben lévő `workspaces` mező a Vite `server.fs.allow` miatt is kell, különben a dev szerver nem szolgálja ki a forkon kívüli csomag fájljait.
- [x] Plugin váz generálása a `crates/` mappában: `npx @tauri-apps/cli plugin new soundtrack` (a generált tartalom CLI-verziónként eltérhet). A `ping` példacommand átnevezése `report_location`-re, a `build.rs` `COMMANDS` listájának frissítése.
- [x] `models.rs`: `Locator`, `LocationEvent` (serde).
- [x] `guest-js/index.ts`: `reportLocation()` → `invoke('plugin:soundtrack|report_location', { location })`.
- [x] `packages/adapter-foliate` (`src/index.ts`, `src/types.ts`; build lépés nincs, a `exports` közvetlenül a `.ts` forrásra mutat):
  - A `<foliate-view>` `relocate` eventjére maga iratkozik fel; `attach`-ot a `view.open()` **előtt** kell hívni, így a kezdő pozíció is kimegy.
  - `bookId` = a `bookSource` (File/Blob/URL) SHA-256 hash-e; a locator-eventek megvárják. `onBookOpened` a hash-t és a Blobot adja (ebből lesz majd az `open_book(bytes)`).
  - `href` = `book.sections[index].id`, `progression` a `page/pages`-ből (a paginator képletével), `totalProgression` = a Foliate `fraction`, `text.highlight` = a látható szöveg első 200 karaktere (normalizált whitespace), `isJump` = `reason` ∈ {`navigation`, `anchor`} (a csúszka, a TOC, a könyvjelző és a fejezetváltó gombok is `navigation`-t adnak). A `reason` csak a fork `view.js`-javításával jut el a view eventjéig, lásd „Fork-diff minimális maradjon”.
  - Azonos helyre küldött ismételt relocate (pl. átméretezés) kiszűrve; `detach()` után a késve beérkező eventek eldobva.
- [x] ReadingContext lecserélése a forkban (PR #2, lásd „Jelenlegi állapot”).
- [x] `src/soundtrack.ts` a forkban: `onLocationChanged(e => reportLocation(e))`. Az `onBookOpened(e => openBook(e.data))` a 2. mérföldkőben jön; addig a book opened/closed DEV kiírás marad.
- [x] Bekötés a forkba (PR #3):
  - `hosts/folioreader/src-tauri/Cargo.toml`: `tauri-plugin-soundtrack = { path = "../../../crates/tauri-plugin-soundtrack" }`
  - `hosts/folioreader/package.json`: `"adapter-foliate": "file:../../packages/adapter-foliate"`, `"tauri-plugin-soundtrack-api": "file:../../crates/tauri-plugin-soundtrack"`
  - `vite.config.ts`: `resolve.dedupe: ["@tauri-apps/api"]` (különben a `crates/` alatti `guest-js` importja nem oldódik fel)
  - `lib.rs`: `.plugin(tauri_plugin_soundtrack::init())`
  - `src-tauri/capabilities/*.json`: `"soundtrack:default"` hozzáadása a `permissions` listához
- [x] Teszt: `cd hosts/folioreader && npm run tauri dev`, lapozás, és a locator megjelenik a Rust konzolon.

### 2. mérföldkő – Szöveg a backendben

- [x] **EPUB crate kiválasztva: `rbook`** (Apache-2.0), rögzített verzióval (`=0.7.12`, 0.x, törő API-változások jöhetnek), `default-features = false, features = ["threadsafe"]` (a `write` nem kell).
  - Elvetve: `epub` (GPL-3.0, az MIT-s FolioReaderrel együtt az egész terméket GPL-essé tenné; régi kurzoros API), `iepub` (kis felhasználói bázis). Tartalék: saját `zip` + `quick-xml` OPF-olvasó (~100 sor), ha az `rbook` gondot okoz.
  - Próba (2026-10-27, 11 helyi EPUB, köztük a Moby Dick és két magyar könyv, egyikben `linear="no"` elemmel): az `rbook` `spine()` indexe, idref-je és href-je **mindegyiknél egyezik** a Foliate `book.sections`-ével. A Foliate oldalt a `foliate-js/epub.js` algoritmusának Python-átirata adta, nem a futó app; a végleges ellenőrzés egy DEV `console.debug(book.sections.map(s => s.id))` kiírással.
  - `Epub::read(Cursor::new(bytes))` működik, így az `open_book` bájtjaihoz nem kell ideiglenes fájl. A nyelv a `metadata().languages()`-ből, a TOC (NCX és EPUB3 nav) a `toc().contents()`-ből jön.
- [x] **Szövegkinyerés: `scraper`** (html5ever, böngészőszerű parse). Azért ez, mert a `text.highlight` a WebView DOM szövege: böngészőszerű parse-szal egyezik a legjobban, ezen múlik a fuzzy keresés. Elvetve: `html2text` (megjelenítésre formáz, torzítja a szöveget és az offseteket), `quick-xml` (szigorú XML, a hibás XHTML-en elbukik). Blokkelemenként (`p`, `h1`–`h6`, `div`, `blockquote`, `li`) bejárva → bekezdések.
- [x] **Második próba** (2026-10-27): `rbook` + `scraper` a Moby Dicken, 8 valódi locatorral a `npm run tauri dev` logjából (a Rust kiírás 60 karakteres `text`-je).
  - **8/8 pontos találat** whitespace-normalizálás után (`split_whitespace().join(" ")`), fuzzy keresés nélkül. Mindkét kinyerés működött: a `<body>` szövegcsomópontjainak összefűzése (mint a `Range.toString()`) és a blokkelemenkénti bekezdésekre bontás (bekezdések szóközzel összefűzve).
  - Mindegyik highlight **egyszer** fordul elő a saját spine elemében, már 30 karakterrel is.
  - A `progression` jelentősen eltér a valódi karakterpozíciótól (pl. 0.215 vs. 0.103, 0.246 vs. 0.130), mert oldalszámból jön. A highlight-keresés tehát kell, a `progression` csak tartalék.
  - Ebből a terv: pontos keresés normalizált szövegben → ha nincs találat, whitespace nélküli keresés → végül `progression × hossz`. Fuzzy keresést csak akkor vezessünk be, ha egy könyvön ezek elbuknak. Az adapter `Range.toString()`-ot használ, ami a blokkok közé nem tesz szóközt; ha egy EPUB-ban a tagek között nincs whitespace (`</h2><p>`), a whitespace nélküli keresés fogja meg.
- [x] **`open_book(bytes)` command** (kód kész, a `cargo check` és a Moby Dick-próba lefut; az appban még nincs kipróbálva, a fork bekötése hiányzik): raw body (`tauri::ipc::Request`, `InvokeBody::Raw`), a JS oldalon `openBook(blob)` → `Uint8Array`. A `bookId` = SHA-256 hex (`epub::content_id`), egyezik az adapterével. Az EPUB az `app_data_dir()/soundtrack/books/<id>.epub`-ba kerül (ha nem sikerül, csak warning). A parse `spawn_blocking`-ban fut (Moby Dick: ~20 ms release, ~270 ms debug buildben). Mellette `close_book` (a `generation` számláló miatt egy épp futó `open_book` nem nyitja újra a bezárt könyvet).
  - Állapot (`lib.rs`, `Session` egy `Mutex`-ben): a megnyitott `Arc<Book>` és a `pending_location`. Ha a `report_location` a könyv betöltése előtt jön, a legutolsó locator elmentődik, és az `open_book` végén feldolgozódik.
- [x] **`epub.rs`** (tiszta Rust): `Book::open(id, bytes)` → `sections` (a Foliate indexelésével, `href` `/` nélkül) + `segments`.
  - Szöveg: a `<body>` blokkelemenként bekezdésekre bontva (a `<br>` is határ), whitespace-normalizálva; a szakasz szövege a bekezdések szóközzel összefűzve (így egyezik a `Range.toString()`-gal).
  - Szegmentálás: mohó, csak bekezdéshatáron vág. Új szegmens, ha a következő bekezdéssel 800 szó fölé menne és már van 300; vagy egy címsornál (`h1`–`h6`), ha már van 100 szó (így a fejezetek külön szegmensbe kerülnek; a TOC-horgonyokra nem volt szükség). A 300 alatti farok az előzőhöz olvad (így néha 800 fölé megy). Szegmensek nem lépnek át spine elemet.
  - Pozíció: spine index + bájt-offset a normalizált szakaszszövegben (`Segment::start/end`).
  - Moby Dick: 13 szakasz, 347 szegmens, 215 845 szó; szegmensméret medián 689, p10 306, p90 791, min 102 (rövid fejezetek), max 1021.
- [x] **Locator → szegmens** (`Book::locate`): pontos keresés a normalizált szövegben → whitespace nélküli keresés → `progression × hossz`. Több találatnál a `progression`-becsléshez legközelebbi nyer. Ha a szakaszban nincs szöveg (pl. borító), nincs szegmens. Lapozáskor a konzolra: `[soundtrack] segment #N section=… words=… via=Exact|IgnoringWhitespace|Progression text="…"`; ha a `href` nem egyezik a reader `href`-jével, WARNING. Moby Dick, valódi locatorokkal: mind `Exact`, a href mindig egyezik.
- [ ] **Bekötés a forkba:** `src/soundtrack.ts`: `onBookOpened(e => openBook(e.data))`, `onBookClosed(() => closeBook())`. Utána teszt az appban: a `book opened` sor a Rust konzolon, és lapozásonként a `segment` sor.

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
- Melyik kész modell legyen? (Felhőalapú LLM API vs. lokális, pl. Ollama, vs. kész osztályozó.) A nyelv eldőlt: csak angol (lásd a félév scope-ját), így angol nyelvű kész osztályozók és az NRC VAD lexikon is szóba jön.
- Honnan lesznek a stemek, és milyen licenccel?

## Ismert buktatók

- **Cargo workspace:** a `hosts/folioreader/src-tauri` legyen `exclude`-olva, különben a FolioReader build hibát dob.
- **Kevés memória (WSL, ~3.7 GB):** a párhuzamos Tauri build OOM-mel elhal (exit 137). Megoldás: `cargo build -j 2`, vagy tartósan `CARGO_BUILD_JOBS=2` / `[build] jobs = 2` a `~/.cargo/config.toml`-ban (a `tauri dev` is ezt használja). Esetleg több memória a `.wslconfig`-ban.
- **Capabilities:** ha a `soundtrack:default` hiányzik, a hívás „not allowed” hibát ad.
- **Fejlesztői környezet (WSL):** Node az nvm-ből (`~/.nvm`, LTS), Rust a rustup-ból (`~/.cargo`), a Tauri Linux-függőségei apt-tal telepítve. A Windows-os `node.exe`/`npm`-et ne használd a WSL-es repóra: a symlinkeknél (`file:` függőség) elbukik. Ha a `which npm` a `/mnt/c/...` útvonalat adja, nincs betöltve az nvm. A WSLg alatt megjelenő `libEGL` / `MESA ZINK` warningok ártalmatlanok. Ha az ablak üres marad: `WEBKIT_DISABLE_DMABUF_RENDERER=1`.
- **Submodule:** módosítás után két commit kell. Először a submodule-on belül (feature ág → PR → fork `main`), utána a fő repóban a submodule-mutató frissítése (`git add hosts/folioreader`). Klónozás: `git clone --recurse-submodules`.
- **Fork-diff minimális maradjon:** a forkban csak a plugin regisztrációja, a capability bejegyzés, az `adapter.attach()` hívás és a UI felcsatolása legyen. Szándékos kivételek:
  1. A `RequireAuth` wrapper eltávolítása a könyvtárnézet elől (`App.tsx`). Ne tegyük vissza, mert vele Folio szerver / bejelentkezés nélkül nem lehet helyi könyvet megnyitni.
  2. A `reason` továbbadása a Foliate view `relocate` eventjében (`src/foliate-js/view.js`, `#onRelocate`: a `lastLocation`-be bekerül a `reason`; ág: `forward-relocate-reason`). Nélküle a `reason` mindig `undefined`, mert a view csak a paginator eventjéből építi újra a detailt, és kihagyja. Emiatt az adapter `isJump`-ja mindig `false` volt. Ugyanez a FolioReader saját hibája is: a `FoliateReader.tsx` relocate-kezelője is a `detail.reason`-t olvassa, így a „quick return” gomb lapozáskor nem tűnt el, és a TOC/link/könyvjelző ugrások is lapozásnak számítottak az olvasási statisztikában. Az upstream FolioReaderben (`bastonta/FolioReader`) és a foliate-js-ben (`johnfactotum/foliate-js`) is hiányzik; ha az upstream javítja, ez a kivétel megszűnik.
  3. A csúszka fókuszának elengedése seek után (`ProgressScrubber.tsx`, ág: `fix-scrubber-focus`), lásd „FolioReader-hiba: csúszka után a nyilak nem lapoztak”. A „Browse” nézet szerver nélkül `Server URL not configured` hibát ad, ez várt viselkedés.
- **A régi ReadingContext problémái** (ezért cseréltük adapterre): az első pozíciónál (`previousLocation === null`) nem megy ki event, így a kezdő pozíció elveszik. A `clearLocation()` a `locationRef`-et nem nullázza. Mivel a `FoliateReader` maga is fogyasztja a contextet, minden `relocate` újrarendereli a teljes olvasókomponenst. A `fraction` a teljes könyvre vonatkozik, a `tocItem.href` pedig TOC-horgony, nem spine elem.
- **Hosszú spine elemek:** a Gutenberg-féle EPUB-okban egy spine elem több fejezetet is tartalmazhat (a Moby Dickben a tartalomjegyzék, az ETYMOLOGY és az EXTRACTS is ugyanabban a fájlban van). A `progression` ezért durva; a szegmens megtalálásához a `text.highlight` alapú keresés kell (2. mérföldkő).
- **React StrictMode (dev):** a view-t létrehozó effect kétszer fut le, ezért induláskor egy `book closed` jön a `book opened` előtt. Ez várt viselkedés, az első, eldobott attach hash-e nem megy ki.
- **Tauri verzió-eltérés warning:** `tauri-plugin-opener (v2.7.1) : @tauri-apps/plugin-opener (v2.6.0)`. Nem tőlünk jön: a `Cargo.lock` gitignore-olva van, ezért a friss build újabb crate-et old fel. Javítás: az npm csomagot `^2.7`-re emelni (külön commitban).
- **FolioReader-hiba: csúszka után a nyilak nem lapoztak** (javítva a forkban, ág: `fix-scrubber-focus`, commit `14a0c11`, még nincs push/PR/kipróbálás; ez a fork-diff 3. kivétele). Kattintás után a `<input type="range">` (`ProgressScrubber.tsx`) fókuszban marad. A globális billentyűkezelő (`FoliateReader.tsx`, `handleGlobalKeyDown`) minden `<input>`-ból jövő billentyűt figyelmen kívül hagy, így a jobbra/balra nyíl a csúszkát lépteti (`step=0.001`, ez kevesebb egy oldalnál), ami `goToFraction`-t hív. A pozíció két oldal között ingadozik, és minden lépés `jump=true` locatort küld. Javítás: egérrel/érintéssel végzett seek után a csúszka elengedi a fókuszt (`blur()` az `onPointerUp`-ban és a globális `pointerup` kezelőben, ha a húzás a csúszkán kívül ér véget). Billentyűzettel (Tab + nyilak) a csúszka továbbra is léptethető. Upstream bejelentésre jelölt.
- **Üres `text.highlight`:** a fejezetek elején (pl. `progression=0.000`) a látható range üres lehet (`text=""`). Ilyenkor a Locator → szegmens leképezés a `progression`-alapú tartalékot használja.
- **Spine-indexelés (`rbook` ↔ Foliate):** a Foliate a `linear="no"` spine elemeket is beszámozza (csak a manifestből hiányzókat hagyja ki), az `rbook` `spine()`-ja szintén. Az `rbook` `reader()`-ét **nem szabad** `LinearBehavior::LinearOnly`-val használni, mert az kihagyja ezeket, és minden `sectionIndex` elcsúszik. A href-ek közti egyetlen eltérés: az `rbook` `/`-rel kezdi (`/OEBPS/x.xhtml`), a Foliate `id`-ja nem (`OEBPS/x.xhtml`); mindkettő dekódolt.
- **A könyvforrás File/Blob:** a FolioReader `bookSource`-a nem mindig fájlútvonal (Androidon főleg nem), ezért az `open_book` bájtokat kap, nem útvonalat.