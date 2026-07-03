use std::collections::HashMap;

use crate::output::Format;
use crate::proc::ProcInfo;

/// Print process tree rooted at `root_pid` in ASCII art.
/// `procs` is indexed by PID, `children` maps parent PID → child PIDs.
pub fn print_tree(
    root_pid: u32,
    pid_map: &HashMap<u32, &ProcInfo>,
    children: &HashMap<u32, Vec<u32>>,
    fmt: &Format,
    prefix: &str,
    is_last: bool,
    is_root: bool,
) {
    let Some(p) = pid_map.get(&root_pid) else {
        return;
    };

    match fmt {
        Format::Json => {
            println!("{}", serde_json::to_string(p).unwrap_or_default());
        }
        Format::Table => {
            let connector = if is_root {
                String::new()
            } else if is_last {
                format!("{prefix}└── ")
            } else {
                format!("{prefix}├── ")
            };
            let cmd_display = if p.command.starts_with('[') {
                p.command.clone()
            } else {
                p.command.split_whitespace().next().unwrap_or(&p.command).to_string()
            };
            if is_root {
                println!("{} ({})", p.pid, cmd_display);
            } else {
                println!("{}{} ({})", connector, p.pid, cmd_display);
            }
        }
    }

    let empty = vec![];
    let mut child_pids = children.get(&root_pid).unwrap_or(&empty).clone();
    child_pids.sort_unstable();
    let count = child_pids.len();

    for (i, child_pid) in child_pids.iter().enumerate() {
        let last = i == count - 1;
        let new_prefix = if is_root {
            String::new()
        } else if is_last {
            format!("{prefix}    ")
        } else {
            format!("{prefix}│   ")
        };
        print_tree(*child_pid, pid_map, children, fmt, &new_prefix, last, false);
    }
}
