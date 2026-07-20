mod procfs;

use procfs::{load_processes, ProcError, ProcessInfo};
use regex::Regex;
use serde::Serialize;
use std::collections::BTreeMap;
use std::env;
use std::io::{self, Write};
use std::process::ExitCode;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum OutputFormat {
    Table,
    Json,
}

#[derive(Debug)]
enum Command {
    List {
        sort: SortKey,
        reverse: bool,
        format: OutputFormat,
    },
    Find {
        pattern: String,
        exact: bool,
        format: OutputFormat,
    },
    Kill {
        target: String,
        signal: Signal,
        force: bool,
    },
    Watch {
        pattern: Option<String>,
        interval: f64,
        format: OutputFormat,
    },
    Tree {
        root: i32,
        format: OutputFormat,
    },
    Help,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum SortKey {
    Pid,
    Cpu,
    Mem,
    Start,
}

#[derive(Clone, Copy, Debug)]
struct Signal {
    name: &'static str,
    number: i32,
}

#[derive(Serialize)]
struct ProcessJson<'a> {
    pid: i32,
    ppid: i32,
    uid: u32,
    user: &'a str,
    cpu_percent: f64,
    mem_percent: f64,
    rss_kb: i64,
    start_time: u64,
    command: &'a str,
}

#[derive(Serialize)]
struct WatchFrame<'a> {
    frame: u64,
    processes: Vec<ProcessJson<'a>>,
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(AppError::Usage(message)) => {
            eprintln!("procmon: {message}");
            ExitCode::from(1)
        }
        Err(AppError::NoMatch(message)) => {
            eprintln!("procmon: {message}");
            ExitCode::from(1)
        }
        Err(AppError::Permission(message)) => {
            eprintln!("procmon: {message}");
            ExitCode::from(2)
        }
        Err(AppError::Internal(message)) => {
            eprintln!("procmon: {message}");
            ExitCode::from(3)
        }
    }
}

#[derive(Debug)]
enum AppError {
    Usage(String),
    NoMatch(String),
    Permission(String),
    Internal(String),
}

impl From<ProcError> for AppError {
    fn from(value: ProcError) -> Self {
        AppError::Internal(value.to_string())
    }
}

fn run() -> Result<(), AppError> {
    let command = parse_args(env::args().skip(1).collect())?;
    match command {
        Command::Help => {
            print_usage();
            Ok(())
        }
        Command::List {
            sort,
            reverse,
            format,
        } => {
            let mut processes = current_user_processes()?;
            sort_processes(&mut processes, sort, reverse);
            print_processes(&processes, format)
        }
        Command::Find {
            pattern,
            exact,
            format,
        } => {
            let processes = current_user_processes()?;
            let found = filter_processes(processes, &pattern, exact)?;
            if found.is_empty() {
                return Err(AppError::NoMatch(format!("no process matched {pattern:?}")));
            }
            print_processes(&found, format)
        }
        Command::Kill {
            target,
            signal,
            force,
        } => kill_target(&target, signal, force),
        Command::Watch {
            pattern,
            interval,
            format,
        } => watch_processes(pattern, interval, format),
        Command::Tree { root, format } => {
            let processes = load_processes()?;
            if format == OutputFormat::Json {
                let tree = tree_order(processes, root);
                print_processes(&tree, format)
            } else {
                print_tree(&processes, root)
            }
        }
    }
}

