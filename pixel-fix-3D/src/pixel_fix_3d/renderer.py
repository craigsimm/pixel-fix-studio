from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Collection, Mapping

import numpy as np
from PIL import Image

from .shapes import ShapePreset
from .state import CameraState
from .textures import TextureEntry

BACKGROUND_RGB = np.array([23, 25, 25], dtype=np.uint8)
DEFAULT_FACE_RGB = np.array([124, 130, 136], dtype=np.uint8)
ACCENT_RGB = np.array([127, 217, 248], dtype=np.uint8)
GRID_RGB = np.array([58, 67, 71], dtype=np.uint8)
GRID_AXIS_RGB = np.array([86, 121, 132], dtype=np.uint8)
LIGHT_DIRECTION = np.array([0.45, 0.75, 0.5], dtype=np.float64)
LIGHT_DIRECTION /= np.linalg.norm(LIGHT_DIRECTION)
SHADE_MIN = 0.35
SHADE_RANGE = 0.65
SHADE_MIDPOINT = SHADE_MIN + (SHADE_RANGE * 0.5)
FLOOR_OFFSET = 0.06
GRID_DIVISIONS = 8
NEAR_CLIP_Z = 0.05


@dataclass(frozen=True)
class RenderOptions:
    show_floor_grid: bool = True
    show_face_highlight: bool = True
    lighting_intensity: float = 1.0
    background_rgb: np.ndarray | None = None


@dataclass(frozen=True)
class RenderResult:
    image: Image.Image
    face_id_buffer: np.ndarray


def sample_texture_nearest(texture: np.ndarray, u: float, v: float) -> np.ndarray:
    height, width, _ = texture.shape
    clamped_u = max(0.0, min(1.0, u))
    clamped_v = max(0.0, min(1.0, v))
    x = min(width - 1, int(clamped_u * (width - 1) + 1e-6))
    y = min(height - 1, int(clamped_v * (height - 1) + 1e-6))
    return texture[y, x]


