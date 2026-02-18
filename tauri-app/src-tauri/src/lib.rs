use std::io::BufRead;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::Manager;

/// Holds the Python server child process so we can kill it on exit.
struct ServerProcess(Mutex<Option<Child>>);

/// Try to spawn the Python backend server returning (child, port).
/// Returns None if the server is already running (e.g. started by beforeDevCommand).
fn try_spawn_server() -> Option<(Child, u16)> {
    // Check if the server is already running (dev mode)
    if std::net::TcpStream::connect("127.0.0.1:8765").is_ok() {
        return None;
    }

    let mut child = Command::new("python")
        .args([
            "-m",
            "robot_automation_studio.server",
            "--port",
            "0",
            "--no-browser",
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .expect(
            "Failed to start Python server. \
             Is Python installed with robot_automation_studio?",
        );

    let stdout = child.stdout.take().expect("Failed to capture server stdout");
    let reader = std::io::BufReader::new(stdout);

    for line in reader.lines() {
        let line = line.unwrap_or_default();
        if let Some(p) = line.strip_prefix("PORT:") {
            if let Ok(port) = p.trim().parse::<u16>() {
                return Some((child, port));
            }
        }
    }

    panic!("Python server did not report a port. Check server logs.");
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let server_info = try_spawn_server();

            match server_info {
                Some((child, port)) => {
                    // We spawned the server — navigate to its URL
                    let url = format!("http://127.0.0.1:{}", port);
                    if let Some(win) = app.get_webview_window("main") {
                        let _ = win.navigate(url.parse().unwrap());
                    }
                    app.manage(ServerProcess(Mutex::new(Some(child))));
                }
                None => {
                    // Server already running (dev mode) — store empty state
                    app.manage(ServerProcess(Mutex::new(None)));
                }
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.try_state::<ServerProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