fn parse_args(args: Vec<String>) -> Result<Command, AppError> {
    if args.is_empty() || args.iter().any(|arg| arg == "-h" || arg == "--help") {
        return Ok(Command::Help);
    }
    let sub = args[0].as_str();
    let mut rest = args[1..].to_vec();
    match sub {
        "list" => {
            let format = take_format(&mut rest)?;
            let reverse = take_flag(&mut rest, "--reverse");
            let sort = match take_value(&mut rest, "--sort")?.as_deref() {
                Some("pid") | None => SortKey::Pid,
                Some("cpu") => SortKey::Cpu,
                Some("mem") => SortKey::Mem,
                Some("start") => SortKey::Start,
                Some(other) => return Err(AppError::Usage(format!("unknown sort key {other:?}"))),
            };
            reject_extra(rest)?;
            Ok(Command::List {
                sort,
                reverse,
                format,
            })
        }
        "find" => {
            let format = take_format(&mut rest)?;
            let exact = take_flag(&mut rest, "--exact");
            if rest.len() != 1 {
                return Err(AppError::Usage("find requires exactly one pattern".to_string()));
            }
            Ok(Command::Find {
                pattern: rest.remove(0),
                exact,
                format,
            })
        }
        "kill" => {
            let _format = take_format(&mut rest)?;
            let force = take_flag(&mut rest, "--force");
            let signal = match take_value(&mut rest, "--signal")? {
                Some(value) => parse_signal(&value)?,
                None => parse_signal("SIGTERM")?,
            };
            if rest.len() != 1 {
                return Err(AppError::Usage("kill requires a pid or pattern".to_string()));
            }
            Ok(Command::Kill {
                target: rest.remove(0),
                signal,
                force,
            })
        }
        "watch" => {
            let format = take_format(&mut rest)?;
            let interval = match take_value(&mut rest, "--interval")? {
                Some(value) => value
                    .parse::<f64>()
                    .map_err(|_| AppError::Usage("--interval must be a number".to_string()))?,
                None => 2.0,
            };
            if interval <= 0.0 {
                return Err(AppError::Usage("--interval must be positive".to_string()));
            }
            if rest.len() > 1 {
                return Err(AppError::Usage(
                    "watch accepts at most one optional pattern".to_string(),
                ));
            }
            Ok(Command::Watch {
                pattern: rest.pop(),
                interval,
                format,
            })
        }
        "tree" => {
            let format = take_format(&mut rest)?;
            let root = match take_value(&mut rest, "--pid")? {
                Some(value) => value
                    .parse::<i32>()
                    .map_err(|_| AppError::Usage("--pid must be an integer".to_string()))?,
                None => 1,
            };
            reject_extra(rest)?;
            Ok(Command::Tree { root, format })
        }
        other => Err(AppError::Usage(format!("unknown subcommand {other:?}"))),
    }
}

fn take_format(args: &mut Vec<String>) -> Result<OutputFormat, AppError> {
    match take_value(args, "--format")?.as_deref() {
        Some("table") | None => Ok(OutputFormat::Table),
        Some("json") => Ok(OutputFormat::Json),
        Some(other) => Err(AppError::Usage(format!("unknown format {other:?}"))),
    }
}

fn take_flag(args: &mut Vec<String>, name: &str) -> bool {
    let old_len = args.len();
    args.retain(|arg| arg != name);
    args.len() != old_len
}

fn take_value(args: &mut Vec<String>, name: &str) -> Result<Option<String>, AppError> {
    if let Some(pos) = args.iter().position(|arg| arg == name) {
        args.remove(pos);
        if pos >= args.len() {
            return Err(AppError::Usage(format!("{name} requires a value")));
        }
        return Ok(Some(args.remove(pos)));
    }
    let prefix = format!("{name}=");
    if let Some(pos) = args.iter().position(|arg| arg.starts_with(&prefix)) {
        let value = args.remove(pos)[prefix.len()..].to_string();
        return Ok(Some(value));
    }
    Ok(None)
}

fn reject_extra(args: Vec<String>) -> Result<(), AppError> {
    if args.is_empty() {
        Ok(())
    } else {
        Err(AppError::Usage(format!("unexpected arguments: {}", args.join(" "))))
    }
}

fn print_usage() {
    println!(
        "Usage:\n  procmon list [--sort pid|cpu|mem|start] [--reverse] [--format table|json]\n  procmon find <pattern> [--exact] [--format table|json]\n  procmon kill <pid|pattern> [--signal SIGTERM|SIGKILL|...] [--force]\n  procmon watch [pattern] [--interval SECS] [--format table|json]\n  procmon tree [--pid <root>] [--format table|json]"
    );
}

