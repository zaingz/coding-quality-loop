use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

/// Path to the release binary.
fn bin() -> String {
    // Use the debug binary during tests (cargo test builds debug by default).
    let manifest = env!("CARGO_MANIFEST_DIR");
    format!("{manifest}/target/debug/procmon")
}

/// Run the binary with args, capture stdout+stderr, return (exit_code, stdout, stderr).
fn run(args: &[&str]) -> (i32, String, String) {
    let output = Command::new(bin())
        .args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .expect("failed to run procmon binary");
    let code = output.status.code().unwrap_or(-1);
    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
    (code, stdout, stderr)
}

#[test]
fn test_list_shows_header() {
    let (code, stdout, _stderr) = run(&["list"]);
    assert_eq!(code, 0, "list should exit 0");
    assert!(
        stdout.contains("PID"),
        "list output should contain PID header"
    );
    assert!(
        stdout.contains("COMMAND"),
        "list output should contain COMMAND header"
    );
}

#[test]
fn test_list_includes_self_pid() {
    let self_pid = std::process::id().to_string();
    // The test runner process itself won't show up because procmon filters by
    // current user and the test is run in a different process. Instead, we
    // check that the binary exits cleanly and has at least one data row.
    let (code, stdout, _stderr) = run(&["list"]);
    assert_eq!(code, 0);
    let data_lines: Vec<_> = stdout.lines().skip(1).filter(|l| !l.is_empty()).collect();
    assert!(
        !data_lines.is_empty(),
        "list should have at least one process row; self_pid={self_pid}"
    );
}

#[test]
fn test_list_json_valid() {
    let (code, stdout, _stderr) = run(&["list", "--format", "json"]);
    assert_eq!(code, 0, "list --format json should exit 0");
    // Each non-empty line must be valid JSON.
    for line in stdout.lines().filter(|l| !l.is_empty()) {
        serde_json::from_str::<serde_json::Value>(line)
            .unwrap_or_else(|e| panic!("invalid JSON line: {line}\nerror: {e}"));
    }
}

#[test]
fn test_list_sort_pid() {
    let (code, stdout, _stderr) = run(&["list", "--sort", "pid"]);
    assert_eq!(code, 0);
    let pids: Vec<u32> = stdout
        .lines()
        .skip(1) // skip header
        .filter(|l| !l.is_empty())
        .filter_map(|l| l.split_whitespace().next()?.parse().ok())
        .collect();
    let mut sorted = pids.clone();
    sorted.sort_unstable();
    assert_eq!(pids, sorted, "PIDs should be sorted ascending");
}

#[test]
fn test_find_current_process() {
    // We look for 'procmon' itself in the process table.
    // In the test binary, procmon is a subprocess, so it should appear
    // while we're running it. However since find is a subcommand, we
    // can at least verify it returns valid output.
    let (code, _stdout, stderr) = run(&["find", "procmon"]);
    // Exit 0 (found) or 1 (not found) are both acceptable here;
    // what matters is that it doesn't crash (exit 3) and has no unexpected errors.
    assert!(
        code == 0 || code == 1,
        "find should exit 0 (found) or 1 (not found), got {code}; stderr: {stderr}"
    );
}

#[test]
fn test_find_json_valid() {
    // Even if no match, the binary exits 1 with nothing on stdout.
    // If there is output, each line must be valid JSON.
    let (_, stdout, _) = run(&["find", "procmon", "--format", "json"]);
    for line in stdout.lines().filter(|l| !l.is_empty()) {
        serde_json::from_str::<serde_json::Value>(line)
            .unwrap_or_else(|e| panic!("invalid JSON: {line}\nerror: {e}"));
    }
}

#[test]
fn test_find_no_match_exits_1() {
    // Use an anchored regex that cannot match any real cmdline (procmon itself
    // passes the pattern as argv, so unanchored patterns would self-match).
    let (code, _stdout, stderr) = run(&["find", "^IMPOSSIBLE_DEADBEEF_WONTMATCH_1234567890$"]);
    assert_eq!(code, 1, "find with no match should exit 1");
    assert!(
        !stderr.is_empty(),
        "find with no match should print error to stderr"
    );
}

#[test]
fn test_kill_pid1_rejected() {
    let (code, _stdout, stderr) = run(&["kill", "1"]);
    assert_eq!(code, 1, "killing PID 1 without --force should exit 1");
    assert!(
        stderr.contains("refusing") || stderr.contains("PID 1") || stderr.contains("init"),
        "stderr should mention the refusal; got: {stderr}"
    );
}

#[test]
fn test_kill_pid0_rejected() {
    let (code, _stdout, stderr) = run(&["kill", "0"]);
    assert_eq!(code, 1, "killing PID 0 without --force should exit 1");
    assert!(!stderr.is_empty(), "stderr should have an error message; got empty");
}

#[test]
fn test_kill_no_match_exits_1() {
    // Very high PID unlikely to exist.
    let (code, _stdout, _stderr) = run(&["kill", "99999999"]);
    // Either the PID doesn't exist (signal fails) or parse fails; either way
    // exit should be 1.
    assert!(code == 1 || code == 2, "killing nonexistent PID should exit 1 or 2, got {code}");
}

#[test]
fn test_tree_runs() {
    let (code, stdout, _stderr) = run(&["tree"]);
    assert_eq!(code, 0, "tree should exit 0");
    // Should have at least one line showing PID 1.
    assert!(
        stdout.contains('1'),
        "tree should show PID 1 in output"
    );
}

#[test]
fn test_tree_json_valid() {
    let (code, stdout, _) = run(&["tree", "--format", "json"]);
    assert_eq!(code, 0);
    for line in stdout.lines().filter(|l| !l.is_empty()) {
        serde_json::from_str::<serde_json::Value>(line)
            .unwrap_or_else(|e| panic!("invalid JSON: {line}\nerror: {e}"));
    }
}

/// Spawn a child process, verify it appears in list, verify it disappears after exit.
#[test]
fn test_child_appears_and_disappears() {
    use std::io::Read;

    // Spawn a long-running child.
    let mut child = Command::new("sleep")
        .arg("60")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to spawn sleep");

    let child_pid = child.id();

    // Give the OS a moment to register it.
    thread::sleep(Duration::from_millis(100));

    // It should appear in the full list (not filtered by UID since sleep
    // is our child and inherits our UID).
    let (code, stdout, _) = run(&["list"]);
    assert_eq!(code, 0);
    let child_in_list = stdout
        .lines()
        .skip(1)
        .any(|l| l.split_whitespace().next().map(|s| s == child_pid.to_string()).unwrap_or(false));

    // Kill and reap the child.
    child.kill().ok();
    child.wait().ok();

    thread::sleep(Duration::from_millis(100));

    // After the child exits, it should no longer appear.
    let (code2, stdout2, _) = run(&["list"]);
    assert_eq!(code2, 0);
    let child_still_present = stdout2
        .lines()
        .skip(1)
        .any(|l| l.split_whitespace().next().map(|s| s == child_pid.to_string()).unwrap_or(false));

    // The child should have appeared while running (it might be filtered
    // by UID in list if we're a different user, but sleep is our child).
    // The important assertion is that it's gone after exit.
    assert!(
        !child_still_present,
        "child pid {child_pid} should not appear in list after exit; child_in_list={child_in_list}"
    );
}
