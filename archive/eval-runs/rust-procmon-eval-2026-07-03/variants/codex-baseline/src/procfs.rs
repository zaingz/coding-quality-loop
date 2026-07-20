use serde::Serialize;
use std::collections::HashMap;
use std::fmt;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

const CLOCK_TICKS_PER_SECOND: f64 = 100.0;
const PAGE_SIZE_KB: i64 = 4;

#[derive(Clone, Debug, Serialize)]
pub struct ProcessInfo {
    pub pid: i32,
    pub ppid: i32,
    pub uid: u32,
    pub user: String,
    pub cpu_percent: f64,
    pub mem_percent: f64,
    pub rss_kb: i64,
    pub start_time: u64,
    pub command: String,
}

#[derive(Debug)]
pub enum ProcError {
    Io(io::Error),
    Parse(String),
}

impl fmt::Display for ProcError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ProcError::Io(error) => write!(formatter, "{error}"),
            ProcError::Parse(message) => write!(formatter, "{message}"),
        }
    }
}

impl From<io::Error> for ProcError {
    fn from(value: io::Error) -> Self {
        ProcError::Io(value)
    }
}

#[derive(Debug, PartialEq)]
pub struct StatFields {
    pub pid: i32,
    pub comm: String,
    pub state: char,
    pub ppid: i32,
    pub utime_ticks: u64,
    pub stime_ticks: u64,
    pub starttime_ticks: u64,
    pub rss_pages: i64,
}

pub fn load_processes() -> Result<Vec<ProcessInfo>, ProcError> {
    let boot_time = boot_time_seconds()?;
    let uptime = uptime_seconds()?;
    let mem_total_kb = mem_total_kb()?;
    let users = passwd_users().unwrap_or_default();
    let mut processes = Vec::new();

    for entry in fs::read_dir("/proc")? {
        let entry = match entry {
            Ok(entry) => entry,
            Err(_) => continue,
        };
        let file_name = entry.file_name();
        let Some(name) = file_name.to_str() else {
            continue;
        };
        if !name.chars().all(|ch| ch.is_ascii_digit()) {
            continue;
        }
        let path = entry.path();
        if let Some(process) = read_process(&path, boot_time, uptime, mem_total_kb, &users) {
            processes.push(process);
        }
    }
    Ok(processes)
}

pub fn current_uid() -> Result<u32, ProcError> {
    let status = fs::read_to_string("/proc/self/status")?;
    parse_uid(&status).ok_or_else(|| ProcError::Parse("could not read current uid".to_string()))
}

fn read_process(
    path: &Path,
    boot_time: u64,
    uptime: f64,
    mem_total_kb: i64,
    users: &HashMap<u32, String>,
) -> Option<ProcessInfo> {
    let stat_text = fs::read_to_string(path.join("stat")).ok()?;
    let stat = parse_stat(&stat_text).ok()?;
    let status_text = fs::read_to_string(path.join("status")).ok()?;
    let uid = parse_uid(&status_text)?;
    let user = users.get(&uid).cloned().unwrap_or_else(|| uid.to_string());
    let cmdline = read_cmdline(path.join("cmdline")).unwrap_or_default();
    let comm = fs::read_to_string(path.join("comm"))
        .map(|text| text.trim().to_string())
        .unwrap_or_else(|_| stat.comm.clone());
    let command = if cmdline.is_empty() { comm } else { cmdline };
    let rss_kb = stat.rss_pages.saturating_mul(PAGE_SIZE_KB);
    let start_since_boot = stat.starttime_ticks as f64 / CLOCK_TICKS_PER_SECOND;
    let elapsed = (uptime - start_since_boot).max(1.0);
    let cpu_seconds = (stat.utime_ticks + stat.stime_ticks) as f64 / CLOCK_TICKS_PER_SECOND;
    let cpu_percent = (cpu_seconds / elapsed) * 100.0;
    let mem_percent = if mem_total_kb > 0 {
        (rss_kb as f64 / mem_total_kb as f64) * 100.0
    } else {
        0.0
    };
    Some(ProcessInfo {
        pid: stat.pid,
        ppid: stat.ppid,
        uid,
        user,
        cpu_percent,
        mem_percent,
        rss_kb,
        start_time: boot_time + start_since_boot as u64,
        command,
    })
}

