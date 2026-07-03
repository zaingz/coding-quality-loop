use regex::Regex;
use std::collections::{BTreeMap, HashMap, HashSet};
use std::ffi::OsStr;
use std::fmt::{self, Write as _};
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExitKind {
    Usage,
    Permission,
    Internal,
}

#[derive(Debug, Clone)]
pub struct ProcmonError {
    message: String,
    kind: ExitKind,
}

impl ProcmonError {
    fn usage(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            kind: ExitKind::Usage,
        }
    }

    fn permission(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            kind: ExitKind::Permission,
        }
    }

    fn internal(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            kind: ExitKind::Internal,
        }
    }

    pub fn exit_code(&self) -> i32 {
        match self.kind {
            ExitKind::Usage => 1,
            ExitKind::Permission => 2,
            ExitKind::Internal => 3,
        }
    }
}

impl fmt::Display for ProcmonError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for ProcmonError {}

type Result<T> = std::result::Result<T, ProcmonError>;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OutputFormat {
    Table,
    Json,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SortKey {
    Pid,
    Cpu,
    Mem,
    Start,
}

#[derive(Debug, Clone)]
pub struct ProcessInfo {
    pub pid: i32,
    pub ppid: i32,
    pub uid: u32,
    pub user: String,
    pub cpu_percent: f64,
    pub mem_percent: f64,
    pub rss_kb: u64,
    pub start_seconds: u64,
    pub start_display: String,
    pub command: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StatInfo {
    pub pid: i32,
    pub comm: String,
    pub state: char,
    pub ppid: i32,
    pub utime_ticks: u64,
    pub stime_ticks: u64,
    pub start_time_ticks: u64,
}

#[derive(Debug, Default)]
struct ProcContext {
    boot_time_seconds: u64,
    uptime_seconds: f64,
    ticks_per_second: f64,
    page_size_kb: u64,
    mem_total_kb: u64,
    passwd: HashMap<u32, String>,
}

pub fn run(args: Vec<String>) -> Result<()> {
    if args.is_empty() {
        print_usage();
        return Err(ProcmonError::usage("missing subcommand"));
    }

    match args[0].as_str() {
        "list" => cmd_list(&args[1..]),
        "find" => cmd_find(&args[1..]),
        "kill" => cmd_kill(&args[1..]),
        "watch" => cmd_watch(&args[1..]),
        "tree" => cmd_tree(&args[1..]),
        "-h" | "--help" | "help" => {
            print_usage();
            Ok(())
        }
        other => Err(ProcmonError::usage(format!("unknown subcommand '{other}'"))),
    }
}

fn cmd_list(args: &[String]) -> Result<()> {
    let options = ListOptions::parse(args)?;
    let current_uid = current_uid();
    let mut processes: Vec<_> = collect_processes()?.into_iter().filter(|p| p.uid == current_uid).collect();
    sort_processes(&mut processes, options.sort, options.reverse);
    print_processes(&processes, options.format, None)
}

fn cmd_find(args: &[String]) -> Result<()> {
    let options = FindOptions::parse(args)?;
    let mut processes = filter_by_pattern(collect_processes()?, &options.pattern, options.exact)?;
    sort_processes(&mut processes, SortKey::Pid, false);
    if processes.is_empty() {
        return Err(ProcmonError::usage("no process matched"));
    }
    print_processes(&processes, options.format, None)
}

fn cmd_kill(args: &[String]) -> Result<()> {
    let options = KillOptions::parse(args)?;
    let targets = resolve_kill_targets(&options.target)?;
    if targets.is_empty() {
        return Err(ProcmonError::usage("no process matched"));
    }

    let self_pid = std::process::id() as i32;
    let mut sent = 0usize;
    let mut denied = Vec::new();
    for pid in targets {
        if !options.force && (pid == 0 || pid == 1 || pid == self_pid) {
            denied.push(pid);
            continue;
        }
        send_signal(pid, options.signal)?;
        sent += 1;
        safe_stdout(&format!("sent {} to {}\n", signal_name(options.signal), pid))?;
    }

    if !denied.is_empty() {
        return Err(ProcmonError::usage(format!(
            "refusing to signal protected pid(s) {}; use --force to override",
            join_pids(&denied)
        )));
    }

    if sent == 0 {
        return Err(ProcmonError::usage("no signal sent"));
    }
    Ok(())
}

fn cmd_watch(args: &[String]) -> Result<()> {
    let options = WatchOptions::parse(args)?;
    let interval = Duration::from_secs_f64(options.interval_secs);
    let mut frame = 0u64;
    loop {
        let processes = if let Some(pattern) = &options.pattern {
            filter_by_pattern(collect_processes()?, pattern, false)?
        } else {
            let current_uid = current_uid();
            collect_processes()?.into_iter().filter(|p| p.uid == current_uid).collect()
        };
        if options.format == OutputFormat::Table {
            let mut out = format!(
                "\x1B[2J\x1B[Hprocmon watch frame {frame} (interval {:.2}s)\n",
                options.interval_secs
            );
            out.push_str(&render_processes(&processes, OutputFormat::Table, None));
            safe_stdout(&out)?;
        } else {
            safe_stdout(&format!("{}\n", watch_frame_json(frame, &processes)))?;
        }
        frame = frame.saturating_add(1);
        thread::sleep(interval);
    }
}

fn cmd_tree(args: &[String]) -> Result<()> {
    let options = TreeOptions::parse(args)?;
    let processes = collect_processes()?;
    if options.format == OutputFormat::Json {
        for (process, depth) in tree_rows(&processes, options.root_pid) {
            safe_stdout(&format!("{}\n", process_json_with_depth(process, depth)))?;
        }
    } else {
        print_tree(&processes, options.root_pid)?;
    }
    Ok(())
}

#[derive(Debug)]
struct ListOptions {
    sort: SortKey,
    reverse: bool,
    format: OutputFormat,
}

impl ListOptions {
    fn parse(args: &[String]) -> Result<Self> {
        let mut sort = SortKey::Pid;
        let mut reverse = false;
        let mut format = OutputFormat::Table;
        let mut i = 0;
        while i < args.len() {
            match args[i].as_str() {
                "--sort" => {
                    i += 1;
                    sort = parse_sort(args.get(i))?;
                }
                "--reverse" => reverse = true,
                "--format" => {
                    i += 1;
                    format = parse_format(args.get(i))?;
                }
                other => return Err(ProcmonError::usage(format!("unexpected list argument '{other}'"))),
            }
            i += 1;
        }
        Ok(Self { sort, reverse, format })
    }
}

#[derive(Debug)]
struct FindOptions {
    pattern: String,
    exact: bool,
    format: OutputFormat,
}

impl FindOptions {
    fn parse(args: &[String]) -> Result<Self> {
        let mut pattern = None;
        let mut exact = false;
        let mut format = OutputFormat::Table;
        let mut i = 0;
        while i < args.len() {
            match args[i].as_str() {
                "--exact" => exact = true,
                "--format" => {
                    i += 1;
                    format = parse_format(args.get(i))?;
                }
                value if value.starts_with('-') => {
                    return Err(ProcmonError::usage(format!("unexpected find argument '{value}'")))
                }
                value => {
                    if pattern.replace(value.to_string()).is_some() {
                        return Err(ProcmonError::usage("find accepts exactly one pattern"));
                    }
                }
            }
            i += 1;
        }
        Ok(Self { pattern: pattern.ok_or_else(|| ProcmonError::usage("find requires a pattern"))?, exact, format })
    }
}

#[derive(Debug)]
struct KillOptions {
    target: String,
    signal: i32,
    force: bool,
}

impl KillOptions {
    fn parse(args: &[String]) -> Result<Self> {
        let mut target = None;
        let mut signal = libc::SIGTERM;
        let mut force = false;
        let mut i = 0;
        while i < args.len() {
            match args[i].as_str() {
                "--signal" => {
                    i += 1;
                    signal = parse_signal(args.get(i))?;
                }
                "--force" => force = true,
                value if value.starts_with('-') => {
                    return Err(ProcmonError::usage(format!("unexpected kill argument '{value}'")))
                }
                value => {
                    if target.replace(value.to_string()).is_some() {
                        return Err(ProcmonError::usage("kill accepts exactly one pid or pattern"));
                    }
                }
            }
            i += 1;
        }
        Ok(Self { target: target.ok_or_else(|| ProcmonError::usage("kill requires a pid or pattern"))?, signal, force })
    }
}

#[derive(Debug)]
struct WatchOptions {
    pattern: Option<String>,
    interval_secs: f64,
    format: OutputFormat,
}

impl WatchOptions {
    fn parse(args: &[String]) -> Result<Self> {
        let mut pattern = None;
        let mut interval_secs = 2.0;
        let mut format = OutputFormat::Table;
        let mut i = 0;
        while i < args.len() {
            match args[i].as_str() {
                "--interval" => {
                    i += 1;
                    let raw = args.get(i).ok_or_else(|| ProcmonError::usage("--interval requires SECS"))?;
                    interval_secs = raw.parse::<f64>().map_err(|_| ProcmonError::usage("invalid interval"))?;
                    if !interval_secs.is_finite() || interval_secs <= 0.0 {
                        return Err(ProcmonError::usage("interval must be positive"));
                    }
                }
                "--format" => {
                    i += 1;
                    format = parse_format(args.get(i))?;
                }
                value if value.starts_with('-') => {
                    return Err(ProcmonError::usage(format!("unexpected watch argument '{value}'")))
                }
                value => {
                    if pattern.replace(value.to_string()).is_some() {
                        return Err(ProcmonError::usage("watch accepts at most one pattern"));
                    }
                }
            }
            i += 1;
        }
        Ok(Self { pattern, interval_secs, format })
    }
}

#[derive(Debug)]
struct TreeOptions {
    root_pid: i32,
    format: OutputFormat,
}

impl TreeOptions {
    fn parse(args: &[String]) -> Result<Self> {
        let mut root_pid = 1;
        let mut format = OutputFormat::Table;
        let mut i = 0;
        while i < args.len() {
            match args[i].as_str() {
                "--pid" => {
                    i += 1;
                    let raw = args.get(i).ok_or_else(|| ProcmonError::usage("--pid requires PID"))?;
                    root_pid = raw.parse::<i32>().map_err(|_| ProcmonError::usage("invalid pid"))?;
                }
                "--format" => {
                    i += 1;
                    format = parse_format(args.get(i))?;
                }
                other => return Err(ProcmonError::usage(format!("unexpected tree argument '{other}'"))),
            }
            i += 1;
        }
        Ok(Self { root_pid, format })
    }
}

fn parse_sort(value: Option<&String>) -> Result<SortKey> {
    match value.map(String::as_str) {
        Some("pid") => Ok(SortKey::Pid),
        Some("cpu") => Ok(SortKey::Cpu),
        Some("mem") => Ok(SortKey::Mem),
        Some("start") => Ok(SortKey::Start),
        Some(other) => Err(ProcmonError::usage(format!("invalid sort key '{other}'"))),
        None => Err(ProcmonError::usage("--sort requires a key")),
    }
}

fn parse_format(value: Option<&String>) -> Result<OutputFormat> {
    match value.map(String::as_str) {
        Some("table") => Ok(OutputFormat::Table),
        Some("json") => Ok(OutputFormat::Json),
        Some(other) => Err(ProcmonError::usage(format!("invalid format '{other}'"))),
        None => Err(ProcmonError::usage("--format requires table or json")),
    }
}

fn parse_signal(value: Option<&String>) -> Result<i32> {
    let value = value.ok_or_else(|| ProcmonError::usage("--signal requires a signal"))?;
    let upper = value.trim_start_matches("SIG").to_ascii_uppercase();
    match upper.as_str() {
        "TERM" => Ok(libc::SIGTERM),
        "KILL" => Ok(libc::SIGKILL),
        "INT" => Ok(libc::SIGINT),
        "HUP" => Ok(libc::SIGHUP),
        "QUIT" => Ok(libc::SIGQUIT),
        "USR1" => Ok(libc::SIGUSR1),
        "USR2" => Ok(libc::SIGUSR2),
        raw => raw.parse::<i32>().map_err(|_| ProcmonError::usage(format!("unsupported signal '{value}'"))),
    }
}

fn signal_name(signal: i32) -> &'static str {
    match signal {
        libc::SIGTERM => "SIGTERM",
        libc::SIGKILL => "SIGKILL",
        libc::SIGINT => "SIGINT",
        libc::SIGHUP => "SIGHUP",
        libc::SIGQUIT => "SIGQUIT",
        libc::SIGUSR1 => "SIGUSR1",
        libc::SIGUSR2 => "SIGUSR2",
        _ => "SIGNAL",
    }
}

fn collect_processes() -> Result<Vec<ProcessInfo>> {
    let context = ProcContext::load()?;
    let mut processes = Vec::new();
    let entries = fs::read_dir("/proc").map_err(|err| ProcmonError::internal(format!("cannot read /proc: {err}")))?;
    for entry in entries.flatten() {
        let file_name = entry.file_name();
        let Some(pid) = parse_pid_name(&file_name) else { continue };
        match read_process(pid, &entry.path(), &context) {
            Ok(process) => processes.push(process),
            Err(ReadProcessError::Race) => {}
            Err(ReadProcessError::Permission) => {}
        }
    }
    Ok(processes)
}

fn parse_pid_name(name: &OsStr) -> Option<i32> {
    name.to_str()?.parse::<i32>().ok()
}

impl ProcContext {
    fn load() -> Result<Self> {
        let uptime_seconds = read_uptime().unwrap_or(0.0);
        let boot_time_seconds = read_boot_time().unwrap_or_else(|| {
            unix_now_seconds().saturating_sub(uptime_seconds.max(0.0) as u64)
        });
        let ticks_per_second = sysconf(libc::_SC_CLK_TCK).unwrap_or(100) as f64;
        let page_size_kb = (sysconf(libc::_SC_PAGESIZE).unwrap_or(4096) as u64 / 1024).max(1);
        let mem_total_kb = read_mem_total_kb().unwrap_or(0);
        Ok(Self { boot_time_seconds, uptime_seconds, ticks_per_second, page_size_kb, mem_total_kb, passwd: read_passwd() })
    }
}

#[derive(Debug)]
enum ReadProcessError {
    Race,
    Permission,
}

fn read_process(pid: i32, dir: &Path, context: &ProcContext) -> std::result::Result<ProcessInfo, ReadProcessError> {
    let stat_text = read_to_string_racy(dir.join("stat"))?;
    let stat = parse_proc_stat(&stat_text).map_err(|_| ReadProcessError::Race)?;
    let status = read_to_string_racy(dir.join("status"))?;
    let uid = parse_status_uid(&status).ok_or(ReadProcessError::Race)?;
    let rss_kb = parse_status_rss_kb(&status).unwrap_or_else(|| stat_rss_from_stat(&stat_text, context.page_size_kb));
    let command = read_cmdline(dir.join("cmdline")).or_else(|| read_comm(dir.join("comm"))).unwrap_or(stat.comm.clone());
    let user = context.passwd.get(&uid).cloned().unwrap_or_else(|| uid.to_string());
    let total_ticks = stat.utime_ticks.saturating_add(stat.stime_ticks);
    let elapsed = (context.uptime_seconds - (stat.start_time_ticks as f64 / context.ticks_per_second)).max(0.01);
    let cpu_percent = ((total_ticks as f64 / context.ticks_per_second) / elapsed * 100.0).max(0.0);
    let mem_percent = if context.mem_total_kb > 0 {
        (rss_kb as f64 / context.mem_total_kb as f64) * 100.0
    } else {
        0.0
    };
    let start_seconds = context.boot_time_seconds.saturating_add((stat.start_time_ticks as f64 / context.ticks_per_second) as u64);
    Ok(ProcessInfo { pid, ppid: stat.ppid, uid, user, cpu_percent, mem_percent, rss_kb, start_seconds, start_display: format_start(start_seconds), command })
}

fn read_to_string_racy(path: PathBuf) -> std::result::Result<String, ReadProcessError> {
    fs::read_to_string(path).map_err(|err| match err.kind() {
        io::ErrorKind::NotFound | io::ErrorKind::InvalidData => ReadProcessError::Race,
        io::ErrorKind::PermissionDenied => ReadProcessError::Permission,
        _ => ReadProcessError::Race,
    })
}

fn read_cmdline(path: PathBuf) -> Option<String> {
    let bytes = fs::read(path).ok()?;
    let parts: Vec<_> = bytes
        .split(|byte| *byte == 0)
        .filter(|part| !part.is_empty())
        .map(|part| String::from_utf8_lossy(part).into_owned())
        .collect();
    if parts.is_empty() { None } else { Some(parts.join(" ")) }
}

fn read_comm(path: PathBuf) -> Option<String> {
    let comm = fs::read_to_string(path).ok()?;
    let trimmed = comm.trim();
    if trimmed.is_empty() { None } else { Some(trimmed.to_string()) }
}

pub fn parse_proc_stat(input: &str) -> std::result::Result<StatInfo, String> {
    let input = input.trim();
    let open = input.find('(').ok_or_else(|| "missing comm open paren".to_string())?;
    let close = input.rfind(')').ok_or_else(|| "missing comm close paren".to_string())?;
    if close <= open {
        return Err("invalid comm parens".to_string());
    }
    let pid = input[..open].trim().parse::<i32>().map_err(|_| "invalid pid".to_string())?;
    let comm = input[open + 1..close].to_string();
    let rest: Vec<&str> = input[close + 1..].split_whitespace().collect();
    if rest.len() < 20 {
        return Err("stat line too short".to_string());
    }
    let state = rest[0].chars().next().ok_or_else(|| "missing state".to_string())?;
    let ppid = rest[1].parse::<i32>().map_err(|_| "invalid ppid".to_string())?;
    let utime_ticks = rest[11].parse::<u64>().map_err(|_| "invalid utime".to_string())?;
    let stime_ticks = rest[12].parse::<u64>().map_err(|_| "invalid stime".to_string())?;
    let start_time_ticks = rest[19].parse::<u64>().map_err(|_| "invalid starttime".to_string())?;
    Ok(StatInfo { pid, comm, state, ppid, utime_ticks, stime_ticks, start_time_ticks })
}

fn stat_rss_from_stat(input: &str, page_size_kb: u64) -> u64 {
    let Some(close) = input.rfind(')') else { return 0 };
    let rest: Vec<&str> = input[close + 1..].split_whitespace().collect();
    rest.get(21).and_then(|raw| raw.parse::<i64>().ok()).unwrap_or(0).max(0) as u64 * page_size_kb
}

fn parse_status_uid(status: &str) -> Option<u32> {
    status.lines().find_map(|line| {
        line.strip_prefix("Uid:")?.split_whitespace().next()?.parse::<u32>().ok()
    })
}

fn parse_status_rss_kb(status: &str) -> Option<u64> {
    status.lines().find_map(|line| {
        line.strip_prefix("VmRSS:")?.split_whitespace().next()?.parse::<u64>().ok()
    })
}

fn read_uptime() -> Option<f64> {
    fs::read_to_string("/proc/uptime").ok()?.split_whitespace().next()?.parse().ok()
}

fn read_boot_time() -> Option<u64> {
    fs::read_to_string("/proc/stat").ok()?.lines().find_map(|line| {
        line.strip_prefix("btime ")?.trim().parse::<u64>().ok()
    })
}

fn read_mem_total_kb() -> Option<u64> {
    fs::read_to_string("/proc/meminfo").ok()?.lines().find_map(|line| {
        line.strip_prefix("MemTotal:")?.split_whitespace().next()?.parse::<u64>().ok()
    })
}

fn read_passwd() -> HashMap<u32, String> {
    let mut map = HashMap::new();
    if let Ok(text) = fs::read_to_string("/etc/passwd") {
        for line in text.lines() {
            let fields: Vec<&str> = line.split(':').collect();
            if fields.len() >= 3 {
                if let Ok(uid) = fields[2].parse::<u32>() {
                    map.entry(uid).or_insert_with(|| fields[0].to_string());
                }
            }
        }
    }
    map
}

fn unix_now_seconds() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs()
}

