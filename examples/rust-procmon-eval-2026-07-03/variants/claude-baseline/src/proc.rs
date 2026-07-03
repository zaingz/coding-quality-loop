//! `/proc` filesystem parsing for Linux process information.
//!
//! All reads are best-effort: if a process dies mid-read we return `None`/`Err`
//! and callers skip it gracefully (TOCTOU is unavoidable with procfs).

use std::collections::HashMap;
use std::fs;
use std::io;
use std::time::{Duration, SystemTime};

use serde::{Deserialize, Serialize};

/// Clock ticks per second (typically 100 on Linux).
fn ticks_per_sec() -> u64 {
    // SAFETY: sysconf is a simple read-only syscall with no memory hazards.
    let v = unsafe { libc::sysconf(libc::_SC_CLK_TCK) };
    if v <= 0 { 100 } else { v as u64 }
}

/// System uptime in seconds, read from `/proc/uptime`.
fn system_uptime_secs() -> f64 {
    fs::read_to_string("/proc/uptime")
        .ok()
        .and_then(|s| {
            s.split_whitespace()
                .next()
                .and_then(|v| v.parse::<f64>().ok())
        })
        .unwrap_or(0.0)
}

/// Total system RAM in KB from `/proc/meminfo`.
fn total_mem_kb() -> u64 {
    fs::read_to_string("/proc/meminfo")
        .ok()
        .and_then(|s| {
            s.lines()
                .find(|l| l.starts_with("MemTotal:"))
                .and_then(|l| l.split_whitespace().nth(1))
                .and_then(|v| v.parse::<u64>().ok())
        })
        .unwrap_or(1)
}

/// Raw fields from `/proc/[pid]/stat` (space-separated, comm may contain spaces).
#[derive(Debug, Clone)]
pub struct ProcStat {
    pub state: char,
    pub ppid: u32,
    pub utime: u64,     // user-mode ticks
    pub stime: u64,     // kernel-mode ticks
    pub starttime: u64, // ticks after boot
    pub rss: i64,       // resident pages (may be negative briefly)
}

impl ProcStat {
    pub fn read(pid: u32) -> io::Result<Self> {
        let raw = fs::read_to_string(format!("/proc/{}/stat", pid))?;
        parse_stat(&raw)
    }
}

/// Parse `/proc/[pid]/stat`.
///
/// The `comm` field (field 2) is wrapped in parentheses and may itself
/// contain spaces and parentheses, so we split on the outermost `(` `)`.
pub fn parse_stat(raw: &str) -> io::Result<ProcStat> {
    // Find the last ')' — comm ends there.
    let rp = raw.rfind(')').ok_or_else(|| {
        io::Error::new(io::ErrorKind::InvalidData, "no ')' in stat")
    })?;
    let lp = raw.find('(').ok_or_else(|| {
        io::Error::new(io::ErrorKind::InvalidData, "no '(' in stat")
    })?;

    let pid_str = raw[..lp].trim();
    let comm = raw[lp + 1..rp].to_string();
    let rest: Vec<&str> = raw[rp + 1..].split_whitespace().collect();

    // rest[0] = state, rest[1] = ppid, ...
    // Fields after comm (0-indexed in rest):
    // 0=state, 1=ppid, 2=pgrp, 3=session, 4=tty_nr,
    // 5=tpgid, 6=flags, 7=minflt, 8=cminflt, 9=majflt, 10=cmajflt,
    // 11=utime, 12=stime, 13=cutime, 14=cstime, 15=priority, 16=nice,
    // 17=num_threads, 18=itrealvalue, 19=starttime, 20=vsize, 21=rss

    let field = |i: usize| -> io::Result<&str> {
        rest.get(i).copied().ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidData, format!("stat field {i} missing"))
        })
    };
    let parse_u64 = |i: usize| -> io::Result<u64> {
        field(i)?.parse::<u64>().map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))
    };
    let parse_i64 = |i: usize| -> io::Result<i64> {
        field(i)?.parse::<i64>().map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))
    };

    // Validate pid_str parses (used in tests / callers that check the pid).
    let _pid = pid_str.parse::<u32>().map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
    let _ = comm; // parsed but not stored in struct (callers use /proc/pid/comm)

    Ok(ProcStat {
        state: field(0)?.chars().next().unwrap_or('?'),
        ppid: field(1)?.parse::<u32>().map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?,
        utime: parse_u64(11)?,
        stime: parse_u64(12)?,
        starttime: parse_u64(19)?,
        rss: parse_i64(21)?,
    })
}

