use std::process::Command;

fn procmon() -> Command {
    Command::new(env!("CARGO_BIN_EXE_procmon"))
}

#[test]
fn list_shows_table_header() {
    let output = procmon().arg("list").output().expect("run procmon list");
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("PID"));
    assert!(stdout.contains("COMMAND"));
}

#[test]
fn find_current_test_harness_with_json() {
    let output = procmon()
        .args(["find", "cli", "--format", "json"])
        .output()
        .expect("run procmon find");
    assert!(output.status.success(), "stderr: {}", String::from_utf8_lossy(&output.stderr));
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.lines().any(|line| line.contains("\"pid\":") && line.contains("\"command\":")), "stdout: {stdout}");
}

#[test]
fn kill_pid_one_is_rejected_without_force() {
    let output = procmon().args(["kill", "1"]).output().expect("run procmon kill");
    assert!(!output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("refusing to signal protected"), "stderr: {stderr}");
}
