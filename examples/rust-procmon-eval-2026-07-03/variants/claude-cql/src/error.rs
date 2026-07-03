use std::fmt;

/// Application error with associated exit code.
#[derive(Debug)]
pub enum AppError {
    /// Usage error or no matching processes (exit 1).
    NoMatch(String),
    /// Permission denied (exit 2).
    Permission(String),
    /// Internal / unexpected error (exit 3).
    Internal(String),
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AppError::NoMatch(msg) => write!(f, "{msg}"),
            AppError::Permission(msg) => write!(f, "{msg}"),
            AppError::Internal(msg) => write!(f, "{msg}"),
        }
    }
}

impl AppError {
    pub fn exit_code(&self) -> i32 {
        match self {
            AppError::NoMatch(_) => 1,
            AppError::Permission(_) => 2,
            AppError::Internal(_) => 3,
        }
    }
}
