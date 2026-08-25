import tkinter as tk
import random

class GoogleSnakeClone:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Snake (6-in-1 Gamemodes)")
        self.root.resizable(False, False)

        # Cấu hình game
        self.width = 500
        self.height = 500
        self.cell_size = 25
        self.cols = self.width // self.cell_size
        self.rows = self.height // self.cell_size

        self.mode = "classic"
        self.score = 0
        self.high_score = 0
        self.game_over = False
        
        self.setup_ui()
        self.reset_game()

    def setup_ui(self):
        # Tạo Menu để chọn Gamemode
        menubar = tk.Menu(self.root)
        
        game_menu = tk.Menu(menubar, tearoff=0)
        game_menu.add_command(label="Chơi lại (F2)", command=self.reset_game)
        game_menu.add_separator()
        
        mode_menu = tk.Menu(game_menu, tearoff=0)
        mode_menu.add_command(label="🍎 Classic (Bình thường)", command=lambda: self.set_mode("classic"))
        mode_menu.add_command(label="👻 Đi Xuyên Tường", command=lambda: self.set_mode("no_wall"))
        mode_menu.add_command(label="☠️ Táo Độc", command=lambda: self.set_mode("poison"))
        mode_menu.add_command(label="🧱 Sinh Tường", command=lambda: self.set_mode("wall"))
        mode_menu.add_command(label="🌀 Portal (Cổng Không Gian)", command=lambda: self.set_mode("portal"))
        mode_menu.add_command(label="🏃 Táo Chạy", command=lambda: self.set_mode("moving"))
        
        game_menu.add_cascade(label="Chế độ chơi (Gamemodes)", menu=mode_menu)
        game_menu.add_separator()
        game_menu.add_command(label="Thoát", command=self.root.quit)
        menubar.add_cascade(label="Game", menu=game_menu)
        
        self.root.config(menu=menubar)

        # Thanh hiển thị điểm
        top_frame = tk.Frame(self.root, bg="#4A752C")
        top_frame.pack(fill=tk.X)

        self.score_var = tk.StringVar(value="Điểm: 0 | Cao nhất: 0")
        tk.Label(top_frame, textvariable=self.score_var, font=("Arial", 14, "bold"),
                 bg="#4A752C", fg="white").pack(side=tk.LEFT, padx=10, pady=5)

        self.mode_var = tk.StringVar(value="Mode: 🍎 Classic")
        tk.Label(top_frame, textvariable=self.mode_var, font=("Arial", 12, "bold"),
                 bg="#4A752C", fg="#A3D152").pack(side=tk.RIGHT, padx=10, pady=5)

        # Bản vẽ game
        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height, bg="#AAD751", highlightthickness=0)
        self.canvas.pack()

        # Nút điều khiển
        self.root.bind("<Key>", self.change_direction)
        self.root.bind("<F2>", lambda e: self.reset_game())

    def set_mode(self, mode):
        self.mode = mode
        modes_vi = {
            "classic": "🍎 Classic",
            "no_wall": "👻 Xuyên Tường",
            "poison": "☠️ Táo Độc",
            "wall": "🧱 Sinh Tường",
            "portal": "🌀 Portal",
            "moving": "🏃 Táo Chạy"
        }
        self.mode_var.set(f"Mode: {modes_vi[mode]}")
        self.reset_game()

    def get_random_empty_pos(self):
        # Tìm ô trống không có rắn, tường, táo độc hay portal
        available = []
        for c in range(self.cols):
            for r in range(self.rows):
                pos = (c, r)
                if (pos not in self.snake and 
                    pos != getattr(self, 'apple', None) and 
                    pos not in self.walls and 
                    pos not in self.poison_apples and 
                    pos not in self.portals):
                    available.append(pos)
        return random.choice(available) if available else None

    def reset_game(self):
        # Khởi tạo lại trạng thái
        self.snake = [(5, 5), (4, 5), (3, 5)]
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.direction_changed = False
        
        self.score = 0
        self.score_var.set(f"Điểm: {self.score} | Cao nhất: {self.high_score}")
        self.game_over = False

        self.walls = []
        self.poison_apples = []
        self.portals = []
        self.apple_timer = 0
        self.apple = (-1, -1)

        # Setup riêng cho từng Mode
        if self.mode == "portal":
            self.portals = [self.get_random_empty_pos(), self.get_random_empty_pos()]

        self.apple = self.get_random_empty_pos()

        # Hủy vòng lặp cũ nếu có
        if hasattr(self, 'timer_id') and self.timer_id:
            self.root.after_cancel(self.timer_id)

        self.update_game()

    def change_direction(self, event):
        # Ngăn lỗi bấm đúp 2 phím cực nhanh khiến rắn tự cắn đuôi (180 độ)
        if self.direction_changed: return
        key = event.keysym.lower()
        
        if key in ["up", "w"] and self.direction != (0, 1):
            self.next_direction = (0, -1)
            self.direction_changed = True
        elif key in ["down", "s"] and self.direction != (0, -1):
            self.next_direction = (0, 1)
            self.direction_changed = True
        elif key in ["left", "a"] and self.direction != (1, 0):
            self.next_direction = (-1, 0)
            self.direction_changed = True
        elif key in ["right", "d"] and self.direction != (-1, 0):
            self.next_direction = (1, 0)
            self.direction_changed = True

    def update_game(self):
        if self.game_over: return

        self.direction = self.next_direction
        self.direction_changed = False
        
        head_x, head_y = self.snake[0]
        dir_x, dir_y = self.direction
        new_head = (head_x + dir_x, head_y + dir_y)

        # LOGIC: Portal (Dịch chuyển không gian)
        if self.mode == "portal" and self.portals:
            if new_head == self.portals[0]:
                new_head = self.portals[1]
            elif new_head == self.portals[1]:
                new_head = self.portals[0]

        # LOGIC: Đi xuyên tường
        if self.mode == "no_wall":
            new_head = (new_head[0] % self.cols, new_head[1] % self.rows)
        else:
            if not (0 <= new_head[0] < self.cols and 0 <= new_head[1] < self.rows):
                self.game_over = True

        # LOGIC: Va chạm
        if not self.game_over:
            if new_head in self.snake or new_head in self.walls or new_head in self.poison_apples:
                self.game_over = True

        if self.game_over:
            self.draw_game_over()
            return

        self.snake.insert(0, new_head)

        # LOGIC: Ăn Táo
        if new_head == self.apple:
            self.score += 1
            if self.score > self.high_score: self.high_score = self.score
            self.score_var.set(f"Điểm: {self.score} | Cao nhất: {self.high_score}")

            self.apple = self.get_random_empty_pos()

            if self.mode == "poison":
                # Sinh thêm táo độc rải rác
                self.poison_apples = []
                for _ in range(self.score // 2 + 1):
                    pos = self.get_random_empty_pos()
                    if pos: self.poison_apples.append(pos)
                    
            elif self.mode == "wall":
                # Sinh thêm gạch chắn đường
                pos = self.get_random_empty_pos()
                if pos: self.walls.append(pos)
                
            elif self.mode == "portal":
                # Đổi chỗ 2 cổng portal
                p1 = self.get_random_empty_pos()
                p2 = self.get_random_empty_pos()
                if p1 and p2: self.portals = [p1, p2]
                
            elif self.mode == "moving":
                self.apple_timer = 0
        else:
            self.snake.pop()

        # LOGIC: Táo Tự Chạy
        if self.mode == "moving":
            self.apple_timer += 1
            if self.apple_timer > 30: # Cứ sau ~3 giây táo chạy chỗ khác
                self.apple = self.get_random_empty_pos()
                self.apple_timer = 0

        self.draw()
        
        # Tăng dần tốc độ khi điểm cao
        speed = max(50, 110 - (self.score * 2))
        self.timer_id = self.root.after(speed, self.update_game)

    def draw(self):
        self.canvas.delete("all")

        # Vẽ nền caro phong cách Google Snake
        for r in range(self.rows):
            for c in range(self.cols):
                color = "#AAD751" if (r + c) % 2 == 0 else "#A2D149"
                x = c * self.cell_size
                y = r * self.cell_size
                self.canvas.create_rectangle(x, y, x+self.cell_size, y+self.cell_size, fill=color, outline="")

        # Vẽ Portals
        if self.portals and len(self.portals) == 2:
            for idx, (px, py) in enumerate(self.portals):
                color = "#4169E1" if idx == 0 else "#FF8C00" # Cổng xanh, cổng cam
                x, y = px * self.cell_size, py * self.cell_size
                self.canvas.create_oval(x+1, y+1, x+self.cell_size-1, y+self.cell_size-1, fill=color, outline="white", width=2)

        # Vẽ Tường
        for wx, wy in self.walls:
            x, y = wx * self.cell_size, wy * self.cell_size
            self.canvas.create_rectangle(x, y, x+self.cell_size, y+self.cell_size, fill="#795548", outline="#3E2723")

        # Vẽ Táo độc
        for px, py in self.poison_apples:
            x, y = px * self.cell_size, py * self.cell_size
            self.canvas.create_oval(x+3, y+3, x+self.cell_size-3, y+self.cell_size-3, fill="#800080", outline="black")

        # Vẽ Táo thường
        if self.apple:
            ax, ay = self.apple
            x, y = ax * self.cell_size, ay * self.cell_size
            self.canvas.create_oval(x+3, y+3, x+self.cell_size-3, y+self.cell_size-3, fill="#E7471D", outline="#C13010")

        # Vẽ Rắn
        for idx, (sx, sy) in enumerate(self.snake):
            x, y = sx * self.cell_size, sy * self.cell_size
            color = "#385C22" if idx == 0 else "#46732C" # Đầu rắn đậm màu hơn thân
            self.canvas.create_rectangle(x, y, x+self.cell_size, y+self.cell_size, fill=color, outline="")

    def draw_game_over(self):
        # Màn hình thua
        self.canvas.create_rectangle(self.width/2 - 120, self.height/2 - 40, 
                                     self.width/2 + 120, self.height/2 + 40, fill="#2c2c2c")
        self.canvas.create_text(self.width/2, self.height/2 - 10, 
                                text="GAME OVER", fill="#FF5252", font=("Arial", 22, "bold"))
        self.canvas.create_text(self.width/2, self.height/2 + 15, 
                                text="Bấm phím [F2] để chơi lại", fill="white", font=("Arial", 12))

if __name__ == "__main__":
    root = tk.Tk()
    GoogleSnakeClone(root)
    root.mainloop()