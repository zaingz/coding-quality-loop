use std::collections::HashMap;
use std::fs;
use std::io;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

/// Information about a single process read from /proc.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcInfo {
    pub pid: u32,
    pub ppid: u32,
    pub uid: u32,
    pub user: String,
    pub state: char,
    /// CPU user+sys ticks (utime + stime from stat)
    pub cpu_ticks: u64,
    /// RSS in kilobytes
    pub rss_kb: u64,
    /// %MEM (RSS / MemTotal * 100)
    pub mem_pct: f64,
    /// %CPU — only meaningful when computed as a delta; single-shot is 0.0
    pub cpu_pct: f64,
    /// Process start time as Unix timestamp (seconds)
    pub start_time: u64,
    /// Process start time formatted as HH:MM or MMM DD
    pub start_fmt: String,
    /// Full command line (argv joined with spaces), or [comm] for kernel threads
    pub command: String,
    /// Short comm name
    pub comm: String,
}

/// Parsed fields from /proc/[pid]/stat.
#[derive(Debug, Clone)]
pub struct StatFields {
    pub comm: String,
    pub state: char,
    pub ppid: u32,
    pub utime: u64,
    pub stime: u64,
    pub starttime: u64,
    pub rss_pages: u64,
}

/// Parse /proc/[pid]/stat content.
///
/// The `comm` field is enclosed in parentheses and may contain spaces and
/// nested parentheses. We find the last `)` to delimit it, then split the
/// remaining fields by whitespace.
pub fn parse_stat(content: &str) -> Option<StatFields> {
    // Find the last ')' which terminates the comm field.
    let close = content.rfind(')')?;
    let open = content.find('(')?;

    let comm = content[open + 1..close].to_string();

    // Everything after ") " — field 3 onward (state is field 3).
    let rest = content[close + 1..].trim();
    let fields: Vec<&str> = rest.split_whitespace().collect();
    // fields[0] = state (field 3)
    // fields[1] = ppid  (field 4)
    // fields[11] = utime (field 14, index 11 in rest)
    // fields[12] = stime (field 15)
    // fields[19] = starttime (field 22, index 19 in rest)
    // fields[21] = rss   (field 24, index 21 in rest)
    if fields.len() < 22 {
        return None;
    }
    let state = fields[0].chars().next()?;
    let ppid: u32 = fields[1].parse().ok()?;
    let utime: u64 = fields[11].parse().ok()?;
    let stime: u64 = fields[12].parse().ok()?;
    let starttime: u64 = fields[19].parse().ok()?;
    let rss_pages: u64 = fields[21].parse().ok()?;

    Some(StatFields {
        comm,
        state,
        ppid,
        utime,
        stime,
        starttime,
        rss_pages,
    })
}

/// Read UID from /proc/[pid]/status.
pub fn read_uid(pid: u32) -> Option<u32> {
    let content = fs::read_to_string(format!("/proc/{pid}/status")).ok()?;
    for line in content.lines() {
        if let Some(rest) = line.strip_prefix("Uid:") {
            // Format: "Uid:\treal\teffective\tsaved\tfs"
            let uid: u32 = rest.split_whitespace().next()?.parse().ok()?;
            return Some(uid);
        }
    }
    None
}

/// Read command line from /proc/[pid]/cmdline.
/// Returns None if the file is empty (kernel thread) or cannot be read.
pub fn read_cmdline(pid: u32) -> Option<String> {
    let bytes = fs::read(format!("/proc/{pid}/cmdline")).ok()?;
    if bytes.is_empty() {
        return None;
    }
    // argv elements are NUL-separated; replace NULs with spaces.
    let s = bytes
        .split(|&b| b == 0)
        .filter(|s| !s.is_empty())
        .map(|s| String::from_utf8_lossy(s).into_owned())
        .collect::<Vec<_>>()
        .join(" ");
    if s.is_empty() {
        None
    } else {
        Some(s)
    }
}

