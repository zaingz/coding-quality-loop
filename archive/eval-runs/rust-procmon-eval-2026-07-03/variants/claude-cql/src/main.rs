mod error;
mod output;
mod proc;
mod signals;
mod table;
mod tree;
mod watch;

use std::collections::HashMap;
use std::process as std_process;

use clap::{Parser, Subcommand, ValueEnum};
use regex::Regex;

use error::AppError;
use output::{print_procs, Format};
use proc::{build_children_map, list_all_procs, read_mem_total_kb, read_uptime};
use signals::{parse_signal, send_signal};
use tree::print_tree;
use watch::run_watch;

// ──────────────────────────────────────────────
// CLI definitions
// ──────────────────────────────────────────────

#[derive(Parser)]
#[command(name = "procmon", version, about = "Linux process monitor")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// List running processes for the current user.
    List {
        /// Sort column: pid | cpu | mem | start
        #[arg(long, default_value = "pid")]
        sort: SortKey,
        /// Reverse sort order
        #[arg(long)]
        reverse: bool,
        /// Output format
        #[arg(long, default_value = "table")]
        format: String,
    },

    /// Find processes matching a regex pattern.
    Find {
        /// Pattern to match against the command line
        pattern: String,
        /// Use substring match instead of regex
        #[arg(long)]
        exact: bool,
        /// Output format
        #[arg(long, default_value = "table")]
        format: String,
    },

    /// Send a signal to a process (by PID or regex pattern).
    Kill {
        /// Target: a PID number or a regex pattern
        target: String,
        /// Signal name or number (default: SIGTERM)
        #[arg(long, default_value = "SIGTERM")]
        signal: String,
        /// Allow killing PID 0, PID 1, or the current process
        #[arg(long)]
        force: bool,
    },

    /// Repeatedly refresh the process list.
    Watch {
        /// Optional pattern to filter processes
        pattern: Option<String>,
        /// Refresh interval in seconds
        #[arg(long, default_value_t = 2.0)]
        interval: f64,
        /// Output format
        #[arg(long, default_value = "table")]
        format: String,
    },

    /// Print an ASCII process tree.
    Tree {
        /// Root PID (default: 1)
        #[arg(long, default_value_t = 1)]
        pid: u32,
        /// Output format
        #[arg(long, default_value = "table")]
        format: String,
    },
}

#[derive(ValueEnum, Clone, Debug)]
enum SortKey {
    Pid,
    Cpu,
    Mem,
    Start,
}

// ──────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────

fn parse_format(s: &str) -> Result<Format, AppError> {
    s.parse::<Format>()
        .map_err(AppError::NoMatch)
}

fn base_procs() -> Result<(Vec<proc::ProcInfo>, u64, f64, u64), AppError> {
    let clk_tck = 100u64;
    let uptime = read_uptime()
        .ok_or_else(|| AppError::Internal("cannot read /proc/uptime".to_string()))?;
    let mem_total_kb = read_mem_total_kb()
        .ok_or_else(|| AppError::Internal("cannot read /proc/meminfo".to_string()))?;
    let procs = list_all_procs(clk_tck, uptime, mem_total_kb);
    Ok((procs, clk_tck, uptime, mem_total_kb))
}

fn sort_procs(procs: &mut [proc::ProcInfo], key: &SortKey, reverse: bool) {
    match key {
        SortKey::Pid => procs.sort_by_key(|p| p.pid),
        SortKey::Cpu => procs.sort_by(|a, b| a.cpu_pct.total_cmp(&b.cpu_pct)),
        SortKey::Mem => procs.sort_by(|a, b| a.mem_pct.total_cmp(&b.mem_pct)),
        SortKey::Start => procs.sort_by_key(|p| p.start_time),
    }
    if reverse {
        procs.reverse();
    }
}

fn current_uid() -> u32 {
    // Safety: getuid() is always safe to call.
    unsafe { libc::getuid() }
}

// ──────────────────────────────────────────────
// Subcommand handlers
// ──────────────────────────────────────────────

fn cmd_list(sort: SortKey, reverse: bool, fmt: &Format) -> Result<(), AppError> {
    let (mut procs, ..) = base_procs()?;
    let uid = current_uid();
    procs.retain(|p| p.uid == uid);
    sort_procs(&mut procs, &sort, reverse);
    print_procs(&procs, fmt);
    Ok(())
}