fn current_user_processes() -> Result<Vec<ProcessInfo>, ProcError> {
    let current_uid = procfs::current_uid()?;
    let processes = load_processes()?;
    Ok(processes
        .into_iter()
        .filter(|process| process.uid == current_uid)
        .collect())
}

fn sort_processes(processes: &mut [ProcessInfo], sort: SortKey, reverse: bool) {
    match sort {
        SortKey::Pid => processes.sort_by_key(|process| process.pid),
        SortKey::Cpu => processes.sort_by(|a, b| a.cpu_percent.total_cmp(&b.cpu_percent)),
        SortKey::Mem => processes.sort_by(|a, b| a.mem_percent.total_cmp(&b.mem_percent)),
        SortKey::Start => processes.sort_by_key(|process| process.start_time),
    }
    if reverse {
        processes.reverse();
    }
}

fn filter_processes(
    processes: Vec<ProcessInfo>,
    pattern: &str,
    exact: bool,
) -> Result<Vec<ProcessInfo>, AppError> {
    if exact {
        Ok(processes
            .into_iter()
            .filter(|process| process.command.contains(pattern))
            .collect())
    } else {
        let regex = Regex::new(pattern)
            .map_err(|error| AppError::Usage(format!("invalid regex {pattern:?}: {error}")))?;
        Ok(processes
            .into_iter()
            .filter(|process| regex.is_match(&process.command))
            .collect())
    }
}

fn print_processes(processes: &[ProcessInfo], format: OutputFormat) -> Result<(), AppError> {
    let stdout = io::stdout();
    let mut out = stdout.lock();
    match format {
        OutputFormat::Table => {
            if !write_line(
                &mut out,
                format_args!(
                    "{:<7} {:<7} {:<12} {:>6} {:>6} {:>8} {:<10} COMMAND",
                    "PID", "PPID", "USER", "%CPU", "%MEM", "RSS(KB)", "START"
                ),
            )? {
                return Ok(());
            }
            for process in processes {
                if !write_line(
                    &mut out,
                    format_args!(
                        "{:<7} {:<7} {:<12} {:>6.1} {:>6.1} {:>8} {:<10} {}",
                        process.pid,
                        process.ppid,
                        truncate(&process.user, 12),
                        process.cpu_percent,
                        process.mem_percent,
                        process.rss_kb,
                        process.start_time,
                        process.command
                    ),
                )? {
                    break;
                }
            }
            Ok(())
        }
        OutputFormat::Json => {
            for process in processes {
                let line = serde_json::to_string(&to_json(process))
                    .map_err(|error| AppError::Internal(error.to_string()))?;
                if !write_line(&mut out, format_args!("{line}"))? {
                    break;
                }
            }
            Ok(())
        }
    }
}

fn write_line<W: Write>(out: &mut W, args: std::fmt::Arguments<'_>) -> Result<bool, AppError> {
    match out.write_fmt(args).and_then(|()| out.write_all(b"\n")) {
        Ok(()) => Ok(true),
        Err(error) if error.kind() == io::ErrorKind::BrokenPipe => Ok(false),
        Err(error) => Err(AppError::Internal(error.to_string())),
    }
}

fn to_json(process: &ProcessInfo) -> ProcessJson<'_> {
    ProcessJson {
        pid: process.pid,
        ppid: process.ppid,
        uid: process.uid,
        user: &process.user,
        cpu_percent: round_one(process.cpu_percent),
        mem_percent: round_one(process.mem_percent),
        rss_kb: process.rss_kb,
        start_time: process.start_time,
        command: &process.command,
    }
}

fn round_one(value: f64) -> f64 {
    (value * 10.0).round() / 10.0
}

fn truncate(value: &str, max: usize) -> String {
    let mut chars = value.chars();
    let result: String = chars.by_ref().take(max).collect();
    if chars.next().is_some() {
        result[..max.saturating_sub(1)].to_string() + "…"
    } else {
        result
    }
}

