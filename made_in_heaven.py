from tkinter import *
from tkinter import messagebox
import pynput
import time
import ctypes
import random
from win32api import GetSystemMetrics
import math

SCRW = GetSystemMetrics(0)
SCRH = GetSystemMetrics(1)
TITLEBAR_HEIGHT = ctypes.windll.user32.GetSystemMetrics(4)
DT = 1000 // 60
REPLAYING_STATES_MESSAGES = ["Currently inactive.", "Recording...", "Waiting for hotkey to replay.", "Replaying..."]
START_BUTTON_MESSAGES = ["Start on hotkey.", "Waiting for hotkey."]
RECORD_BUTTON_MESSAGES = ["Record", "Recording..."]
REPLAY_BUTTON_MESSAGES = ["Replay", "Replayng..."]
curr_bul_id = 0

def is_float(text):
    try:
        float(text)
        return True
    except ValueError:
        return False

def entry_check(entry, check_func, transform_func, error_msg):
    text = entry.get()
    is_valid = check_func(text)
    if not is_valid:
        messagebox.showerror("Error", error_msg)
    else:
        return transform_func(text)

def mouse_eat_event(event, mouse):
    if event[3] == 0:  # move
        mouse.position = event[0], event[1]
    elif event[3] == 1:  # click
        if event[1]:
            mouse.press(event[0])
        else:
            mouse.release(event[0])
    else:  # scroll
        mouse.scroll(event[0], event[1])

def point_inside_rect(rx, ry, rw, rh, px, py):
    return rx <= px <= rx + rw and ry <= py <= ry + rh

def rect_inside_screen(rx, ry, rw, rh, add_space=True):
    return rx > SCRW + 100 * add_space or rx + rw < -100 * add_space or ry > SCRH + 100 * add_space or ry + rh < -100 * add_space

def run_into(sx, sy, targetx, targety, speed):
    dx = targetx - sx
    dy = targety - sy
    nx, ny = normalize(dx, dy)
    return nx * speed, ny * speed

def key_to_str(key):
    if hasattr(key, "name"):
        return key.name
    else:
        return key.char

def length(x, y):
    return (x ** 2 + y ** 2) ** 0.5

def normalize(x, y):
    leng = length(x, y)
    return x / leng, y / leng

def get_bul_id():
    global curr_bul_id
    curr_bul_id += 1
    return curr_bul_id - 1

class Bullet(Toplevel):
    def __init__(self, master, x, y, size=100):
        super().__init__(master)
        self.x, self.y = x, y
        self.width, self.height = size, size
        self.vx, self.vy = 0, 0
        self.ax, self.ay = 0, 0
        self.id = get_bul_id()
        self.geometry(f"{self.width}x{self.height}+{int(self.x)}+{int(self.y)}")

    def outside_screen(self):
        return rect_inside_screen(self.x, self.y, self.width, self.height)

    def update(self, bul_dict):
        self.geometry(f"+{int(self.x)}+{int(self.y)}")
        self.x += self.vx 
        self.y += self.vy
        self.vx += self.ax
        self.vy += self.ay
        if self.outside_screen():
            del bul_dict[self.id]
            self.destroy()