class SoftwareRenderer:
    def __init__(self, width: int = 272, height: int = 204) -> None:
        self.width = width
        self.height = height
        self.aspect = width / height
        self._fov = math.radians(52.0)

    def render(
        self,
        shape: ShapePreset,
        camera: CameraState,
        textures_by_face: Mapping[int, TextureEntry],
        selected_face_ids: Collection[int] | None = None,
        options: RenderOptions | None = None,
    ) -> RenderResult:
        options = options or RenderOptions()
        selected_faces = set(selected_face_ids or ())
        color_buffer = self._make_background_buffer(options.background_rgb)
        depth_buffer = np.full((self.height, self.width), np.inf, dtype=np.float64)
        face_id_buffer = np.full((self.height, self.width), -1, dtype=np.int32)
        texture_arrays = {
            face_id: np.asarray(entry.image.convert("RGBA"), dtype=np.uint8)
            for face_id, entry in textures_by_face.items()
        }

        camera_position, camera_right, camera_up, camera_forward = self._camera_basis(camera)
        if options.show_floor_grid:
            self._draw_floor_grid(
                color_buffer=color_buffer,
                shape=shape,
                camera_position=camera_position,
                camera_right=camera_right,
                camera_up=camera_up,
                camera_forward=camera_forward,
            )

        projected_faces: list[tuple[float, int, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool]] = []
        for face in shape.face_groups:
            world_vertices = np.asarray(face.vertices, dtype=np.float64)
            centroid = np.mean(world_vertices, axis=0)
            normal = np.cross(world_vertices[1] - world_vertices[0], world_vertices[2] - world_vertices[0])
            normal_length = np.linalg.norm(normal)
            if normal_length == 0:
                continue
            normal /= normal_length
            if float(np.dot(normal, camera_position - centroid)) <= 0.0:
                continue

            camera_vertices = self._to_camera_space(world_vertices, camera_position, camera_right, camera_up, camera_forward)
            if np.any(camera_vertices[:, 2] <= NEAR_CLIP_Z):
                continue

            screen_points = self._project(camera_vertices)
            projected_faces.append(
                (
                    float(np.mean(camera_vertices[:, 2])),
                    face.face_id,
                    world_vertices,
                    camera_vertices,
                    screen_points,
                    np.asarray(face.uvs, dtype=np.float64),
                    normal,
                    face.face_id in selected_faces and options.show_face_highlight,
                )
            )

        projected_faces.sort(key=lambda item: item[0], reverse=True)

        for _, face_id, _world_vertices, camera_vertices, screen_points, uvs, normal, highlight_selected in projected_faces:
            base_shade = SHADE_MIN + (SHADE_RANGE * max(0.0, float(np.dot(normal, LIGHT_DIRECTION))))
            contrast_scale = self._lighting_contrast_scale(options.lighting_intensity)
            shade = np.clip(
                SHADE_MIDPOINT + ((base_shade - SHADE_MIDPOINT) * contrast_scale),
                0.0,
                1.0,
            )
            triangles = self._fan_indices(len(screen_points))
            texture = texture_arrays.get(face_id)
            for tri_indices in triangles:
                tri_camera = camera_vertices[list(tri_indices)]
                tri_screen = screen_points[list(tri_indices)]
                tri_uvs = uvs[list(tri_indices)]
                self._rasterize_triangle(
                    color_buffer=color_buffer,
                    depth_buffer=depth_buffer,
                    face_id_buffer=face_id_buffer,
                    triangle_camera=tri_camera,
                    triangle_screen=tri_screen,
                    triangle_uvs=tri_uvs,
                    face_id=face_id,
                    texture=texture,
                    shade=shade,
                    selected=highlight_selected,
                )

        return RenderResult(image=Image.fromarray(color_buffer, mode="RGB"), face_id_buffer=face_id_buffer)

    def _make_background_buffer(self, background_rgb: np.ndarray | None) -> np.ndarray:
        if (
            background_rgb is not None
            and background_rgb.shape == (self.height, self.width, 3)
            and background_rgb.dtype == np.uint8
        ):
            return background_rgb.copy()
        return np.tile(BACKGROUND_RGB, (self.height, self.width, 1))

    def _draw_floor_grid(
        self,
        *,
        color_buffer: np.ndarray,
        shape: ShapePreset,
        camera_position: np.ndarray,
        camera_right: np.ndarray,
        camera_up: np.ndarray,
        camera_forward: np.ndarray,
    ) -> None:
        vertices = np.asarray([vertex for face in shape.face_groups for vertex in face.vertices], dtype=np.float64)
        mins = vertices.min(axis=0)
        maxs = vertices.max(axis=0)
        floor_y = mins[1] - FLOOR_OFFSET
        half_extent = max(1.6, max(maxs[0] - mins[0], maxs[2] - mins[2]) * 1.3)
        step = (half_extent * 2.0) / GRID_DIVISIONS
        positions = [(-half_extent + (step * index)) for index in range(GRID_DIVISIONS + 1)]

        for value in positions:
            accent = abs(value) <= (step * 0.25)
            self._draw_projected_line(
                color_buffer=color_buffer,
                start=np.array([-half_extent, floor_y, value], dtype=np.float64),
                end=np.array([half_extent, floor_y, value], dtype=np.float64),
                color=GRID_AXIS_RGB if accent else GRID_RGB,
                alpha=0.52 if accent else 0.34,
                camera_position=camera_position,
                camera_right=camera_right,
                camera_up=camera_up,
                camera_forward=camera_forward,
            )
            self._draw_projected_line(
                color_buffer=color_buffer,
                start=np.array([value, floor_y, -half_extent], dtype=np.float64),
                end=np.array([value, floor_y, half_extent], dtype=np.float64),
                color=GRID_AXIS_RGB if accent else GRID_RGB,
                alpha=0.52 if accent else 0.34,
                camera_position=camera_position,
                camera_right=camera_right,
                camera_up=camera_up,
                camera_forward=camera_forward,
            )

    def _draw_projected_line(
        self,
        *,
        color_buffer: np.ndarray,
        start: np.ndarray,
        end: np.ndarray,
        color: np.ndarray,
        alpha: float,
        camera_position: np.ndarray,
        camera_right: np.ndarray,
        camera_up: np.ndarray,
        camera_forward: np.ndarray,
    ) -> None:
        camera_vertices = self._to_camera_space(
            np.vstack((start, end)),
            camera_position,
            camera_right,
            camera_up,
            camera_forward,
        )
        clipped = self._clip_line_to_near_plane(camera_vertices)
        if clipped is None:
            return
        projected = self._project(clipped)
        self._draw_screen_line(
            color_buffer=color_buffer,
            x0=projected[0, 0],
            y0=projected[0, 1],
            x1=projected[1, 0],
            y1=projected[1, 1],
            color=color,
            alpha=alpha,
        )

    @staticmethod
    def _clip_line_to_near_plane(camera_vertices: np.ndarray) -> np.ndarray | None:
        a = camera_vertices[0].astype(np.float64, copy=True)
        b = camera_vertices[1].astype(np.float64, copy=True)
        if a[2] <= NEAR_CLIP_Z and b[2] <= NEAR_CLIP_Z:
            return None
        if a[2] <= NEAR_CLIP_Z:
            t = (NEAR_CLIP_Z - a[2]) / (b[2] - a[2])
            a = a + ((b - a) * t)
            a[2] = NEAR_CLIP_Z
        elif b[2] <= NEAR_CLIP_Z:
            t = (NEAR_CLIP_Z - b[2]) / (a[2] - b[2])
            b = b + ((a - b) * t)
            b[2] = NEAR_CLIP_Z
        return np.vstack((a, b))

    def _draw_screen_line(
        self,
        *,
        color_buffer: np.ndarray,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        color: np.ndarray,
        alpha: float,
    ) -> None:
        delta_x = x1 - x0
        delta_y = y1 - y0
        steps = max(1, int(math.ceil(max(abs(delta_x), abs(delta_y)))))
        for step_index in range(steps + 1):
            t = step_index / steps
            pixel_x = int(round(x0 + (delta_x * t)))
            pixel_y = int(round(y0 + (delta_y * t)))
            if 0 <= pixel_x < self.width and 0 <= pixel_y < self.height:
                color_buffer[pixel_y, pixel_x] = self._blend_rgb(color_buffer[pixel_y, pixel_x], color, alpha)

    @staticmethod
    def _blend_rgb(base_rgb: np.ndarray, overlay_rgb: np.ndarray, alpha: float) -> np.ndarray:
        blended = (base_rgb.astype(np.float64) * (1.0 - alpha)) + (overlay_rgb.astype(np.float64) * alpha)
        return np.clip(blended, 0, 255).astype(np.uint8)

    @staticmethod
    def _lighting_contrast_scale(lighting_intensity: float) -> float:
        intensity = max(0.0, lighting_intensity)
        return intensity * intensity

    def _camera_basis(self, camera: CameraState) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        camera_position = np.array(
            [
                math.cos(camera.pitch) * math.sin(camera.yaw) * camera.distance,
                math.sin(camera.pitch) * camera.distance,
                math.cos(camera.pitch) * math.cos(camera.yaw) * camera.distance,
            ],
            dtype=np.float64,
        )
        target = np.zeros(3, dtype=np.float64)
        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        forward = target - camera_position
        forward /= np.linalg.norm(forward)
        right = np.cross(forward, world_up)
        right /= np.linalg.norm(right)
        up = np.cross(right, forward)
        up /= np.linalg.norm(up)
        return camera_position, right, up, forward

    @staticmethod
    def _to_camera_space(
        world_vertices: np.ndarray,
        camera_position: np.ndarray,
        camera_right: np.ndarray,
        camera_up: np.ndarray,
        camera_forward: np.ndarray,
    ) -> np.ndarray:
        translated = world_vertices - camera_position
        return np.column_stack(
            (
                translated @ camera_right,
                translated @ camera_up,
                translated @ camera_forward,
            )
        )

    def _project(self, camera_vertices: np.ndarray) -> np.ndarray:
        projected = np.zeros((len(camera_vertices), 3), dtype=np.float64)
        f = 1.0 / math.tan(self._fov / 2.0)
        projected[:, 0] = ((camera_vertices[:, 0] * f) / (camera_vertices[:, 2] * self.aspect) * 0.5 + 0.5) * (self.width - 1)
        projected[:, 1] = (1.0 - (((camera_vertices[:, 1] * f) / camera_vertices[:, 2]) * 0.5 + 0.5)) * (self.height - 1)
        projected[:, 2] = camera_vertices[:, 2]
        return projected

    @staticmethod
    def _fan_indices(vertex_count: int) -> list[tuple[int, int, int]]:
        return [(0, index, index + 1) for index in range(1, vertex_count - 1)]

    def _rasterize_triangle(
        self,
        *,
        color_buffer: np.ndarray,
        depth_buffer: np.ndarray,
        face_id_buffer: np.ndarray,
        triangle_camera: np.ndarray,
        triangle_screen: np.ndarray,
        triangle_uvs: np.ndarray,
        face_id: int,
        texture: np.ndarray | None,
        shade: float,
        selected: bool,
    ) -> None:
        del triangle_camera
        x0, y0, z0 = triangle_screen[0]
        x1, y1, z1 = triangle_screen[1]
        x2, y2, z2 = triangle_screen[2]
        min_x = max(0, int(math.floor(min(x0, x1, x2))))
        max_x = min(self.width - 1, int(math.ceil(max(x0, x1, x2))))
        min_y = max(0, int(math.floor(min(y0, y1, y2))))
        max_y = min(self.height - 1, int(math.ceil(max(y0, y1, y2))))
        area = self._edge(x0, y0, x1, y1, x2, y2)
        if area == 0:
            return

        x_coords = np.arange(min_x, max_x + 1, dtype=np.float64) + 0.5
        y_coords = np.arange(min_y, max_y + 1, dtype=np.float64) + 0.5
        sample_x, sample_y = np.meshgrid(x_coords, y_coords)

        w0 = self._edge(x1, y1, x2, y2, sample_x, sample_y) / area
        w1 = self._edge(x2, y2, x0, y0, sample_x, sample_y) / area
        w2 = self._edge(x0, y0, x1, y1, sample_x, sample_y) / area
        mask = (w0 >= 0.0) & (w1 >= 0.0) & (w2 >= 0.0)
        if not np.any(mask):
            return

        depth = (w0 * z0) + (w1 * z1) + (w2 * z2)
        region_depth = depth_buffer[min_y : max_y + 1, min_x : max_x + 1]
        mask &= depth < region_depth
        if not np.any(mask):
            return

        u = (w0 * triangle_uvs[0, 0]) + (w1 * triangle_uvs[1, 0]) + (w2 * triangle_uvs[2, 0])
        v = (w0 * triangle_uvs[0, 1]) + (w1 * triangle_uvs[1, 1]) + (w2 * triangle_uvs[2, 1])
        if texture is None:
            texels = np.empty((int(mask.sum()), 4), dtype=np.float64)
            texels[:, :3] = DEFAULT_FACE_RGB.astype(np.float64)
            texels[:, 3] = 255.0
        else:
            height, width, _channels = texture.shape
            tex_x = np.minimum(width - 1, (np.clip(u, 0.0, 1.0) * (width - 1) + 1e-6).astype(np.int32))
            tex_y = np.minimum(height - 1, (np.clip(v, 0.0, 1.0) * (height - 1) + 1e-6).astype(np.int32))
            texels = texture[tex_y[mask], tex_x[mask]].astype(np.float64)

        region_color = color_buffer[min_y : max_y + 1, min_x : max_x + 1]
        region_face_ids = face_id_buffer[min_y : max_y + 1, min_x : max_x + 1]
        base_rgb = region_color[mask].astype(np.float64)
        rgb = texels[:, :3] * shade
        alpha = texels[:, 3:4] / 255.0
        rgb = (rgb * alpha) + (base_rgb * (1.0 - alpha))
        if selected:
            rgb = np.clip((rgb * 0.82) + (ACCENT_RGB.astype(np.float64) * 0.28) + 12.0, 0, 255)

        region_color[mask] = np.clip(rgb, 0, 255).astype(np.uint8)
        region_depth[mask] = depth[mask]
        region_face_ids[mask] = face_id

    @staticmethod
    def _edge(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
        return (cx - ax) * (by - ay) - (cy - ay) * (bx - ax)
