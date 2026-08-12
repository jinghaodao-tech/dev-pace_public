#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use chrono::{Datelike, Duration as ChronoDuration, Local};
use rdev::listen;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use windows::core::VARIANT;
use windows::Win32::System::Com::{
    CoCreateInstance, CoInitializeEx, CLSCTX_INPROC_SERVER, COINIT_MULTITHREADED,
};
use windows::Win32::UI::Accessibility::{
    CUIAutomation, IUIAutomation, IUIAutomationElement, IUIAutomationElementArray,
    IUIAutomationValuePattern, TreeScope_Descendants, UIA_ControlTypePropertyId,
    UIA_EditControlTypeId, UIA_ValuePatternId,
};

const LOG_SCHEMA_VERSION: u8 = 2;

fn dashboard_script_path() -> PathBuf {
    project_root().join("tools").join("analyze.py")
}

#[derive(Serialize, Deserialize, Debug)]
struct ActivityLog {
    #[serde(rename = "v", default = "legacy_schema_version")]
    schema_version: u8,
    timestamp: String,
    main_window: String,
    distribution: HashMap<String, u32>,
    state: String,
}

fn legacy_schema_version() -> u8 {
    1
}

fn project_root() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|path| {
            path.parent()
                .and_then(|p| p.parent())
                .and_then(|p| p.parent())
                .map(|p| p.to_path_buf())
        })
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")))
}

fn web_ai_host(value: &str) -> Option<&'static str> {
    let lower = value.to_ascii_lowercase();
    if lower.contains("chatgpt.com") {
        Some("chatgpt.com")
    } else if lower.contains("claude.ai") {
        Some("claude.ai")
    } else if lower.contains("gemini.google.com") {
        Some("gemini.google.com")
    } else if lower.contains("perplexity.ai") {
        Some("perplexity.ai")
    } else if lower.contains("copilot.microsoft.com") {
        Some("copilot.microsoft.com")
    } else {
        None
    }
}

fn get_browser_ai_host(
    automation: &IUIAutomation,
    root: &IUIAutomationElement,
) -> Option<&'static str> {
    unsafe {
        let edit_control_type = VARIANT::from(UIA_EditControlTypeId.0);
        let condition = automation
            .CreatePropertyCondition(
                UIA_ControlTypePropertyId,
                &edit_control_type,
            )
            .ok()?;
        let elements: IUIAutomationElementArray =
            root.FindAll(TreeScope_Descendants, &condition).ok()?;
        let length = elements.Length().ok()?;

        for index in 0..length {
            let element = elements.GetElement(index).ok()?;
            let pattern: IUIAutomationValuePattern =
                match element.GetCurrentPatternAs(UIA_ValuePatternId) {
                    Ok(pattern) => pattern,
                    Err(_) => continue,
                };
            let value = pattern.CurrentValue().ok()?.to_string();
            if let Some(host) = web_ai_host(&value) {
                return Some(host);
            }
        }
    }
    None
}

fn get_active_window_title(automation: Option<&IUIAutomation>) -> String {
    use windows::Win32::UI::WindowsAndMessaging::*;
    unsafe {
        let hwnd = GetForegroundWindow();
        let length = GetWindowTextLengthW(hwnd) + 1;
        let mut buffer = vec![0u16; length as usize];
        GetWindowTextW(hwnd, &mut buffer);
        let mut title = String::from_utf16_lossy(&buffer)
            .trim_matches(char::from(0))
            .to_string();

        if title.contains("Google Chrome")
            || title.contains("Microsoft Edge")
            || title.contains("Mozilla Firefox")
            || title.contains("Brave")
        {
            if let Some(automation) = automation {
                if let Ok(root) = automation.ElementFromHandle(hwnd) {
                    if let Some(host) = get_browser_ai_host(automation, &root) {
                        title.push_str(" [web-ai:");
                        title.push_str(host);
                        title.push(']');
                    }
                }
            }
        }
        title
    }
}

fn is_thinking_window(title: &str) -> bool {
    let lower = title.to_ascii_lowercase();
    if lower.contains("youtube")
        || lower.contains("steam")
        || lower.contains("the sims")
        || lower.contains("lock screen")
        || lower.contains("task view")
        || lower.contains("clipchamp")
        || lower.contains("notification")
    {
        return false;
    }

    lower.contains("google chrome")
        || lower.contains("microsoft edge")
        || lower.contains("mozilla firefox")
        || lower.contains("visual studio code")
        || lower.contains("vs code")
        || lower.contains("codex")
        || lower.contains("chatgpt")
        || lower.contains("claude")
        || lower.contains("gemini")
        || lower.contains("perplexity")
        || lower.contains("copilot")
        || lower.contains("powershell")
        || lower.contains("windows terminal")
        || lower.contains("obsidian")
        || lower.contains("word")
        || lower.contains("powerpoint")
        || lower.contains("excel")
        || lower.contains("ubuntu")
}