class Main:
    CLICK_MODE = 0
    HOLD_MODE = 2
    REBIND_MODE = 3
    RECORD_MODE = 4
    DODGE_MODE = 5
    def __init__(self, master):
        # ===== Init window and configure grid =====
        self.master = master
        master.title("[Made in Heaven]")
        self.master.grid_columnconfigure((0, 1), weight=1)  # to make them equal
        self.master.grid_rowconfigure((0, 1, 2), weight=1)  # to make them equal

        # ===== Menu bar =====
        self.menubar = Menu(self.master)
        self.modesmenu = Menu(self.menubar, tearoff=0)
        self.modesmenu.add_command(label="Click", command=lambda: self.switch_mode(Main.CLICK_MODE))
        self.modesmenu.add_command(label="Hold", command=lambda: self.switch_mode(Main.HOLD_MODE))
        self.modesmenu.add_command(label="Rebind", command=lambda: self.switch_mode(Main.REBIND_MODE))
        self.modesmenu.add_command(label="Record & Replay", command=lambda: self.switch_mode(Main.RECORD_MODE))
        self.modesmenu.add_command(label="", command=lambda: self.switch_mode(Main.DODGE_MODE))  # yes
        self.menubar.add_cascade(label="Modes", menu=self.modesmenu)
        self.master.config(menu=self.menubar)

        # ===== Click variables =====
        self.button_choice = StringVar()
        self.button_choice.set("left")
        self.clicking_allowed = False

        # ===== Click mode =====
        self.click_frame = LabelFrame(self.master, text="Click Mode", width=38)
        self.click_frame.columnconfigure((0, 1), weight=1)
        Label(self.click_frame, text="Amount of clicks:").grid(row=0, column=0, sticky=W)
        self.amount_of_clicks_entry = Entry(self.click_frame)
        self.amount_of_clicks_entry.grid(row=0, column=1, sticky=EW)
        Label(self.click_frame, text="Delay between clicks (ms):").grid(row=1, column=0, sticky=W)
        self.delay_between_clicks_entry = Entry(self.click_frame)
        self.delay_between_clicks_entry.grid(row=1, column=1, sticky=EW)
        self.click_frame.grid(row=0, columnspan=2, sticky=EW)

        # ===== Hold mode =====
        self.hold_frame = LabelFrame(self.master, text="Hold Mode", width=38)
        self.hold_frame.columnconfigure((0, 1), weight=1)
        Label(self.hold_frame, text="Holding duration (ms):").grid(row=0, column=0, sticky=W)
        self.hold_duration_entry = Entry(self.hold_frame)
        self.hold_duration_entry.grid(row=0, column=1, sticky=EW)

        # ===== Mouse Selection Options and Start Button =====
        self.mouse_sel_frame = LabelFrame(self.master, text="Mouse Selection Options", width=38)
        self.mouse_sel_frame.columnconfigure((0, 1), weight=1)
        self.left_button_radio = Radiobutton(self.mouse_sel_frame, text="Click left button", variable=self.button_choice, value="left")  # default
        self.left_button_radio.grid(row=0, column=0, sticky=W)
        self.right_button_radio = Radiobutton(self.mouse_sel_frame, text="Click right button", variable=self.button_choice, value="right")
        self.right_button_radio.grid(row=0, column=1, sticky=E)
        self.start_button = Button(self.mouse_sel_frame, text="Start on hotkey", command=self.toggle_clicking, width=38)
        self.start_button.grid(row=2, columnspan=2, sticky=EW)
        self.mouse_sel_frame.grid(row=1, columnspan=2, sticky=EW)

        # ===== Rebind mode =====
        self.key_label = Label(self.master, text="Press any key to rebind\nCurrent key is f6")

        # ===== Record & Replay mode =====
        self.record_mode_frame = LabelFrame(self.master, text="Record & Replay Mode")
        self.record_mode_frame.columnconfigure((0, 1), weight=1)
        Label(self.record_mode_frame, text="When recording, press hotkey to finish.\nPress hotkey again to replay.").grid(row=0, columnspan=2)
        self.recording_state_label = Label(self.record_mode_frame, text="Currently not recording...")
        self.recording_state_label.grid(row=1, columnspan=2)
        Label(self.record_mode_frame, text="Replay speed multiplier:").grid(row=2, column=0)
        self.speed_mult_entry = Entry(self.record_mode_frame)
        self.speed_mult_entry.grid(row=2, column=1)
        Label(self.record_mode_frame, text="Repeat:").grid(row=3, column=0)
        self.repeat_entry = Entry(self.record_mode_frame)
        self.repeat_entry.grid(row=3, column=1)
        #self.record_button = Button(self.record_mode_frame, text=RECORD_BUTTON_MESSAGES[0], command=lambda: (setattr(self, "recording_state", 1), self.saved_events.clear(), self.recording_state_label.config(text=RECORD_BUTTON_MESSAGES[1])))
        #self.record_button.grid(row=4, column=0, sticky=EW)
        #self.replay_button = Button(self.record_mode_frame, text=REPLAY_BUTTON_MESSAGES[0], command=lambda: (setattr(self, "events", self.saved_events.copy()), self.replay()))
        #self.replay_button.grid(row=4, column=1, sticky=EW)
        self.recording_state = 0  # 0 is for not working, 1 is for recording, 2 is forwaiting to replay and 3 is for replaying
        self.saved_events = []
        self.events = []

        # ===== Fight Mode =====
        self.restart_button = Button(self.master, text="Restart Game", command=lambda: self.switch_mode(Main.DODGE_MODE))

        # ===== Configure size and position =====
        self.width, self.height = 317, 137
        self.x, self.y = 0, 0
        self.master.resizable(False, False)
        self.master.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
        
        # ===== Keyboard and Mouse controlling =====
        self.current_mode = Main.CLICK_MODE
        self.start_key = pynput.keyboard.Key.f6 # for user binding
        def on_press(key):
            if self.binding:
                self.start_key = key
                self.key_label["text"] = f"Press any key to rebind\nCurrent key is {self.str_start_key}"
            else:
                if key == self.start_key:
                    if self.timer == -1:
                        if self.current_mode == Main.CLICK_MODE:
                            self.timer = int(self.amount_of_clicks_entry.get())
                            self.click_mode_click()
                        elif self.current_mode == Main.HOLD_MODE:
                            self.timer = int(self.hold_duration_entry.get())
                            self.hold_mode_hold()
                        elif self.current_mode == Main.RECORD_MODE:
                            if self.recording_state == 0 and self.saved_events:
                                self.recording_state = 3
                            else:
                                self.recording_state = (self.recording_state + 1) % 4
                            if self.recording_state == 3:
                                self.timer = entry_check(self.repeat_entry, lambda text: text.isdigit() and int(text) > 0, int, "Amount of times to repeat can only be a positive integer")
                                self.events = self.saved_events.copy()
                                self.replay()
                            self.recording_state_label["text"] = REPLAYING_STATES_MESSAGES[self.recording_state]
                    else:
                        self.timer = -1
                elif key == pynput.keyboard.Key.esc:
                    self.recording_state = 0
                    self.events.clear()
                    self.saved_events.clear()


        def on_move(x, y):
            self.mousex = x
            self.mousey = y
            if self.recording_state == 1:
                self.saved_events.append((x, y, time.time(), 0))

        def on_click(x, y, button, pressed):
            if self.recording_state == 1:
                self.saved_events.append((button, pressed, time.time(), 1))

        def on_scroll(x, y, dx, dy):
            if self.recording_state == 1:
                self.saved_events.append((dx, dy, time.time(), 2))

        self.binding = False
        self.mouse = pynput.mouse.Controller()
        self.keyboard_listener = pynput.keyboard.Listener(on_press=on_press)
        self.keyboard_listener.start()
        pynput.mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll).start()

        # ===== Minigame =====
        self.reset_game()

        # ===== Misc variables =====
        self.timer = -1

    def reset_game(self):
        self.x, self.y = self.master.winfo_x(), self.master.winfo_y()
        self.vx, self.vy = 0, 0
        self.ax, self.ay = 0, 0
        self.mousex, self.mousey = 0, 0
        self.game_timer = 0
        self.score_timer = 0
        self.delay_timer = 0
        self.difficulty = 1
        self.state = 1  # random.randint(1, 3)
        self.state_timer = 0
        self.bullets = {}
        self.dashed = True
        self.delta_angle = 45
        self.delta_delta_angle = 1

    def dash_into(self, targetx, targety):
        if length(self.vx, self.vy) > 2:
            self.ax = self.vx * -0.1
            self.ay = self.vy * -0.1
            self.dashed = True
        else:
            self.ax, self.ay = run_into(self.centerx, self.centery, targetx, targety, self.difficulty * 3)
            self.vx = self.vy = 0
            self.game_timer = 20 / (self.difficulty)
            self.dashed = False

    def game_update(self):
        player_lost = point_inside_rect(self.x, self.y, self.truewidth, self.trueheight, self.mousex, self.mousey)  # if player inside main window - they lose

        # ===== Do not update if start time is not 0 (so player can be ready for fight) =====
        if self.delay_timer > 0:
            self.delay_timer -= 1
            self.master.after(DT, self.game_update)
            return

        # ===== Update position and timers =====
        self.master.geometry(f"+{int(self.x)}+{int(self.y)}")
        self.x += self.vx 
        self.y += self.vy
        self.vx += self.ax
        self.vy += self.ay
        self.score_timer += self.difficulty * 10
        self.difficulty += self.score_timer * .5e-7
        self.state_timer += 1

        # ===== Update bullets =====
        for bul in self.bullets.copy().values():
            bul.update(self.bullets)
            player_lost |= point_inside_rect(bul.x, bul.y, bul.width, bul.height, self.mousex, self.mousey)

        # ===== Change state =====
        if self.state_timer >= 500:  # change state
            changed = False
            if self.dashed and self.state == 1 and 0 <= self.centerx <= SCRW and 0 <= self.centery <= SCRH:
                self.state = 2
                changed = True
            elif self.game_timer == 500 and self.state == 2:
                self.state = random.choice((1, 3))
                changed = True
            elif self.state == 3:
                self.state = 1
                changed = True
            if changed:
                self.ax = self.ay = self.vx = self.vy = 0
                # self.delay_timer = 20
                self.game_timer = 0
                self.state_timer = 0

        # ===== Update self depending on state =====
        if self.state == 1:
            if self.game_timer == 0:
                self.dash_into(self.mousex, self.mousey)
            else:
                self.game_timer = max(self.game_timer - 1, 0)
            if self.speed < 2:
                for i in range(1, 6):
                    bul = Bullet(self.master, self.centerx, self.centery)
                    bul.vx, bul.vy = run_into(bul.x, bul.y, self.mousex, self.mousey, 16)
                    bul.ax, bul.ay = bul.vx * -0.002 * i, bul.vy * -0.002 * i
                    self.bullets[bul.id] = bul
        elif self.state == 2:
            if self.game_timer % 10 == 0:
                for angle in range(0, 360 + 1, 45):
                    bul = Bullet(self.master, self.centerx, self.centery, 150)
                    a = math.radians(angle + self.delta_angle) + (self.difficulty + 1) ** 3
                    bul.ax, bul.ay = math.cos(a) * (self.difficulty + .1) ** 3, math.sin(a) * (self.difficulty + .1) ** 3
                    self.bullets[bul.id] = bul
            self.game_timer += 1
            self.delta_angle += self.delta_delta_angle
        elif self.state == 3:
            if length(SCRW / 2 - self.centerx, SCRH / 2 - self.centery) > 50:
                dx, dy = run_into(self.centerx, self.centery, SCRW / 2, SCRH / 2, 5)
                self.x += dx
                self.y += dy
            else:
                if self.game_timer % 5 == 0:
                    bul = Bullet(self.master, random.randint(0, SCRW), 5)
                    bul.ay = .2
                    bul.ax = random.uniform(-0.25, 0.25)
                    self.bullets[bul.id] = bul
            self.game_timer += 1
        # ===== If cursor touches window, player loses =====
        if player_lost:  # if cursor is inside window
            for bul in self.bullets.copy().values():
                bul.destroy()
            messagebox.showinfo("You lost!", f"Your score is {int(self.score_timer // 800)}")
        else:
            self.master.after(DT, self.game_update)

    @property
    def centerx(self):
        return self.x + self.truewidth / 2

    @property
    def centery(self):
        return self.y + self.trueheight / 2

    @property
    def str_start_key(self):
        return key_to_str(self.start_key)

    @property
    def selected_button(self):
        return  [pynput.mouse.Button.left, pynput.mouse.Button.right][self.button_choice.get() == "right"]

    @property
    def trueheight(self):
        return self.master.winfo_height()

    @property
    def truewidth(self):
        return self.master.winfo_width()

    @property
    def speed(self):
        return (self.vx ** 2 + self.vy ** 2) ** 0.5

    def switch_mode(self, mode):
        self.click_frame.grid_forget()
        self.hold_frame.grid_forget()
        self.key_label.place_forget()
        self.mouse_sel_frame.grid_forget()
        self.record_mode_frame.grid_forget()
        self.restart_button.place_forget()
        if mode == Main.CLICK_MODE:
            self.click_frame.grid(row=0, columnspan=2, sticky=EW)
            self.mouse_sel_frame.grid(row=1, columnspan=2, sticky=EW)
        elif mode == Main.HOLD_MODE:
            self.hold_frame.grid(row=0, columnspan=2, sticky=EW)
            self.mouse_sel_frame.grid(row=1, columnspan=2, sticky=EW)
        elif mode == Main.REBIND_MODE:
            self.key_label.place(relx=0.5, rely=0.5, anchor=CENTER)
        elif mode == Main.RECORD_MODE:
            self.record_mode_frame.grid(rowspan=2, columnspan=2, sticky=NSEW)
        elif mode == Main.DODGE_MODE:
            self.reset_game()
            self.delay_timer = 150
            self.master.after(DT, self.game_update)
            self.restart_button.place(relx=0.5, rely=0.5, anchor=CENTER)
        self.current_mode = mode
        self.binding = mode == Main.REBIND_MODE

    def click_check(self):
        if self.current_mode == Main.CLICK_MODE:
            return self.amount_of_clicks_entry.get().isdigit() and self.delay_between_clicks_entry.get().isdigit() and self.clicking_allowed
        elif self.current_mode == Main.HOLD_MODE:
            return self.hold_duration_entry.get().isdigit() and self.clicking_allowed

    def toggle_clicking(self):
        if self.clicking_allowed:
            self.start_button["text"] = START_BUTTON_MESSAGES[0]
            self.clicking_allowed = False
        else:
            if self.current_mode == Main.CLICK_MODE:
                amount = entry_check(self.amount_of_clicks_entry, lambda text: text.isdigit() and int(text) > 0, int, "Amount of clicks can only be a non-negative value")
                delay = entry_check(self.delay_between_clicks_entry, lambda text: text.isdigit() and int(text) > 0, int, "Delay between clicks can only be a non-negative value")
                if all((amount, delay)):
                    self.start_button["text"] = START_BUTTON_MESSAGES[1]
                    self.clicking_allowed = True
            elif self.current_mode == Main.HOLD_MODE:
                duration = entry_check(self.hold_duration_entry, lambda text: text.isdigit() and int(text) > 0, int, "Duration can only be a non-negative value")
                if duration:
                    self.start_button["text"] = START_BUTTON_MESSAGES[1]
                    self.clicking_allowed = True

    def click_mode_click(self):
        if self.timer > 0 and self.click_check():
            self.mouse.press(self.selected_button)
            self.mouse.release(self.selected_button)
            time.sleep(int(self.delay_between_clicks_entry.get()) / 1000)
            self.timer -= 1
            if self.timer == 0:
                self.timer = -1
                #self.toggle_clicking()
            self.master.after(0, self.click_mode_click)

    def hold_mode_hold(self):
        if not hasattr(self, "time_start"):
            self.time_start = time.time()
            self.mouse.press(self.selected_button)
        if self.timer <= 0:
            self.timer = -1
            del self.time_start
            self.mouse.release(self.selected_button)
        else:
            self.timer -= (time.time() - self.time_start) * 1000
            self.time_start = time.time()
            self.master.after(0, self.hold_mode_hold)

    def replay(self):
        if self.events:
            curr_event = self.events[0]
            mouse_eat_event(curr_event, self.mouse)
            if self.events:
                dt = self.events[1 % len(self.events)][2] - curr_event[2]
            else:
                dt = 0
            del self.events[0]
            self.master.after(int(round(dt * 1000 / entry_check(self.speed_mult_entry, lambda text: is_float(text) and float(text) > 0, float, "Replay speed multiplier is not a positive decimal"))), self.replay)  
        else:
            if self.timer > 1:
                self.timer -= 1
                self.events = self.saved_events.copy()
                self.master.after(1, self.replay)
            else:
                self.timer = -1
                self.recording_state = 0
                self.recording_state_label["text"] = REPLAYING_STATES_MESSAGES[0]
            


if __name__ == "__main__":
    master = Tk()
    main = Main(master)
    master.mainloop()