fn cmd_find(pattern: &str, exact: bool, fmt: &Format) -> Result<(), AppError> {
    let (mut procs, ..) = base_procs()?;

    if exact {
        procs.retain(|p| p.command.contains(pattern) || p.comm.contains(pattern));
    } else {
        let re = Regex::new(pattern)
            .map_err(|e| AppError::NoMatch(format!("invalid regex '{pattern}': {e}")))?;
        procs.retain(|p| re.is_match(&p.command) || re.is_match(&p.comm));
    }

    if procs.is_empty() {
        return Err(AppError::NoMatch(format!(
            "no processes matched '{pattern}'"
        )));
    }

    procs.sort_by_key(|p| p.pid);
    print_procs(&procs, fmt);
    Ok(())
}

fn cmd_kill(target: &str, signal_str: &str, force: bool) -> Result<(), AppError> {
    let sig = parse_signal(signal_str)?;
    let self_pid = std_process::id();

    // Try interpreting target as a single PID first.
    if let Ok(pid) = target.parse::<u32>() {
        check_kill_guards(pid, self_pid, force)?;
        send_signal(pid, sig)?;
        eprintln!("Sent signal {signal_str} to pid {pid}");
        return Ok(());
    }

    // Otherwise treat as a regex pattern.
    let re = Regex::new(target)
        .map_err(|e| AppError::NoMatch(format!("invalid regex '{target}': {e}")))?;

    let (procs, ..) = base_procs()?;
    let matched: Vec<_> = procs
        .iter()
        .filter(|p| re.is_match(&p.command) || re.is_match(&p.comm))
        .collect();

    if matched.is_empty() {
        return Err(AppError::NoMatch(format!(
            "no processes matched '{target}'"
        )));
    }

    let mut sent = 0usize;
    for p in matched {
        if let Err(e) = check_kill_guards(p.pid, self_pid, force) {
            eprintln!("Skipping pid {}: {}", p.pid, e);
            continue;
        }
        match send_signal(p.pid, sig) {
            Ok(()) => {
                eprintln!("Sent signal {signal_str} to pid {} ({})", p.pid, p.command);
                sent += 1;
            }
            Err(e) => eprintln!("Error killing pid {}: {}", p.pid, e),
        }
    }

    if sent == 0 {
        return Err(AppError::NoMatch(format!(
            "no processes were signalled for '{target}'"
        )));
    }

    Ok(())
}

fn check_kill_guards(pid: u32, self_pid: u32, force: bool) -> Result<(), AppError> {
    if !force {
        if pid == 0 {
            return Err(AppError::NoMatch(
                "refusing to kill PID 0 without --force".to_string(),
            ));
        }
        if pid == 1 {
            return Err(AppError::NoMatch(
                "refusing to kill PID 1 (init) without --force".to_string(),
            ));
        }
        if pid == self_pid {
            return Err(AppError::NoMatch(format!(
                "refusing to kill current process (PID {self_pid}) without --force"
            )));
        }
    }
    Ok(())
}

fn cmd_tree(root_pid: u32, fmt: &Format) -> Result<(), AppError> {
    let (procs, ..) = base_procs()?;
    let pid_map: HashMap<u32, &proc::ProcInfo> = procs.iter().map(|p| (p.pid, p)).collect();
    let children = build_children_map(&procs);
    print_tree(root_pid, &pid_map, &children, fmt, "", true, true);
    Ok(())
}

// ──────────────────────────────────────────────
// Entry point
// ──────────────────────────────────────────────

fn run() -> Result<(), AppError> {
    let cli = Cli::parse();

    match cli.command {
        Command::List { sort, reverse, format } => {
            let fmt = parse_format(&format)?;
            cmd_list(sort, reverse, &fmt)?;
        }
        Command::Find { pattern, exact, format } => {
            let fmt = parse_format(&format)?;
            cmd_find(&pattern, exact, &fmt)?;
        }
        Command::Kill { target, signal, force } => {
            cmd_kill(&target, &signal, force)?;
        }
        Command::Watch { pattern, interval, format } => {
            let fmt = parse_format(&format)?;
            run_watch(pattern.as_deref(), interval, &fmt, false)?;
        }
        Command::Tree { pid, format } => {
            let fmt = parse_format(&format)?;
            cmd_tree(pid, &fmt)?;
        }
    }

    Ok(())
}

fn main() {
    match run() {
        Ok(()) => {}
        Err(e) => {
            eprintln!("error: {e}");
            std_process::exit(e.exit_code());
        }
    }
}
