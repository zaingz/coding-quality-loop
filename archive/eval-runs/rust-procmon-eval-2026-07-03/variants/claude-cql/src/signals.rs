use crate::error::AppError;

/// Parse a signal name or number into the libc signal integer.
pub fn parse_signal(s: &str) -> Result<libc::c_int, AppError> {
    // Try numeric first.
    if let Ok(n) = s.parse::<libc::c_int>() {
        return Ok(n);
    }
    // Strip optional "SIG" prefix.
    let upper = s.to_uppercase();
    let name = upper.strip_prefix("SIG").unwrap_or(&upper);
    let sig = match name {
        "HUP" => libc::SIGHUP,
        "INT" => libc::SIGINT,
        "QUIT" => libc::SIGQUIT,
        "ILL" => libc::SIGILL,
        "ABRT" => libc::SIGABRT,
        "FPE" => libc::SIGFPE,
        "KILL" => libc::SIGKILL,
        "SEGV" => libc::SIGSEGV,
        "PIPE" => libc::SIGPIPE,
        "ALRM" => libc::SIGALRM,
        "TERM" => libc::SIGTERM,
        "USR1" => libc::SIGUSR1,
        "USR2" => libc::SIGUSR2,
        "CHLD" => libc::SIGCHLD,
        "CONT" => libc::SIGCONT,
        "STOP" => libc::SIGSTOP,
        "TSTP" => libc::SIGTSTP,
        "TTIN" => libc::SIGTTIN,
        "TTOU" => libc::SIGTTOU,
        _ => {
            return Err(AppError::NoMatch(format!(
                "unknown signal '{s}'; use a name like SIGTERM or a number"
            )))
        }
    };
    Ok(sig)
}

/// Send `signal` to `pid`.
///
/// # Safety
/// `libc::kill` is a direct syscall wrapper; there is no memory safety risk
/// here, but FFI requires an `unsafe` block.
pub fn send_signal(pid: u32, signal: libc::c_int) -> Result<(), AppError> {
    // Safety: kill(2) only reads the arguments; no memory aliasing concerns.
    let ret = unsafe { libc::kill(pid as libc::pid_t, signal) };
    if ret == 0 {
        Ok(())
    } else {
        let errno = std::io::Error::last_os_error();
        if errno.kind() == std::io::ErrorKind::PermissionDenied {
            Err(AppError::Permission(format!(
                "permission denied sending signal to pid {pid}"
            )))
        } else {
            Err(AppError::NoMatch(format!(
                "kill({pid}, {signal}) failed: {errno}"
            )))
        }
    }
}
