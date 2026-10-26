"""Game: ties the world, balloons, effects, HUD and menus together."""

import math
import os
import random

from direct.showbase.ShowBase import ShowBase
from panda3d.core import ClockObject, Point2, Point3, Vec3, WindowProperties

from . import config as C
from .audio import Audio
from .balloons import BalloonField
from .effects import Blaster, Effects
from .hud import HUD
from .menus import HowToScreen, ModeSelect, PauseScreen, ResultsScreen, SettingsScreen, TitleScreen
from .post import PostFX
from .rules import Session
from .ui import GOLD, INK, Kit
from .world import World

AIM_KEYS = {"arrow_left": (-1, 0), "arrow_right": (1, 0), "arrow_up": (0, 1), "arrow_down": (0, -1),
            "a": (-1, 0), "d": (1, 0), "w": (0, 1), "s": (0, -1)}
AIM_SPEED = 1.3          # film units per second for keyboard aiming
MENU_NAV = {"arrow_up": -1, "arrow_down": 1, "arrow_left": -1, "arrow_right": 1}


class Game(ShowBase):
    def __init__(self, args):
        ShowBase.__init__(self)
        self.args = args
        self.store = args.store
        self.settings = self.store.settings
        self.disableMouse()
        self.camLens.setMinFov(C.FOV_VERTICAL)
        self.camLens.setNearFar(0.05, 5000)
        self.camera.setPos(0, 0, 0)

        self.audio = Audio(self, self.settings)
        self.kit = Kit(self, self.audio)
        self.world = World(self, self.settings.quality)
        self.field = BalloonField(self, seed=args.seed)
        self.effects = Effects(self, self.kit.font_bold)
        self.blaster = Blaster(self, self.camera)
        self.hud = HUD(self, self.kit)
        self.post = PostFX(self, bloom=self.settings.quality == "high")

        self.state = "title"
        self.screen = None
        self.session = None
        self.aim = [0.0, 0.0]
        self.trigger = False
        self.cooldown = 0.0
        self.shake = 0.0
        self.countdown = 0.0
        self.end_timer = 0.0
        self.ambient_clock = 0.0
        self.last_beep = None
        self.cam_h = 0.0
        self.cam_p = 0.0
        self.time = 0.0
        self.keys_down = set()
        self.hover_kind = None
        self._shots = sorted(self._parse_shots(args.screenshot))
        self._script = self._parse_script(args.script)

        self._bind_input()
        self.apply_settings()
        self.taskMgr.add(self._loop, "game-loop")
        self.accept("window-event", self._on_window)
        self._populate_ambient(10)

        if args.mode:
            self.start_game(args.mode, args.difficulty or self.settings.difficulty)
        else:
            self.show_title()

    # -- setup helpers ---------------------------------------------------------------
    @staticmethod
    def _parse_shots(items):
        out = []
        for item in items:
            t, _, path = item.partition(":")
            out.append((float(t), path))
        return out

    @staticmethod
    def _parse_script(text):
        steps = []
        for part in filter(None, (p.strip() for p in text.split(","))):
            t, _, action = part.partition(":")
            steps.append((float(t), action))
        return sorted(steps)

    def _bind_input(self):
        self.accept("mouse1", self._trigger_down)
        self.accept("mouse1-up", self._trigger_up)
        self.accept("space", self._space_down)
        self.accept("space-up", self._trigger_up)
        self.accept("escape", self._on_escape)
        self.accept("p", self._on_pause_key)
        self.accept("m", self.audio.toggle_mute)
        self.accept("f11", self._toggle_fullscreen)
        self.accept("enter", self._on_enter)
        self.accept("tab", self._menu_nav, [1])
        self.accept("shift-tab", self._menu_nav, [-1])
        for key in AIM_KEYS:
            self.accept(key, self._key_down, [key])
            self.accept(key + "-up", self.keys_down.discard, [key])
        for key in MENU_NAV:
            self.accept(key + "-repeat", self._menu_nav, [MENU_NAV[key]])

    def apply_settings(self):
        self.setFrameRateMeter(self.settings.show_fps)
        self.audio.refresh()
        wp = self.win.getProperties() if self.win else None
        if wp is not None and wp.getFullscreen() != self.settings.fullscreen and not self.args.windowed:
            self._set_fullscreen(self.settings.fullscreen)

    def _set_fullscreen(self, on):
        props = WindowProperties()
        props.setFullscreen(on)
        if on and self.pipe:
            props.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        elif not on:
            props.setSize(*self.args.size)
        self.win.requestProperties(props)

    def _toggle_fullscreen(self):
        self.settings.fullscreen = not self.settings.fullscreen
        self._set_fullscreen(self.settings.fullscreen)
        self.store.save()

    def _on_window(self, win):
        self.windowEvent(win)
        if self.post:
            self.post.on_resize()

    def _set_cursor(self, hidden):
        props = WindowProperties()
        props.setCursorHidden(hidden)
        self.win.requestProperties(props)

    # -- screens ---------------------------------------------------------------------
    def _swap(self, screen):
        if self.screen:
            self.screen.destroy()
        self.screen = screen

    def show_title(self):
        self.state = "title"
        self._menu_mode()
        self._swap(TitleScreen(self))

    def show_mode_select(self):
        self.state = "modes"
        self._swap(ModeSelect(self))

    def show_how_to(self):
        self.state = "howto"
        self._swap(HowToScreen(self))

    def show_settings(self):
        self.state = "settings"
        self._swap(SettingsScreen(self, self.show_title))

    def show_pause_settings(self):
        self._swap(SettingsScreen(self, self._back_to_pause, dim=0.55))

    def _back_to_pause(self):
        self._swap(PauseScreen(self))

    def _menu_mode(self):
        self.session = None
        self.hud.hide()
        self._set_cursor(False)
        self.world.set_sky("day")
        self.audio.play_music("music_carnival")
        self.audio.set_music_rate(1.0)

    def quit(self):
        self.store.save()
        self.userExit()

    # -- game flow -------------------------------------------------------------------
    def start_game(self, mode_key, difficulty_key):
        self._swap(None)
        self.store.settings.difficulty = difficulty_key
        self.store.settings.last_mode = mode_key
        self.store.save()
        self.session = Session(mode_key, difficulty_key, seed=self.args.seed)
        self.field.clear()
        self.effects.clear()
        mode = self.session.mode
        self.world.set_sky(mode.sky)
        self.audio.play_music("music_zen" if mode_key == "zen" else "music_carnival")
        self.audio.set_music_rate(1.0)
        self.hud.setup(self.session, self.store.profile.best_for(mode_key, difficulty_key))
        self.hud.show()
        self._set_cursor(True)
        self.state = "countdown"
        self.countdown = 3.0
        self.last_beep = None
        self.end_timer = 0.0
        self.trigger = False
        self._populate_ambient(4, kinds=("classic",))

    def restart_run(self):
        if self.session:
            self.start_game(self.session.mode.key, self.session.difficulty.key)

    def pause_game(self):
        if self.state in ("playing", "countdown"):
            self._paused_from = self.state
            self.state = "paused"
            self.trigger = False
            self._set_cursor(False)
            self.hud.crosshair.show(False)
            self.audio.set_music_rate(1.0)
            self._swap(PauseScreen(self))

    def resume(self):
        if self.state == "paused":
            self._swap(None)
            self.state = getattr(self, "_paused_from", "playing")
            self._set_cursor(True)
            self.hud.crosshair.show(True)
            if self.session and self.session.slowmo_left > 0:
                self.audio.set_music_rate(0.8)

    def quit_to_menu(self):
        if self.session and self.state == "paused" and self.session.mode.key == "zen" and self.session.popped:
            # ending a Zen session still shows your results
            self._swap(None)
            self.state = "playing"
            self._handle_events(self.session.quit(), Point3(0, 20, 0))
            return
        self.field.clear()
        self.effects.clear()
        self._populate_ambient(10)
        self.show_title()

    def _end_game(self):
        session = self.session
        new_best = self.store.profile.record(session)
        best = self.store.profile.best_for(session.mode.key, session.difficulty.key)
        self.store.save()
        self.state = "results"
        self.trigger = False
        self.hud.hide()
        self._set_cursor(False)
        self.audio.set_music_rate(1.0)
        self.audio.play("newbest" if new_best else "gameover")
        self._swap(ResultsScreen(self, session, new_best, best))

    # -- input --------------------------------------------------------------------------
    def _trigger_down(self):
        self.trigger = True
        if self.state in ("playing",):
            self._fire()
        elif self.state in ("title", "modes", "howto", "settings", "results"):
            self._menu_pop()

    def _trigger_up(self):
        self.trigger = False

    def _space_down(self):
        if self.state in ("playing", "countdown"):
            self._trigger_down()
        else:
            self._on_enter()

    def _key_down(self, key):
        self.keys_down.add(key)
        if key in MENU_NAV:
            self._menu_nav(MENU_NAV[key])

    def _on_escape(self):
        if self.state in ("playing", "countdown"):
            self.pause_game()
        elif self.screen:
            self.screen.back()

    def _on_pause_key(self):
        if self.state in ("playing", "countdown"):
            self.pause_game()
        elif self.state == "paused":
            self.resume()

    def _on_enter(self):
        if self.screen:
            self.screen.activate()

    def _menu_nav(self, delta):
        if self.screen and self.state not in ("playing", "countdown"):
            self.screen.nav(delta)

    def _update_aim(self, dt):
        moved = False
        dx = sum(AIM_KEYS[k][0] for k in self.keys_down)
        dy = sum(AIM_KEYS[k][1] for k in self.keys_down)
        playing = self.state in ("playing", "countdown")
        if self.args.autoplay and playing:
            self._bot(dt)
            moved = True
        elif (dx or dy) and playing:
            self.aim[0] = max(-1.0, min(1.0, self.aim[0] + dx * AIM_SPEED * dt))
            self.aim[1] = max(-1.0, min(1.0, self.aim[1] + dy * AIM_SPEED * dt))
            moved = True
            if self.win:
                w, h = self.win.getXSize(), self.win.getYSize()
                self.win.movePointer(0, int((self.aim[0] + 1) * w / 2), int((1 - self.aim[1]) * h / 2))
        elif self.mouseWatcherNode.hasMouse():
            m = self.mouseWatcherNode.getMouse()
            self.aim[0], self.aim[1] = m.getX(), m.getY()
        return moved

    def _bot(self, dt):
        """Demo/test bot: tracks the most valuable balloon it can see."""
        best, best_score = None, -1e9
        for b in self.field.balloons:
            if b.key == "bomb" or not b.alive:
                continue
            film = self._project(b.node.getPos(self.render))
            if film is None or abs(film[0]) > 0.95 or film[1] < -0.6 or film[1] > 0.9:
                continue
            value = b.kind.points + (40 if b.key in ("frost", "nova", "clock") else 0)
            d = math.hypot(film[0] - self.aim[0], film[1] - self.aim[1])
            score = value - d * 60
            if score > best_score:
                best, best_score = film, score
        if best:
            k = min(1.0, dt * 9)
            self.aim[0] += (best[0] - self.aim[0]) * k
            self.aim[1] += (best[1] - self.aim[1]) * k
            if math.hypot(best[0] - self.aim[0], best[1] - self.aim[1]) < 0.04 and self.state == "playing":
                self.trigger = True
                return
        self.trigger = False

    def _project(self, world_pos):
        p = self.cam.getRelativePoint(self.render, world_pos)
        out = Point2()
        if self.camLens.project(p, out):
            return (out.x, out.y)
        return None

    # -- shooting ---------------------------------------------------------------------
    def _fire(self, auto=False):
        if self.cooldown > 0 or not self.session or self.session.over:
            return
        self.cooldown = C.AUTO_FIRE_COOLDOWN if auto else C.FIRE_COOLDOWN
        self.blaster.fire()
        self.hud.crosshair.fire()
        self.audio.play("shoot", 0.55, random.uniform(0.95, 1.08))
        assist = self.session.difficulty.aim_assist
        balloon, point = self.field.pick(tuple(self.aim), assist)
        muzzle = self.blaster.muzzle_world()
        events = self.session.register_shot(balloon is not None)
        if balloon is None:
            origin, d = self.field.ray_from_screen(tuple(self.aim))
            self.effects.tracer(muzzle, origin + d * 60)
            self._handle_events(events, origin + d * 30)
            return
        self.effects.tracer(muzzle, point)
        self.hud.crosshair.hit_marker(bad=balloon.key == "bomb")
        if balloon.damage():
            self._pop(balloon)
        else:
            pts = self.session.chip()
            self.audio.play("clank", 0.8, random.uniform(0.9, 1.1))
            self.effects.popup(point, f"+{pts}", (0.85, 0.9, 1, 1), 0.7)
            self.effects.sparkle_trail(point, (1, 1, 0.8))
        self._handle_events(events, point)

    def _pop(self, balloon, by_blast=False):
        pos = balloon.node.getPos(self.render)
        key = balloon.key
        big = key in ("gold", "nova", "bomb")
        self.field.remove(balloon)
        self.effects.pop(pos, balloon.color, size=balloon.radius, big=big)
        if key == "bomb" and not by_blast:
            self.audio.play("bomb")
        else:
            self.audio.pop(big)
        if not self.session:
            return
        result = self.session.pop(key, by_blast)
        if result.points > 0:
            col = GOLD if key == "gold" else INK
            text = f"+{result.points}"
            if result.multiplier > 1:
                text += f"  x{result.multiplier}"
            self.effects.popup(pos, text, col, 1.2 if big else 1.0)
            self.hud.punch_score()
            self.audio.play("blip", 0.35, 1.0 + min(self.session.chain, 30) * 0.035)
        if result.callout:
            self.hud.big(result.callout)
        self._handle_events(result.events, pos)

    def _handle_events(self, events, pos):
        for ev in events:
            kind = ev[0]
            if kind == "bomb":
                self._shake(1.0)
                self._flash((1, 0.25, 0.15), 0.55)
                if self.post.enabled:
                    self.post.chroma = 0.012
                self.hud.big("BOOM!", (1, 0.35, 0.3, 1), 0.9)
                if self.session.timed:
                    self.effects.popup(pos, "-5s", (1, 0.4, 0.35, 1), 1.3)
            elif kind == "nova":
                self.audio.play("nova")
                self.effects.shockwave(pos, (0.9, 0.5, 1.0), C.NOVA_RADIUS)
                self._shake(0.35)
                caught = self.field.in_radius(pos, C.NOVA_RADIUS)
                for b in caught:
                    self._pop(b, by_blast=True)
                if caught:
                    self.hud.small(f"NOVA BLAST  x{len(caught) + 1}", (0.95, 0.7, 1, 1))
            elif kind == "slowmo":
                self.audio.play("freeze")
                self.hud.small("SLOW-MO!", (0.7, 0.95, 1, 1))
                self.audio.set_music_rate(0.8)
                self._flash((0.6, 0.9, 1.0), 0.3)
            elif kind == "slowmo_end":
                self.audio.set_music_rate(1.0)
            elif kind == "time_bonus":
                self.audio.play("bonus")
                self.hud.small(f"+{int(ev[1])} SECONDS", (0.45, 1, 0.6, 1))
            elif kind == "time_penalty":
                pass
            elif kind == "life_gained":
                self.audio.play("bonus")
                self.hud.small("+1 LIFE", (1, 0.5, 0.6, 1))
            elif kind == "life_lost":
                self.audio.play("lose", 0.8)
                self._flash((1, 0.2, 0.2), 0.25)
                self._shake(0.25)
            elif kind == "gold":
                self.audio.play("gold")
                self._shake(0.15)
            elif kind == "multiplier":
                self.audio.play("powerup", 0.6, 0.9 + ev[1] * 0.08)
                self.hud.big(f"x{ev[1]} COMBO!", GOLD, 0.9)
            elif kind == "combo_lost":
                self.hud.small("Combo lost", (0.8, 0.8, 0.9, 1), 0.9)
            elif kind == "defused":
                self.effects.popup(pos, "Defused!", (0.7, 1, 0.7, 1), 0.9)
            elif kind == "game_over":
                self.state = "ending"
                self.end_timer = 1.6
                self.trigger = False
                heading = {"time": "TIME'S UP!", "survival": "GAME OVER", "zen": "WELL PLAYED!"}
                self.hud.big(heading[self.session.mode.key], INK, 1.6)

    def _shake(self, amount):
        if self.settings.screen_shake:
            self.shake = min(1.5, self.shake + amount)

    def _flash(self, color, amount):
        if self.post.enabled:
            self.post.flash_screen(color, amount)
        else:
            self.hud.flash(color, amount)

    # -- ambient / menu background ------------------------------------------------------
    def _populate_ambient(self, count, kinds=None):
        for _ in range(count):
            key = random.choice(kinds or ("classic", "classic", "classic", "swift", "gold", "frost", "nova"))
            self.field.spawn(key, 0.6, start_visible=True)

    def _menu_pop(self):
        """Balloons in the menu background can be popped just for fun."""
        balloon, point = self.field.pick(tuple(self.aim), 1.0)
        if balloon:
            self._pop(balloon)

    # -- main loop ---------------------------------------------------------------------
    def _loop(self, task):
        dt = min(ClockObject.getGlobalClock().getDt(), 1 / 20)
        self.time += dt
        self._run_automation()
        self._update_aim(dt)
        state = self.state
        world_dt = dt

        if state == "countdown":
            prev = self.countdown
            self.countdown -= dt
            beep = math.ceil(self.countdown)
            if beep != math.ceil(prev) or self.last_beep is None:
                if beep > 0:
                    self.hud.big(str(beep), INK, 0.9)
                    self.audio.play("count")
                self.last_beep = beep
            if self.countdown <= 0:
                self.state = "playing"
                self.hud.big("GO!", GOLD, 0.8)
                self.audio.play("go")
        elif state == "playing":
            s = self.session
            self._handle_events(s.update(dt), Point3(0, 20, 0))
            world_dt = dt * s.time_scale
            if s.timed and 0 < s.time_left <= 5:
                sec = math.ceil(s.time_left)
                if sec != self.last_beep:
                    self.last_beep = sec
                    self.audio.play("count", 0.6)
            for _ in range(s.due_spawns(world_dt)):
                self.field.spawn(s.pick_kind(), s.speed_scale(), s.difficulty.size)
            self.cooldown -= dt
            if self.trigger and self.cooldown <= 0:
                self._fire(auto=True)
        elif state == "ending":
            world_dt = dt * 0.35
            self.end_timer -= dt
            if self.end_timer <= 0:
                self._end_game()
        elif state in ("title", "modes", "howto", "settings", "results"):
            self.ambient_clock -= dt
            if self.ambient_clock <= 0:
                self.ambient_clock = random.uniform(0.6, 1.2)
                self._populate_ambient(1)

        if state != "paused":
            escaped = self.field.update(world_dt)
            if self.session and state == "playing":
                for b in escaped:
                    ev = self.session.escape(b.key)
                    if ev:
                        self.audio.play("escape", 0.6)
                    self._handle_events(ev, b.last_pos)
            self.effects.update(world_dt)
            self.world.update(world_dt)
            # trailing sparkles for gold balloons
            for b in self.field.balloons:
                if b.key == "gold" and random.random() < 0.25:
                    self.effects.sparkle_trail(b.node.getPos() + Vec3(0, 0, -b.radius), (1, 0.85, 0.4))

        # hover feedback on the crosshair
        playing = state in ("playing", "countdown")
        if playing:
            hit, _ = self.field.pick(tuple(self.aim), self.session.difficulty.aim_assist)
            self.hud.crosshair.set_target(hit.key if hit else None)
        aspect = self.getAspectRatio()
        self.hud.crosshair.set_pos(self.aim[0] * aspect, self.aim[1])
        if self.session and state not in ("results",):
            self.hud.update(dt, self.session)

        self._update_camera(dt, playing)
        fov = self.camLens.getFov()
        tan_half = (math.tan(math.radians(fov[0] / 2)), math.tan(math.radians(fov[1] / 2)))
        self.blaster.update(dt, self.aim if playing else (-0.1, -0.1), tan_half)
        self.post.update(dt, slowmo=bool(self.session and self.session.slowmo_left > 0 and state == "playing"))
        if self.screen:
            self.screen.tick(dt)
        return task.cont

    def _update_camera(self, dt, playing):
        if playing:
            th, tp = -self.aim[0] * 3.5, 2.0 + self.aim[1] * 2.0
        else:
            th, tp = math.sin(self.time * 0.12) * 6.0, 4.0 + math.sin(self.time * 0.2) * 1.5
        k = min(1.0, dt * 3)
        self.cam_h += (th - self.cam_h) * k
        self.cam_p += (tp - self.cam_p) * k
        self.shake = max(0.0, self.shake - dt * 2.2)
        s = self.shake ** 2
        jx = (random.random() - 0.5) * s * 1.6
        jy = (random.random() - 0.5) * s * 1.6
        self.camera.setHpr(self.cam_h + jx, self.cam_p + jy, (random.random() - 0.5) * s * 2)

    # -- automation (screenshots / smoke tests) ------------------------------------
    def _run_automation(self):
        t = self.time
        while self._script and self._script[0][0] <= t:
            _, action = self._script.pop(0)
            self._script_action(action)
        while self._shots and self._shots[0][0] <= t:
            _, path = self._shots.pop(0)
            folder = os.path.dirname(path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            self.graphicsEngine.renderFrame()
            self.win.saveScreenshot(path)
            print(f"[shot] {path}")
        if self.args.quit_after and t >= self.args.quit_after:
            score = self.session.score if self.session else 0
            fps = ClockObject.getGlobalClock().getAverageFrameRate()
            print(f"[quit] after {t:.1f}s state={self.state} score={score} fps={fps:.0f}")
            self.userExit()

    def _script_action(self, action):
        name, _, arg = action.partition("=")
        if name == "title":
            self.show_title()
        elif name == "modes":
            self.show_mode_select()
        elif name == "howto":
            self.show_how_to()
        elif name == "settings":
            self.show_settings()
        elif name == "play":
            mode, _, diff = arg.partition("/")
            self.start_game(mode or "time", diff or "normal")
        elif name == "pause":
            self.pause_game()
        elif name == "resume":
            self.resume()
        elif name == "end":
            if self.session:
                self._handle_events(self.session.quit(), Point3(0, 20, 0))
        elif name == "aim":
            x, _, y = arg.partition("/")
            self.aim = [float(x), float(y)]
        elif name == "fire":
            self._trigger_down()
            self._trigger_up()
