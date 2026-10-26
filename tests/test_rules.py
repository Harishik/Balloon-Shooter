import pytest

from balloon_shooter import config as C
from balloon_shooter.rules import Session


def test_classic_pop_scores_base_points():
    s = Session("time", "normal", seed=1)
    r = s.pop("classic")
    assert r.points == 10
    assert s.score == 10
    assert s.popped == 1


def test_combo_multiplier_grows_every_step_and_caps():
    s = Session("time", "normal", seed=1)
    for _ in range(C.COMBO_STEP):
        s.pop("classic")
    assert s.multiplier == 2
    for _ in range(C.COMBO_STEP * 10):
        s.pop("classic")
    assert s.multiplier == C.COMBO_MAX_MULT


def test_multiplier_event_fires_when_level_rises():
    s = Session("time", "normal", seed=1)
    events = []
    for _ in range(C.COMBO_STEP):
        events += s.pop("classic").events
    assert ("multiplier", 2) in events


def test_armor_chip_scores_and_extends_combo():
    s = Session("time", "normal", seed=1)
    assert s.chip() == 5
    assert s.score == 5
    assert s.chain == 1


def test_streak_callout():
    s = Session("time", "normal", seed=1)
    callouts = [s.pop("classic").callout for _ in range(10)]
    assert callouts[-1] == C.STREAK_CALLOUTS[10]


def test_miss_breaks_combo_except_in_zen():
    s = Session("time", "normal", seed=1)
    for _ in range(6):
        s.pop("classic")
    s.register_shot(hit=False)
    assert s.chain == 0

    z = Session("zen", "normal", seed=1)
    for _ in range(6):
        z.pop("classic")
    z.register_shot(hit=False)
    assert z.chain == 6


def test_combo_expires_after_window():
    s = Session("zen", "normal", seed=1)
    s.pop("classic")
    s.update(C.COMBO_WINDOW + 0.01)
    assert s.chain == 0


def test_bomb_costs_time_and_combo_in_time_attack():
    s = Session("time", "normal", seed=1)
    for _ in range(7):
        s.pop("classic")
    before = s.time_left
    r = s.pop("bomb")
    assert s.chain == 0
    assert s.time_left == pytest.approx(before - 5.0)
    assert ("bomb",) in r.events


def test_bomb_never_takes_score_below_zero():
    s = Session("time", "normal", seed=1)
    s.pop("bomb")
    assert s.score == 0


def test_bomb_caught_in_blast_is_harmless():
    s = Session("survival", "normal", seed=1)
    lives = s.lives
    r = s.pop("bomb", by_blast=True)
    assert s.lives == lives
    assert ("defused",) in r.events


def test_survival_lives_and_game_over():
    s = Session("survival", "normal", seed=1)
    assert s.lives == C.MODES["survival"].lives
    s.pop("bomb")
    assert s.lives == C.MODES["survival"].lives - 2
    for _ in range(s.lives):
        s.escape("classic")
    assert s.over


def test_escaped_bomb_is_free():
    s = Session("survival", "normal", seed=1)
    s.escape("bomb")
    assert s.lives == C.MODES["survival"].lives
    assert s.escaped == 0


def test_heart_restores_a_life_up_to_max():
    s = Session("survival", "normal", seed=1)
    s.escape("classic")
    s.pop("heart")
    assert s.lives == C.MODES["survival"].lives
    s.pop("heart")
    assert s.lives == C.MODES["survival"].lives


def test_time_attack_ends_when_clock_runs_out():
    s = Session("time", "normal", seed=1)
    events = s.update(C.MODES["time"].duration + 1)
    assert s.over
    assert ("game_over",) in events
    assert s.pop("classic").points == 0     # no scoring after the end


def test_clock_adds_time_and_frost_starts_slowmo():
    s = Session("time", "normal", seed=1)
    before = s.time_left
    s.pop("clock")
    assert s.time_left == pytest.approx(before + C.CLOCK_BONUS)
    s.pop("frost")
    assert s.time_scale == C.SLOWMO_SCALE
    events = s.update(C.SLOWMO_DURATION + 0.1)
    assert ("slowmo_end",) in events
    assert s.time_scale == 1.0


def test_clock_only_spawns_when_time_is_running_low():
    s = Session("time", "normal", seed=1)
    assert "clock" not in s.kind_weights()
    s.time_left = C.CLOCK_MAX_TIME - 1
    assert "clock" in s.kind_weights()


def test_mode_specific_balloons():
    assert "bomb" not in Session("zen", "normal").kind_weights()
    assert "heart" not in Session("time", "normal").kind_weights()
    assert "clock" not in Session("survival", "normal").kind_weights()


def test_heart_only_spawns_when_hurt():
    s = Session("survival", "normal", seed=1)
    assert "heart" not in s.kind_weights()
    s.escape("classic")
    assert "heart" in s.kind_weights()


def test_difficulty_scales_pacing():
    easy = Session("time", "easy")
    hard = Session("time", "hard")
    assert easy.spawn_interval() > hard.spawn_interval()
    assert easy.speed_scale() < hard.speed_scale()


def test_intensity_ramps_up_over_time():
    s = Session("survival", "normal", seed=1)
    start = s.spawn_interval()
    s.update(120)
    assert s.spawn_interval() < start


def test_due_spawns_are_paced():
    s = Session("time", "normal", seed=3)
    total = sum(s.due_spawns(0.1) for _ in range(100))   # 10 seconds
    assert 8 <= total <= 30


def test_accuracy_and_medals():
    s = Session("time", "normal", seed=1)
    s.register_shot(True)
    s.register_shot(False)
    assert s.accuracy == 50.0
    assert s.medal() == -1
    s.score = C.MODES["time"].medals[1]
    assert s.medal() == 1


def test_pick_kind_is_deterministic_with_seed():
    a = Session("time", "normal", seed=42)
    b = Session("time", "normal", seed=42)
    assert [a.pick_kind() for _ in range(50)] == [b.pick_kind() for _ in range(50)]
