fn main() {
    let code = match procmon::run(std::env::args().skip(1).collect()) {
        Ok(()) => 0,
        Err(err) => {
            eprintln!("procmon: {err}");
            err.exit_code()
        }
    };
    std::process::exit(code);
}
