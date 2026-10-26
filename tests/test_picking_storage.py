import json

import pytest

from balloon_shooter.picking import closest_hit, ray_ellipsoid
from balloon_shooter.rules import Session
from balloon_shooter.storage import Store


def test_ray_hits_sphere_in_front():
    t = ray_ellipsoid((0, 0, 0), (0, 1, 0), (0, 10, 0), 1.0)
    assert t == pytest.approx(9.0)


def test_ray_misses_sphere_to_the_side():
    assert ray_ellipsoid((0, 0, 0), (0, 1, 0), (3, 10, 0), 1.0) is None


def test_ray_ignores_targets_behind():
    assert ray_ellipsoid((0, 0, 0), (0, 1, 0), (0, -10, 0), 1.0) is None


def test_stretch_makes_balloon_taller():
    # just above a unit sphere, but inside the stretched ellipsoid
    assert ray_ellipsoid((0, 0, 1.1), (0, 1, 0), (0, 10, 0), 1.0) is None
    assert ray_ellipsoid((0, 0, 1.1), (0, 1, 0), (0, 10, 0), 1.0, stretch=1.2) is not None


def test_closest_hit_picks_nearest():
    targets = [("far", (0, 20, 0), 1, 1), ("near", (0, 8, 0), 1, 1), ("off", (5, 5, 0), 1, 1)]
    hit, t = closest_hit((0, 0, 0), (0, 1, 0), targets)
    assert hit == "near"
    assert t == pytest.approx(7.0)


def test_store_round_trip(tmp_path):
    store = Store(str(tmp_path))
    store.settings.music_volume = 0.3
    store.settings.difficulty = "hard"
    s = Session("time", "hard", seed=1)
    s.score = 1234
    assert store.profile.record(s) is True
    store.save()

    again = Store(str(tmp_path))
    assert again.settings.music_volume == 0.3
    assert again.settings.difficulty == "hard"
    assert again.profile.best_for("time", "hard") == 1234
    assert again.profile.total_games == 1


def test_lower_score_is_not_a_new_best(tmp_path):
    store = Store(str(tmp_path))
    s = Session("zen", "normal")
    s.score = 500
    store.profile.record(s)
    s2 = Session("zen", "normal")
    s2.score = 100
    assert store.profile.record(s2) is False
    assert store.profile.best_for("zen", "normal") == 500


def test_corrupt_or_odd_files_fall_back_to_defaults(tmp_path):
    (tmp_path / "settings.json").write_text("{not json")
    (tmp_path / "profile.json").write_text(json.dumps({"total_popped": "lots", "best_chain": 7}))
    store = Store(str(tmp_path))
    assert store.settings.master_volume == 0.8
    assert store.profile.total_popped == 0       # wrong type ignored
    assert store.profile.best_chain == 7


def test_int_accepted_for_float_setting(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"master_volume": 1, "fullscreen": 1}))
    store = Store(str(tmp_path))
    assert store.settings.master_volume == 1.0
    assert store.settings.fullscreen is False     # ints are not bools
