import type {
  BookOpenedEvent,
  LocationEvent,
  ReaderAdapter,
  Unsubscribe,
} from './types';

export type * from './types';

const HIGHLIGHT_LENGTH = 200;

/** A `<foliate-view>` elem általunk használt része. */
interface FoliateView extends EventTarget {
  book?: { sections?: { id?: string }[] };
  renderer?: { scrolled?: boolean };
}

/** A `<foliate-view>` `relocate` eventjének általunk használt mezői. */
interface RelocateDetail {
  reason?: string;
  range?: Range;
  index?: number;
  fraction?: number;
  page?: number;
  pages?: number;
  tocItem?: { label?: string } | null;
}

export type BookSource = File | Blob | string;

export interface FoliateAdapter extends ReaderAdapter {
  /** A view-t a `view.open()` előtt kell átadni, hogy a kezdő pozíció se vesszen el. */
  attach(view: EventTarget, source: BookSource): void;
  detach(): void;
}

function createEmitter<T>() {
  const listeners = new Set<(value: T) => void>();
  return {
    on(cb: (value: T) => void): Unsubscribe {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    emit(value: T) {
      for (const cb of listeners) {
        try {
          cb(value);
        } catch (e) {
          console.error('[adapter-foliate] listener error', e);
        }
      }
    },
  };
}

async function toBlob(source: BookSource): Promise<Blob> {
  if (typeof source !== 'string') return source;
  const response = await fetch(source);
  return response.blob();
}

async function sha256Hex(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer());
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
}

function clamp01(x: number): number {
  return Math.min(1, Math.max(0, x));
}

/**
 * A view szintű `fraction` a teljes könyvre vonatkozik, ezért a fejezeten belüli arányt
 * a `page`/`pages` párból számoljuk, a foliate-js paginatorának képletével
 * (lapozós módban az első és utolsó oldal üres kitöltő oldal).
 */
function sectionProgression(detail: RelocateDetail, scrolled: boolean): number {
  const page = detail.page;
  const pages = detail.pages;
  if (page == null || pages == null) return 0;
  if (scrolled) return pages > 1 ? clamp01((page - 1) / (pages - 1)) : 0;
  return pages > 2 ? clamp01((page - 1) / (pages - 2)) : 0;
}

export function createFoliateAdapter(): FoliateAdapter {
  const locationChanged = createEmitter<LocationEvent>();
  const bookOpened = createEmitter<BookOpenedEvent>();
  const bookClosed = createEmitter<void>();

  let view: FoliateView | null = null;
  let generation = 0;
  let bookIdPromise: Promise<string> | null = null;
  let lastKey: string | null = null;

  const onRelocate = (e: Event) => {
    const currentView = view;
    if (!currentView || !bookIdPromise) return;
    const detail = ((e as CustomEvent<RelocateDetail>).detail ?? {}) as RelocateDetail;
    const sectionIndex = detail.index ?? 0;

    // A range később megváltozhat, ezért a szöveget azonnal kiolvassuk.
    const visibleText = detail.range?.toString().replace(/\s+/g, ' ').trim() ?? '';
    const href = currentView.book?.sections?.[sectionIndex]?.id ?? String(sectionIndex);
    const progression = sectionProgression(detail, currentView.renderer?.scrolled ?? false);
    const highlight = visibleText.slice(0, HIGHLIGHT_LENGTH);
    const isJump = detail.reason === 'navigation' || detail.reason === 'anchor';

    const myGeneration = generation;
    bookIdPromise
      .then(bookId => {
        if (myGeneration !== generation) return;
        // A foliate átméretezéskor is küld relocate-et ugyanarra a helyre.
        const key = `${href}|${progression.toFixed(4)}|${highlight}`;
        if (key === lastKey) return;
        lastKey = key;

        locationChanged.emit({
          locator: {
            bookId,
            href,
            sectionIndex,
            progression,
            totalProgression: detail.fraction,
            text: highlight ? { highlight } : undefined,
          },
          chapterTitle: detail.tocItem?.label || undefined,
          isJump,
          visibleText,
        });
      })
      .catch(() => {
        // A hash hibáját az attach már naplózta.
      });
  };

  const detach = () => {
    if (!view) return;
    view.removeEventListener('relocate', onRelocate);
    view = null;
    bookIdPromise = null;
    lastKey = null;
    generation++;
    bookClosed.emit();
  };

  const attach = (newView: EventTarget, source: BookSource) => {
    detach();
    view = newView as FoliateView;
    const myGeneration = generation;

    bookIdPromise = toBlob(source).then(async data => {
      const bookId = await sha256Hex(data);
      if (myGeneration === generation) bookOpened.emit({ bookId, data });
      return bookId;
    });
    bookIdPromise.catch(e => console.warn('[adapter-foliate] could not hash book', e));

    view.addEventListener('relocate', onRelocate);
  };

  return {
    attach,
    detach,
    onLocationChanged: locationChanged.on,
    onBookOpened: bookOpened.on,
    onBookClosed: bookClosed.on,
  };
}