fn sysconf(name: libc::c_int) -> Option<i64> {
    // SAFETY: sysconf is a thread-safe libc query for process/system constants and does not dereference pointers.
    let value = unsafe { libc::sysconf(name) };
    if value > 0 { Some(value) } else { None }
}

fn current_uid() -> u32 {
    // SAFETY: getuid has no parameters, no memory safety preconditions, and cannot fail.
    unsafe { libc::getuid() as u32 }
}

fn send_signal(pid: i32, signal: i32) -> Result<()> {
    // SAFETY: kill(2) is called with integer pid/signal values parsed by this process; no Rust memory invariants are affected.
    let rc = unsafe { libc::kill(pid, signal) };
    if rc == 0 {
        Ok(())
    } else {
        let err = io::Error::last_os_error();
        match err.raw_os_error() {
            Some(libc::EPERM) => Err(ProcmonError::permission(format!("permission denied signaling pid {pid}"))),
            Some(libc::ESRCH) => Err(ProcmonError::usage(format!("pid {pid} does not exist"))),
            _ => Err(ProcmonError::internal(format!("failed to signal pid {pid}: {err}"))),
        }
    }
}

fn filter_by_pattern(processes: Vec<ProcessInfo>, pattern: &str, exact: bool) -> Result<Vec<ProcessInfo>> {
    if exact {
        Ok(processes.into_iter().filter(|p| p.command.contains(pattern)).collect())
    } else {
        let regex = Regex::new(pattern).map_err(|err| ProcmonError::usage(format!("invalid regex: {err}")))?;
        Ok(processes.into_iter().filter(|p| regex.is_match(&p.command)).collect())
    }
}

