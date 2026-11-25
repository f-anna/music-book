// Background analysis: one thread, the cache first, the model only on a miss.
// Pure Rust module

use std::collections::VecDeque;
use std::sync::{Arc, Condvar, Mutex};
use std::time::{Duration, Instant};

use crate::analysis::MoodAnalyzer;
use crate::epub::Book;
use crate::models::MoodAnalysis;
use crate::store::{Key, Store};

/// Cache hits are answered at once; only misses go to the worker's own thread,
/// so a request never waits for a model analysis.
pub struct Worker {
    shared: Arc<Shared>,
    /// Locked only for single reads and writes, never during an analysis.
    store: Arc<Mutex<Store>>,
    model_id: String,
}

struct Shared {
    queue: Mutex<Queue>,
    wake: Condvar,
}

#[derive(Default)]
struct Queue {
    book: Option<Arc<Book>>,
    /// The segment of the latest request, to ignore page turns within it.
    current: Option<usize>,
    pending: VecDeque<usize>,
}

impl Worker {
    pub fn spawn(store: Store, analyzer: Box<dyn MoodAnalyzer>) -> Self {
        let shared = Arc::new(Shared { queue: Mutex::new(Queue::default()), wake: Condvar::new() });
        let store = Arc::new(Mutex::new(store));
        let model_id = analyzer.model_id().to_owned();
        let (thread_shared, thread_store) = (shared.clone(), store.clone());
        std::thread::Builder::new()
            .name("soundtrack-analysis".into())
            .spawn(move || run(&thread_shared, &thread_store, analyzer.as_ref()))
            .expect("cannot start the analysis thread");
        Worker { shared, store, model_id }
    }

    /// Prints `segment`'s analysis right away if it is cached; otherwise queues it, and the next
    /// segment ahead too if that is not cached. Replaces the earlier requests, so that fast paging
    /// does not pile up work; an analysis already running is finished and cached.
    pub fn request(&self, book: &Arc<Book>, segment: usize) {
        let mut queue = self.shared.queue.lock().unwrap();
        let same_book = queue.book.as_ref().is_some_and(|b| Arc::ptr_eq(b, book));
        if same_book && queue.current == Some(segment) {
            return;
        }
        queue.book = Some(book.clone());
        queue.current = Some(segment);
        queue.pending.clear();

        let ahead = segment + 1;
        for index in std::iter::once(segment).chain((ahead < book.segments.len()).then_some(ahead)) {
            match cached(&self.store, &book.id, index, &self.model_id) {
                Some(analysis) if index == segment => print_analysis(index, "cache", None, &analysis),
                Some(_) => {}
                None => queue.pending.push_back(index),
            }
        }
        if !queue.pending.is_empty() {
            self.shared.wake.notify_one();
        }
    }

    /// Drops the pending requests and the book (on close).
    pub fn clear(&self) {
        *self.shared.queue.lock().unwrap() = Queue::default();
    }
}

fn cached(store: &Mutex<Store>, book_hash: &str, seg_index: usize, model_id: &str) -> Option<MoodAnalysis> {
    let key = Key { book_hash, seg_index, model_id };
    store.lock().unwrap().get(&key).unwrap_or_else(|e| {
        eprintln!("[soundtrack] cache read failed: {e}");
        None
    })
}

fn run(shared: &Shared, store: &Mutex<Store>, analyzer: &dyn MoodAnalyzer) {
    loop {
        let (book, index) = {
            let mut queue = shared.queue.lock().unwrap();
            loop {
                if let Some(book) = queue.book.clone() {
                    if let Some(index) = queue.pending.pop_front() {
                        break (book, index);
                    }
                }
                queue = shared.wake.wait(queue).unwrap();
            }
        };
        analyze_segment(store, analyzer, &book, index);
    }
}

fn analyze_segment(store: &Mutex<Store>, analyzer: &dyn MoodAnalyzer, book: &Book, index: usize) {
    // It may have been analyzed since it was queued (e.g. as the segment ahead).
    if cached(store, &book.id, index, analyzer.model_id()).is_some() {
        return;
    }
    let segment = &book.segments[index];
    let started = Instant::now();
    match analyzer.analyze(book.segment_text(segment)) {
        Ok(analysis) => {
            let elapsed = started.elapsed();
            let key = Key { book_hash: &book.id, seg_index: index, model_id: analyzer.model_id() };
            if let Err(e) = store.lock().unwrap().put(&key, segment, &analysis, elapsed) {
                eprintln!("[soundtrack] cache write failed: {e}");
            }
            print_analysis(index, "model", Some(elapsed), &analysis);
        }
        // Not cached, so the next request tries again.
        Err(e) => eprintln!(
            "[soundtrack] analysis #{index} failed after {:.1}s: {e}",
            started.elapsed().as_secs_f32()
        ),
    }
}

fn print_analysis(index: usize, via: &str, elapsed: Option<Duration>, a: &MoodAnalysis) {
    let elapsed = elapsed.map(|d| format!(" {:.1}s", d.as_secs_f32())).unwrap_or_default();
    let tags: Vec<_> = a.tags.iter().map(|t| t.name()).collect();
    eprintln!(
        "[soundtrack] analysis #{index} via={via}{elapsed} V={} A={} T={} tags=[{}] {:?}",
        a.valence,
        a.arousal,
        a.tension,
        tags.join(", "),
        a.rationale,
    );
}
