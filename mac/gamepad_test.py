import pygame

pygame.init()
pygame.joystick.init()

count = pygame.joystick.get_count()
print("연결된 게임패드 수:", count)

if count == 0:
    print("게임패드를 찾지 못했습니다.")
    raise SystemExit

pad = pygame.joystick.Joystick(0)
pad.init()

print("게임패드 이름:", pad.get_name())
print("축 개수:", pad.get_numaxes())
print("버튼 개수:", pad.get_numbuttons())
print("D-pad 개수:", pad.get_numhats())
print()
print("Xbox 컨트롤러를 움직여 보세요.")
print("종료: Ctrl+C")
print()

try:
    while True:
        for event in pygame.event.get():
            if event.type == pygame.JOYAXISMOTION:
                print(f"AXIS {event.axis}: {event.value:.3f}")
            elif event.type == pygame.JOYBUTTONDOWN:
                print(f"BUTTON {event.button}: DOWN")
            elif event.type == pygame.JOYBUTTONUP:
                print(f"BUTTON {event.button}: UP")
            elif event.type == pygame.JOYHATMOTION:
                print(f"HAT {event.hat}: {event.value}")
except KeyboardInterrupt:
    print("\n테스트 종료")
finally:
    pygame.quit()