fn resolve_kill_targets(target: &str) -> Result<Vec<i32>> {
    if let Ok(pid) = target.parse::<i32>() {
        return Ok(vec![pid]);
    }
    let matches = filter_by_pattern(collect_processes()?, target, false)?;
    let mut pids: Vec<_> = matches.into_iter().map(|p| p.pid).collect();
    pids.sort_unstable();
    pids.dedup();
    Ok(pids)
}

pub fn sort_processes(processes: &mut [ProcessInfo], sort: SortKey, reverse: bool) {
    match sort {
        SortKey::Pid => processes.sort_by_key(|p| p.pid),
        SortKey::Cpu => processes.sort_by(|a, b| a.cpu_percent.total_cmp(&b.cpu_percent).then(a.pid.cmp(&b.pid))),
        SortKey::Mem => processes.sort_by(|a, b| a.mem_percent.total_cmp(&b.mem_percent).then(a.pid.cmp(&b.pid))),
        SortKey::Start => processes.sort_by_key(|p| (p.start_seconds, p.pid)),
    }
    if reverse {
        processes.reverse();
    }
}

fn print_processes(
    processes: &[ProcessInfo],
    format: OutputFormat,
    depth: Option<&HashMap<i32, usize>>,
) -> Result<()> {
    safe_stdout(&render_processes(processes, format, depth))
}

