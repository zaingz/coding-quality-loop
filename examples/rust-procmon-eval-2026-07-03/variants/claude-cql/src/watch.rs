use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use crate::error::AppError;
use crate::output::{print_procs, Format};
use crate::proc::{list_all_procs, read_mem_total_kb, read_uptime};

/// Run the watch loop. Refreshes every `interval_secs` until Ctrl-C.
pub fn run_watch(
    pattern: Option<&str>,
    interval_secs: f64,
    fmt: &Format,
    exact: bool,
) -> Result<(), AppError> {
    let clk_tck = 100u64; // standard Linux HZ
    let mem_total_kb = read_mem_total_kb().unwrap_or(1);

    // Compile regex pattern if provided and not exact mode.
    let regex = if let Some(pat) = pattern {
        if !exact {
            Some(
                regex::Regex::new(pat)
                    .map_err(|e| AppError::NoMatch(format!("invalid regex '{pat}': {e}")))?,
            )
        } else {
            None
        }
    } else {
        None
    };

    let running = Arc::new(AtomicBool::new(true));
    let r = running.clone();

    // Use a process-global AtomicBool set by the SIGINT handler.
    STOP_FLAG.store(false, Ordering::SeqCst);
    // SAFETY: registering a signal handler that only performs an async-signal-safe
    // atomic store. The cast via *const () avoids the function_casts_as_integer lint.
    unsafe {
        libc::signal(
            libc::SIGINT,
            handle_sigint as *const () as libc::sighandler_t,
        );
    }
    let _ = r; // suppress warning; we use STOP_FLAG instead

    let interval = Duration::from_secs_f64(interval_secs.max(0.1));

    loop {
        if STOP_FLAG.load(Ordering::SeqCst) || !running.load(Ordering::SeqCst) {
            break;
        }

        let uptime = read_uptime().unwrap_or(1.0);
        let mut procs = list_all_procs(clk_tck, uptime, mem_total_kb);

        // Filter by pattern.
        if let Some(pat) = pattern {
            if exact {
                procs.retain(|p| p.command.contains(pat) || p.comm.contains(pat));
            } else if let Some(ref re) = regex {
                procs.retain(|p| re.is_match(&p.command) || re.is_match(&p.comm));
            }
        }

        procs.sort_by_key(|p| p.pid);

        // Clear screen and reprint.
        print!("\x1b[H\x1b[2J");
        print_procs(&procs, fmt);

        thread::sleep(interval);

        if STOP_FLAG.load(Ordering::SeqCst) {
            break;
        }
    }

    // Restore default SIGINT.
    // SAFETY: restoring to default signal disposition.
    unsafe {
        libc::signal(libc::SIGINT, libc::SIG_DFL);
    }

    Ok(())
}

/// Process-global stop flag set by SIGINT handler.
static STOP_FLAG: AtomicBool = AtomicBool::new(false);

/// SIGINT handler: set the global stop flag.
///
/// # Safety
/// This function is async-signal-safe: it only calls an atomic store.
extern "C" fn handle_sigint(_: libc::c_int) {
    STOP_FLAG.store(true, Ordering::SeqCst);
}