fn parse_signal(value: &str) -> Result<Signal, AppError> {
    let normalized = value.trim().to_ascii_uppercase();
    let with_prefix = if normalized.starts_with("SIG") {
        normalized
    } else {
        format!("SIG{normalized}")
    };
    let number = match with_prefix.as_str() {
        "SIGHUP" => libc::SIGHUP,
        "SIGINT" => libc::SIGINT,
        "SIGQUIT" => libc::SIGQUIT,
        "SIGKILL" => libc::SIGKILL,
        "SIGTERM" => libc::SIGTERM,
        "SIGSTOP" => libc::SIGSTOP,
        "SIGCONT" => libc::SIGCONT,
        "SIGUSR1" => libc::SIGUSR1,
        "SIGUSR2" => libc::SIGUSR2,
        _ => {
            return Err(AppError::Usage(format!(
                "unsupported signal {value:?}; try SIGTERM, SIGKILL, SIGINT, SIGHUP, SIGSTOP, SIGCONT, SIGUSR1, or SIGUSR2"
            )))
        }
    };
    let name: &'static str = match with_prefix.as_str() {
        "SIGHUP" => "SIGHUP",
        "SIGINT" => "SIGINT",
        "SIGQUIT" => "SIGQUIT",
        "SIGKILL" => "SIGKILL",
        "SIGTERM" => "SIGTERM",
        "SIGSTOP" => "SIGSTOP",
        "SIGCONT" => "SIGCONT",
        "SIGUSR1" => "SIGUSR1",
        "SIGUSR2" => "SIGUSR2",
        _ => unreachable!(),
    };
    Ok(Signal { name, number })
}

fn kill_target(target: &str, signal: Signal, force: bool) -> Result<(), AppError> {
    let pids = if let Ok(pid) = target.parse::<i32>() {
        vec![pid]
    } else {
        let processes = current_user_processes()?;
        let matches = filter_processes(processes, target, false)?;
        matches.into_iter().map(|process| process.pid).collect()
    };
    if pids.is_empty() {
        return Err(AppError::NoMatch(format!("no process matched {target:?}")));
    }
    let own_pid = i32::try_from(std::process::id()).unwrap_or(i32::MAX);
    for pid in &pids {
        if !force && (*pid == 0 || *pid == 1 || *pid == own_pid) {
            return Err(AppError::Usage(format!(
                "refusing to send {} to protected pid {pid}; use --force to override",
                signal.name
            )));
        }
    }
    for pid in pids {
        send_signal(pid, signal)?;
        eprintln!("sent {} to pid {pid}", signal.name);
    }
    Ok(())
}

fn send_signal(pid: i32, signal: Signal) -> Result<(), AppError> {
    // SAFETY: libc::kill is the Linux system call interface for sending a signal.
    // We pass plain integer values parsed from user input or /proc, do not retain
    // pointers, and check errno through io::Error immediately after the call.
    let result = unsafe { libc::kill(pid, signal.number) };
    if result == 0 {
        return Ok(());
    }
    let error = io::Error::last_os_error();
    match error.raw_os_error() {
        Some(libc::EPERM) => Err(AppError::Permission(format!(
            "permission denied sending {} to pid {pid}",
            signal.name
        ))),
        Some(libc::ESRCH) => Err(AppError::NoMatch(format!("pid {pid} does not exist"))),
        _ => Err(AppError::Internal(format!(
            "failed to send {} to pid {pid}: {error}",
            signal.name
        ))),
    }
}

fn watch_processes(
    pattern: Option<String>,
    interval: f64,
    format: OutputFormat,
) -> Result<(), AppError> {
    let running = Arc::new(AtomicBool::new(true));
    let ctrlc_flag = Arc::clone(&running);
    ctrlc::set_handler(move || {
        ctrlc_flag.store(false, Ordering::SeqCst);
    })
    .map_err(|error| AppError::Internal(format!("failed to install Ctrl-C handler: {error}")))?;

    let mut frame = 0;
    while running.load(Ordering::SeqCst) {
        let mut processes = current_user_processes()?;
        sort_processes(&mut processes, SortKey::Pid, false);
        if let Some(ref pat) = pattern {
            processes = filter_processes(processes, pat, false)?;
        }
        if format == OutputFormat::Json {
            let json_processes = processes.iter().map(to_json).collect::<Vec<_>>();
            let line = serde_json::to_string(&WatchFrame {
                frame,
                processes: json_processes,
            })
            .map_err(|error| AppError::Internal(error.to_string()))?;
            println!("{line}");
        } else {
            print!("\x1B[2J\x1B[H");
            io::stdout()
                .flush()
                .map_err(|error| AppError::Internal(error.to_string()))?;
            println!("procmon watch frame {frame}");
            print_processes(&processes, format)?;
        }
        frame += 1;
        thread::sleep(Duration::from_secs_f64(interval));
    }
    Ok(())
}