fn render_processes(
    processes: &[ProcessInfo],
    format: OutputFormat,
    depth: Option<&HashMap<i32, usize>>,
) -> String {
    match format {
        OutputFormat::Table => render_table(processes, depth),
        OutputFormat::Json => {
            let mut out = String::new();
            for process in processes {
                writeln!(out, "{}", process_json(process)).expect("writing to string cannot fail");
            }
            out
        }
    }
}

fn render_table(processes: &[ProcessInfo], depth: Option<&HashMap<i32, usize>>) -> String {
    let mut out = String::new();
    writeln!(
        out,
        "{:<6} {:<6} {:<10} {:>5} {:>5} {:>8} {:<8} COMMAND",
        "PID", "PPID", "USER", "%CPU", "%MEM", "RSS(KB)", "START"
    )
    .expect("writing to string cannot fail");
    for process in processes {
        let indent = depth.and_then(|d| d.get(&process.pid)).copied().unwrap_or(0);
        let command = if indent == 0 { process.command.clone() } else { format!("{}{}", "  ".repeat(indent), process.command) };
        writeln!(
            out,
            "{:<6} {:<6} {:<10.10} {:>5.1} {:>5.1} {:>8} {:<8} {}",
            process.pid,
            process.ppid,
            process.user,
            process.cpu_percent,
            process.mem_percent,
            process.rss_kb,
            process.start_display,
            command
        )
        .expect("writing to string cannot fail");
    }
    out
}