/// Parsed fields from `/proc/[pid]/status`.
#[derive(Debug, Clone)]
pub struct ProcStatus {
    pub uid: u32,
    pub vm_rss_kb: u64,
}

impl ProcStatus {
    pub fn read(pid: u32) -> io::Result<Self> {
        let raw = fs::read_to_string(format!("/proc/{}/status", pid))?;
        let mut uid = 0u32;
        let mut vm_rss_kb = 0u64;
        for line in raw.lines() {
            if let Some(rest) = line.strip_prefix("Uid:") {
                uid = rest.split_whitespace()
                    .next()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(0);
            } else if let Some(rest) = line.strip_prefix("VmRSS:") {
                vm_rss_kb = rest.split_whitespace()
                    .next()
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(0);
            }
        }
        Ok(ProcStatus { uid, vm_rss_kb })
    }
}

/// Read the full command line from `/proc/[pid]/cmdline` (NUL-separated args).
pub fn read_cmdline(pid: u32) -> String {
    fs::read(format!("/proc/{}/cmdline", pid))
        .map(|b| {
            // args are NUL-separated; replace NUL with space
            let s: String = b.iter()
                .map(|&c| if c == 0 { ' ' } else { c as char })
                .collect();
            s.trim().to_string()
        })
        .unwrap_or_default()
}

/// Read the short comm name from `/proc/[pid]/comm`.
pub fn read_comm(pid: u32) -> String {
    fs::read_to_string(format!("/proc/{}/comm", pid))
        .map(|s| s.trim().to_string())
        .unwrap_or_default()
}

/// Username lookup by UID via `/etc/passwd`.
fn uid_to_name(uid: u32) -> String {
    fs::read_to_string("/etc/passwd")
        .ok()
        .and_then(|s| {
            s.lines()
                .find(|l| {
                    l.split(':').nth(2).and_then(|u| u.parse::<u32>().ok()) == Some(uid)
                })
                .and_then(|l| l.split(':').next().map(|n| n.to_string()))
        })
        .unwrap_or_else(|| uid.to_string())
}

/// A fully populated process entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessInfo {
    pub pid: u32,
    pub ppid: u32,
    pub uid: u32,
    pub user: String,
    pub cpu_pct: f64,
    pub mem_pct: f64,
    pub rss_kb: u64,
    /// Wall-clock epoch seconds when the process started.
    pub start_epoch: u64,
    /// Human-readable start time (HH:MM or Mon DD).
    pub start_str: String,
    pub command: String,
    pub comm: String,
    pub state: char,
}

