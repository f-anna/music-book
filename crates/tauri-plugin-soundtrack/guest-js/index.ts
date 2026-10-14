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

export async function reportLocation(location: LocationEvent): Promise<void> {
  await invoke('plugin:soundtrack|report_location', { location });
}