/// Read system uptime in seconds from /proc/uptime.
pub fn read_uptime() -> Option<f64> {
    let content = fs::read_to_string("/proc/uptime").ok()?;
    content.split_whitespace().next()?.parse().ok()
}

/// Read total memory in kB from /proc/meminfo.
pub fn read_mem_total_kb() -> Option<u64> {
    let content = fs::read_to_string("/proc/meminfo").ok()?;
    for line in content.lines() {
        if let Some(rest) = line.strip_prefix("MemTotal:") {
            return rest.split_whitespace().next()?.parse().ok();
        }
    }
    None
}

/// Resolve a UID to a username by reading /etc/passwd.
pub fn uid_to_username(uid: u32) -> String {
    if let Ok(content) = fs::read_to_string("/etc/passwd") {
        for line in content.lines() {
            let parts: Vec<&str> = line.split(':').collect();
            if parts.len() >= 3 {
                if let Ok(u) = parts[2].parse::<u32>() {
                    if u == uid {
                        return parts[0].to_string();
                    }
                }
            }
        }
    }
    uid.to_string()
}

/// Format a Unix timestamp as HH:MM (today) or Mon DD (different day).
fn format_start_time(ts: u64) -> String {
    // We avoid chrono for simplicity; use basic arithmetic.
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);

    let secs_per_day = 86400u64;
    let today_start = (now / secs_per_day) * secs_per_day;

    if ts >= today_start {
        // Same day: HH:MM
        let elapsed = ts - today_start;
        let hh = elapsed / 3600;
        let mm = (elapsed % 3600) / 60;
        format!("{hh:02}:{mm:02}")
    } else {
        // Different day: estimate day-of-year
        let days_ago = (now.saturating_sub(ts)) / secs_per_day;
        if days_ago < 365 {
            // Month/day approximation
            let month_names = [
                "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov",
                "Dec",
            ];
            // rough: 365 days, 12 months
            let day_of_year = (ts % (365 * secs_per_day)) / secs_per_day;
            let month_idx = ((day_of_year * 12) / 365).min(11) as usize;
            let day_of_month = ((day_of_year % (365 / 12)) + 1).min(31);
            format!("{} {:02}", month_names[month_idx], day_of_month)
        } else {
            // Very old: just show year
            let year = 1970 + ts / (365 * secs_per_day);
            format!("{year}")
        }
    }
}

/// Read a single process entry. Returns None if the process has exited or
/// cannot be read (race condition handling).
pub fn read_proc_entry(
    pid: u32,
    clk_tck: u64,
    uptime_secs: f64,
    mem_total_kb: u64,
) -> Option<ProcInfo> {
    let stat_content = match fs::read_to_string(format!("/proc/{pid}/stat")) {
        Ok(s) => s,
        Err(e) if e.kind() == io::ErrorKind::NotFound => return None,
        Err(_) => return None,
    };

    let stat = parse_stat(&stat_content)?;
    let uid = read_uid(pid)?;
    let user = uid_to_username(uid);
    let cmdline = read_cmdline(pid).unwrap_or_else(|| format!("[{}]", stat.comm));

    let page_size_kb = 4; // standard 4 KiB pages
    let rss_kb = stat.rss_pages * page_size_kb;
    let mem_pct = if mem_total_kb > 0 {
        (rss_kb as f64 / mem_total_kb as f64) * 100.0
    } else {
        0.0
    };

    // Compute process start wall-clock time.
    let start_secs_since_boot = stat.starttime as f64 / clk_tck as f64;
    let now_secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0);
    let start_unix = (now_secs - uptime_secs + start_secs_since_boot) as u64;
    let start_fmt = format_start_time(start_unix);

    Some(ProcInfo {
        pid,
        ppid: stat.ppid,
        uid,
        user,
        state: stat.state,
        cpu_ticks: stat.utime + stat.stime,
        rss_kb,
        mem_pct,
        cpu_pct: 0.0, // set by caller after delta computation
        start_time: start_unix,
        start_fmt,
        command: cmdline,
        comm: stat.comm,
    })
}

