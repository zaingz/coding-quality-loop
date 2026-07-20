mod format;
mod proc;

use std::collections::HashMap;
use std::io::{self, Write};
use std::process;
use std::thread;
use std::time::Duration;

use clap::{Parser, Subcommand, ValueEnum};
use regex::Regex;

use proc::{ProcessInfo, collect_processes};
use format::{print_table, print_json};

// ─── CLI definitions ────────────────────────────────────────────────────────

#[derive(Parser)]
#[command(
    name = "procmon",
    version,
    about = "Linux process monitor — list, find, kill, watch, tree",
    long_about = None
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Clone, ValueEnum, PartialEq)]
enum Format {
    Table,
    Json,
}

#[derive(Clone, ValueEnum, PartialEq)]
enum SortKey {
    Pid,
    Cpu,
    Mem,
    Start,
}

#[derive(Subcommand)]
enum Command {
    /// List running processes for the current user.
    List {
        /// Sort key
        #[arg(long, value_enum, default_value = "pid")]
        sort: SortKey,
        /// Reverse sort order
        #[arg(long)]
        reverse: bool,
        /// Show processes for all users (default: current user only)
        #[arg(long)]
        all: bool,
        /// Output format
        #[arg(long, value_enum, default_value = "table")]
        format: Format,
    },
    /// Find processes whose command line matches a pattern.
    Find {
        /// Pattern to search for
        pattern: String,
        /// Treat pattern as exact substring (not regex)
        #[arg(long)]
        exact: bool,
        /// Output format
        #[arg(long, value_enum, default_value = "table")]
        format: Format,
    },
    /// Send a signal to a process (by PID or pattern).
    Kill {
        /// PID or regex pattern
        target: String,
        /// Signal to send (e.g. SIGTERM, SIGKILL, 9)
        #[arg(long, default_value = "SIGTERM")]
        signal: String,
        /// Allow killing PID 1, PID 0, or the current process
        #[arg(long)]
        force: bool,
    },
    /// Periodically refresh the process table.
    Watch {
        /// Optional pattern filter
        pattern: Option<String>,
        /// Refresh interval in seconds
        #[arg(long, default_value_t = 2.0)]
        interval: f64,
        /// Output format
        #[arg(long, value_enum, default_value = "table")]
        format: Format,
    },
    /// Print an ASCII process tree.
    Tree {
        /// Root PID (default: 1)
        #[arg(long, default_value_t = 1)]
        pid: u32,
        /// Output format
        #[arg(long, value_enum, default_value = "table")]
        format: Format,
    },
}

// ─── Entry point ────────────────────────────────────────────────────────────

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Command::List { sort, reverse, all, format } => {
            cmd_list(sort, reverse, all, format);
        }
        Command::Find { pattern, exact, format } => {
            cmd_find(&pattern, exact, format);
        }
        Command::Kill { target, signal, force } => {
            cmd_kill(&target, &signal, force);
        }
        Command::Watch { pattern, interval, format } => {
            cmd_watch(pattern.as_deref(), interval, format);
        }
        Command::Tree { pid, format } => {
            cmd_tree(pid, format);
        }
    }
}

// ─── Subcommand implementations ─────────────────────────────────────────────

fn cmd_list(sort: SortKey, reverse: bool, all: bool, fmt: Format) {
    let uid_filter = if all { None } else { Some(current_uid()) };
    let mut procs = collect_processes(uid_filter);
    apply_sort(&mut procs, &sort, reverse);
    output(&procs, &fmt);
}

fn cmd_find(pattern: &str, exact: bool, fmt: Format) {
    let procs = collect_processes(None);
    let matched: Vec<ProcessInfo> = if exact {
        procs.into_iter().filter(|p| p.command.contains(pattern)).collect()
    } else {
        let re = match Regex::new(pattern) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("procmon: invalid regex '{}': {}", pattern, e);
                process::exit(1);
            }
        };
        procs.into_iter().filter(|p| re.is_match(&p.command)).collect()
    };

    if matched.is_empty() {
        eprintln!("procmon: no processes matched '{}'", pattern);
        process::exit(1);
    }
    output(&matched, &fmt);
}

fn cmd_kill(target: &str, signal_str: &str, force: bool) {
    let sig = parse_signal(signal_str);
    let current_pid = std::process::id();

    // If target is a numeric PID, kill that one process.
    if let Ok(pid) = target.parse::<u32>() {
        guard_pid(pid, current_pid, force);
        send_signal(pid, sig);
        return;
    }

    // Otherwise treat as regex pattern.
    let re = match Regex::new(target) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("procmon: invalid pattern '{}': {}", target, e);
            process::exit(1);
        }
    };

    let procs = collect_processes(None);
    let targets: Vec<&ProcessInfo> = procs.iter()
        .filter(|p| re.is_match(&p.command))
        .collect();

    if targets.is_empty() {
        eprintln!("procmon: no processes matched '{}'", target);
        process::exit(1);
    }

    for p in targets {
        guard_pid(p.pid, current_pid, force);
        send_signal(p.pid, sig);
    }
}

