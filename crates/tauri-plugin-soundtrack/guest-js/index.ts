import { invoke } from '@tauri-apps/api/core';

// The input types of the plugin (the counterparts of `src/models.rs`). 
// Structurally they match the adapter types; 
// later both will come from a generated `soundtrack-types` package.

export interface Locator {
  bookId: string;
  href: string;
  sectionIndex: number;
  progression: number;
  totalProgression?: number;
  text?: { highlight?: string };
}

export interface LocationEvent {
  locator: Locator;
  chapterTitle?: string;
  isJump: boolean;
  visibleText?: string;
}

/** Sends the EPUB to the backend as a raw body. Resolves to the book id (SHA-256 of the content). */
export async function openBook(data: Blob): Promise<string> {
  return invoke<string>('plugin:soundtrack|open_book', new Uint8Array(await data.arrayBuffer()));
}

export async function closeBook(): Promise<void> {
  await invoke('plugin:soundtrack|close_book');
}

export async function reportLocation(location: LocationEvent): Promise<void> {
  await invoke('plugin:soundtrack|report_location', { location });
}