/// List all visible processes. Silently skips entries that have exited.
pub fn list_all_procs(clk_tck: u64, uptime_secs: f64, mem_total_kb: u64) -> Vec<ProcInfo> {
    let entries = match fs::read_dir("/proc") {
        Ok(e) => e,
        Err(_) => return vec![],
    };

    entries
        .filter_map(|e| e.ok())
        .filter_map(|e| {
            let name = e.file_name();
            let s = name.to_str()?;
            // Only digit-only entries are PID directories.
            if s.chars().all(|c| c.is_ascii_digit()) {
                s.parse::<u32>().ok()
            } else {
                None
            }
        })
        .filter_map(|pid| read_proc_entry(pid, clk_tck, uptime_secs, mem_total_kb))
        .collect()
}

/// Build a parent→children map from a process list.
pub fn build_children_map(procs: &[ProcInfo]) -> HashMap<u32, Vec<u32>> {
    let mut map: HashMap<u32, Vec<u32>> = HashMap::new();
    for p in procs {
        map.entry(p.ppid).or_default().push(p.pid);
    }
    map
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_stat_basic() {
        // Real-world style stat line for pid 1.
        let line = "1 (systemd) S 0 1 1 0 -1 4194560 12345 678901 53 2024 1234 567 0 0 20 0 1 0 1000 12345678 1500 18446744073709551615 1 1 0 0 0 0 671173123 4096 1260 0 0 0 17 0 0 0 30 0 0 0 0 0 0 0 0 0 0";
        let stat = parse_stat(line).expect("should parse");
        assert_eq!(stat.comm, "systemd");
        assert_eq!(stat.state, 'S');
        assert_eq!(stat.ppid, 0);
        assert_eq!(stat.utime, 1234);
        assert_eq!(stat.stime, 567);
        assert_eq!(stat.starttime, 1000);
        assert_eq!(stat.rss_pages, 1500);
    }

    #[test]
    fn test_parse_stat_comm_with_spaces() {
        // comm field containing spaces and parentheses.
        let line = "42 (my (weird) proc) S 1 42 42 0 -1 4194304 100 0 0 0 10 5 0 0 20 0 1 0 2000 1048576 256 18446744073709551615 0 0 0 0 0 0 0 0 0 0 0 0 17 0 0 0 0 0 0 0 0 0 0 0 0 0 0";
        let stat = parse_stat(line).expect("should parse");
        assert_eq!(stat.comm, "my (weird) proc");
        assert_eq!(stat.ppid, 1);
        assert_eq!(stat.utime, 10);
        assert_eq!(stat.stime, 5);
        assert_eq!(stat.starttime, 2000);
        assert_eq!(stat.rss_pages, 256);
    }

    #[test]
    fn test_parse_stat_invalid() {
        assert!(parse_stat("").is_none());
        assert!(parse_stat("notastat").is_none());
    }

    #[test]
    fn test_read_uptime() {
        let uptime = read_uptime().expect("should read uptime on Linux");
        assert!(uptime > 0.0);
    }

    #[test]
    fn test_read_mem_total() {
        let mem = read_mem_total_kb().expect("should read MemTotal on Linux");
        assert!(mem > 0);
    }

    #[test]
    fn test_list_includes_self() {
        let clk_tck = 100;
        let uptime = read_uptime().unwrap_or(1.0);
        let mem = read_mem_total_kb().unwrap_or(1024 * 1024);
        let procs = list_all_procs(clk_tck, uptime, mem);
        let self_pid = std::process::id();
        assert!(
            procs.iter().any(|p| p.pid == self_pid),
            "current process (pid {self_pid}) should appear in list"
        );
    }
}
