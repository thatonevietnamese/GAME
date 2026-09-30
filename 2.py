# -*- coding: utf-8 -*-
"""
QUIZ MILLIONAIRE - CUSTOM UI EDITION (PyQt6 Native Media)
=========================================================
Yêu cầu cài đặt:
    pip install PyQt6
"""

from __future__ import annotations

import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QUrl, QSize
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QSlider, QStackedWidget, QVBoxLayout, QWidget
)

# ============================================================
# PATHS / DEFAULTS
# ============================================================

APP_DIR = Path(__file__).resolve().parent
DEFAULT_QUEST_FILE = APP_DIR / "quest.txt"
SETTINGS_FILE = APP_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "quest_file": str(DEFAULT_QUEST_FILE),
    "loop_video": True,
    "question_background": "",
    "answered_background": "",
    "correct_background": "",
    "wrong_background": "",
    "reveal_delay": 1.5,
    "ladder_delay": 1.0,
    "card_opacity": 85,
    "blink_speed": 200,
    "blink_count": 6,
    "q_y_pos": 55,          # Vị trí Y ô câu hỏi (% màn hình)
    "q_height": 90,         # Chiều cao ô câu hỏi (px)
    "ans_y_pos": 72,        # Vị trí Y bảng đáp án (% màn hình)
    "ladder_x_pos": 78,     # Vị trí X thang tiền (% màn hình)
    "ladder_y_pos": 15,     # Vị trí Y thang tiền (% màn hình)
    "ladder_width": 20,     # Độ rộng thang tiền (% màn hình)
}


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class Question:
    number: int
    text: str
    answers: list[str]
    money: str
    correct_index: int = 0
    image_path: str = ""
    hint: str = ""


# ============================================================
# FILE HELPERS & PARSER
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


def is_video_file(path: str) -> bool:
    return Path(path).suffix.lower() in {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}


def is_image_file(path: str) -> bool:
    return Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def parse_quest_file(path_str: str) -> list[Question]:
    path = Path(path_str) if path_str else DEFAULT_QUEST_FILE
    if not path.exists():
        path = DEFAULT_QUEST_FILE

    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file câu hỏi:\n{path}\n\nHãy chọn hoặc tạo file quest.txt hợp lệ."
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

        if len(parts) < 6:
            raise ValueError(
                f"Dòng {line_no} cần tối thiểu 6 phần trong ngoặc kép (1 câu hỏi + 4 đáp án + số tiền).\n\n{raw_line}"
            )

        parts = [unescape_quoted_text(p) for p in parts]
        question_text = parts[0]
        answers = parts[1:5]
        money = parts[5]
        correct_index = 0
        image_path = ""
        hint = ""

        if len(parts) >= 7:
            correct = parts[6].strip().upper()
            if correct in {"A", "B", "C", "D"}:
                correct_index = ord(correct) - ord("A")
            elif correct in {"0", "1", "2", "3"}:
                correct_index = int(correct)

        if len(parts) >= 8:
            p8 = parts[7].strip()
            if is_image_file(p8) or is_video_file(p8):
                image_path = p8
            else:
                hint = p8

        if len(parts) >= 9:
            hint = parts[8].strip()

        questions.append(
            Question(
                number=number,
                text=question_text,
                answers=answers,
                money=money,
                correct_index=correct_index,
                image_path=image_path,
                hint=hint
            )
        )

    if not questions:
        raise ValueError("File câu hỏi không có dữ liệu hợp lệ.")

    questions.sort(key=lambda q: q.number)
    return questions


# ============================================================
# CUSTOM POINTED BOX (KHUNG 2 ĐẦU NHỌN)
# ============================================================

