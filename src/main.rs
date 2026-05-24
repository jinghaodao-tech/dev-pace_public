#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use chrono::{Datelike, Local, Duration as ChronoDuration};
use rdev::listen;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

#[derive(Serialize, Deserialize, Debug)]
struct ActivityLog {
    timestamp: String,
    main_window: String,
    distribution: HashMap<String, u32>,
    state: String,
    ops: u32,
}

fn get_active_window_title() -> String {
    use windows::Win32::UI::WindowsAndMessaging::*;
    unsafe {
        let hwnd = GetForegroundWindow();
        let length = GetWindowTextLengthW(hwnd) + 1;
        let mut buffer = vec![0u16; length as usize];
        GetWindowTextW(hwnd, &mut buffer);
        String::from_utf16_lossy(&buffer).trim_matches(char::from(0)).to_string()
    }
}

fn get_filename() -> String {
    let now = Local::now();
    let days_since_monday = now.weekday().num_days_from_monday();
    let monday = now.date_naive() - ChronoDuration::days(days_since_monday as i64);
    format!("activity_{}.jsonl", monday.format("%Y-%m-%d"))
}

fn run_recorder() {
    let last_op_time = Arc::new(Mutex::new(Instant::now()));
    let ops_count = Arc::new(Mutex::new(0));

    let ops_count_clone = Arc::clone(&ops_count);
    let last_op_time_clone = Arc::clone(&last_op_time);
    thread::spawn(move || {
        listen(move |_| {
            *ops_count_clone.lock().unwrap() += 1;
            *last_op_time_clone.lock().unwrap() = Instant::now();
        }).expect("Failed to start listener");
    });

    loop {
        let mut window_map: HashMap<String, u32> = HashMap::new();
        for _ in 0..60 {
            let win = get_active_window_title();
            *window_map.entry(win).or_insert(0) += 1;
            thread::sleep(Duration::from_secs(1));
        }

        let ops = {
            let mut count = ops_count.lock().unwrap();
            let val = *count;
            *count = 0;
            val
        };

        let elapsed = last_op_time.lock().unwrap().elapsed().as_secs();
        let state = if elapsed < 60 { "Active" } else if elapsed < 1200 { "DeepThinking" } else { "Away" };
        let main_window = window_map.iter().max_by_key(|&(_, count)| count).map(|(name, _)| name.clone()).unwrap_or_else(|| "Unknown".to_string());

        let log = ActivityLog {
            timestamp: Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
            main_window,
            distribution: window_map,
            state: state.to_string(),
            ops,
        };

        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(get_filename()) {
            if let Ok(json) = serde_json::to_string(&log) {
                let _ = writeln!(file, "{}", json);
            }
        }
    }
}

fn show_stats() {
    let filename = get_filename();
    let file = File::open(&filename).expect("まだ今週のログがありません");
    let reader = BufReader::new(file);

    let mut total_ops = 0;
    let mut window_times: HashMap<String, u32> = HashMap::new();

    for line in reader.lines() {
        if let Ok(json) = line {
            if let Ok(log) = serde_json::from_str::<ActivityLog>(&json) {
                total_ops += log.ops;
                for (win, time) in log.distribution {
                    *window_times.entry(win).or_insert(0) += time;
                }
            }
        }
    }

    println!("--- 今週の作業統計 ({}) ---", filename);
    println!("総操作回数(Ops): {}", total_ops);
    println!("各アプリの利用時間 (Top 10):");
    let mut sorted: Vec<_> = window_times.into_iter().collect();
    sorted.sort_by(|a, b| b.1.cmp(&a.1));
    for (win, time) in sorted.iter().take(10) {
        println!("  {:>30}: {:>5}秒", win, time);
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() > 1 && args[1] == "stats" {
        show_stats();
    } else {
        run_recorder();
    }
}