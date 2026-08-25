import tkinter as tk
from tkinter import messagebox
import random

class Minesweeper:
    def __init__(self, root):
        self.root = root
        self.root.title("Minesweeper")
        
        # Cho phép thay đổi kích thước cửa sổ
        self.root.resizable(True, True)
        
        # Game settings
        self.difficulty = "beginner"
        self.rows = 9
        self.cols = 9
        self.mines = 10
        self.cell_size = 25
        
        self.game_over = False
        self.first_click = True
        self.seconds = 0
        self.timer_id = None
        self.mine_count = self.mines
        
        self.current_rows = self.rows
        self.current_cols = self.cols
        
        self.create_menu()
        self.create_ui()
        
    def create_menu(self):
        menubar = tk.Menu(self.root)
        
        game_menu = tk.Menu(menubar, tearoff=0)
        game_menu.add_command(label="New Game", command=self.new_game)
        game_menu.add_separator()
        
        diff_menu = tk.Menu(game_menu, tearoff=0)
        diff_menu.add_command(label="Beginner (9x9, 10)", command=lambda: self.set_level("beginner"))
        diff_menu.add_command(label="Intermediate (16x16, 40)", command=lambda: self.set_level("intermediate"))
        diff_menu.add_command(label="Expert (16x30, 99)", command=lambda: self.set_level("expert"))
        diff_menu.add_separator()
        diff_menu.add_command(label="Custom...", command=self.custom_level)
        game_menu.add_cascade(label="Level", menu=diff_menu)
        
        game_menu.add_separator()
        game_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="Game", menu=game_menu)
        
        self.root.config(menu=menubar)
        
    def custom_level(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Custom Level")
        dlg.transient(self.root)
        dlg.grab_set()
        
        tk.Label(dlg, text="Rows (5-50):").grid(row=0, column=0, padx=5, pady=5)
        rows_var = tk.StringVar(value=str(self.rows))
        tk.Entry(dlg, textvariable=rows_var, width=10).grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(dlg, text="Columns (5-50):").grid(row=1, column=0, padx=5, pady=5)
        cols_var = tk.StringVar(value=str(self.cols))
        tk.Entry(dlg, textvariable=cols_var, width=10).grid(row=1, column=1, padx=5, pady=5)
        
        tk.Label(dlg, text="Mines:").grid(row=2, column=0, padx=5, pady=5)
        mines_var = tk.StringVar(value=str(self.mines))
        tk.Entry(dlg, textvariable=mines_var, width=10).grid(row=2, column=1, padx=5, pady=5)
        
        def apply_custom():
            try:
                r = int(rows_var.get())
                c = int(cols_var.get())
                m = int(mines_var.get())
                
                if r < 5: r = 5
                if r > 50: r = 50 
                if c < 5: c = 5
                if c > 50: c = 50 
                
                if m >= r * c: m = (r * c) - 9
                if m < 1: m = 1
                
                self.rows, self.cols, self.mines = r, c, m
                self.difficulty = "custom"
                dlg.destroy()
                self.new_game()
            except ValueError:
                pass
                
        tk.Button(dlg, text="Play", command=apply_custom).grid(row=3, column=0, columnspan=2, pady=10)
        
    def set_level(self, level):
        self.difficulty = level
        if level == "beginner":
            self.rows, self.cols, self.mines = 9, 9, 10
        elif level == "intermediate":
            self.rows, self.cols, self.mines = 16, 16, 40
        else:
            self.rows, self.cols, self.mines = 16, 30, 99
        self.new_game()
        
    def create_ui(self):
        # Dọn dẹp giao diện cũ
        if hasattr(self, 'top_frame'):
            self.top_frame.destroy()
        if hasattr(self, 'board_wrapper'):
            self.board_wrapper.destroy()

        # --- TOP BAR ---
        self.top_frame = tk.Frame(self.root, bg="#c0c0c0", bd=2, relief=tk.RAISED)
        self.top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.mine_var = tk.StringVar(value=f"{self.mine_count:03d}")
        tk.Label(self.top_frame, textvariable=self.mine_var, font=("Courier", 16, "bold"), 
                 width=4, bg="black", fg="red").pack(side=tk.LEFT, padx=10, pady=5)
        
        self.face_btn = tk.Button(self.top_frame, text="🙂", font=("Arial", 14), width=3,
                               command=self.new_game, bg="#c0c0c0")
        # Center the face button
        self.face_btn.pack(side=tk.LEFT, expand=True, pady=5)
        
        self.timer_var = tk.StringVar(value="000")
        tk.Label(self.top_frame, textvariable=self.timer_var, font=("Courier", 16, "bold"),
                 width=4, bg="black", fg="red").pack(side=tk.RIGHT, padx=10, pady=5)
        
        # --- SCROLLABLE BOARD AREA ---
        # Container bọc bàn cờ (có hỗ trợ co giãn)
        self.board_wrapper = tk.Frame(self.root, bg="#808080")
        self.board_wrapper.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        # Canvas để làm thanh cuộn
        self.canvas = tk.Canvas(self.board_wrapper, bg="#808080", highlightthickness=0)
        
        self.vsb = tk.Scrollbar(self.board_wrapper, orient="vertical", command=self.canvas.yview)
        self.hsb = tk.Scrollbar(self.board_wrapper, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Game frame nằm bên trong Canvas
        self.game_frame = tk.Frame(self.canvas, bg="#808080", bd=3, relief=tk.SUNKEN)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.game_frame, anchor="nw")
        
        # Cập nhật thanh cuộn khi kích thước bàn cờ thay đổi
        def on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.game_frame.bind("<Configure>", on_frame_configure)
        
        self.color_unrevealed = "#c0c0c0"
        self.color_revealed = "#d9d9d9"
        
        self.buttons = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                btn = tk.Button(self.game_frame, width=2, height=1, font=("Arial", 9, "bold"),
                              bg=self.color_unrevealed, relief=tk.RAISED, bd=2,
                              command=lambda r=r, c=c: self.click(r, c))
                # Dùng sticky="nsew" để các nút co giãn khít nhau
                btn.grid(row=r, column=c, sticky="nsew")
                btn.bind('<Button-3>', lambda e, r=r, c=c: self.right_click(r, c))
                btn.bind('<Double-Button-1>', lambda e, r=r, c=c: self.chord(r, c))
                row.append(btn)
            self.buttons.append(row)
            
        self.reset_state()
        self.adjust_window_size()
        
    def adjust_window_size(self):
        # Tính toán để ép giao diện vừa với màn hình
        self.root.update_idletasks()
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        req_width = self.root.winfo_reqwidth()
        req_height = self.root.winfo_reqheight()
        
        # Giới hạn cửa sổ tối đa bằng 80% kích thước màn hình
        max_width = int(screen_width * 0.8)
        max_height = int(screen_height * 0.8)
        
        win_width = min(req_width, max_width)
        win_height = min(req_height, max_height)
        
        # Chỉnh luôn kích thước canvas ban đầu
        self.canvas.config(width=win_width - 30, height=win_height - 100)
        
        # Canh giữa màn hình
        x = (screen_width - win_width) // 2
        y = (screen_height - win_height) // 2
        self.root.geometry(f"{win_width}x{win_height}+{x}+{y}")
        
    def reset_state(self):
        self.game_over = False
        self.first_click = True
        self.mine_count = self.mines
        self.mine_var.set(f"{self.mine_count:03d}")
        self.seconds = 0
        self.timer_var.set("000")
        
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
            
        for r in range(self.rows):
            for c in range(self.cols):
                btn = self.buttons[r][c]
                btn.config(text="", bg=self.color_unrevealed, relief=tk.RAISED, state=tk.NORMAL)
                
        self.flags = [[False]*self.cols for _ in range(self.rows)]
        self.revealed = [[False]*self.cols for _ in range(self.rows)]
        self.mines_pos = set()
        self.face_btn.config(text="🙂")
        
    def new_game(self):
        if self.current_rows != self.rows or self.current_cols != self.cols:
            self.current_rows = self.rows
            self.current_cols = self.cols
            self.create_ui()
        else:
            self.reset_state()
            
    def click(self, r, c):
        if self.game_over or self.flags[r][c]:
            return
            
        if self.first_click:
            self.first_click = False
            self.place_mines(r, c)
            self.start_timer()
            
        if (r, c) in self.mines_pos:
            self.lose(r, c)
            return
            
        self.reveal(r, c)
        self.check_win()
        
    def right_click(self, r, c):
        if self.game_over or self.revealed[r][c]:
            return
            
        btn = self.buttons[r][c]
        if not self.flags[r][c]:
            if self.mine_count > 0:
                self.flags[r][c] = True
                btn.config(text="🚩", fg="red")
                self.mine_count -= 1
        else:
            self.flags[r][c] = False
            btn.config(text="")
            self.mine_count += 1
            
        self.mine_var.set(f"{max(0,self.mine_count):03d}")
        
    def chord(self, r, c):
        if not self.revealed[r][c]:
            return
        count = self.count_mines(r, c)
        flags = sum(1 for nr, nc in self.neighbors(r, c) if self.flags[nr][nc])
        if flags == count:
            for nr, nc in self.neighbors(r, c):
                if not self.revealed[nr][nc] and not self.flags[nr][nc]:
                    self.click(nr, nc)
                    
    def place_mines(self, first_r, first_c):
        safe = { (first_r, first_c) } | set(self.neighbors(first_r, first_c))
        available = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in safe]
        actual_mines = min(self.mines, len(available))
        self.mines_pos = set(random.sample(available, actual_mines))
        
    def neighbors(self, r, c):
        result = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0: continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    result.append((nr, nc))
        return result
        
    def count_mines(self, r, c):
        return sum(1 for nr, nc in self.neighbors(r, c) if (nr, nc) in self.mines_pos)
        
    def reveal(self, start_r, start_c):
        if self.revealed[start_r][start_c] or self.flags[start_r][start_c]:
            return
            
        stack = [(start_r, start_c)]
        colors = ["blue", "green", "red", "darkblue", "darkred", "cyan", "black", "gray"]
        
        while stack:
            r, c = stack.pop()
            
            if self.revealed[r][c] or self.flags[r][c]:
                continue
                
            self.revealed[r][c] = True
            btn = self.buttons[r][c]
            count = self.count_mines(r, c)
            
            if count > 0:
                btn.config(text=str(count), fg=colors[count-1], bg=self.color_revealed, relief=tk.SUNKEN)
            else:
                btn.config(bg=self.color_revealed, relief=tk.SUNKEN)
                for nr, nc in self.neighbors(r, c):
                    if not self.revealed[nr][nc] and not self.flags[nr][nc]:
                        stack.append((nr, nc))
                    
    def lose(self, hit_r, hit_c):
        self.game_over = True
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
        self.face_btn.config(text="😵")
        
        for r in range(self.rows):
            for c in range(self.cols):
                btn = self.buttons[r][c]
                if (r, c) in self.mines_pos:
                    if r == hit_r and c == hit_c:
                        btn.config(bg="red", text="💣")
                    else:
                        btn.config(text="💣")
                elif self.flags[r][c]:
                    btn.config(text="❌")
                    
        messagebox.showinfo("Game Over", "Bùm! Bạn đạp trúng mìn rồi!")
        
    def check_win(self):
        revealed = sum(1 for r in range(self.rows) for c in range(self.cols) if self.revealed[r][c])
        if revealed == self.rows * self.cols - self.mines:
            self.game_over = True
            if self.timer_id:
                self.root.after_cancel(self.timer_id)
                self.timer_id = None
            self.face_btn.config(text="😎")
            
            for r, c in self.mines_pos:
                self.buttons[r][c].config(text="🚩", fg="red")
                
            messagebox.showinfo("You Win!", "Tuyệt vời, phá đảo thành công!")
            
    def start_timer(self):
        self.seconds = 0
        self.update_timer()
        
    def update_timer(self):
        self.timer_var.set(f"{min(999,self.seconds):03d}")
        self.timer_id = self.root.after(1000, self.update_timer)
        self.seconds += 1

if __name__ == "__main__":
    root = tk.Tk()
    Minesweeper(root)
    root.mainloop()