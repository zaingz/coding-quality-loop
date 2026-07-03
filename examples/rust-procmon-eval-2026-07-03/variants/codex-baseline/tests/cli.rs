use std::process::Command;

fn procmon() -> &'static str {
    env!("CARGO_BIN_EXE_procmon")
}

#[test]
fn list_prints_table_with_procmon() {
    let output = Command::new(procmon())
        .arg("list")
        .output()
        .expect("run procmon list");
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).expect("utf8 stdout");
    assert!(stdout.contains("PID"));
    assert!(stdout.contains("COMMAND"));
    assert!(stdout.contains("procmon"), "stdout was: {stdout}");
}

#[test]
fn find_current_procmon_as_json() {
    let output = Command::new(procmon())
        .args(["find", "procmon", "--format", "json"])
        .output()
        .expect("run procmon find");
    assert!(output.status.success());
    let stdout = String::from_utf8(output.stdout).expect("utf8 stdout");
    let first = stdout.lines().next().expect("json line");
    let value: serde_json::Value = serde_json::from_str(first).expect("valid json");
    assert!(value["command"].as_str().unwrap_or_default().contains("procmon"));
}

#[test]
fn refuses_to_kill_pid_one_without_force() {
    let output = Command::new(procmon())
        .args(["kill", "1"])
        .output()
        .expect("run procmon kill 1");
    assert!(!output.status.success());
    let stderr = String::from_utf8(output.stderr).expect("utf8 stderr");
    assert!(stderr.contains("refusing"));
}