fn process_json(process: &ProcessInfo) -> String {
    format!(
        "{{\"pid\":{},\"ppid\":{},\"user\":{},\"uid\":{},\"cpu_percent\":{:.2},\"mem_percent\":{:.2},\"rss_kb\":{},\"start\":{},\"command\":{}}}",
        process.pid,
        process.ppid,
        json_string(&process.user),
        process.uid,
        process.cpu_percent,
        process.mem_percent,
        process.rss_kb,
        json_string(&process.start_display),
        json_string(&process.command)
    )
}

fn process_json_with_depth(process: &ProcessInfo, depth: usize) -> String {
    let mut base = process_json(process);
    base.pop();
    write!(base, ",\"depth\":{depth}}}").expect("writing to string cannot fail");
    base
}

fn watch_frame_json(frame: u64, processes: &[ProcessInfo]) -> String {
    let mut out = format!("{{\"frame\":{frame},\"timestamp_unix\":{},\"processes\":[", unix_now_seconds());
    for (index, process) in processes.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        out.push_str(&process_json(process));
    }
    out.push_str("]}");
    out
}

fn json_string(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    out.push('"');
    for ch in value.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            ch if ch.is_control() => write!(out, "\\u{:04x}", ch as u32).expect("writing to string cannot fail"),
            ch => out.push(ch),
        }
    }
    out.push('"');
    out
}

