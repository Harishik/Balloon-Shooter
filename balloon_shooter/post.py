"""Post-processing: bloom, colour grading, vignette and full-screen flashes."""

from direct.filter.FilterManager import FilterManager
from panda3d.core import Texture, Vec2, Vec4

from . import shaders as S


class PostFX:
    def __init__(self, base, bloom=True):
        self.base = base
        self.enabled = False
        self.bloom_strength = 0.55
        self.saturation = 1.12
        self.vignette = 0.45
        self.chroma = 0.0
        self.tint = Vec4(0.6, 0.9, 1.2, 0.0)
        self.flash = Vec4(1, 1, 1, 0)
        self._flash_decay = 4.0
        self.manager = None
        self.final = None
        try:
            self._setup(bloom)
            self.enabled = True
        except Exception as exc:     # old GPUs: fall back to plain rendering
            print(f"[postfx] disabled: {exc}")
            self.teardown()

    def _setup(self, bloom):
        self.manager = FilterManager(self.base.win, self.base.cam)
        scene = Texture("scene")
        self.final = self.manager.renderSceneInto(colortex=scene)
        if self.final is None:
            raise RuntimeError("offscreen buffers unsupported")
        bloom_tex = Texture("bloom-b")
        if bloom:
            bright = Texture("bright")
            blur_a = Texture("bloom-a")
            q_bright = self.manager.renderQuadInto(colortex=bright, div=4)
            q_bright.setShader(S.make(S.POST_VERT, S.BRIGHT_FRAG))
            q_bright.setShaderInput("u_src", scene)
            q_h = self.manager.renderQuadInto(colortex=blur_a, div=4)
            q_h.setShader(S.make(S.POST_VERT, S.BLUR_FRAG))
            q_h.setShaderInput("u_src", bright)
            q_h.setShaderInput("u_dir", Vec2(4.0 / self.base.win.getXSize(), 0))
            q_v = self.manager.renderQuadInto(colortex=bloom_tex, div=4)
            q_v.setShader(S.make(S.POST_VERT, S.BLUR_FRAG))
            q_v.setShaderInput("u_src", blur_a)
            q_v.setShaderInput("u_dir", Vec2(0, 4.0 / self.base.win.getYSize()))
            self._blur = (q_h, q_v)
        else:
            self.bloom_strength = 0.0
            bloom_tex = scene
            self._blur = ()
        self.final.setShader(S.make(S.POST_VERT, S.COMPOSITE_FRAG))
        self.final.setShaderInput("u_scene", scene)
        self.final.setShaderInput("u_bloom", bloom_tex)
        self._push()

    def teardown(self):
        if self.manager:
            try:
                self.manager.cleanup()
            except Exception:
                pass
        self.manager = None
        self.final = None
        self.enabled = False

    def on_resize(self):
        if self.enabled and self._blur:
            q_h, q_v = self._blur
            q_h.setShaderInput("u_dir", Vec2(4.0 / max(1, self.base.win.getXSize()), 0))
            q_v.setShaderInput("u_dir", Vec2(0, 4.0 / max(1, self.base.win.getYSize())))

    def flash_screen(self, color=(1, 1, 1), amount=0.6, decay=4.0):
        self.flash = Vec4(*color, amount)
        self._flash_decay = decay

    def _push(self):
        if not self.final:
            return
        self.final.setShaderInput("u_grade", Vec4(self.bloom_strength, self.saturation, self.vignette, self.chroma))
        self.final.setShaderInput("u_tintcol", self.tint)
        self.final.setShaderInput("u_flashcol", self.flash)

    def update(self, dt, slowmo=False):
        target = 0.55 if slowmo else 0.0
        self.tint.w += (target - self.tint.w) * min(1.0, dt * 6)
        self.flash.w = max(0.0, self.flash.w - dt * self._flash_decay)
        self.chroma = max(0.0, self.chroma - dt * 0.05)
        self._push()