/// Collect all readable processes owned by `uid_filter` (None = all users).
pub fn collect_processes(uid_filter: Option<u32>) -> Vec<ProcessInfo> {
    let tps = ticks_per_sec() as f64;
    let uptime = system_uptime_secs();
    let total_mem = total_mem_kb() as f64;

    // Read /proc/uptime btime for absolute start calculation.
    let boot_time_epoch = read_boot_time_epoch();

    let rd = match fs::read_dir("/proc") {
        Ok(d) => d,
        Err(_) => return vec![],
    };

    let mut procs = Vec::new();

    for entry in rd.flatten() {
        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        let pid: u32 = match name_str.parse() {
            Ok(p) => p,
            Err(_) => continue,
        };

        let stat = match ProcStat::read(pid) {
            Ok(s) => s,
            Err(_) => continue,
        };
        let status = match ProcStatus::read(pid) {
            Ok(s) => s,
            Err(_) => continue,
        };

        if let Some(filter_uid) = uid_filter {
            if status.uid != filter_uid {
                continue;
            }
        }

        let cmdline = read_cmdline(pid);
        let comm = read_comm(pid);

        // CPU %: (utime+stime)/tps / process_elapsed_secs * 100
        let proc_elapsed = uptime - (stat.starttime as f64 / tps);
        let cpu_pct = if proc_elapsed > 0.0 {
            ((stat.utime + stat.stime) as f64 / tps / proc_elapsed) * 100.0
        } else {
            0.0
        };

        // RSS in KB: stat rss is pages, page size typically 4096.
        let page_kb = page_size_kb();
        let rss_kb = if stat.rss > 0 {
            stat.rss as u64 * page_kb
        } else {
            status.vm_rss_kb
        };

        let mem_pct = (rss_kb as f64 / 1024.0) / total_mem * 100.0;

        let start_epoch = boot_time_epoch + (stat.starttime as f64 / tps) as u64;
        let start_str = format_start_time(start_epoch);

        let user = uid_to_name(status.uid);

        let command = if cmdline.is_empty() {
            format!("[{}]", comm)
        } else {
            cmdline.clone()
        };

        procs.push(ProcessInfo {
            pid,
            ppid: stat.ppid,
            uid: status.uid,
            user,
            cpu_pct,
            mem_pct,
            rss_kb,
            start_epoch,
            start_str,
            command,
            comm,
            state: stat.state,
        });
    }

    procs
}

fn page_size_kb() -> u64 {
    // SAFETY: sysconf read-only call.
    let sz = unsafe { libc::sysconf(libc::_SC_PAGESIZE) };
    if sz <= 0 { 4 } else { sz as u64 / 1024 }
}

fn read_boot_time_epoch() -> u64 {
    fs::read_to_string("/proc/stat")
        .ok()
        .and_then(|s| {
            s.lines()
                .find(|l| l.starts_with("btime "))
                .and_then(|l| l.split_whitespace().nth(1))
                .and_then(|v| v.parse::<u64>().ok())
        })
        .unwrap_or(0)
}

fn format_start_time(epoch: u64) -> String {
    // We format as HH:MM if started today, else "Mon DD".
    let now = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_secs();

    // Days since epoch (UTC, ignoring leap seconds)
    let today_day = now / 86400;
    let start_day = epoch / 86400;

    if today_day == start_day {
        let secs_in_day = epoch % 86400;
        let h = secs_in_day / 3600;
        let m = (secs_in_day % 3600) / 60;
        format!("{:02}:{:02}", h, m)
    } else {
        // Simple month+day
        let months = ["Jan","Feb","Mar","Apr","May","Jun",
                      "Jul","Aug","Sep","Oct","Nov","Dec"];
        // Rough date calc (ignoring leap years for display only)
        let days_since_epoch = epoch / 86400;
        let year = 1970 + days_since_epoch / 365;
        let day_in_year = days_since_epoch % 365;
        let month_days = [31u64,28,31,30,31,30,31,31,30,31,30,31];
        let mut month = 0usize;
        let mut rem = day_in_year;
        for (i, &md) in month_days.iter().enumerate() {
            if rem < md { month = i; break; }
            rem -= md;
        }
        let _ = year; // suppress warning; we just show Mon DD
        format!("{} {:02}", months[month], rem + 1)
    }
}

/// Build a parent→children map from a slice of processes.
pub fn build_tree(procs: &[ProcessInfo]) -> HashMap<u32, Vec<u32>> {
    let mut map: HashMap<u32, Vec<u32>> = HashMap::new();
    for p in procs {
        map.entry(p.ppid).or_default().push(p.pid);
    }
    map
}
