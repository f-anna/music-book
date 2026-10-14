// Olvasófüggetlen típusok. Később a plugin modelljeiből generálva (ts-rs / tauri-specta)
// egy külön `soundtrack-types` csomagba kerülnek.

export type Unsubscribe = () => void;

export interface Locator {
  /** A könyv fájltartalmának SHA-256 hash-e (hex). */
  bookId: string;
  /** Spine elem azonosítója (a könyvön belüli fájl útvonala). */
  href: string;
  /** Spine index. */
  sectionIndex: number;
  /** 0..1 a spine elemen belül (közelítő). */
  progression: number;
  /** 0..1 a teljes könyvben (közelítő). */
  totalProgression?: number;
  /** A látható szöveg eleje: ez alapján keresi meg a backend a pontos pozíciót. */
  text?: { highlight?: string };
}

export interface LocationEvent {
  locator: Locator;
  chapterTitle?: string;
  /** Igaz, ha ugrás történt (TOC, link, keresés), nem sima lapozás. */
  isJump: boolean;
  /** A teljes látható szöveg; csak ellenőrzésre / debugra. */
  visibleText?: string;
}

export interface BookOpenedEvent {
  bookId: string;
  data: Blob;
}

export interface ReaderAdapter {
  onLocationChanged(cb: (e: LocationEvent) => void): Unsubscribe;
  onBookOpened(cb: (e: BookOpenedEvent) => void): Unsubscribe;
  onBookClosed(cb: () => void): Unsubscribe;
}
