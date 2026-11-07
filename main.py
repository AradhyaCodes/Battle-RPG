import cv2
import mediapipe as mp
import pygame
import sys
import numpy as np
import os
import math

# ==========================================
# 1. INITIALIZATION
# ==========================================
pygame.init()
WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Full Body Boss Fight")
clock = pygame.time.Clock()

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(min_detection_confidence=0.7, min_tracking_confidence=0.7)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

# ==========================================
# 2. ASSET LOADING & STATE MACHINE
# ==========================================
def load_animation_folder(folder_path, scale_size=(350, 350)):
    frames = []
    if not os.path.exists(folder_path):
        print(f"WARNING: Folder not found -> {folder_path}")
        return frames
        
    for filename in sorted(os.listdir(folder_path)):
        if filename.endswith(".png"):
            img_path = os.path.join(folder_path, filename)
            img = pygame.image.load(img_path).convert_alpha()
            img = pygame.transform.scale(img, scale_size)
            frames.append(img)
    return frames

boss_animations = {
    "idle": load_animation_folder("assets/01_demon_idle"),
    "cleave": load_animation_folder("assets/03_demon_cleave"),
    "take_hit": load_animation_folder("assets/04_demon_take_hit"),
    "death": load_animation_folder("assets/05_demon_death")
}

# ==========================================
# 3. GAME VARIABLES & RESET FUNCTION
# ==========================================
def reset_game():
    global boss_hp, player_hp, game_status, current_state, frame_index
    global left_arm_ready, right_arm_ready, attack_timer, sweeping_attack_rect
    
    boss_hp = 250
    player_hp = 60
    game_status = "playing"
    current_state = "idle"
    frame_index = 0.0
    left_arm_ready = True
    right_arm_ready = True
    attack_timer = 0
    sweeping_attack_rect = None

# Animation & Position
current_state = "idle"
frame_index = 0.0
animation_speed = 0.25
base_x = 100  
base_y = 200
current_boss_x = base_x
current_boss_y = base_y
time_counter = 0.0

# Game Logic 
max_boss_hp = 250
max_player_hp = 60
boss_hp = 250
player_hp = 60
game_status = "playing" 

# Punch "Reload" Logic
left_arm_ready = True
right_arm_ready = True

# Attack Variables
attack_timer = 0
time_between_attacks = 65 
sweeping_attack_rect = None 
attack_speed = 62 

