import pygame


class Camera:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.offset = pygame.Vector2()
        self.shake_time = 0.0
        self.shake_power = 0.0

    def follow(self, target_rect: pygame.Rect, screen_size: tuple[int, int], dt: float) -> None:
        desired = pygame.Vector2(
            target_rect.centerx - screen_size[0] / 2,
            target_rect.centery - screen_size[1] / 2,
        )
        desired.x = max(0, min(desired.x, max(0, self.width - screen_size[0])))
        desired.y = max(0, min(desired.y, max(0, self.height - screen_size[1])))
        self.offset += (desired - self.offset) * min(1.0, dt * 8.0)

        if self.shake_time > 0:
            self.shake_time -= dt
            jitter = pygame.Vector2(
                pygame.time.get_ticks() % 7 - 3,
                pygame.time.get_ticks() % 11 - 5,
            )
            self.offset += jitter * self.shake_power

    def shake(self, power: float, duration: float) -> None:
        self.shake_power = max(self.shake_power, power)
        self.shake_time = max(self.shake_time, duration)

    def apply(self, rect: pygame.Rect) -> pygame.Rect:
        return rect.move(-int(self.offset.x), -int(self.offset.y))

    def apply_pos(self, pos: pygame.Vector2 | tuple[float, float]) -> pygame.Vector2:
        return pygame.Vector2(pos) - self.offset

    def world_mouse(self, mouse_pos: tuple[int, int]) -> pygame.Vector2:
        return pygame.Vector2(mouse_pos) + self.offset