class PointedBox(QWidget):
    clicked = pyqtSignal()

    def __init__(self, text: str = "", parent=None, is_button: bool = False):
        super().__init__(parent)
        self.text = text
        self.is_button = is_button
        self.bg_color = QColor(7, 22, 46, 230)
        self.border_color = QColor(27, 101, 173)
        self.text_color = QColor(255, 255, 255)
        self.font_size = 11
        self.is_hovered = False
        self.is_usable = True

        if is_button:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(80, 35)

    def minimumSizeHint(self) -> QSize:
        return QSize(40, 25)

    def set_colors(self, bg: str | QColor, border: str | QColor, text: str | QColor = "#FFFFFF"):
        self.bg_color = QColor(bg) if isinstance(bg, str) else bg
        self.border_color = QColor(border) if isinstance(border, str) else border
        self.text_color = QColor(text) if isinstance(text, str) else text
        self.update()

    def set_text(self, text: str):
        self.text = text
        self.update()

    def set_usable(self, usable: bool):
        self.is_usable = usable
        if not usable:
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
            self.set_colors("#222222", "#555555", "#777777")
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()

    def enterEvent(self, event):
        if self.is_button and self.is_usable:
            self.is_hovered = True
            self.update()

    def leaveEvent(self, event):
        if self.is_button and self.is_usable:
            self.is_hovered = False
            self.update()

    def mousePressEvent(self, event):
        if self.is_button and self.is_usable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = float(self.width()), float(self.height())
        cut = min(h * 0.35, w * 0.18, 15.0)

        path = QPainterPath()
        path.moveTo(cut, 0)
        path.lineTo(w - cut, 0)
        path.lineTo(w, h / 2.0)
        path.lineTo(w - cut, h)
        path.lineTo(cut, h)
        path.lineTo(0, h / 2.0)
        path.closeSubpath()

        fill_color = self.bg_color
        if self.is_button and self.is_hovered and self.is_usable:
            fill_color = fill_color.lighter(125)

        painter.fillPath(path, fill_color)

        pen = QPen(self.border_color, 2)
        painter.setPen(pen)
        painter.drawPath(path)

        if self.text:
            painter.setPen(self.text_color)
            font = QFont("Segoe UI", self.font_size, QFont.Weight.Bold)
            painter.setFont(font)

            text_rect = QRectF(cut, 0, w - (cut * 2), h)
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self.text
            )


# ============================================================
# BACKGROUND CONTAINER (AUDIO + VIDEO SUPPORT)
# ============================================================

class NativeBackgroundContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pixmap = None
        self.source_path = ""

        self.video_widget = QVideoWidget(self)
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)

        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.audio_output.setVolume(1.0)

        self.video_widget.lower()
        self.video_widget.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.video_widget.setGeometry(self.rect())

    def set_background(self, path: str, loop: bool = True):
        if self.source_path == path and path != "":
            return

        self.stop_background()
        self.source_path = path or ""

        if not self.source_path or not Path(self.source_path).exists():
            self.current_pixmap = None
            self.update()
            return

        if is_video_file(self.source_path):
            self.current_pixmap = None
            self.video_widget.setGeometry(self.rect())
            self.video_widget.show()
            self.video_widget.lower()

            if loop:
                self.media_player.setLoops(QMediaPlayer.Loops.Infinite)
            else:
                self.media_player.setLoops(QMediaPlayer.Loops.Once)

            self.media_player.setSource(QUrl.fromLocalFile(self.source_path))
            self.media_player.play()

        elif is_image_file(self.source_path):
            self.video_widget.hide()
            image = QImage(self.source_path)
            if not image.isNull():
                self.current_pixmap = QPixmap.fromImage(image)
                self.update()

    def stop_background(self):
        self.media_player.stop()
        self.video_widget.hide()

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
        self.setWindowTitle("Quiz Millionaire - Custom UI Edition")
        self.resize(1280, 720)
        self.setMinimumSize(960, 580)

        self.settings = load_settings()
        self.questions: list[Question] = []
        self.current_index = 0
        self.answer_locked = False
        self.active_timers: list[QTimer] = []

        self.used_5050 = False
        self.used_hint = False
        self.used_phone = False

        self.bg_container = NativeBackgroundContainer(self)
        self.setCentralWidget(self.bg_container)

        self.main_layout = QVBoxLayout(self.bg_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)

        self.home_view = QWidget()
        self.settings_view = QWidget()
        self.quiz_view = QWidget()
        self.finished_view = QWidget()

        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.settings_view)
        self.stack.addWidget(self.quiz_view)
        self.stack.addWidget(self.finished_view)

        self.apply_global_styles()
        self.show_home()

    def clear_active_timers(self):
        for t in self.active_timers:
            t.stop()
            t.deleteLater()
        self.active_timers.clear()

    def apply_global_styles(self):
        opacity_pct = int(self.settings.get("card_opacity", 85))
        alpha = int((opacity_pct / 100.0) * 255)

        self.setStyleSheet(f"""
            QWidget {{
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }}
            QFrame#Card {{
                background-color: rgba(7, 22, 46, {alpha});
                border: 2px solid #1B65AD;
                border-radius: 8px;
            }}
            QPushButton {{
                background-color: #1A62AA;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #3381D0;
                border-radius: 6px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: #2C82CE;
            }}
            QLineEdit {{
                background-color: #07162E;
                color: white;
                border: 1px solid #1B65AD;
                border-radius: 4px;
                padding: 4px;
            }}
            QCheckBox, QLabel {{
                color: white;
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: #07162E;
                border: 1px solid #1B65AD;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #FFD84A;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }}
        """)

    def animate_blink(self, widget: PointedBox | QLabel, colors_a: tuple, colors_b: tuple, count: int, interval_ms: int, on_finished=None):
        timer = QTimer(self)
        state = {"step": 0}

        def toggle():
            if state["step"] >= count:
                timer.stop()
                if timer in self.active_timers:
                    self.active_timers.remove(timer)
                timer.deleteLater()

                if isinstance(widget, PointedBox):
                    widget.set_colors(colors_a[0], colors_a[1], colors_a[2])
                elif isinstance(widget, QLabel):
                    widget.setStyleSheet(colors_a[0])

                if on_finished:
                    on_finished()
                return

            cur_colors = colors_a if state["step"] % 2 == 0 else colors_b
            if isinstance(widget, PointedBox):
                widget.set_colors(cur_colors[0], cur_colors[1], cur_colors[2])
            elif isinstance(widget, QLabel):
                widget.setStyleSheet(cur_colors[0])

            state["step"] += 1

        timer.timeout.connect(toggle)
        self.active_timers.append(timer)
        timer.start(interval_ms)

    # --------------------------------------------------------
    # HOME VIEW
    # --------------------------------------------------------

    def show_home(self):
        self.clear_active_timers()
        self.bg_container.stop_background()
        self.bg_container.set_background("")

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 30, 40, 30)

        lbl_sub = QLabel("QUIZ")
        lbl_sub.setStyleSheet("color: #F5F8FF; font-size: 20px; font-weight: bold;")
        lbl_title = QLabel("MILLIONAIRE")
        lbl_title.setStyleSheet("color: #FFD84A; font-size: 38px; font-weight: bold;")

        card_layout.addWidget(lbl_sub, alignment=Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        btn_box = QHBoxLayout()
        btn_start = QPushButton("BẮT ĐẦU CHƠI")
        btn_start.clicked.connect(self.start_quiz)
        btn_settings = QPushButton("CÀI ĐẶT UI & VỊ TRÍ")
        btn_settings.clicked.connect(self.show_settings)

        btn_box.addWidget(btn_start)
        btn_box.addWidget(btn_settings)
        card_layout.addLayout(btn_box)

        layout.addWidget(card)

        self.stack.removeWidget(self.home_view)
        self.home_view = widget
        self.stack.addWidget(self.home_view)
        self.stack.setCurrentWidget(self.home_view)

    # --------------------------------------------------------
    # SETTINGS VIEW
    # --------------------------------------------------------

    def show_settings(self):
        self.clear_active_timers()
        self.bg_container.stop_background()
        self.bg_container.set_background("")

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        card_left = QFrame()
        card_left.setObjectName("Card")
        left_layout = QVBoxLayout(card_left)
        left_layout.setContentsMargins(15, 15, 15, 15)

        lbl_title = QLabel("CÀI ĐẶT BỐ CỤC & VỊ TRÍ UI")
        lbl_title.setStyleSheet("color: #FFD84A; font-size: 18px; font-weight: bold;")
        left_layout.addWidget(lbl_title, alignment=Qt.AlignmentFlag.AlignCenter)

        fields = [
            ("quest_file", "File câu hỏi (.txt):", "txt"),
            ("question_background", "Nền câu hỏi:", "all"),
            ("answered_background", "Nền đã chọn:", "all"),
            ("correct_background", "Nền trả lời đúng:", "all"),
            ("wrong_background", "Nền trả lời sai:", "all"),
        ]

        self.setting_inputs = {}
        for key, label_text, ftype in fields:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 11px;")
            lbl.setFixedWidth(110)
            inp = QLineEdit(str(self.settings.get(key, "")))
            self.setting_inputs[key] = inp
            btn_browse = QPushButton("Chọn")
            btn_browse.clicked.connect(lambda _, x=inp, t=ftype: self._browse_file(x, t))
            row.addWidget(lbl)
            row.addWidget(inp)
            row.addWidget(btn_browse)
            left_layout.addLayout(row)

        self.sliders = {}

        def add_pos_slider(key, label_text, min_v, max_v, default_v, suffix="%"):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("font-size: 11px; font-weight: bold;")
            lbl.setFixedWidth(150)

            sld = QSlider(Qt.Orientation.Horizontal)
            sld.setRange(min_v, max_v)
            sld.setValue(int(self.settings.get(key, default_v)))

            val_lbl = QLabel(f"{sld.value()}{suffix}")
            val_lbl.setFixedWidth(40)
            sld.valueChanged.connect(lambda v: (val_lbl.setText(f"{v}{suffix}"), self._update_preview_canvas()))

            row.addWidget(lbl)
            row.addWidget(sld)
            row.addWidget(val_lbl)
            left_layout.addLayout(row)
            self.sliders[key] = sld

        add_pos_slider("q_y_pos", "Vị trí Y Ô câu hỏi:", 10, 80, 55)
        add_pos_slider("q_height", "Chiều cao Ô câu hỏi:", 50, 160, 90, "px")
        add_pos_slider("ans_y_pos", "Vị trí Y Bảng đáp án:", 40, 90, 72)
        add_pos_slider("ladder_x_pos", "Vị trí X Thang tiền:", 50, 90, 78)
        add_pos_slider("ladder_y_pos", "Vị trí Y Thang tiền:", 5, 50, 15)
        add_pos_slider("ladder_width", "Độ rộng Thang tiền:", 15, 40, 20)

        self.chk_loop = QCheckBox("Lặp video nền liên tục")
        self.chk_loop.setChecked(bool(self.settings.get("loop_video", True)))
        left_layout.addWidget(self.chk_loop)

        btn_box = QHBoxLayout()
        btn_save = QPushButton("LƯU & BẮT ĐẦU")
        btn_save.clicked.connect(self._save_settings_and_back)
        btn_back = QPushButton("HỦY")
        btn_back.clicked.connect(self.show_home)
        btn_box.addWidget(btn_back)
        btn_box.addWidget(btn_save)
        left_layout.addLayout(btn_box)

        layout.addWidget(card_left, stretch=3)

        card_right = QFrame()
        card_right.setObjectName("Card")
        right_layout = QVBoxLayout(card_right)
        right_layout.setContentsMargins(15, 15, 15, 15)

        lbl_prev_title = QLabel("SƠ ĐỒ BỐ CỤC UI (PREVIEW)")
        lbl_prev_title.setStyleSheet("color: #FFD84A; font-size: 15px; font-weight: bold;")
        lbl_prev_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(lbl_prev_title)

        self.preview_canvas = QWidget()
        self.preview_canvas.setStyleSheet("background-color: #040D1A; border: 2px solid #1B65AD; border-radius: 6px;")
        right_layout.addWidget(self.preview_canvas, stretch=1)

        layout.addWidget(card_right, stretch=2)

        self.stack.removeWidget(self.settings_view)
        self.settings_view = widget
        self.stack.addWidget(self.settings_view)
        self.stack.setCurrentWidget(self.settings_view)

        QTimer.singleShot(100, self._update_preview_canvas)

    def _update_preview_canvas(self):
        if not hasattr(self, "preview_canvas") or not self.preview_canvas.isVisible():
            return

        cw, ch = self.preview_canvas.width(), self.preview_canvas.height()
        if cw <= 0 or ch <= 0:
            return

        for child in self.preview_canvas.findChildren(QWidget):
            child.deleteLater()

        qy = (self.sliders["q_y_pos"].value() / 100.0) * ch
        qh = (self.sliders["q_height"].value() / 720.0) * ch
        ay = (self.sliders["ans_y_pos"].value() / 100.0) * ch
        lx = (self.sliders["ladder_x_pos"].value() / 100.0) * cw
        ly = (self.sliders["ladder_y_pos"].value() / 100.0) * ch
        lw = (self.sliders["ladder_width"].value() / 100.0) * cw

        box_q = PointedBox("CÂU HỎI MẪU", self.preview_canvas)
        box_q.set_colors("rgba(26, 98, 170, 200)", "#FFD84A")
        box_q.setGeometry(int(cw * 0.05), int(qy), int(cw * 0.68), int(max(qh, 25)))
        box_q.show()

        ans_w = int(cw * 0.33)
        ans_h = int(ch * 0.1)
        for i in range(4):
            ax = int(cw * 0.05) if i % 2 == 0 else int(cw * 0.05 + ans_w + 10)
            row_y = int(ay) + (i // 2) * (ans_h + 5)
            box_a = PointedBox(f"{chr(65+i)}. Đáp án", self.preview_canvas)
            box_a.set_colors("rgba(15, 49, 100, 200)", "#1B65AD")
            box_a.setGeometry(ax, row_y, ans_w, ans_h)
            box_a.show()

        box_l = QFrame(self.preview_canvas)
        box_l.setStyleSheet("background-color: rgba(7, 22, 46, 220); border: 1px solid #FFD84A; border-radius: 4px;")
        box_l.setGeometry(int(lx), int(ly), int(lw), int(ch * 0.75))
        lbl_l = QLabel("THANG TIỀN", box_l)
        lbl_l.setStyleSheet("color: #FFD84A; font-size: 10px; font-weight: bold;")
        lbl_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_l.setGeometry(0, 5, int(lw), 20)
        box_l.show()

    def _browse_file(self, target_input: QLineEdit, ftype: str = "all"):
        if ftype == "txt":
            filter_str = "Text Files (*.txt);;All Files (*.*)"
        else:
            filter_str = "Tất cả (*.png *.jpg *.jpeg *.mp4 *.avi *.mov *.mkv *.webm);;All Files (*.*)"

        path, _ = QFileDialog.getOpenFileName(self, "Chọn file", "", filter_str)
        if path:
            target_input.setText(path)

    def _save_settings_and_back(self):
        for key, inp in self.setting_inputs.items():
            self.settings[key] = inp.text().strip()

        for key, sld in self.sliders.items():
            self.settings[key] = sld.value()

        self.settings["loop_video"] = self.chk_loop.isChecked()
        save_settings(self.settings)
        self.apply_global_styles()
        self.start_quiz()

    # --------------------------------------------------------
    # QUIZ VIEW & LIFELINES
    # --------------------------------------------------------

    def start_quiz(self):
        try:
            quest_path = self.settings.get("quest_file", str(DEFAULT_QUEST_FILE))
            self.questions = parse_quest_file(quest_path)
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi đọc File Câu Hỏi", str(exc))
            return

        self.current_index = 0
        self.used_5050 = False
        self.used_hint = False
        self.used_phone = False
        self.show_question()

    def show_question(self):
        self.clear_active_timers()
        self.bg_container.set_background(
            self.settings.get("question_background", ""),
            self.settings.get("loop_video", True)
        )

        q = self.questions[self.current_index]
        self.answer_locked = False

        widget = QWidget()

        q_y_pct = self.settings.get("q_y_pos", 55) / 100.0
        q_h_px = self.settings.get("q_height", 90)
        ans_y_pct = self.settings.get("ans_y_pos", 72) / 100.0
        lad_x_pct = self.settings.get("ladder_x_pos", 78) / 100.0
        lad_y_pct = self.settings.get("ladder_y_pos", 15) / 100.0
        lad_w_pct = self.settings.get("ladder_width", 20) / 100.0

        top_frame = QFrame(widget)
        top_frame.setObjectName("Card")
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(15, 5, 15, 5)

        lbl_q_num = QLabel(f"CÂU {self.current_index + 1}/{len(self.questions)}")
        lbl_q_num.setStyleSheet("color: #FFD84A; font-size: 15px; font-weight: bold;")
        top_layout.addWidget(lbl_q_num)

        self.box_question = PointedBox(q.text, widget)
        self.box_question.set_colors("rgba(7, 22, 46, 230)", "#1B65AD", "#FFFFFF")

        self.ans_buttons = []
        letters = ["A", "B", "C", "D"]
        for idx, letter in enumerate(letters):
            btn = PointedBox(f"{letter}:  {q.answers[idx]}", widget, is_button=True)
            btn.set_colors("rgba(15, 49, 100, 230)", "#1B65AD", "#FFFFFF")
            btn.clicked.connect(lambda i=idx: self.select_answer(i))
            self.ans_buttons.append(btn)

        self.ladder_frame = QFrame(widget)
        self.ladder_frame.setObjectName("Card")
        ladder_layout = QVBoxLayout(self.ladder_frame)
        ladder_layout.setContentsMargins(8, 8, 8, 8)

        lifeline_box = QHBoxLayout()
        lifeline_box.setSpacing(6)

        self.btn_5050 = PointedBox("50:50", is_button=True)
        self.btn_5050.font_size = 10
        self.btn_5050.set_colors("#1A62AA", "#3381D0")
        self.btn_5050.clicked.connect(self.use_lifeline_5050)
        if self.used_5050:
            self.btn_5050.set_usable(False)

        self.btn_hint = PointedBox("GỢI Ý", is_button=True)
        self.btn_hint.font_size = 10
        self.btn_hint.set_colors("#1A62AA", "#3381D0")
        self.btn_hint.clicked.connect(self.use_lifeline_hint)
        if self.used_hint:
            self.btn_hint.set_usable(False)

        self.btn_phone = PointedBox("GỌI ĐIỆN", is_button=True)
        self.btn_phone.font_size = 9
        self.btn_phone.set_colors("#1A62AA", "#3381D0")
        self.btn_phone.clicked.connect(self.use_lifeline_phone)
        if self.used_phone:
            self.btn_phone.set_usable(False)

        lifeline_box.addWidget(self.btn_5050)
        lifeline_box.addWidget(self.btn_hint)
        lifeline_box.addWidget(self.btn_phone)

        ladder_layout.addLayout(lifeline_box)

        lbl_head = QLabel("THANG TIỀN")
        lbl_head.setStyleSheet("color: #FFD84A; font-size: 12px; font-weight: bold; margin-top: 4px;")
        lbl_head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ladder_layout.addWidget(lbl_head)

        self.ladder_labels = []
        active_label = None

        for i in range(len(self.questions) - 1, -1, -1):
            lbl_item = QLabel(f"{i + 1:02d} • {self.questions[i].money}")
            lbl_item.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            if i == self.current_index:
                lbl_item.setStyleSheet("background-color: #F4A300; color: #08162E; font-weight: bold; padding: 2px 6px; border-radius: 3px;")
                active_label = lbl_item
            elif i < self.current_index:
                lbl_item.setStyleSheet("color: #22C55E; font-weight: bold; padding: 2px 6px;")
            else:
                lbl_item.setStyleSheet("color: #EAF2FF; padding: 2px 6px;")

            ladder_layout.addWidget(lbl_item)
            self.ladder_labels.append((i, lbl_item))

        ctrl_frame = QWidget(widget)
        ctrl_layout = QHBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(10, 0, 10, 0)

        btn_exit = QPushButton("THOÁT")
        btn_exit.clicked.connect(self.quit_game_with_money)

        self.btn_next = QPushButton("CÂU TIẾP ➔")
        self.btn_next.setEnabled(False)
        self.btn_next.clicked.connect(self.next_question)

        ctrl_layout.addStretch()
        ctrl_layout.addWidget(btn_exit)
        ctrl_layout.addWidget(self.btn_next)

        def layout_reposition(event=None):
            W, H = widget.width(), widget.height()
            if W <= 0 or H <= 0:
                return

            top_frame.setGeometry(int(W * 0.03), 10, int(W * 0.7), 40)

            qw = int(W * 0.7)
            qy = int(H * q_y_pct)
            self.box_question.setGeometry(int(W * 0.03), qy, qw, q_h_px)

            ay = int(H * ans_y_pct)
            aw = int((qw - 15) / 2)
            ah = int(min((H - ay - 50) / 2, 50))
            for i, b in enumerate(self.ans_buttons):
                bx = int(W * 0.03) if i % 2 == 0 else int(W * 0.03 + aw + 15)
                by = ay + (i // 2) * (ah + 8)
                b.setGeometry(bx, by, aw, ah)

            lx = int(W * lad_x_pct)
            ly = int(H * lad_y_pct)
            lw = int(W * lad_w_pct)
            self.ladder_frame.setGeometry(lx, ly, lw, int(H * 0.82))

            ctrl_frame.setGeometry(int(W * 0.03), H - 45, int(W * 0.7), 40)

        widget.resizeEvent = layout_reposition

        self.stack.removeWidget(self.quiz_view)
        self.quiz_view = widget
        self.stack.addWidget(self.quiz_view)
        self.stack.setCurrentWidget(self.quiz_view)

        if active_label:
            style_money_a = ("background-color: #F4A300; color: #08162E; font-weight: bold; padding: 2px 6px; border-radius: 3px;",)
            style_money_b = ("background-color: #FFD84A; color: #08162E; font-weight: bold; padding: 2px 6px; border-radius: 3px;",)
            QTimer.singleShot(150, lambda: self.animate_blink(active_label, style_money_a, style_money_b, count=8, interval_ms=180))

    # --------------------------------------------------------
    # LIFELINE LOGIC
    # --------------------------------------------------------

    def use_lifeline_5050(self):
        if self.used_5050 or self.answer_locked:
            return

        self.used_5050 = True
        self.btn_5050.set_usable(False)

        q = self.questions[self.current_index]
        correct = q.correct_index
        wrong_indices = [i for i in range(4) if i != correct]

        remove_indices = random.sample(wrong_indices, 2)
        for idx in remove_indices:
            self.ans_buttons[idx].set_text("")
            self.ans_buttons[idx].set_usable(False)

    def use_lifeline_hint(self):
        if self.used_hint or self.answer_locked:
            return

        self.used_hint = True
        self.btn_hint.set_usable(False)

        q = self.questions[self.current_index]
        letters = ["A", "B", "C", "D"]

        if q.hint and q.hint.strip():
            hint_text = f"💡 GỢI Ý DÀNH CHO BẠN:\n\n{q.hint.strip()}"
        else:
            hint_text = f"💡 GỢI Ý MẶC ĐỊNH:\n\nĐáp án đúng nằm ở phương án [{letters[q.correct_index]}]: {q.answers[q.correct_index]}"

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Quyền trợ giúp: Gợi ý")
        msg_box.setText(hint_text)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #07162E;
                border: 2px solid #1B65AD;
            }
            QMessageBox QLabel {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                min-width: 320px;
            }
            QPushButton {
                background-color: #1A62AA;
                color: white;
                font-weight: bold;
                min-width: 80px;
                padding: 6px;
                border: 1px solid #3381D0;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2C82CE;
            }
        """)
        msg_box.exec()

    def use_lifeline_phone(self):
        if self.used_phone or self.answer_locked:
            return

        self.used_phone = True
        self.btn_phone.set_usable(False)

        q = self.questions[self.current_index]
        letters = ["A", "B", "C", "D"]
        friend_choice = letters[q.correct_index]

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Quyền trợ giúp: Gọi điện cho người thân")
        msg_box.setText(
            f"📞 CUỘC GỌI CHO NGƯỜI THÂN:\n\n"
            f"\"Theo tôi tìm hiểu thì đáp án chính xác nhất là {friend_choice}!\""
        )
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #07162E;
                border: 2px solid #1B65AD;
            }
            QMessageBox QLabel {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                min-width: 320px;
            }
            QPushButton {
                background-color: #1A62AA;
                color: white;
                font-weight: bold;
                min-width: 80px;
                padding: 6px;
                border: 1px solid #3381D0;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2C82CE;
            }
        """)
        msg_box.exec()

    # --------------------------------------------------------
    # GAMEPLAY & REVEAL
    # --------------------------------------------------------

    def select_answer(self, selected_index: int):
        if self.answer_locked:
            return

        self.answer_locked = True
        self.bg_container.set_background(
            self.settings.get("answered_background", ""),
            self.settings.get("loop_video", True)
        )

        self.ans_buttons[selected_index].set_colors("#F4A300", "#FFD84A", "#08162E")

        reveal_ms = int(float(self.settings.get("reveal_delay", 1.5)) * 1000)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self.reveal_answer(selected_index))
        self.active_timers.append(timer)
        timer.start(reveal_ms)

    def reveal_answer(self, selected_index: int):
        correct_index = self.questions[self.current_index].correct_index
        blink_speed = int(self.settings.get("blink_speed", 200))
        blink_count = int(self.settings.get("blink_count", 6))

        if selected_index == correct_index:
            self.bg_container.set_background(
                self.settings.get("correct_background", ""),
                self.settings.get("loop_video", True)
            )

            colors_correct_a = ("#16A34A", "#22C55E", "#FFFFFF")
            colors_correct_b = ("#15803D", "#4ADE80", "#FFFFFF")

            self.animate_blink(
                self.ans_buttons[correct_index],
                colors_correct_a, colors_correct_b,
                blink_count, blink_speed,
                on_finished=lambda: self.btn_next.setEnabled(True)
            )

        else:
            self.bg_container.set_background(
                self.settings.get("wrong_background", ""),
                self.settings.get("loop_video", True)
            )

            colors_wrong_a = ("#D92D20", "#FF8D8D", "#FFFFFF")
            colors_wrong_b = ("#800000", "#D92D20", "#FFFFFF")

            colors_correct_a = ("#16A34A", "#22C55E", "#FFFFFF")
            colors_correct_b = ("#15803D", "#4ADE80", "#FFFFFF")

            self.animate_blink(self.ans_buttons[selected_index], colors_wrong_a, colors_wrong_b, blink_count, blink_speed)

            self.animate_blink(
                self.ans_buttons[correct_index],
                colors_correct_a, colors_correct_b,
                blink_count, blink_speed,
                on_finished=self.on_wrong_answer
            )

            for i, btn in enumerate(self.ans_buttons):
                if i not in (selected_index, correct_index):
                    btn.set_colors("rgba(10, 39, 77, 180)", "#1B65AD", "#8098BC")

    def on_wrong_answer(self):
        loss_money = "0 VNĐ"
        if self.current_index >= 10 and len(self.questions) >= 10:
            loss_money = self.questions[9].money
        elif self.current_index >= 5 and len(self.questions) >= 5:
            loss_money = self.questions[4].money

        self.show_finished(
            title="💥 BẠN ĐÃ THUA!",
            status_text="Rất tiếc, bạn đã chọn sai đáp án.",
            money_str=loss_money
        )

    def quit_game_with_money(self):
        if self.current_index > 0:
            prize = self.questions[self.current_index - 1].money
        else:
            prize = "0 VNĐ"

        self.show_finished(
            title="⏸️ BẠN ĐÃ TẠM DỪNG",
            status_text="Bạn đã tạm dừng và nhận được số tiền:",
            money_str=prize
        )

    def next_question(self):
        if self.current_index >= len(self.questions) - 1:
            prize = self.questions[self.current_index].money
            self.show_finished(
                title="🎉 XIN CHÚC MỪNG!",
                status_text="Bạn đã hoàn thành xuất sắc tất cả các câu hỏi!",
                money_str=prize
            )
            return
        self.current_index += 1
        self.show_question()

    # --------------------------------------------------------
    # FINISHED / GAME OVER VIEW
    # --------------------------------------------------------

    def show_finished(self, title: str = "HOÀN THÀNH CHƯƠNG TRÌNH", status_text: str = "", money_str: str = "0 VNĐ"):
        self.clear_active_timers()
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
        card_layout.setContentsMargins(50, 40, 50, 40)

        lbl_win = QLabel(title)
        lbl_win.setStyleSheet("color: #FFD84A; font-size: 26px; font-weight: bold;")
        card_layout.addWidget(lbl_win, alignment=Qt.AlignmentFlag.AlignCenter)

        if status_text:
            lbl_status = QLabel(status_text)
            lbl_status.setStyleSheet("color: #FFFFFF; font-size: 15px; margin-top: 8px;")
            card_layout.addWidget(lbl_status, alignment=Qt.AlignmentFlag.AlignCenter)

        lbl_money = QLabel(f"Số tiền nhận được: {money_str}")
        lbl_money.setStyleSheet("color: #22C55E; font-size: 22px; font-weight: bold; margin: 15px 0;")
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
        self.clear_active_timers()
        self.bg_container.stop_background()
        event.accept()


# ============================================================
# MAIN ENTRY
# ============================================================

def main():
    app = QApplication(sys.argv)
    window = MillionaireQuizApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
