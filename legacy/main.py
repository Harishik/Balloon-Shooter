import pygame
import random
import sys
import os

pygame.init()

# Display Setup
WIDTH, HEIGHT = 800, 600
win = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Balloon Shooter")

# Defining the paths to image files
background_path = os.path.join(os.path.dirname(__file__), 'background.png')
final_score_background_path = os.path.join(os.path.dirname(__file__), 'final_score_background.png')
balloon_path = os.path.join(os.path.dirname(__file__), 'balloon.png')
bonus_balloon_path = os.path.join(os.path.dirname(__file__), 'bonus_balloon.png')
scope_path = os.path.join(os.path.dirname(__file__), 'scope.jpg')

# Loading the background images
try:
    background = pygame.image.load(background_path)
    background = pygame.transform.scale(background, (WIDTH, HEIGHT))
except pygame.error as e:
    print(f"Cannot load background image: {background_path}")
    sys.exit(e)

try:
    final_score_background = pygame.image.load(final_score_background_path)
    final_score_background = pygame.transform.scale(final_score_background, (WIDTH, HEIGHT))
except pygame.error as e:
    print(f"Cannot load final score background image: {final_score_background_path}")
    sys.exit(e)

# To load and resize the uploaded balloon images
try:
    balloon_image = pygame.image.load(balloon_path)
    balloon_image = pygame.transform.scale(balloon_image, (50, 80))
except pygame.error as e:
    print(f"Cannot load balloon image: {balloon_path}")
    sys.exit(e)

try:
    bonus_balloon_image = pygame.image.load(bonus_balloon_path)
    bonus_balloon_image = pygame.transform.scale(bonus_balloon_image, (50, 80))
except pygame.error as e:
    print(f"Cannot load bonus balloon image: {bonus_balloon_path}")
    sys.exit(e)

# To load and resize the uploaded scope image
try:
    scope_image = pygame.image.load(scope_path)
    scope_image = pygame.transform.scale(scope_image, (40, 40))
except pygame.error as e:
    print(f"Cannot load scope image: {scope_path}")
    sys.exit(e)

# Defining the colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)


# Balloon class
class Balloon(pygame.sprite.Sprite):
    def __init__(self, is_bonus=False):
        super().__init__()
        self.is_bonus = is_bonus
        self.image = bonus_balloon_image if self.is_bonus else balloon_image
        self.rect = self.image.get_rect()
        self.rect.x = random.randint(0, WIDTH - self.rect.width)
        self.rect.y = HEIGHT
        self.speed = random.randint(1, 3)

    def update(self):
        self.rect.y -= self.speed
        if self.rect.y < -self.rect.height:
            self.kill()


# Sprite group for balloons
balloons = pygame.sprite.Group()

# Game variables
score = 0
balloons_popped = 0
shots_fired = 0
font = pygame.font.Font(None, 36)
start_time = pygame.time.get_ticks()
game_duration = 30000  # 30 seconds
spawn_interval = 1000  # 1 second
last_spawn_time = pygame.time.get_ticks()
bonus_spawn_interval = 5000  # 5 seconds
last_bonus_spawn_time = pygame.time.get_ticks()

# To hide the default mouse cursor
pygame.mouse.set_visible(False)


def display_final_score():
    runtime = (pygame.time.get_ticks() - start_time) / 1000
    accuracy = (balloons_popped / shots_fired) * 100 if shots_fired > 0 else 0
    win.blit(final_score_background, (0, 0))

    final_score_text = font.render(f"Final Score: {score}", True, BLACK)
    balloons_popped_text = font.render(f"Balloons Popped: {balloons_popped}", True, BLACK)
    runtime_text = font.render(f"Runtime: {runtime:.2f} seconds", True, BLACK)
    accuracy_text = font.render(f"Accuracy: {accuracy:.2f}%", True, BLACK)

    win.blit(final_score_text, (WIDTH // 2 - final_score_text.get_width() // 2, HEIGHT // 2 - 100))
    win.blit(balloons_popped_text, (WIDTH // 2 - balloons_popped_text.get_width() // 2, HEIGHT // 2 - 50))
    win.blit(runtime_text, (WIDTH // 2 - runtime_text.get_width() // 2, HEIGHT // 2))
    win.blit(accuracy_text, (WIDTH // 2 - accuracy_text.get_width() // 2, HEIGHT // 2 + 50))

    pygame.draw.rect(win, GREEN, [WIDTH // 2 - 100, HEIGHT // 2 + 100, 200, 50])
    restart_text = font.render("Restart", True, BLACK)
    win.blit(restart_text, (WIDTH // 2 - restart_text.get_width() // 2, HEIGHT // 2 + 110))

    pygame.draw.rect(win, RED, [WIDTH // 2 - 100, HEIGHT // 2 + 160, 200, 50])
    exit_text = font.render("Exit", True, BLACK)
    win.blit(exit_text, (WIDTH // 2 - exit_text.get_width() // 2, HEIGHT // 2 + 170))

    pygame.display.flip()

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if WIDTH // 2 - 100 <= event.pos[0] <= WIDTH // 2 + 100:
                    if HEIGHT // 2 + 100 <= event.pos[1] <= HEIGHT // 2 + 150:
                        main()  # Restart the game
                        waiting = False
                    elif HEIGHT // 2 + 160 <= event.pos[1] <= HEIGHT // 2 + 210:
                        pygame.quit()
                        sys.exit()


def main():
    global score, balloons_popped, shots_fired, start_time, last_spawn_time, last_bonus_spawn_time
    score = 0
    balloons_popped = 0
    shots_fired = 0
    start_time = pygame.time.get_ticks()
    last_spawn_time = pygame.time.get_ticks()
    last_bonus_spawn_time = pygame.time.get_ticks()
    balloons.empty()

    running = True
    while running:
        win.blit(background, (0, 0))
        current_time = pygame.time.get_ticks()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                shots_fired += 1
                for balloon in balloons:
                    if balloon.rect.collidepoint(event.pos):
                        balloons_popped += 1
                        if balloon.is_bonus:
                            score += 10
                        else:
                            score += 1
                        balloon.kill()

        # For spawning balloons(Red) at a controlled time intervals
        if current_time - last_spawn_time > spawn_interval:
            balloons.add(Balloon())
            last_spawn_time = current_time

        # For spawning the bonus balloons(Blue) at a controlled time intervals
        if current_time - last_bonus_spawn_time > bonus_spawn_interval:
            balloons.add(Balloon(is_bonus=True))
            last_bonus_spawn_time = current_time

        # To update balloons
        balloons.update()
        balloons.draw(win)

        # For displaying the score
        score_text = font.render(f"Score: {score}", True, WHITE)
        win.blit(score_text, (10, 10))

        # To display the timer
        elapsed_time = (current_time - start_time) / 1000
        timer_text = font.render(f"Time: {elapsed_time:.2f}", True, WHITE)
        win.blit(timer_text, (WIDTH - 150, 10))

        # Displaying scope at mouse's position
        mouse_pos = pygame.mouse.get_pos()
        win.blit(scope_image,
                 (mouse_pos[0] - scope_image.get_width() // 2, mouse_pos[1] - scope_image.get_height() // 2))

        # Checking for the game to end
        if current_time - start_time > game_duration:
            running = False

        pygame.display.flip()

    display_final_score()


main()

pygame.quit()
sys.exit()
