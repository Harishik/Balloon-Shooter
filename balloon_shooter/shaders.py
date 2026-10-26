"""GLSL shaders. Written against GLSL 1.20 so they run on every platform
Panda3D supports, including the legacy macOS OpenGL context."""

from panda3d.core import Shader

_COMMON_VERT = """
#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec4 p3d_Color;
varying vec3 v_world;
varying vec3 v_normal;
varying vec4 v_color;
varying vec3 v_obj;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_world = (p3d_ModelMatrix * p3d_Vertex).xyz;
    v_normal = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
    v_color = p3d_Color;
    v_obj = p3d_Vertex.xyz;
}
"""

_LIGHTING = """
uniform vec3 u_sun_dir;
uniform vec3 u_sun_col;
uniform vec3 u_ambient;
uniform vec3 u_horizon;
uniform vec3 u_zenith;
uniform vec3 u_cam;
uniform float u_fog;

vec3 hemi(vec3 n) {
    vec3 ground = u_ambient * vec3(0.55, 0.50, 0.45);
    return mix(ground, u_ambient, n.z * 0.5 + 0.5);
}
vec3 apply_fog(vec3 col, vec3 world) {
    float d = length(world - u_cam);
    float f = 1.0 - exp(-pow(d * u_fog, 1.6));
    vec3 dir = normalize(world - u_cam);
    float sun = pow(max(dot(dir, u_sun_dir), 0.0), 8.0);
    vec3 fogc = mix(u_horizon, u_sun_col, sun * 0.5);
    return mix(col, fogc, clamp(f, 0.0, 1.0));
}
"""

LIT_FRAG = """
#version 120
varying vec3 v_world;
varying vec3 v_normal;
varying vec4 v_color;
varying vec3 v_obj;
uniform vec4 u_tint;
""" + _LIGHTING + """
void main() {
    vec3 n = normalize(v_normal);
    float diff = max(dot(n, u_sun_dir), 0.0);
    float wrap = max((dot(n, u_sun_dir) + 0.35) / 1.35, 0.0);
    vec3 albedo = v_color.rgb * u_tint.rgb;
    vec3 col = albedo * (hemi(n) + u_sun_col * mix(diff, wrap, 0.4) * 0.95);
    gl_FragColor = vec4(apply_fog(col, v_world), v_color.a * u_tint.a);
}
"""

BALLOON_FRAG = """
#version 120
varying vec3 v_world;
varying vec3 v_normal;
varying vec4 v_color;
varying vec3 v_obj;
uniform vec4 u_color;       // rgb + alpha
uniform vec4 u_params;      // x glow, y metal, z flash, w pattern id
uniform vec4 u_band;        // band colour rgb + strength
uniform float u_time;
""" + _LIGHTING + """
float hash(vec3 p) { return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }

void main() {
    vec3 n = normalize(v_normal);
    vec3 v = normalize(u_cam - v_world);
    vec3 l = u_sun_dir;
    vec3 h = normalize(l + v);
    float glow = u_params.x;
    float metal = u_params.y;
    float flash = u_params.z;
    float pattern = u_params.w;

    vec3 base = u_color.rgb;
    vec3 emissive = vec3(0.0);

    // pattern 1: a glowing band around the middle (bomb fuse, clock, frost)
    if (pattern > 0.5 && pattern < 1.5) {
        float band = smoothstep(0.16, 0.08, abs(v_obj.z - 0.05));
        base = mix(base, u_band.rgb, band);
        emissive += u_band.rgb * band * u_band.a * (0.75 + 0.25 * sin(u_time * 8.0));
    }
    // pattern 2: swirling energy (nova)
    if (pattern > 1.5 && pattern < 2.5) {
        float a = atan(v_obj.y, v_obj.x);
        float s = sin(a * 3.0 + v_obj.z * 4.0 - u_time * 5.0) * 0.5 + 0.5;
        base = mix(base, u_band.rgb, s * 0.6);
        emissive += u_band.rgb * s * u_band.a;
    }
    // pattern 3: sparkles (gold)
    if (pattern > 2.5 && pattern < 3.5) {
        vec3 cell = floor(v_obj * 9.0);
        float sp = step(0.93, hash(cell + floor(u_time * 6.0)));
        emissive += u_band.rgb * sp * u_band.a;
    }
    // pattern 4: heart-pink stripes
    if (pattern > 3.5 && pattern < 4.5) {
        float st = step(0.5, fract((v_obj.z + atan(v_obj.y, v_obj.x) * 0.3) * 3.0));
        base = mix(base, u_band.rgb, st * 0.35);
    }

    float ndl = dot(n, l);
    float diff = max(ndl, 0.0);
    float wrap = max((ndl + 0.5) / 1.5, 0.0);
    float shin = mix(60.0, 140.0, metal);
    float spec = pow(max(dot(n, h), 0.0), shin) * mix(0.9, 1.6, metal);
    float fres = pow(1.0 - max(dot(n, v), 0.0), 3.0);
    // light shining through the rubber when the sun is behind it
    float trans = pow(max(dot(-v, l), 0.0), 3.0) * (1.0 - metal) * 0.6;

    vec3 sky = mix(u_horizon, u_zenith, n.z * 0.5 + 0.5);
    vec3 col = base * (hemi(n) * 0.9 + u_sun_col * mix(diff, wrap, 0.5));
    col = mix(col, base * sky * 1.2 + col * 0.3, metal * 0.6);
    col += base * trans * u_sun_col;
    col += u_sun_col * spec;
    col += sky * fres * mix(0.35, 0.7, metal);
    col += base * glow * (0.8 + 0.2 * sin(u_time * 6.0)) + emissive;
    col = mix(col, vec3(1.0), flash);

    gl_FragColor = vec4(apply_fog(col, v_world), u_color.a);
}
"""

