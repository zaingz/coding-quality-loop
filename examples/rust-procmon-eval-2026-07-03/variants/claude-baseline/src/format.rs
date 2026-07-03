//! Output formatting: table and JSON modes.

use crate::proc::ProcessInfo;

/// Print a fixed-width table of processes to stdout.
pub fn print_table(procs: &[ProcessInfo]) {
    // Header
    println!("{:<7} {:<7} {:<10} {:>5} {:>5} {:>9} {:>8}  COMMAND",
        "PID", "PPID", "USER", "%CPU", "%MEM", "RSS(KB)", "START");
    println!("{}", "-".repeat(80));

    for p in procs {
        let cmd = truncate(&p.command, 40);
        println!(
            "{:<7} {:<7} {:<10} {:>5.1} {:>5.1} {:>9} {:>8}  {}",
            p.pid, p.ppid, truncate(&p.user, 10), p.cpu_pct, p.mem_pct,
            p.rss_kb, p.start_str, cmd
        );
    }
}

/// Print one JSON line per process to stdout.
pub fn print_json(procs: &[ProcessInfo]) {
    for p in procs {
        // serde_json::to_string never fails for our well-formed struct.
        println!("{}", serde_json::to_string(p).unwrap());
    }
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_string()
    } else {
        format!("{}…", &s[..max.saturating_sub(1)])
    }
}
