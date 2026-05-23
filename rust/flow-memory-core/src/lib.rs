//! Optional Rust helpers for performance-critical Flow Memory math.

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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn computes_motion_energy() {
        let a = [0.0, 1.0, 0.0];
        let b = [0.0, 0.0, 1.0];
        assert!(motion_energy(&a, &b) > 0.0);
    }
}