pub fn parse_stat(input: &str) -> Result<StatFields, ProcError> {
    let left = input
        .find('(')
        .ok_or_else(|| ProcError::Parse("stat is missing command start".to_string()))?;
    let right = input
        .rfind(')')
        .ok_or_else(|| ProcError::Parse("stat is missing command end".to_string()))?;
    if right <= left {
        return Err(ProcError::Parse("malformed stat command".to_string()));
    }
    let pid = input[..left]
        .trim()
        .parse::<i32>()
        .map_err(|error| ProcError::Parse(format!("invalid stat pid: {error}")))?;
    let comm = input[left + 1..right].to_string();
    let fields = input[right + 1..].split_whitespace().collect::<Vec<_>>();
    if fields.len() <= 21 {
        return Err(ProcError::Parse("stat has too few fields".to_string()));
    }
    let state = fields[0]
        .chars()
        .next()
        .ok_or_else(|| ProcError::Parse("stat state is empty".to_string()))?;
    Ok(StatFields {
        pid,
        comm,
        state,
        ppid: parse_field(fields[1], "ppid")?,
        utime_ticks: parse_field(fields[11], "utime")?,
        stime_ticks: parse_field(fields[12], "stime")?,
        starttime_ticks: parse_field(fields[19], "starttime")?,
        rss_pages: parse_field(fields[21], "rss")?,
    })
}

fn parse_field<T>(value: &str, name: &str) -> Result<T, ProcError>
where
    T: std::str::FromStr,
    T::Err: fmt::Display,
{
    value
        .parse::<T>()
        .map_err(|error| ProcError::Parse(format!("invalid stat {name}: {error}")))
}

fn parse_uid(status: &str) -> Option<u32> {
    status.lines().find_map(|line| {
        line.strip_prefix("Uid:").and_then(|rest| {
            rest.split_whitespace()
                .next()
                .and_then(|uid| uid.parse::<u32>().ok())
        })
    })
}

fn read_cmdline(path: PathBuf) -> io::Result<String> {
    let bytes = fs::read(path)?;
    let parts = bytes
        .split(|byte| *byte == 0)
        .filter(|part| !part.is_empty())
        .map(|part| String::from_utf8_lossy(part).into_owned())
        .collect::<Vec<_>>();
    Ok(parts.join(" "))
}

fn boot_time_seconds() -> Result<u64, ProcError> {
    let text = fs::read_to_string("/proc/stat")?;
    for line in text.lines() {
        if let Some(value) = line.strip_prefix("btime ") {
            return value
                .trim()
                .parse::<u64>()
                .map_err(|error| ProcError::Parse(format!("invalid btime: {error}")));
        }
    }
    Err(ProcError::Parse("/proc/stat has no btime".to_string()))
}

fn uptime_seconds() -> Result<f64, ProcError> {
    let text = fs::read_to_string("/proc/uptime")?;
    text.split_whitespace()
        .next()
        .ok_or_else(|| ProcError::Parse("/proc/uptime is empty".to_string()))?
        .parse::<f64>()
        .map_err(|error| ProcError::Parse(format!("invalid uptime: {error}")))
}

fn mem_total_kb() -> Result<i64, ProcError> {
    let text = fs::read_to_string("/proc/meminfo")?;
    for line in text.lines() {
        if let Some(value) = line.strip_prefix("MemTotal:") {
            return value
                .split_whitespace()
                .next()
                .ok_or_else(|| ProcError::Parse("MemTotal has no value".to_string()))?
                .parse::<i64>()
                .map_err(|error| ProcError::Parse(format!("invalid MemTotal: {error}")));
        }
    }
    Err(ProcError::Parse("/proc/meminfo has no MemTotal".to_string()))
}

fn passwd_users() -> io::Result<HashMap<u32, String>> {
    let text = fs::read_to_string("/etc/passwd")?;
    let mut users = HashMap::new();
    for line in text.lines() {
        if line.trim_start().starts_with('#') || line.is_empty() {
            continue;
        }
        let parts = line.split(':').collect::<Vec<_>>();
        if parts.len() >= 3 {
            if let Ok(uid) = parts[2].parse::<u32>() {
                users.insert(uid, parts[0].to_string());
            }
        }
    }
    Ok(users)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_stat_with_spaces_and_parentheses_in_comm() {
        let stat = "123 (my weird)name) S 7 2 3 4 5 6 7 8 9 10 120 30 14 15 16 17 18 19 2000 21 42 24";
        let parsed = parse_stat(stat).unwrap();
        assert_eq!(parsed.pid, 123);
        assert_eq!(parsed.comm, "my weird)name");
        assert_eq!(parsed.state, 'S');
        assert_eq!(parsed.ppid, 7);
        assert_eq!(parsed.utime_ticks, 120);
        assert_eq!(parsed.stime_ticks, 30);
        assert_eq!(parsed.starttime_ticks, 2000);
        assert_eq!(parsed.rss_pages, 42);
    }
}
