layout(location = 0) out vec4 fragColor;

uniform float uTime;
uniform vec4 uTelemetry0; // signal, learning_tick_count, agent_count, event_rate
uniform vec4 uTelemetry1; // memory_activation_count, risk, confidence, connected

float hash(float n) {
    return fract(sin(n) * 43758.5453123);
}

float signedHash(float n) {
    return hash(n) * 2.0 - 1.0;
}

vec2 bezier(vec2 a, vec2 b, vec2 c, vec2 d, float t) {
    float u = 1.0 - t;
    return u * u * u * a + 3.0 * u * u * t * b + 3.0 * u * t * t * c + t * t * t * d;
}

float signalLevel() {
    return clamp(uTelemetry0.x, 0.0, 1.0);
}

float learningLevel() {
    return clamp(uTelemetry0.y / 8.0, 0.0, 1.0);
}

float agentLevel() {
    return clamp(uTelemetry0.z / 12.0, 0.0, 1.0);
}

float eventLevel() {
    return clamp(uTelemetry0.w, 0.0, 1.0);
}

float memoryLevel() {
    return clamp(uTelemetry1.x / 16.0, 0.0, 1.0);
}

float riskLevel() {
    return clamp(uTelemetry1.y, 0.0, 1.0);
}

float confidenceLevel() {
    return clamp(uTelemetry1.z, 0.0, 1.0);
}

float connectedLevel() {
    return clamp(uTelemetry1.w, 0.0, 1.0);
}

vec3 strandColor(float t) {
    vec3 amber = mix(vec3(0.74, 0.50, 0.25), vec3(0.96, 0.34, 0.21), riskLevel());
    vec3 blue = mix(vec3(0.08, 0.28, 0.78), vec3(0.12, 0.50, 1.00), signalLevel());
    vec3 memory = mix(vec3(0.72, 0.82, 0.96), vec3(0.92, 0.98, 1.00), confidenceLevel());
    vec3 base = t < 0.5 ? mix(amber, blue, t * 2.0) : mix(blue, memory, (t - 0.5) * 2.0);
    return mix(base, vec3(0.92, 0.96, 1.0), learningLevel() * 0.16 + connectedLevel() * 0.10);
}

float segmentDistance(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a;
    vec2 ba = b - a;
    float h = clamp(dot(pa, ba) / max(dot(ba, ba), 0.00001), 0.0, 1.0);
    return length(pa - ba * h);
}

float glowLine(vec2 p, vec2 a, vec2 b, float width) {
    float d = segmentDistance(p, a, b);
    float core = smoothstep(width, 0.0, d);
    float aura = smoothstep(width * 9.0, 0.0, d) * 0.22;
    return core + aura;
}

void addStrand(inout vec3 color, inout float alpha, vec2 p, float id) {
    float lane = mod(id, 17.0) / 16.0;
    float side = signedHash(id * 4.13);
    vec2 a = vec2(-1.30, mix(-0.62, 0.62, lane));
    vec2 d = vec2(1.16, mix(-0.44, 0.44, fract(lane * 1.73 + hash(id))));
    vec2 b = vec2(-0.52 + signedHash(id * 1.7) * 0.12, a.y * 0.46 + side * 0.30);
    vec2 c = vec2(0.28 + signedHash(id * 2.1) * 0.18, d.y * 0.38 - side * 0.24);

    float width = mix(0.0022, 0.0064, hash(id * 8.1)) * (1.0 + signalLevel() * 0.75 + agentLevel() * 0.28);
    vec3 accum = vec3(0.0);
    float strand = 0.0;
    vec2 prev = bezier(a, b, c, d, 0.0);

    for (int i = 1; i <= 52; i++) {
        float t = float(i) / 52.0;
        vec2 cur = bezier(a, b, c, d, t);
        float g = glowLine(p, prev, cur, width);
        strand += g;
        accum += strandColor(t) * g;
        prev = cur;
    }

    float pulseT = fract(uTime * mix(0.030, 0.085, hash(id * 3.9)) * (1.0 + learningLevel() * 1.40 + eventLevel() * 0.90) + hash(id * 5.4));
    vec2 pulsePos = bezier(a, b, c, d, pulseT);
    float pulse = smoothstep(0.035 + signalLevel() * 0.018, 0.0, length(p - pulsePos));
    float weight = 0.28 + 0.50 * smoothstep(0.18, 0.0, abs(pulseT - 0.50));
    float liveBoost = 1.0 + signalLevel() * 0.75 + memoryLevel() * 0.35;

    color += accum * (0.09 + weight * 0.12) * liveBoost;
    color += strandColor(pulseT) * pulse * (0.85 + learningLevel() * 0.95);
    alpha += strand * 0.018 * liveBoost + pulse * (0.42 + signalLevel() * 0.36);
}

float knot(vec2 p, float id) {
    float r = 0.13 + id * 0.024;
    float a = atan(p.y, p.x);
    float l = length(p);
    float target = r + sin(a * (2.0 + id) + uTime * (0.18 + id * 0.03) * (1.0 + learningLevel())) * (0.038 + memoryLevel() * 0.018);
    return smoothstep(0.030, 0.0, abs(l - target));
}

void main() {
    vec2 resolution = uTDOutputInfo.res.zw;
    vec2 uv = vUV.st;
    vec2 p = uv * 2.0 - 1.0;
    p.x *= resolution.x / max(resolution.y, 1.0);

    vec3 color = mix(vec3(0.018, 0.028, 0.045), vec3(0.018, 0.040, 0.078), connectedLevel());
    float alpha = 1.0;

    float vignette = smoothstep(1.35, 0.15, length(p));
    color += vec3(0.015, 0.035, 0.070) * vignette * (1.0 + signalLevel() * 0.45);

    for (int i = 0; i < 42; i++) {
        addStrand(color, alpha, p, float(i) + 1.0);
    }

    vec3 knotColor = vec3(0.18, 0.48, 1.0);
    for (int i = 0; i < 7; i++) {
        float k = knot(p + vec2(signedHash(float(i) + 9.0) * 0.025, signedHash(float(i) + 14.0) * 0.020), float(i));
        color += mix(knotColor, vec3(0.92, 0.96, 1.0), float(i) / 7.0) * k * (0.42 + learningLevel() * 0.52);
        alpha += k * (0.18 + signalLevel() * 0.16);
    }

    for (int i = 0; i < 80; i++) {
        vec2 n = vec2(hash(float(i) * 8.17), hash(float(i) * 3.71));
        vec2 q = (n * 2.0 - 1.0) * vec2(1.55, 0.86);
        q.x += sin(uTime * (0.025 + eventLevel() * 0.055) + float(i)) * (0.018 + signalLevel() * 0.018);
        float dotGlow = smoothstep(0.010 + agentLevel() * 0.006, 0.0, length(p - q));
        color += mix(vec3(0.50, 0.68, 1.0), vec3(0.92, 0.96, 1.0), confidenceLevel()) * dotGlow * (0.18 + eventLevel() * 0.22);
    }

    color *= 0.86 + vignette * (0.32 + connectedLevel() * 0.10);
    color = pow(color, vec3(0.92));
    fragColor = TDOutputSwizzle(vec4(color, clamp(alpha, 0.0, 1.0)));
}