fn is_ai_window(title: &str) -> bool {
    let lower = title.to_ascii_lowercase();
    lower.contains("chatgpt")
        || lower.contains("claude")
        || lower.contains("codex")
        || lower.contains("gemini")
        || lower.contains("perplexity")
        || lower.contains("copilot")
        || lower.contains("[web-ai:")
}

fn log_path() -> PathBuf {
    let now = Local::now();
    let days_since_monday = now.weekday().num_days_from_monday();
    let monday = now.date_naive() - ChronoDuration::days(days_since_monday as i64);
    let filename = format!("activity_{}.jsonl", monday.format("%Y-%m-%d"));
    project_root().join("logs").join(filename)
}

fn current_exe_path() -> Result<String, String> {
    std::env::current_exe()
        .map_err(|e| e.to_string())
        .map(|path| path.to_string_lossy().to_string())
}

fn install_startup() -> Result<(), String> {
    let exe = current_exe_path()?;
    let status = std::process::Command::new("reg")
        .args([
            "add",
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
            "/v",
            "dev-pace",
            "/t",
            "REG_SZ",
            "/d",
            &format!("\"{}\"", exe),
            "/f",
        ])
        .status()
        .map_err(|e| e.to_string())?;

    if status.success() {
        Ok(())
    } else {
        Err(format!("reg add failed: {}", status))
    }
}

fn remove_startup() -> Result<(), String> {
    let status = std::process::Command::new("reg")
        .args([
            "delete",
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
            "/v",
            "dev-pace",
            "/f",
        ])
        .status()
        .map_err(|e| e.to_string())?;

    if status.success() {
        Ok(())
    } else {
        Err(format!("reg delete failed: {}", status))
    }
}

fn refresh_dashboard() {
    let output = std::env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(|p| p.to_path_buf()))
        .map(|dir| dir.join("outputs").join("activity_dashboard.html"))
        .unwrap_or_else(|| project_root().join("outputs").join("activity_dashboard.html"));

    let python = if std::process::Command::new("pythonw").arg("--version").output().is_ok() {
        "pythonw"
    } else {
        "python"
    };

    let script = dashboard_script_path();
    let _ = std::process::Command::new(python)
        .args([script.to_string_lossy().as_ref(), "--output", output.to_string_lossy().as_ref()])
        .spawn();
}

fn run_recorder() {
    let automation = unsafe {
        let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
        CoCreateInstance::<_, IUIAutomation>(&CUIAutomation, None, CLSCTX_INPROC_SERVER).ok()
    };

    let last_op_time = Arc::new(Mutex::new(Instant::now()));
    let last_op_time_clone = Arc::clone(&last_op_time);
    thread::spawn(move || {
        listen(move |_| {
            *last_op_time_clone.lock().unwrap() = Instant::now();
        })
        .expect("Failed to start listener");
    });

    loop {
        let mut window_map: HashMap<String, u32> = HashMap::new();
        for _ in 0..60 {
            let win = get_active_window_title(automation.as_ref());
            *window_map.entry(win).or_insert(0) += 1;
            thread::sleep(Duration::from_secs(1));
        }

        let main_window = window_map
            .iter()
            .max_by_key(|&(_, count)| count)
            .map(|(name, _)| name.clone())
            .unwrap_or_else(|| "Unknown".to_string());

        let elapsed = last_op_time.lock().unwrap().elapsed().as_secs();
        let state = if elapsed >= 1200 {
            "Away"
        } else if elapsed < 60 && is_ai_window(&main_window) {
            "AIConversation"
        } else if elapsed < 60 {
            "Active"
        } else if is_thinking_window(&main_window) {
            "DeepThinking"
        } else {
            "Idle"
        };

        let log = ActivityLog {
            schema_version: LOG_SCHEMA_VERSION,
            timestamp: Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
            main_window,
            distribution: window_map,
            state: state.to_string(),
        };

        let path = log_path();
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
            if let Ok(json) = serde_json::to_string(&log) {
                let _ = writeln!(file, "{}", json);
                refresh_dashboard();
            }
        }
    }
}

fn show_stats() {
    let filename = log_path();
    let file = File::open(&filename).expect("log file not found");
    let reader = BufReader::new(file);

    let mut window_times: HashMap<String, u32> = HashMap::new();

    for line in reader.lines() {
        if let Ok(json) = line {
            if let Ok(log) = serde_json::from_str::<ActivityLog>(&json) {
                for (win, time) in log.distribution {
                    *window_times.entry(win).or_insert(0) += time;
                }
            }
        }
    }

    println!("Activity summary ({})", filename.display());
    println!("Top 10 windows:");
    let mut sorted: Vec<_> = window_times.into_iter().collect();
    sorted.sort_by(|a, b| b.1.cmp(&a.1));
    for (win, time) in sorted.iter().take(10) {
        println!("  {:>30}: {:>5}", win, time);
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("stats") => show_stats(),
        Some("--install-startup") => {
            install_startup().expect("failed to register startup");
            println!("Startup registration complete");
        }
        Some("--remove-startup") => {
            remove_startup().expect("failed to remove startup registration");
            println!("Startup registration removed");
        }
        _ => run_recorder(),
    }
}
