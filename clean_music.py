import os
import unicodedata
import tkinter as tk
from tkinter import filedialog, messagebox

def remove_fancy_unicode(text):
    """Lọc bỏ các ký tự Unicode cách điệu (math/fancy) gây lỗi hiển thị"""
    normalized = unicodedata.normalize('NFKD', text)
    clean_chars = []
    for c in normalized:
        if ord(c) < 128 or ('À' <= c <= 'ỹ') or c in ' -_()[]+.':
            clean_chars.append(c)
        else:
            try:
                name = unicodedata.name(c)
                if 'MATHEMATICAL' in name:
                    continue
                else:
                    clean_chars.append(c)
            except ValueError:
                continue
    return "".join(clean_chars)

def process_folder(directory_path):
    """Xử lý đổi tên tệp trong thư mục"""
    count = 0
    for filename in os.listdir(directory_path):
        if filename.lower().endswith(('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.aac')):
            name, ext = os.path.splitext(filename)
            cleaned_name = " ".join(remove_fancy_unicode(name).split())
            new_filename = cleaned_name + ext
            
            if new_filename != filename:
                old_path = os.path.join(directory_path, filename)
                new_path = os.path.join(directory_path, new_filename)
                try:
                    os.rename(old_path, new_path)
                    count += 1
                except Exception as e:
                    print(f"Lỗi đổi tên: {e}")
    return count

def main():
    # Khởi tạo cửa sổ ẩn (chỉ dùng để hiện hộp thoại chọn file)
    root = tk.Tk()
    root.withdraw()
    
    # Hiện hộp thoại chọn thư mục
    folder_selected = filedialog.askdirectory(title="Chọn thư mục chứa nhạc")
    
    if folder_selected:
        try:
            total = process_folder(folder_selected)
            messagebox.showinfo("Thành công", f"Đã làm sạch xong {total} bài hát!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Có lỗi xảy ra: {e}")
    else:
        # Nếu người dùng bấm Cancel
        pass

if __name__ == "__main__":
    main()