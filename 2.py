# -*- coding: utf-8 -*-
"""
QUIZ MILLIONAIRE - GPU ACCELERATED BUILD (PyQt6)
================================================
Yêu cầu cài đặt:
    pip install PyQt6 opencv-python

File chạy kèm:
    quest.txt
    settings.json (tự tạo khi lưu cài đặt)
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget
)

# ============================================================
# PATHS / DEFAULTS
# ============================================================

APP_DIR = Path(__file__).resolve().parent
QUEST_FILE = APP_DIR / "quest.txt"
SETTINGS_FILE = APP_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "loop_video": True,
    "question_background": "",
    "answered_background": "",
    "correct_background": "",
    "wrong_background": "",
}


# ============================================================
# DATA
# ============================================================

@dataclass
class Question:
    number: int
    text: str
    answers: list[str]
    money: str
    correct_index: int = 0


# ============================================================
# FILE HELPERS
# ============================================================

def load_settings() -> dict:
    result = DEFAULT_SETTINGS.copy()
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result.update(data)
    except Exception:
        pass
    return result


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def unescape_quoted_text(text: str) -> str:
    text = text.replace(r"\"", '"')
    text = text.replace(r"\\", "\\")
    return text


def parse_quest_file(path: Path) -> list[Question]:
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {path.name}.\n\nHãy tạo quest.txt cùng thư mục với file Python."
        )

    questions: list[Question] = []
    pattern = re.compile(r"^\s*q(\d+)\s*:\s*(.*)$", re.IGNORECASE)

    for line_no, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = pattern.match(line)
        if not match:
            raise ValueError(f"Sai định dạng quest.txt ở dòng {line_no}:\n\n{raw_line}")

        number = int(match.group(1))
        body = match.group(2)
        parts = re.findall(r'"((?:\\.|[^"\\])*)"', body)

        if len(parts) not in (6, 7):
            raise ValueError(
                f"Dòng {line_no} phải có 6 hoặc 7 phần trong dấu ngoặc kép:\n"
                f"1 câu hỏi + 4 đáp án + số tiền + (tùy chọn) đáp án đúng.\n\n{raw_line}"
            )

        parts = [unescape_quoted_text(p) for p in parts]
        question_text = parts[0]
        answers = parts[1:5]
        money = parts[5]
        correct_index = 0

        if len(parts) == 7:
            correct = parts[6].strip().upper()
            if correct in {"A", "B", "C", "D"}:
                correct_index = ord(correct) - ord("A")
            elif correct in {"0", "1", "2", "3"}:
                correct_index = int(correct)
            else:
                raise ValueError(
                    f"Dòng {line_no}: đáp án đúng phải là A/B/C/D (hoặc 0/1/2/3), nhận được: {parts[6]!r}"
                )

        questions.append(
            Question(
                number=number,
                text=question_text,
                answers=answers,
                money=money,
                correct_index=correct_index,
            )
        )

    if not questions:
        raise ValueError("quest.txt không có câu hỏi hợp lệ.")

    questions.sort(key=lambda q: q.number)
    return questions


def is_video_file(path: str) -> bool:
    return Path(path).suffix.lower() in {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}


def is_image_file(path: str) -> bool:
    return Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


# ============================================================
# GPU BACKGROUND RENDERER & THREADING
# ============================================================

class VideoThread(QThread):
    """Luồng giải mã video riêng biệt để giải phóng CPU chính."""
    frame_signal = pyqtSignal(QImage)

    def __init__(self, video_path: str, loop: bool = True):
        super().__init__()
        self.video_path = video_path
        self.loop = loop
        self.running = True

    def run(self):
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        delay = int(1000 / (fps if fps and fps > 1 else 30))

        while self.running:
            ret, frame = cap.read()
            if not ret:
                if self.loop:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    break

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            q_img = QImage(rgb_frame.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
            self.frame_signal.emit(q_img)
            self.msleep(delay)

        cap.release()

    def stop(self):
        self.running = False
        self.wait()


class GPUBackgroundContainer(QWidget):
    """Widget vẽ toàn bộ hình ảnh/video trực tiếp bằng GPU (Direct3D/OpenGL)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pixmap = None
        self.video_thread = None
        self.source_path = ""

    def set_background(self, path: str, loop: bool = True):
        self.stop_background()
        self.source_path = path or ""

        if not self.source_path or not Path(self.source_path).exists():
            self.current_pixmap = None
            self.update()
            return

        if is_video_file(self.source_path):
            self.video_thread = VideoThread(self.source_path, loop)
            self.video_thread.frame_signal.connect(self._on_video_frame)
            self.video_thread.start()
        elif is_image_file(self.source_path):
            image = QImage(self.source_path)
            if not image.isNull():
                self.current_pixmap = QPixmap.fromImage(image)
                self.update()

    def _on_video_frame(self, q_img: QImage):
        self.current_pixmap = QPixmap.fromImage(q_img)
        self.update()

    def stop_background(self):
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#07162E"))

        if self.current_pixmap and not self.current_pixmap.isNull():
            w, h = self.width(), self.height()
            pw, ph = self.current_pixmap.width(), self.current_pixmap.height()

            if pw > 0 and ph > 0:
                scale = max(w / pw, h / ph)
                nw, nh = int(pw * scale), int(ph * scale)

                # Vẽ Scaled Cover bằng GPU
                scaled = self.current_pixmap.scaled(
                    nw, nh,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                x = (w - nw) // 2
                y = (h - nh) // 2
                painter.drawPixmap(x, y, scaled)


# ============================================================
# MAIN APPLICATION WINDOW
# ============================================================

class MillionaireQuizApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quiz Millionaire - GPU Accelerated")
        self.resize(1280, 720)
        self.setMinimumSize(1000, 620)

        self.settings = load_settings()
        self.questions: list[Question] = []
        self.current_index = 0
        self.answer_locked = False

        # Container chứa GPU background
        self.bg_container = GPUBackgroundContainer(self)
        self.setCentralWidget(self.bg_container)

        # Trục chứa các trang UI
        self.main_layout = QVBoxLayout(self.bg_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

        # Các giao diện
        self.home_view = QWidget()
        self.settings_view = QWidget()
        self.quiz_view = QWidget()
        self.finished_view = QWidget()

        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.settings_view)
        self.stack.addWidget(self.quiz_view)
        self.stack.addWidget(self.finished_view)

        self.setup_styles()
        self.show_home()

    def setup_styles(self):
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI';
            }
            QFrame#Card {
                background-color: rgba(7, 27, 60, 230);
                border: 2px solid #1B65AD;
                border-radius: 12px;
            }
            QPushButton {
                background-color: #1A62AA;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #2C82CE;
            }
            QPushButton:disabled {
                background-color: #0C2C55;
                color: #557096;
            }
            QLineEdit {
                background-color: #07162E;
                color: white;
                border: 1px solid #1B65AD;
                border-radius: 4px;
                padding: 6px;
            }
            QCheckBox {
                color: white;
                font-size: 13px;
            }
        """)

    # --------------------------------------------------------
    # HOME
    # --------------------------------------------------------

    def show_home(self):
        self.bg_container.stop_background()
        self.bg_container.set_background("")

        # Re-build layout
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_sub = QLabel("QUIZ")
        lbl_sub.setStyleSheet("color: #F5F8FF; font-size: 24px; font-weight: bold;")
        lbl_title = QLabel("MILLIONAIRE")
        lbl_title.setStyleSheet("color: #FFD84A; font-size: 42px; font-weight: bold;")
        lbl_desc = QLabel("Trả lời câu hỏi • Leo thang tiền thưởng")
        lbl_desc.setStyleSheet("color: #AFC7E8; font-size: 14px; margin-bottom: 20px;")

        card_layout.addWidget(lbl_sub, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_desc, alignment=Qt.AlignmentFlag.AlignCenter)

        btn_box = QHBoxLayout()
        btn_start = QPushButton("BẮT ĐẦU")
        btn_start.clicked.connect(self.start_quiz)
        btn_settings = QPushButton("CÀI ĐẶT")
        btn_settings.clicked.connect(self.show_settings)

        btn_box.addWidget(btn_start)
        btn_box.addWidget(btn_settings)
        card_layout.addLayout(btn_box)

        lbl_note = QLabel("quest.txt phải nằm cùng thư mục.\nCó thể thêm \"A\"/\"B\"/\"C\"/\"D\" ở cuối để chỉ đáp án đúng.")
        lbl_note.setStyleSheet("color: #7E97BA; font-size: 11px; margin-top: 20px;")
        lbl_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_note)

        layout.addWidget(card)

        self.stack.removeWidget(self.home_view)
        self.home_view = widget
        self.stack.addWidget(self.home_view)
        self.stack.setCurrentWidget(self.home_view)

    # --------------------------------------------------------
    # SETTINGS
    # --------------------------------------------------------

    def show_settings(self):
        self.bg_container.stop_background()
        self.bg_container.set_background("")

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 30, 30, 30)

        lbl_title = QLabel("CÀI ĐẶT NỀN")
        lbl_title.setStyleSheet("color: #FFD84A; font-size: 26px; font-weight: bold;")
        card_layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        fields = [
            ("question_background", "Nền HIỂN THỊ CÂU HỎI:"),
            ("answered_background", "Nền khi ĐÃ CHỌN:"),
            ("correct_background", "Nền khi TRẢ LỜI ĐÚNG:"),
            ("wrong_background", "Nền khi TRẢ LỜI SAI:"),
        ]

        self.setting_inputs = {}

        for key, label_text in fields:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
            lbl.setFixedWidth(200)

            inp = QLineEdit(self.settings.get(key, ""))
            self.setting_inputs[key] = inp

            btn_browse = QPushButton("CHỌN")
            btn_browse.clicked.connect(lambda _, x=inp: self._browse_file(x))

            row.addWidget(lbl)
            row.addWidget(inp)
            row.addWidget(btn_browse)
            card_layout.addLayout(row)

        self.chk_loop = QCheckBox("Lặp video liên tục")
        self.chk_loop.setChecked(bool(self.settings.get("loop_video", True)))
        card_layout.addWidget(self.chk_loop)

        btn_box = QHBoxLayout()
        btn_save = QPushButton("LƯU & QUAY LẠI")
        btn_save.clicked.connect(self._save_settings_and_back)
        btn_back = QPushButton("QUAY LẠI")
        btn_back.clicked.connect(self.show_home)

        btn_box.addWidget(btn_back)
        btn_box.addWidget(btn_save)
        card_layout.addLayout(btn_box)

        layout.addWidget(card)

        self.stack.removeWidget(self.settings_view)
        self.settings_view = widget
        self.stack.addWidget(self.settings_view)
        self.stack.setCurrentWidget(self.settings_view)

    def _browse_file(self, target_input: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh hoặc video", "",
            "Tất cả (*.png *.jpg *.jpeg *.mp4 *.avi *.mov *.mkv *.webm);;Video (*.mp4 *.avi *.mov *.mkv);;Ảnh (*.png *.jpg *.jpeg)"
        )
        if path:
            target_input.setText(path)

    def _save_settings_and_back(self):
        for key, inp in self.setting_inputs.items():
            self.settings[key] = inp.text().strip()
        self.settings["loop_video"] = self.chk_loop.isChecked()
        save_settings(self.settings)
        self.show_home()

    # --------------------------------------------------------
    # QUIZ
    # --------------------------------------------------------

    def start_quiz(self):
        try:
            self.questions = parse_quest_file(QUEST_FILE)
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi quest.txt", str(exc))
            return

        self.current_index = 0
        self.show_question()

    def show_question(self):
        self.bg_container.set_background(
            self.settings.get("question_background", ""),
            self.settings.get("loop_video", True)
        )

        q = self.questions[self.current_index]
        self.answer_locked = False

        widget = QWidget()
        main_h_layout = QHBoxLayout(widget)
        main_h_layout.setContentsMargins(20, 20, 20, 20)

        # Left Column (Top + Question + Answers + Controls)
        left_box = QVBoxLayout()

        # Top Bar
        top_frame = QFrame()
        top_frame.setObjectName("Card")
        top_layout = QHBoxLayout(top_frame)
        lbl_q_num = QLabel(f"CÂU {self.current_index + 1}/{len(self.questions)}")
        lbl_q_num.setStyleSheet("color: #FFD84A; font-size: 18px; font-weight: bold;")
        lbl_money = QLabel(f"💰 {q.money}")
        lbl_money.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")

        top_layout.addWidget(lbl_q_num)
        top_layout.addStretch()
        top_layout.addWidget(lbl_money)
        left_box.addWidget(top_frame)

        # Question Box
        q_frame = QFrame()
        q_frame.setObjectName("Card")
        q_layout = QVBoxLayout(q_frame)
        lbl_q_text = QLabel(q.text)
        lbl_q_text.setWordWrap(True)
        lbl_q_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_q_text.setStyleSheet("color: white; font-size: 22px; font-weight: bold;")
        q_layout.addWidget(lbl_q_text)
        left_box.addWidget(q_frame, stretch=2)

        # Answers Grid
        ans_grid = QGridLayout()
        self.ans_buttons = []
        letters = ["A", "B", "C", "D"]

        for idx, letter in enumerate(letters):
            btn = QPushButton(f"{letter}.  {q.answers[idx]}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(15, 49, 100, 220);
                    border: 2px solid #1B65AD;
                    text-align: left;
                    font-size: 15px;
                    padding: 15px;
                }
                QPushButton:hover {
                    background-color: #174B8D;
                }
            """)
            btn.clicked.connect(lambda _, i=idx: self.select_answer(i))
            ans_grid.addWidget(btn, idx // 2, idx % 2)
            self.ans_buttons.append(btn)

        left_box.addLayout(ans_grid, stretch=2)

        # Result & Navigation Bar
        ctrl_layout = QHBoxLayout()
        self.lbl_result = QLabel("")
        self.lbl_result.setStyleSheet("font-size: 14px; font-weight: bold;")

        btn_exit = QPushButton("THOÁT")
        btn_exit.clicked.connect(self.show_home)

        self.btn_next = QPushButton("CÂU TIẾP")
        self.btn_next.setEnabled(False)
        self.btn_next.clicked.connect(self.next_question)

        ctrl_layout.addWidget(self.lbl_result)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(btn_exit)
        ctrl_layout.addWidget(self.btn_next)

        left_box.addLayout(ctrl_layout)
        main_h_layout.addLayout(left_box, stretch=3)

        # Right Column (Money Ladder)
        ladder_frame = QFrame()
        ladder_frame.setObjectName("Card")
        ladder_layout = QVBoxLayout(ladder_frame)

        lbl_ladder_head = QLabel("TIỀN THƯỞNG")
        lbl_ladder_head.setStyleSheet("color: #FFD84A; font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        lbl_ladder_head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ladder_layout.addWidget(lbl_ladder_head)

        for i in range(len(self.questions) - 1, -1, -1):
            lbl_item = QLabel(f"{i + 1:02d}   {self.questions[i].money}")
            lbl_item.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if i == self.current_index:
                lbl_item.setStyleSheet("background-color: #F4A300; color: #08162E; font-weight: bold; padding: 4px 10px; border-radius: 4px;")
            else:
                lbl_item.setStyleSheet("color: #EAF2FF; padding: 4px 10px;")
            ladder_layout.addWidget(lbl_item)

        main_h_layout.addWidget(ladder_frame, stretch=1)

        self.stack.removeWidget(self.quiz_view)
        self.quiz_view = widget
        self.stack.addWidget(self.quiz_view)
        self.stack.setCurrentWidget(self.quiz_view)

    def select_answer(self, selected_index: int):
        if self.answer_locked:
            return

        self.answer_locked = True
        self.bg_container.set_background(
            self.settings.get("answered_background", ""),
            self.settings.get("loop_video", True)
        )

        self.ans_buttons[selected_index].setStyleSheet("""
            background-color: #F4A300; color: #08162E;
            font-weight: bold; border: 2px solid #FFD84A; font-size: 15px; padding: 15px;
        """)

        QTimer.singleShot(700, lambda: self.reveal_answer(selected_index))

    def reveal_answer(self, selected_index: int):
        correct_index = self.questions[self.current_index].correct_index

        if selected_index == correct_index:
            self.bg_container.set_background(
                self.settings.get("correct_background", ""),
                self.settings.get("loop_video", True)
            )
            self.ans_buttons[correct_index].setStyleSheet("""
                background-color: #16A34A; color: white;
                font-weight: bold; border: 2px solid #7CFF9B; font-size: 15px; padding: 15px;
            """)
            self.lbl_result.setText("✔ CHÍNH XÁC! Trả lời đúng.")
            self.lbl_result.setStyleSheet("color: #7CFF9B; font-size: 14px; font-weight: bold;")
        else:
            self.bg_container.set_background(
                self.settings.get("wrong_background", ""),
                self.settings.get("loop_video", True)
            )
            self.ans_buttons[selected_index].setStyleSheet("""
                background-color: #D92D20; color: white;
                font-weight: bold; border: 2px solid #FF8D8D; font-size: 15px; padding: 15px;
            """)
            self.ans_buttons[correct_index].setStyleSheet("""
                background-color: #16A34A; color: white;
                font-weight: bold; border: 2px solid #7CFF9B; font-size: 15px; padding: 15px;
            """)
            self.lbl_result.setText("✘ SAI! Đáp án đúng đã được đánh dấu xanh.")
            self.lbl_result.setStyleSheet("color: #FF8D8D; font-size: 14px; font-weight: bold;")

        for i, btn in enumerate(self.ans_buttons):
            if i not in (selected_index, correct_index):
                btn.setStyleSheet("""
                    background-color: rgba(10, 39, 77, 180); color: #8098BC;
                    border: 1px solid #1B65AD; font-size: 15px; padding: 15px;
                """)

        self.btn_next.setEnabled(True)

    def next_question(self):
        if self.current_index >= len(self.questions) - 1:
            self.show_finished()
            return
        self.current_index += 1
        self.show_question()

    # --------------------------------------------------------
    # FINISHED
    # --------------------------------------------------------

    def show_finished(self):
        self.bg_container.set_background(
            self.settings.get("correct_background", ""),
            self.settings.get("loop_video", True)
        )

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(50, 50, 50, 50)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_win = QLabel("🎉 HOÀN THÀNH!")
        lbl_win.setStyleSheet("color: #FFD84A; font-size: 32px; font-weight: bold;")
        lbl_desc = QLabel("Đã đi hết bộ câu hỏi.")
        lbl_desc.setStyleSheet("color: #F5F8FF; font-size: 16px;")

        card_layout.addWidget(lbl_win, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_desc, alignment=Qt.AlignmentFlag.AlignCenter)

        if self.questions:
            lbl_money = QLabel(f"Mốc cuối: {self.questions[-1].money}")
            lbl_money.setStyleSheet("color: #7CFF9B; font-size: 20px; font-weight: bold; margin: 15px 0;")
            card_layout.addWidget(lbl_money, alignment=Qt.AlignmentFlag.AlignCenter)

        btn_box = QHBoxLayout()
        btn_replay = QPushButton("CHƠI LẠI")
        btn_replay.clicked.connect(self.start_quiz)
        btn_home = QPushButton("TRANG CHỦ")
        btn_home.clicked.connect(self.show_home)

        btn_box.addWidget(btn_replay)
        btn_box.addWidget(btn_home)
        card_layout.addLayout(btn_box)

        layout.addWidget(card)

        self.stack.removeWidget(self.finished_view)
        self.finished_view = widget
        self.stack.addWidget(self.finished_view)
        self.stack.setCurrentWidget(self.finished_view)

    def closeEvent(self, event):
        self.bg_container.stop_background()
        event.accept()


# ============================================================
# MAIN
# ============================================================

def main():
    app = QApplication(sys.argv)
    window = MillionaireQuizApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