fn tree_rows(processes: &[ProcessInfo], root_pid: i32) -> Vec<(&ProcessInfo, usize)> {
    let by_pid: HashMap<i32, &ProcessInfo> = processes.iter().map(|p| (p.pid, p)).collect();
    let mut children: BTreeMap<i32, Vec<&ProcessInfo>> = BTreeMap::new();
    for process in processes {
        children.entry(process.ppid).or_default().push(process);
    }
    for group in children.values_mut() {
        group.sort_by_key(|p| p.pid);
    }
    let mut rows = Vec::new();
    let mut seen = HashSet::new();
    if let Some(root) = by_pid.get(&root_pid) {
        append_tree_rows(root, 0, &children, &mut seen, &mut rows);
    }
    rows
}

fn append_tree_rows<'a>(
    process: &'a ProcessInfo,
    depth: usize,
    children: &BTreeMap<i32, Vec<&'a ProcessInfo>>,
    seen: &mut HashSet<i32>,
    rows: &mut Vec<(&'a ProcessInfo, usize)>,
) {
    if !seen.insert(process.pid) {
        return;
    }
    rows.push((process, depth));
    if let Some(kids) = children.get(&process.pid) {
        for child in kids {
            append_tree_rows(child, depth + 1, children, seen, rows);
        }
    }
}

