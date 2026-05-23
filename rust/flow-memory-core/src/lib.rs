//! Optional Rust helpers for performance-critical and preflight Flow Memory checks.

/// Mean absolute difference between two equal-length frame signatures.
pub fn motion_energy(previous: &[f32], current: &[f32]) -> f32 {
    let n = previous.len().min(current.len());
    if n == 0 {
        return 0.0;
    }
    let mut total = 0.0;
    for i in 0..n {
        total += (current[i] - previous[i]).abs();
    }
    total / n as f32
}

/// Minimal FlowIR manifest preflight check for future hardened runtime handoff.
///
/// This avoids a JSON dependency in the helper crate. It is not a full schema
/// validator; it catches the required markers before a richer Rust validator is
/// introduced.
pub fn flowir_preflight(manifest_json: &str) -> Result<(), &'static str> {
    if !manifest_json.contains("\"name\"") {
        return Err("missing agent name field");
    }
    if !manifest_json.contains("\"memory\"") {
        return Err("missing memory field");
    }
    if !manifest_json.contains("\"economy\"") {
        return Err("missing economy field");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn computes_motion_energy() {
        let a = [0.0, 1.0, 0.0];
        let b = [0.0, 0.0, 1.0];
        assert!(motion_energy(&a, &b) > 0.0);
    }

    #[test]
    fn preflights_flowir_manifest() {
        let manifest = r#"{"name":"agent","memory":{},"economy":{}}"#;
        assert!(flowir_preflight(manifest).is_ok());
        assert!(flowir_preflight("{}").is_err());
    }
}
