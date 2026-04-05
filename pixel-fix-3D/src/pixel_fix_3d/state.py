from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

DEFAULT_STATUS_MESSAGE = "Load textures, pick a face, and assign a texture."
DEFAULT_SHAPE_KEY = "cube"
MIN_CAMERA_DISTANCE = 2.0
MAX_CAMERA_DISTANCE = 8.0
MIN_CAMERA_PITCH = math.radians(-89)
MAX_CAMERA_PITCH = math.radians(89)
DEFAULT_CAMERA_YAW = math.radians(45)
DEFAULT_CAMERA_PITCH = math.radians(35.26438968)
DEFAULT_CAMERA_DISTANCE = 4.25


@dataclass(frozen=True)
class CameraState:
    yaw: float = DEFAULT_CAMERA_YAW
    pitch: float = DEFAULT_CAMERA_PITCH
    distance: float = DEFAULT_CAMERA_DISTANCE


@dataclass(frozen=True)
class EditorState:
    shape_key: str = DEFAULT_SHAPE_KEY
    camera: CameraState = field(default_factory=CameraState)
    selected_face_id: int | None = None
    selected_face_ids: tuple[int, ...] = ()
    status_message: str = DEFAULT_STATUS_MESSAGE
    face_texture_assignments: dict[str, dict[int, str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_ids = _normalize_face_ids(self.selected_face_ids)
        active_face_id = self.selected_face_id
        if active_face_id is not None and active_face_id not in normalized_ids:
            normalized_ids = (*normalized_ids, active_face_id)
        if active_face_id is None and normalized_ids:
            active_face_id = normalized_ids[-1]
        object.__setattr__(self, "selected_face_id", active_face_id)
        object.__setattr__(self, "selected_face_ids", normalized_ids)

    def texture_for_face(self, face_id: int | None) -> str | None:
        if face_id is None:
            return None
        return self.face_texture_assignments.get(self.shape_key, {}).get(face_id)


def _normalize_face_ids(face_ids: tuple[int, ...] | list[int]) -> tuple[int, ...]:
    normalized: list[int] = []
    seen: set[int] = set()
    for face_id in face_ids:
        if not isinstance(face_id, int) or face_id in seen:
            continue
        normalized.append(face_id)
        seen.add(face_id)
    return tuple(normalized)


def reset_camera() -> CameraState:
    return CameraState()


def snap_camera_view(camera: CameraState, view_name: str) -> CameraState:
    if view_name == "iso":
        default = reset_camera()
        return CameraState(yaw=default.yaw, pitch=default.pitch, distance=camera.distance)
    if view_name == "front":
        return CameraState(yaw=0.0, pitch=0.0, distance=camera.distance)
    if view_name == "right":
        return CameraState(yaw=math.pi / 2.0, pitch=0.0, distance=camera.distance)
    if view_name == "back":
        return CameraState(yaw=math.pi, pitch=0.0, distance=camera.distance)
    if view_name == "left":
        return CameraState(yaw=-(math.pi / 2.0), pitch=0.0, distance=camera.distance)
    if view_name == "top":
        return CameraState(yaw=0.0, pitch=math.radians(89), distance=camera.distance)
    if view_name == "bottom":
        return CameraState(yaw=0.0, pitch=math.radians(-89), distance=camera.distance)
    if view_name == "backleft":
        return CameraState(yaw=math.radians(-135), pitch=DEFAULT_CAMERA_PITCH, distance=camera.distance)
    if view_name == "backright":
        return CameraState(yaw=math.radians(135), pitch=DEFAULT_CAMERA_PITCH, distance=camera.distance)
    return camera


def rotate_camera(camera: CameraState, delta_yaw: float, delta_pitch: float) -> CameraState:
    return CameraState(
        yaw=camera.yaw + delta_yaw,
        pitch=max(MIN_CAMERA_PITCH, min(MAX_CAMERA_PITCH, camera.pitch + delta_pitch)),
        distance=camera.distance,
    )


def zoom_camera(camera: CameraState, delta_distance: float) -> CameraState:
    return CameraState(
        yaw=camera.yaw,
        pitch=camera.pitch,
        distance=max(MIN_CAMERA_DISTANCE, min(MAX_CAMERA_DISTANCE, camera.distance + delta_distance)),
    )


def set_shape(state: EditorState, shape_key: str, shape_label: str) -> EditorState:
    return replace(
        state,
        shape_key=shape_key,
        camera=reset_camera(),
        selected_face_id=None,
        selected_face_ids=(),
        status_message=f"{shape_label} ready. Click a face to texture it.",
    )


def clear_selection(state: EditorState, *, status_message: str = "No face selected.") -> EditorState:
    return replace(state, selected_face_id=None, selected_face_ids=(), status_message=status_message)


def select_face(state: EditorState, face_id: int | None, face_label: str | None) -> EditorState:
    if face_id is None or face_label is None:
        return clear_selection(state)
    return replace(
        state,
        selected_face_id=face_id,
        selected_face_ids=(face_id,),
        status_message=f"Selected face: {face_label}.",
    )


def toggle_face_in_selection(state: EditorState, face_id: int | None, face_label: str | None) -> EditorState:
    if face_id is None or face_label is None:
        return state
    if face_id in state.selected_face_ids:
        remaining = tuple(existing_id for existing_id in state.selected_face_ids if existing_id != face_id)
        if not remaining:
            return clear_selection(state)
        active_face_id = state.selected_face_id if state.selected_face_id in remaining else remaining[-1]
        return replace(
            state,
            selected_face_id=active_face_id,
            selected_face_ids=remaining,
            status_message=f"Removed {face_label} from the selection.",
        )
    updated_ids = (*state.selected_face_ids, face_id)
    count = len(updated_ids)
    status_message = f"Added {face_label} to the selection."
    if count > 1:
        status_message = f"{count} faces selected (active: {face_label})."
    return replace(
        state,
        selected_face_id=face_id,
        selected_face_ids=updated_ids,
        status_message=status_message,
    )


def toggle_select_all_faces(state: EditorState, face_ids: tuple[int, ...], shape_label: str) -> EditorState:
    normalized_ids = _normalize_face_ids(face_ids)
    if not normalized_ids:
        return clear_selection(state)
    if len(state.selected_face_ids) == len(normalized_ids) and set(state.selected_face_ids) == set(normalized_ids):
        return clear_selection(state, status_message="Deselected all faces.")
    active_face_id = state.selected_face_id if state.selected_face_id in normalized_ids else normalized_ids[0]
    return replace(
        state,
        selected_face_id=active_face_id,
        selected_face_ids=normalized_ids,
        status_message=f"Selected all {len(normalized_ids)} faces on {shape_label}.",
    )


def assign_texture_to_selected_face(
    state: EditorState,
    texture_id: str,
    texture_name: str,
    face_label: str | None,
) -> EditorState:
    if state.selected_face_id is None or face_label is None:
        return replace(state, status_message="Select a face before assigning a texture.")
    assignments = {key: dict(value) for key, value in state.face_texture_assignments.items()}
    shape_assignments = assignments.setdefault(state.shape_key, {})
    shape_assignments[state.selected_face_id] = texture_id
    return replace(
        state,
        face_texture_assignments=assignments,
        status_message=f"Applied {texture_name} to {face_label}.",
    )


def assign_texture_to_faces(state: EditorState, texture_id: str, texture_name: str, face_ids: tuple[int, ...]) -> EditorState:
    if not face_ids:
        return replace(state, status_message="Select at least one face before assigning a texture.")
    assignments = {key: dict(value) for key, value in state.face_texture_assignments.items()}
    shape_assignments = assignments.setdefault(state.shape_key, {})
    for face_id in face_ids:
        shape_assignments[face_id] = texture_id
    if len(face_ids) == 1:
        return replace(
            state,
            face_texture_assignments=assignments,
            status_message=f"Applied {texture_name} to 1 face.",
        )
    return replace(
        state,
        face_texture_assignments=assignments,
        status_message=f"Applied {texture_name} to {len(face_ids)} faces.",
    )


def clear_selected_face_texture(state: EditorState, face_label: str | None) -> EditorState:
    if state.selected_face_id is None or face_label is None:
        return replace(state, status_message="Select a face before clearing its texture.")
    assignments = {key: dict(value) for key, value in state.face_texture_assignments.items()}
    shape_assignments = assignments.setdefault(state.shape_key, {})
    if state.selected_face_id in shape_assignments:
        del shape_assignments[state.selected_face_id]
        return replace(
            state,
            face_texture_assignments=assignments,
            status_message=f"Cleared the texture on {face_label}.",
        )
    return replace(state, status_message=f"{face_label} is already using the default material.")


def clear_shape_textures(state: EditorState, shape_label: str) -> EditorState:
    assignments = {key: dict(value) for key, value in state.face_texture_assignments.items()}
    if assignments.pop(state.shape_key, None) is None:
        return replace(state, status_message=f"{shape_label} has no face textures to clear.")
    return replace(
        state,
        face_texture_assignments=assignments,
        selected_face_id=None,
        selected_face_ids=(),
        status_message=f"Cleared all face textures on {shape_label}.",
    )
