from __future__ import annotations

import math

from pixel_fix_3d.state import (
    EditorState,
    assign_texture_to_selected_face,
    clear_selected_face_texture,
    clear_shape_textures,
    select_face,
    set_shape,
    snap_camera_view,
)


def test_shape_switch_resets_face_and_preserves_assignments() -> None:
    state = EditorState()
    state = select_face(state, 0, "Front")
    state = assign_texture_to_selected_face(state, "brick", "brick.png", "Front")
    state = set_shape(state, "ramp", "Ramp")
    assert state.shape_key == "ramp"
    assert state.selected_face_id is None
    assert state.face_texture_assignments["cube"][0] == "brick"


def test_assign_and_clear_selected_face_texture() -> None:
    state = EditorState()
    state = select_face(state, 1, "Back")
    state = assign_texture_to_selected_face(state, "metal", "metal.png", "Back")
    assert state.face_texture_assignments["cube"][1] == "metal"
    state = clear_selected_face_texture(state, "Back")
    assert 1 not in state.face_texture_assignments["cube"]


def test_clear_shape_textures_removes_current_shape_only() -> None:
    state = EditorState(face_texture_assignments={"cube": {0: "brick"}, "ramp": {5: "stone"}})
    cleared = clear_shape_textures(state, "Cube")
    assert "cube" not in cleared.face_texture_assignments
    assert cleared.face_texture_assignments["ramp"][5] == "stone"


def test_assign_texture_requires_selected_face() -> None:
    state = EditorState()
    updated = assign_texture_to_selected_face(state, "brick", "brick.png", None)
    assert updated.face_texture_assignments == {}
    assert "Select a face" in updated.status_message


def test_snap_camera_view_preserves_distance() -> None:
    state = EditorState()
    iso = snap_camera_view(state.camera, "iso")
    top = snap_camera_view(state.camera, "top")
    right = snap_camera_view(state.camera, "right")
    bottom = snap_camera_view(state.camera, "bottom")
    backleft = snap_camera_view(state.camera, "backleft")
    backright = snap_camera_view(state.camera, "backright")
    assert iso.distance == state.camera.distance
    assert top.distance == state.camera.distance
    assert right.distance == state.camera.distance
    assert bottom.distance == state.camera.distance
    assert backleft.distance == state.camera.distance
    assert backright.distance == state.camera.distance
    assert iso.pitch > 0.5
    assert iso.yaw > 0.5
    assert top.pitch > 1.5
    assert right.yaw > 1.5
    assert bottom.pitch < -1.5
    assert math.isclose(backleft.yaw, math.radians(-135), rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(backright.yaw, math.radians(135), rel_tol=0.0, abs_tol=1e-9)
