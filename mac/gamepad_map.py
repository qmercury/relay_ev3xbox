import time

import pygame

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("Xbox 컨트롤러를 찾지 못했습니다.")
    raise SystemExit

pad = pygame.joystick.Joystick(0)
pad.init()

print("게임패드:", pad.get_name())
print("축:", pad.get_numaxes())
print("버튼:", pad.get_numbuttons())
print()
print("현재 모든 입력값을 표시합니다.")
print("스틱, 트리거, D-pad, 버튼을 하나씩 조작해 보세요.")
print("종료: Ctrl+C")
print()

try:
    while True:
        pygame.event.pump()

        axes = [round(pad.get_axis(i), 2) for i in range(pad.get_numaxes())]
        buttons = [pad.get_button(i) for i in range(pad.get_numbuttons())]
        pressed = [i for i, value in enumerate(buttons) if value]

        print(
            f"\rAXIS {axes}   BUTTON DOWN {pressed}          ",
            end="",
            flush=True,
        )
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\n테스트 종료")
finally:
    pygame.quit()