# ==========================================
# 4. MAIN GAME LOOP
# ==========================================
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            # Restart game when 'R' is pressed if game is over
            if event.key == pygame.K_r and game_status in ["won", "lost"]:
                reset_game()

    # --- Webcam Processing ---
    success, frame = cap.read()
    if not success:
        continue

    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb_frame)

    frame_surface = pygame.surfarray.make_surface(np.transpose(rgb_frame, (1, 0, 2)))
    screen.blit(frame_surface, (0, 0))

    # --- Boss AI & Physics (Calculated early for the Hitbox) ---
    time_counter += 0.05
    hover_y = math.sin(time_counter) * 15
    current_boss_x = base_x
    current_boss_y = base_y + hover_y

    # Create the Boss Hitbox
    boss_rect = pygame.Rect(current_boss_x, current_boss_y, 350, 350)

    # --- Draw UI Guides ---
    duck_line_y = 400
    punch_zone_x = 750 # Reload axis
    
    # Draw Horizontal line (Ducking)
    pygame.draw.line(screen, (0,125, 0), (0, duck_line_y), (WIDTH, duck_line_y), 2) 
    # Draw Vertical line (Punch Reload Axis)
    pygame.draw.line(screen, (255, 165, 0), (punch_zone_x, 0), (punch_zone_x, HEIGHT), 2) 
    # Draw Boss Hitbox (Yellow)
    pygame.draw.rect(screen, (255, 255, 0), boss_rect, 2)

    # --- Tracking & Input Logic ---
    player_hit = False
    nose_center = None

    if results.pose_landmarks and game_status == "playing":
        landmarks = results.pose_landmarks.landmark
        nose = landmarks[mp_pose.PoseLandmark.NOSE]
        left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
        right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
        
        nose_x = int(nose.x * WIDTH)
        nose_y = int(nose.y * HEIGHT)
        nose_center = (nose_x, nose_y)
        is_ducking = nose_y > duck_line_y

        lw_visible = left_wrist.visibility > 0.5
        rw_visible = right_wrist.visibility > 0.5

        lw_x, lw_y = int(left_wrist.x * WIDTH), int(left_wrist.y * HEIGHT)
        rw_x, rw_y = int(right_wrist.x * WIDTH), int(right_wrist.y * HEIGHT)
        
        # Visual tracking feedback for your head
        head_color = (0, 255, 0) if is_ducking else (255, 0, 0)
        pygame.draw.circle(screen, head_color, nose_center, 30, 3)

        # Draw cyan circles on wrists IF they are visible
        if lw_visible:
            color = (0, 255, 0) if left_arm_ready else (0, 255, 255)
            pygame.draw.circle(screen, color, (lw_x, lw_y), 20, 2)
        if rw_visible:
            color = (0, 255, 0) if right_arm_ready else (0, 255, 255)
            pygame.draw.circle(screen, color, (rw_x, rw_y), 20, 2)

        # --- PUNCH MECHANICS ---
        if boss_hp > 0:
            # 1. Check for Reloads
            if lw_visible and lw_x > punch_zone_x:
                left_arm_ready = True
            if rw_visible and rw_x > punch_zone_x:
                right_arm_ready = True

            # 2. Check for Hits
            hit_registered = False
            
            if lw_visible and left_arm_ready and (lw_x < punch_zone_x):
                if boss_rect.collidepoint(lw_x, lw_y):
                    hit_registered = True
                    left_arm_ready = False 
                    
            if rw_visible and right_arm_ready and (rw_x < punch_zone_x) and not hit_registered:
                if boss_rect.collidepoint(rw_x, rw_y):
                    hit_registered = True
                    right_arm_ready = False 

            # 3. Apply Damage
            if hit_registered:
                boss_hp -= 25 # Increased player damage per hit
                
                if boss_hp <= 0:
                    boss_hp = 0
                    current_state = "death"
                    frame_index = 0.0
                    sweeping_attack_rect = None
                    game_status = "won"
                elif current_state != "cleave": 
                    current_state = "take_hit"
                    frame_index = 0.0

    # --- Boss AI (Attacks) ---
    if current_state == "idle" and boss_hp > 0 and game_status == "playing":
        attack_timer += 1
        if attack_timer >= time_between_attacks:
            current_state = "cleave"
            frame_index = 0.0
            attack_timer = 0
            # Spawn attack moving left to right at head height
            sweeping_attack_rect = pygame.Rect(current_boss_x + 150, current_boss_y + 50, 100, 200)

    # --- Handle Attacks ---
    if sweeping_attack_rect and game_status == "playing":
        sweeping_attack_rect.x += attack_speed
        
        pygame.draw.rect(screen, (255, 50, 50), sweeping_attack_rect, border_radius=5)
        
        if nose_center and sweeping_attack_rect.collidepoint(nose_center):
            player_hit = True
            sweeping_attack_rect = None 
            
            player_hp -= 20 
            if player_hp <= 0:
                player_hp = 0
                game_status = "lost"

        elif sweeping_attack_rect.x > WIDTH:
            sweeping_attack_rect = None 

    # --- Animation Frame Management ---
    current_animation_list = boss_animations.get(current_state, [])
    if current_animation_list:
        frame_index += animation_speed
        if frame_index >= len(current_animation_list):
            if current_state == "death":
                frame_index = len(current_animation_list) - 1 
            else:
                frame_index = 0.0
                current_state = "idle"
        current_sprite = current_animation_list[int(frame_index)]
    else:
        current_sprite = pygame.Surface((350, 350))
        current_sprite.fill((255, 0, 255))

    # --- Rendering ---
    screen.blit(current_sprite, (current_boss_x, current_boss_y))

    if player_hit:
        flash = pygame.Surface((WIDTH, HEIGHT))
        flash.set_alpha(120)
        flash.fill((255, 0, 0))
        screen.blit(flash, (0, 0))

    # --- UI: Health Bars ---
    font = pygame.font.SysFont(None, 48)

    # Anvi HP Bar
    pygame.draw.rect(screen, (100, 100, 100), (50, 20, 400, 30))
    if boss_hp > 0:
        pygame.draw.rect(screen, (255, 0, 0), (50, 20, 400 * (boss_hp / max_boss_hp), 30))
    hp_text = font.render("Anvi HP", True, (255, 255, 255))
    screen.blit(hp_text, (50, 60))

    # Player HP Bar
    pygame.draw.rect(screen, (100, 100, 100), (WIDTH - 450, 20, 400, 30))
    if player_hp > 0:
        pygame.draw.rect(screen, (0, 255, 0), (WIDTH - 450, 20, 400 * (player_hp / max_player_hp), 30))
    player_hp_text = font.render("Player HP", True, (255, 255, 255))
    screen.blit(player_hp_text, (WIDTH - 450, 60))

    # --- End Game Screens ---
    if game_status == "lost":
        font_large = pygame.font.SysFont(None, 150)
        lost_text = font_large.render("YOU DIED", True, (255, 0, 0))
        screen.blit(lost_text, (WIDTH // 2 - lost_text.get_width() // 2, HEIGHT // 2 - 50))
        
        font_small = pygame.font.SysFont(None, 48)
        restart_text = font_small.render("Press 'R' to Restart", True, (255, 255, 255))
        screen.blit(restart_text, (WIDTH // 2 - restart_text.get_width() // 2, HEIGHT // 2 + 60))

    elif game_status == "won":
        font_large = pygame.font.SysFont(None, 150)
        won_text = font_large.render("VICTORY!", True, (255, 215, 0)) 
        screen.blit(won_text, (WIDTH // 2 - won_text.get_width() // 2, HEIGHT // 2 - 50))
        
        font_small = pygame.font.SysFont(None, 48)
        restart_text = font_small.render("Press 'R' to Restart", True, (255, 255, 255))
        screen.blit(restart_text, (WIDTH // 2 - restart_text.get_width() // 2, HEIGHT // 2 + 60))

    pygame.display.flip()
    clock.tick(60)

# ==========================================
# 5. CLEANUP
# ==========================================
cap.release()
pygame.quit()
sys.exit()

    