SKY_FRAG = """
#version 120
varying vec3 v_world;
varying vec3 v_normal;
varying vec4 v_color;
varying vec3 v_obj;
uniform vec3 u_sun_dir;
uniform vec3 u_sun_col;
uniform vec3 u_horizon;
uniform vec3 u_zenith;
uniform vec3 u_cam;
uniform float u_stars;
uniform float u_time;

float hash(vec3 p) { return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }

void main() {
    vec3 d = normalize(v_obj);
    float up = clamp(d.z, -1.0, 1.0);
    float t = pow(clamp(up, 0.0, 1.0), 0.55);
    vec3 col = mix(u_horizon, u_zenith, t);
    col = mix(col, u_horizon * 0.85, clamp(-up * 3.0, 0.0, 1.0));
    float s = max(dot(d, u_sun_dir), 0.0);
    col += u_sun_col * (pow(s, 6.0) * 0.35 + pow(s, 64.0) * 0.6);
    col += u_sun_col * smoothstep(0.9993, 0.9997, s) * 2.0;
    if (u_stars > 0.0) {
        vec3 cell = floor(d * 260.0);
        float h = hash(cell);
        float twinkle = 0.6 + 0.4 * sin(u_time * 2.0 + h * 40.0);
        float star = step(0.9975, h) * twinkle * clamp(up * 3.0, 0.0, 1.0);
        col += vec3(star) * u_stars;
    }
    gl_FragColor = vec4(col, 1.0);
}
"""

# Unlit, vertex coloured and textured (particles, tracers, sprites).
SPRITE_VERT = """
#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
varying vec2 v_uv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_uv = p3d_MultiTexCoord0;
}
"""

SPRITE_FRAG = """
#version 120
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec4 u_tint;
varying vec2 v_uv;
void main() {
    gl_FragColor = texture2D(p3d_Texture0, v_uv) * u_tint * p3d_ColorScale;
}
"""

# --- post processing ---------------------------------------------------------------
POST_VERT = """
#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
varying vec2 v_uv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_uv = p3d_MultiTexCoord0;
}
"""

BRIGHT_FRAG = """
#version 120
uniform sampler2D u_src;
varying vec2 v_uv;
void main() {
    vec3 c = texture2D(u_src, v_uv).rgb;
    float l = dot(c, vec3(0.299, 0.587, 0.114));
    gl_FragColor = vec4(c * smoothstep(0.88, 1.15, l), 1.0);
}
"""

BLUR_FRAG = """
#version 120
uniform sampler2D u_src;
uniform vec2 u_dir;
varying vec2 v_uv;
void main() {
    vec3 c = texture2D(u_src, v_uv).rgb * 0.227;
    c += texture2D(u_src, v_uv + u_dir * 1.385).rgb * 0.316;
    c += texture2D(u_src, v_uv - u_dir * 1.385).rgb * 0.316;
    c += texture2D(u_src, v_uv + u_dir * 3.231).rgb * 0.070;
    c += texture2D(u_src, v_uv - u_dir * 3.231).rgb * 0.070;
    gl_FragColor = vec4(c, 1.0);
}
"""

COMPOSITE_FRAG = """
#version 120
uniform sampler2D u_scene;
uniform sampler2D u_bloom;
uniform vec4 u_grade;      // x bloom strength, y saturation, z vignette, w chromatic offset
uniform vec4 u_tintcol;    // rgb tint, a amount
uniform vec4 u_flashcol;   // rgb flash, a amount
varying vec2 v_uv;
void main() {
    vec2 off = (v_uv - 0.5) * u_grade.w;
    vec3 c;
    c.r = texture2D(u_scene, v_uv + off).r;
    c.g = texture2D(u_scene, v_uv).g;
    c.b = texture2D(u_scene, v_uv - off).b;
    c += texture2D(u_bloom, v_uv).rgb * u_grade.x;
    float l = dot(c, vec3(0.299, 0.587, 0.114));
    c = mix(vec3(l), c, u_grade.y);
    c = mix(c, c * u_tintcol.rgb + u_tintcol.rgb * 0.12, u_tintcol.a);
    float vig = smoothstep(0.35, 0.95, length(v_uv - 0.5) * 1.25);
    c *= 1.0 - vig * u_grade.z;
    c = mix(c, u_flashcol.rgb, u_flashcol.a);
    gl_FragColor = vec4(c, 1.0);
}
"""


def make(vert, frag):
    return Shader.make(Shader.SL_GLSL, vertex=vert, fragment=frag)


def lit():
    return make(_COMMON_VERT, LIT_FRAG)


def balloon():
    return make(_COMMON_VERT, BALLOON_FRAG)


def sky():
    return make(_COMMON_VERT, SKY_FRAG)


def sprite():
    return make(SPRITE_VERT, SPRITE_FRAG)
