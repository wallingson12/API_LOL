import keyboard
import time

segurando_c = False


def alternar_c():
    global segurando_c

    if segurando_c:
        keyboard.release("c")
        segurando_c = False
    else:
        keyboard.press("c")
        segurando_c = True


def ativar_range():
    keyboard.add_hotkey("space", alternar_c)

    while True:
        time.sleep(1)
