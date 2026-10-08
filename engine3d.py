"""Cena 3D de demonstração usando RenderContext/GLSL do Kivy."""
import math
from kivy.clock import Clock
from kivy.graphics import Mesh, RenderContext
from kivy.graphics.transformation import Matrix
from kivy.uix.widget import Widget

VERTEX_SHADER = r"""
#ifdef GL_ES
precision highp float;
#endif
attribute vec3 vPosition;
attribute vec3 vColor;
uniform mat4 modelview_mat;
uniform mat4 projection_mat;
varying vec3 color;
void main(void) {
    color = vColor;
    gl_Position = projection_mat * modelview_mat * vec4(vPosition, 1.0);
}
"""
FRAGMENT_SHADER = r"""
#ifdef GL_ES
precision mediump float;
#endif
varying vec3 color;
void main(void) {
    gl_FragColor = vec4(color, 1.0);
}
"""


class Engine3D(Widget):
    """Pequena cena 3D com chão, blocos, câmera e movimento local."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.canvas = RenderContext(compute_normal_mat=False)
        self.canvas.shader.vs = VERTEX_SHADER
        self.canvas.shader.fs = FRAGMENT_SHADER
        self.position = [0.0, 1.7, 6.0]
        self.yaw = 0.0
        self.pitch = -0.12
        self.velocity_y = 0.0
        self.grounded = False
        self.move_forward = 0.0
        self.move_side = 0.0
        self.remote_players = {}
        self._vertices = []
        self._indices = []
        self._build_world()
        self._rebuild_mesh()
        self.bind(size=self._update_projection, pos=self._update_projection)
        Clock.schedule_interval(self._update, 1 / 60)

    def _quad(self, a, b, c, d, color):
        base = len(self._vertices) // 6
        for point in (a, b, c, d):
            self._vertices.extend([point[0], point[1], point[2], color[0], color[1], color[2]])
        self._indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    def _cube(self, x, y, z, sx, sy, sz, color):
        x0, x1 = x - sx / 2, x + sx / 2
        y0, y1 = y - sy / 2, y + sy / 2
        z0, z1 = z - sz / 2, z + sz / 2
        self._quad((x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1),color)
        self._quad((x1,y0,z0),(x0,y0,z0),(x0,y1,z0),(x1,y1,z0),color)
        self._quad((x0,y0,z0),(x0,y0,z1),(x0,y1,z1),(x0,y1,z0),color)
        self._quad((x1,y0,z1),(x1,y0,z0),(x1,y1,z0),(x1,y1,z1),color)
        self._quad((x0,y1,z1),(x1,y1,z1),(x1,y1,z0),(x0,y1,z0),color)
        self._quad((x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1),color)

    def _build_world(self):
        # Chão em quadrados, com cores discretas.
        for gx in range(-10, 11):
            for gz in range(-10, 11):
                shade = 0.19 if (gx + gz) % 2 == 0 else 0.14
                c = (shade, shade, shade + 0.015)
                self._quad((gx,0,gz),(gx+1,0,gz),(gx+1,0,gz+1),(gx,0,gz+1),c)
        self._cube(0, 0.5, 0, 1, 1, 1, (1.0, 0.30, 0.04))
        self._cube(2, 0.5, -2, 1, 1, 1, (0.95, 0.42, 0.08))
        self._cube(-2, 1.0, -4, 1, 2, 1, (0.24, 0.42, 0.72))
        self._cube(4, 1.5, -5, 1, 3, 1, (0.30, 0.62, 0.36))

    def _rebuild_mesh(self):
        self.canvas.clear()
        with self.canvas:
            self.mesh = Mesh(
                vertices=self._vertices,
                indices=self._indices,
                fmt=[("vPosition", 3, "float"), ("vColor", 3, "float")],
                mode="triangles",
            )

    def _update_projection(self, *_args):
        width = max(1.0, float(self.width))
        height = max(1.0, float(self.height))
        self.canvas['projection_mat'] = Matrix().view_clip(-width / height, width / height, -1, 1, 1, 100, 1)

    def _update(self, dt):
        dt = min(float(dt), 0.05)
        self._update_projection()
        self.velocity_y -= 9.8 * dt
        self.position[1] += self.velocity_y * dt
        if self.position[1] < 1.7:
            self.position[1] = 1.7
            self.velocity_y = 0.0
            self.grounded = True
        forward = self.move_forward
        side = self.move_side
        length = math.hypot(forward, side)
        if length > 1:
            forward /= length
            side /= length
        speed = 4.5 * dt
        self.position[0] += (math.sin(self.yaw) * forward + math.cos(self.yaw) * side) * speed
        self.position[2] += (-math.cos(self.yaw) * forward + math.sin(self.yaw) * side) * speed
        self.position[0] = max(-9.5, min(9.5, self.position[0]))
        self.position[2] = max(-9.5, min(9.5, self.position[2]))
        eye = self.position
        target = (eye[0] + math.sin(self.yaw) * math.cos(self.pitch),
                  eye[1] + math.sin(self.pitch),
                  eye[2] - math.cos(self.yaw) * math.cos(self.pitch))
        view = Matrix().look_at(eye[0], eye[1], eye[2], target[0], target[1], target[2], 0, 1, 0)
        self.canvas['modelview_mat'] = view
        self.canvas.ask_update()

    def move(self, forward=0.0, side=0.0):
        self.move_forward = float(forward)
        self.move_side = float(side)

    def jump(self):
        if self.grounded:
            self.velocity_y = 5.2
            self.grounded = False

    def rotate(self, dx, dy):
        self.yaw += float(dx) * 0.006
        self.pitch = max(-1.1, min(0.65, self.pitch + float(dy) * 0.004))

    def get_position(self):
        return tuple(self.position)

    def set_remote_player(self, player_id, x, y, z):
        # Placeholder visual: rede de estado funciona; avatares instanciados ainda não são renderizados.
        self.remote_players[str(player_id)] = (float(x), float(y), float(z))

    def remove_remote_player(self, player_id):
        self.remote_players.pop(str(player_id), None)

    @staticmethod
    def load_obj_model(path):
        """Lê vértices/faces triangulares simples de OBJ; não trata materiais nem UVs."""
        vertices, faces = [], []
        with open(path, "r", encoding="utf-8", errors="replace") as source:
            for line in source:
                parts = line.strip().split()
                if not parts:
                    continue
                if parts[0] == "v" and len(parts) >= 4:
                    vertices.append(tuple(float(v) for v in parts[1:4]))
                elif parts[0] == "f" and len(parts) >= 4:
                    ids = [int(item.split("/")[0]) for item in parts[1:]]
                    for i in range(1, len(ids) - 1):
                        faces.append((ids[0], ids[i], ids[i + 1]))
        return vertices, faces
