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
    status_message: str = DEFAULT_STATUS_MESSAGE
    face_texture_assignments: dict[str, dict[int, str]] = field(default_factory=dict)

    def texture_for_face(self, face_id: int | None) -> str | None:
        if face_id is None:
            return None
        return self.face_texture_assignments.get(self.shape_key, {}).get(face_id)


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
        status_message=f"{shape_label} ready. Click a face to texture it.",
    )


def select_face(state: EditorState, face_id: int | None, face_label: str | None) -> EditorState:
    if face_id is None or face_label is None:
        return replace(state, selected_face_id=None, status_message="No face selected.")
    return replace(state, selected_face_id=face_id, status_message=f"Selected face: {face_label}.")


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
        status_message=f"Cleared all face textures on {shape_label}.",
    )
