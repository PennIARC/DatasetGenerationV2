#version 330 core

out vec4 f_color;
in vec2 v_text;

uniform sampler2D Texture;
uniform float time;
uniform float noise_strength;

// Simple pseudo-random function
float rand(vec2 co) {
    return fract(sin(dot(co.xy ,vec2(12.9898,78.233))) * 43758.5453);
}

void main() {
    vec2 uv = v_text;
    vec4 color = texture(Texture, uv);

    // 1. Noise / Grain
    float noise = rand(uv + time) * noise_strength;
    color.rgb += noise;

    // 2. Slight Chromatic Aberration
    float aberration = 0.002;
    color.r = texture(Texture, vec2(uv.x + aberration, uv.y)).r;
    color.b = texture(Texture, vec2(uv.x - aberration, uv.y)).b;

    // 3. Vignette
    float dist = distance(uv, vec2(0.5, 0.5));
    color.rgb *= (1.0 - dist * 0.4);

    // 4. Contrast
    color.rgb = (color.rgb - 0.5) * 1.1 + 0.5;

    f_color = color;
}