fn tree_order(processes: Vec<ProcessInfo>, root: i32) -> Vec<ProcessInfo> {
    let by_pid = processes
        .iter()
        .map(|process| (process.pid, process.clone()))
        .collect::<BTreeMap<_, _>>();
    let children = children_by_parent(&processes);
    let mut ordered = Vec::new();
    append_tree(root, &by_pid, &children, &mut ordered);
    ordered
}

fn append_tree(
    pid: i32,
    by_pid: &BTreeMap<i32, ProcessInfo>,
    children: &BTreeMap<i32, Vec<i32>>,
    output: &mut Vec<ProcessInfo>,
) {
    if let Some(process) = by_pid.get(&pid) {
        output.push(process.clone());
    }
    if let Some(kids) = children.get(&pid) {
        for child in kids {
            append_tree(*child, by_pid, children, output);
        }
    }
}

fn print_tree(processes: &[ProcessInfo], root: i32) -> Result<(), AppError> {
    let by_pid = processes
        .iter()
        .map(|process| (process.pid, process))
        .collect::<BTreeMap<_, _>>();
    let children = children_by_parent(processes);
    if !by_pid.contains_key(&root) && !children.contains_key(&root) {
        return Err(AppError::NoMatch(format!("pid {root} is not visible")));
    }
    print_tree_node(root, "", true, &by_pid, &children);
    Ok(())
}

fn print_tree_node(
    pid: i32,
    prefix: &str,
    last: bool,
    by_pid: &BTreeMap<i32, &ProcessInfo>,
    children: &BTreeMap<i32, Vec<i32>>,
) {
    let connector = if prefix.is_empty() {
        ""
    } else if last {
        "└─ "
    } else {
        "├─ "
    };
    if let Some(process) = by_pid.get(&pid) {
        println!("{prefix}{connector}{} {}", process.pid, process.command);
    } else {
        println!("{prefix}{connector}{pid} <not visible>");
    }
    let next_prefix = if prefix.is_empty() {
        String::new()
    } else if last {
        format!("{prefix}   ")
    } else {
        format!("{prefix}│  ")
    };
    if let Some(kids) = children.get(&pid) {
        for (index, child) in kids.iter().enumerate() {
            print_tree_node(*child, &next_prefix, index + 1 == kids.len(), by_pid, children);
        }
    }
}

fn children_by_parent(processes: &[ProcessInfo]) -> BTreeMap<i32, Vec<i32>> {
    let mut children: BTreeMap<i32, Vec<i32>> = BTreeMap::new();
    for process in processes {
        children.entry(process.ppid).or_default().push(process.pid);
    }
    for kids in children.values_mut() {
        kids.sort_unstable();
    }
    children
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn signal_parser_accepts_common_names() {
        assert_eq!(parse_signal("TERM").unwrap().number, libc::SIGTERM);
        assert_eq!(parse_signal("SIGKILL").unwrap().number, libc::SIGKILL);
    }

    #[test]
    fn literal_filter_uses_substring() {
        let processes = vec![ProcessInfo {
            pid: 10,
            ppid: 1,
            uid: 1000,
            user: "u".to_string(),
            cpu_percent: 0.0,
            mem_percent: 0.0,
            rss_kb: 1,
            start_time: 2,
            command: "alpha beta".to_string(),
        }];
        let found = filter_processes(processes, "beta", true).unwrap();
        assert_eq!(found.len(), 1);
    }
}
