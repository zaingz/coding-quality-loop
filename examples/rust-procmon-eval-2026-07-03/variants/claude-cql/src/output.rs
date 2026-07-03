use crate::proc::ProcInfo;
use crate::table;

#[derive(Debug, Clone, PartialEq)]
pub enum Format {
    Table,
    Json,
}

impl std::str::FromStr for Format {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "table" => Ok(Format::Table),
            "json" => Ok(Format::Json),
            other => Err(format!("unknown format '{other}'; use table or json")),
        }
    }
}

/// Print processes in the requested format.
pub fn print_procs(procs: &[ProcInfo], fmt: &Format) {
    match fmt {
        Format::Table => table::print_table(procs),
        Format::Json => {
            for p in procs {
                // Each process is a single JSON line.
                println!("{}", serde_json::to_string(p).unwrap_or_else(|e| {
                    format!("{{\"error\":\"{e}\"}}")
                }));
            }
        }
    }
}