fn print_tree(processes: &[ProcessInfo], root_pid: i32) -> Result<()> {
    let rows = tree_rows(processes, root_pid);
    let mut out = String::new();
    writeln!(
        out,
        "{:<6} {:<6} {:<10} {:>5} {:>5} {:>8} {:<8} COMMAND",
        "PID", "PPID", "USER", "%CPU", "%MEM", "RSS(KB)", "START"
    )
    .expect("writing to string cannot fail");
    for (process, depth) in rows {
        writeln!(
            out,
            "{:<6} {:<6} {:<10.10} {:>5.1} {:>5.1} {:>8} {:<8} {}{}",
            process.pid,
            process.ppid,
            process.user,
            process.cpu_percent,
            process.mem_percent,
            process.rss_kb,
            process.start_display,
            "  ".repeat(depth),
            process.command
        )
        .expect("writing to string cannot fail");
    }
    safe_stdout(&out)
}

fn safe_stdout(output: &str) -> Result<()> {
    let mut stdout = io::stdout().lock();
    match stdout.write_all(output.as_bytes()).and_then(|()| stdout.flush()) {
        Ok(()) => Ok(()),
        Err(err) if err.kind() == io::ErrorKind::BrokenPipe => Ok(()),
        Err(err) => Err(ProcmonError::internal(format!("failed writing stdout: {err}"))),
    }
}