fn cmd_watch(pattern: Option<&str>, interval_secs: f64, fmt: Format) {
    // Install a SIGINT handler that sets the RUNNING flag so the loop exits cleanly.
    // SAFETY: we only set an atomic flag inside the handler — async-signal-safe.
    unsafe {
        libc::signal(libc::SIGINT, sigint_handler as *const () as libc::sighandler_t);
    }

    let re = pattern.map(|p| Regex::new(p).unwrap_or_else(|e| {
        eprintln!("procmon: invalid pattern: {}", e);
        process::exit(1);
    }));

    let millis = (interval_secs * 1000.0) as u64;

    loop {
        if !RUNNING.load(std::sync::atomic::Ordering::Relaxed) {
            break;
        }
        // Clear screen (simple ANSI).
        print!("\x1b[2J\x1b[H");
        let _ = io::stdout().flush();

        let procs = collect_processes(None);
        let filtered: Vec<ProcessInfo> = match &re {
            Some(r) => procs.into_iter().filter(|p| r.is_match(&p.command)).collect(),
            None => procs,
        };

        output(&filtered, &fmt);
        println!("\n[interval: {:.1}s — Ctrl-C to quit]", interval_secs);
        let _ = io::stdout().flush();

        thread::sleep(Duration::from_millis(millis));
    }
}

static RUNNING: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(true);

extern "C" fn sigint_handler(_: libc::c_int) {
    RUNNING.store(false, std::sync::atomic::Ordering::Relaxed);
}

fn cmd_tree(root_pid: u32, fmt: Format) {
    let procs = collect_processes(None);
    let by_pid: HashMap<u32, &ProcessInfo> = procs.iter().map(|p| (p.pid, p)).collect();
    let children = proc::build_tree(&procs);

    if fmt == Format::Json {
        print_tree_json(root_pid, &by_pid, &children, 0);
    } else {
        print_tree_text(root_pid, &by_pid, &children, "", true);
    }
}

fn print_tree_text(
    pid: u32,
    by_pid: &HashMap<u32, &ProcessInfo>,
    children: &HashMap<u32, Vec<u32>>,
    prefix: &str,
    is_last: bool,
) {
    let connector = if is_last { "└─ " } else { "├─ " };
    match by_pid.get(&pid) {
        Some(p) => println!("{}{}{} ({})", prefix, connector, p.command, pid),
        None => println!("{}{}[{}]", prefix, connector, pid),
    }
    let child_prefix = format!("{}{}  ", prefix, if is_last { "  " } else { "│ " });
    if let Some(kids) = children.get(&pid) {
        let mut sorted = kids.clone();
        sorted.sort_unstable();
        let n = sorted.len();
        for (i, &cpid) in sorted.iter().enumerate() {
            print_tree_text(cpid, by_pid, children, &child_prefix, i + 1 == n);
        }
    }
}

fn print_tree_json(
    pid: u32,
    by_pid: &HashMap<u32, &ProcessInfo>,
    children: &HashMap<u32, Vec<u32>>,
    depth: usize,
) {
    if let Some(p) = by_pid.get(&pid) {
        let mut val = serde_json::to_value(p).unwrap();
        val["depth"] = serde_json::json!(depth);
        println!("{}", serde_json::to_string(&val).unwrap());
    }
    if let Some(kids) = children.get(&pid) {
        let mut sorted = kids.clone();
        sorted.sort_unstable();
        for &cpid in &sorted {
            print_tree_json(cpid, by_pid, children, depth + 1);
        }
    }
}

// ─── Helpers ────────────────────────────────────────────────────────────────

fn output(procs: &[ProcessInfo], fmt: &Format) {
    match fmt {
        Format::Table => print_table(procs),
        Format::Json => print_json(procs),
    }
}

fn apply_sort(procs: &mut [ProcessInfo], key: &SortKey, reverse: bool) {
    match key {
        SortKey::Pid => procs.sort_by_key(|p| p.pid),
        SortKey::Cpu => procs.sort_by(|a, b| a.cpu_pct.partial_cmp(&b.cpu_pct).unwrap()),
        SortKey::Mem => procs.sort_by(|a, b| a.mem_pct.partial_cmp(&b.mem_pct).unwrap()),
        SortKey::Start => procs.sort_by_key(|p| p.start_epoch),
    }
    if reverse {
        procs.reverse();
    }
}

fn current_uid() -> u32 {
    // SAFETY: getuid is a trivially safe syscall.
    unsafe { libc::getuid() }
}

fn parse_signal(s: &str) -> libc::c_int {
    // Accept "SIGTERM", "TERM", or a numeric string.
    let upper = s.to_uppercase();
    let name = upper.strip_prefix("SIG").unwrap_or(&upper);
    match name {
        "HUP"  => libc::SIGHUP,
        "INT"  => libc::SIGINT,
        "QUIT" => libc::SIGQUIT,
        "KILL" => libc::SIGKILL,
        "TERM" => libc::SIGTERM,
        "USR1" => libc::SIGUSR1,
        "USR2" => libc::SIGUSR2,
        "STOP" => libc::SIGSTOP,
        "CONT" => libc::SIGCONT,
        _ => s.parse::<libc::c_int>().unwrap_or_else(|_| {
            eprintln!("procmon: unknown signal '{}'; defaulting to SIGTERM", s);
            libc::SIGTERM
        }),
    }
}

fn guard_pid(pid: u32, current_pid: u32, force: bool) {
    if !force && (pid == 0 || pid == 1 || pid == current_pid) {
        eprintln!(
            "procmon: refusing to send signal to protected PID {}. Use --force to override.",
            pid
        );
        process::exit(1);
    }
}

fn send_signal(pid: u32, sig: libc::c_int) {
    // SAFETY: kill(2) is safe; we pass a validated signal and a PID we've looked up.
    let ret = unsafe { libc::kill(pid as libc::pid_t, sig) };
    if ret != 0 {
        let err = io::Error::last_os_error();
        let kind = err.raw_os_error().unwrap_or(0);
        let exit_code = if kind == libc::EPERM { 2 } else { 3 };
        eprintln!("procmon: kill({}, {}): {}", pid, sig, err);
        process::exit(exit_code);
    } else {
        eprintln!("procmon: sent signal {} to PID {}", sig, pid);
    }
}
