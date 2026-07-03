use crate::proc::ProcInfo;

/// Column widths for the fixed-width table.
const W_PID: usize = 7;
const W_PPID: usize = 7;
const W_USER: usize = 10;
const W_CPU: usize = 6;
const W_MEM: usize = 6;
const W_RSS: usize = 10;
const W_START: usize = 9;
// COMMAND is the remainder; we truncate at 60 chars for readability.
const W_CMD: usize = 60;

/// Print the table header.
pub fn print_header() {
    println!(
        "{:<W_PID$} {:<W_PPID$} {:<W_USER$} {:>W_CPU$} {:>W_MEM$} {:>W_RSS$} {:<W_START$} COMMAND",
        "PID", "PPID", "USER", "%CPU", "%MEM", "RSS(KB)", "START"
    );
}

/// Print a single process row.
pub fn print_row(p: &ProcInfo) {
    let cmd = if p.command.len() > W_CMD {
        format!("{}…", &p.command[..W_CMD - 1])
    } else {
        p.command.clone()
    };
    println!(
        "{:<W_PID$} {:<W_PPID$} {:<W_USER$} {:>W_CPU$.1} {:>W_MEM$.1} {:>W_RSS$} {:<W_START$} {}",
        p.pid, p.ppid, p.user, p.cpu_pct, p.mem_pct, p.rss_kb, p.start_fmt, cmd
    );
}

/// Print a full table (header + rows) for a list of processes.
pub fn print_table(procs: &[ProcInfo]) {
    print_header();
    for p in procs {
        print_row(p);
    }
}