fn format_start(epoch_seconds: u64) -> String {
    let now = unix_now_seconds();
    if now.saturating_sub(epoch_seconds) < 86_400 {
        let seconds_today = epoch_seconds % 86_400;
        format!("{:02}:{:02}", seconds_today / 3600, (seconds_today % 3600) / 60)
    } else {
        let days = epoch_seconds / 86_400;
        format!("d{days}")
    }
}

fn join_pids(pids: &[i32]) -> String {
    pids.iter().map(i32::to_string).collect::<Vec<_>>().join(",")
}

fn print_usage() {
    eprintln!("usage:");
    eprintln!("  procmon list [--sort pid|cpu|mem|start] [--reverse] [--format table|json]");
    eprintln!("  procmon find <pattern> [--exact] [--format table|json]");
    eprintln!("  procmon kill <pid|pattern> [--signal SIGTERM|SIGKILL|...] [--force]");
    eprintln!("  procmon watch [pattern] [--interval SECS] [--format table|json]");
    eprintln!("  procmon tree [--pid PID] [--format table|json]");
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_process(pid: i32, ppid: i32, command: &str) -> ProcessInfo {
        ProcessInfo {
            pid,
            ppid,
            uid: 1000,
            user: "tester".to_string(),
            cpu_percent: pid as f64,
            mem_percent: (100 - pid) as f64,
            rss_kb: 42,
            start_seconds: pid as u64,
            start_display: "12:00".to_string(),
            command: command.to_string(),
        }
    }

    #[test]
    fn parses_proc_stat_with_spaces_and_parentheses_in_comm() {
        let stat = "123 (my proc) name) S 7 1 2 3 4 5 6 7 8 9 101 202 13 14 15 16 17 18 1900 20 21 22";
        let parsed = parse_proc_stat(stat).expect("stat parses");
        assert_eq!(parsed.pid, 123);
        assert_eq!(parsed.comm, "my proc) name");
        assert_eq!(parsed.state, 'S');
        assert_eq!(parsed.ppid, 7);
        assert_eq!(parsed.utime_ticks, 101);
        assert_eq!(parsed.stime_ticks, 202);
        assert_eq!(parsed.start_time_ticks, 1900);
    }

    #[test]
    fn sorts_by_pid_and_reverse() {
        let mut processes = vec![sample_process(3, 1, "c"), sample_process(1, 0, "a"), sample_process(2, 1, "b")];
        sort_processes(&mut processes, SortKey::Pid, true);
        let pids: Vec<i32> = processes.into_iter().map(|p| p.pid).collect();
        assert_eq!(pids, vec![3, 2, 1]);
    }

    #[test]
    fn exact_find_is_literal_substring() {
        let processes = vec![sample_process(1, 0, "alpha [worker]"), sample_process(2, 0, "beta")];
        let matches = filter_by_pattern(processes, "[worker]", true).expect("literal match");
        assert_eq!(matches.len(), 1);
        assert_eq!(matches[0].pid, 1);
    }

    #[test]
    fn json_string_escapes_control_characters() {
        assert_eq!(json_string("a\"b\\c\n"), "\"a\\\"b\\\\c\\n\"");
    }

    #[test]
    fn tree_rows_indent_children() {
        let processes = vec![sample_process(1, 0, "root"), sample_process(2, 1, "child"), sample_process(3, 2, "grandchild")];
        let rows = tree_rows(&processes, 1);
        let depths: Vec<_> = rows.into_iter().map(|(p, d)| (p.pid, d)).collect();
        assert_eq!(depths, vec![(1, 0), (2, 1), (3, 2)]);
    }
}
