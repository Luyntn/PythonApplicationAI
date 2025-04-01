import os
import re
import base64
import xml.etree.ElementTree as ET
import pandas as pd
import random
from gtts import gTTS
import pygame
import sys

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.video import Video
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.clock import Clock

# Hàm chuẩn hóa văn bản
def normalize_text(text):
    text = text.strip().lower()
    text = " ".join(text.split())
    return text

# Hàm mã hóa/giải mã Base64
def encode_str(s):
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")

def decode_str(s):
    return base64.b64decode(s.encode("utf-8")).decode("utf-8")

def speak_vietnamese(text):
    if not text:
        return
    try:
        # Khởi tạo pygame mixer
        pygame.mixer.quit()  # Thoát mixer nếu đã được khởi tạo trước đó
        pygame.mixer.init()  # Khởi tạo lại mixer

        # Sử dụng gTTS để tạo file âm thanh
        tts = gTTS(text=text, lang='vi')
        temp_file = "temp_output.mp3"
        tts.save(temp_file)
        
        # Phát âm thanh với pygame
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        # Chờ âm thanh phát xong rồi xóa file tạm
        while pygame.mixer.music.get_busy():  # Kiểm tra xem âm thanh còn đang phát không
            pygame.time.Clock().tick(10)  # Thời gian chờ để tiếp tục kiểm tra
        
        # Xóa tệp âm thanh sau khi phát xong
        os.remove(temp_file)
        
    except Exception:
       error = sys.exc_info()[1]
       print("Lỗi khi phát âm thanh 2:")

class ChatVideoLayout(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Khởi tạo thông tin AI
        self.active_history_file = "chat_history.xml"
        self.active_ai_name = "Tiểu Hồ Ly"
        self.last_question = ""
        # Khởi tạo pygame
        pygame.init()  # Khởi tạo pygame
        # --- Video: nền toàn màn hình ---
        self.video = Video(source="", state="stop", options={'eos': 'loop'})
        self.video.size_hint = (1, 1)
        # Nâng video lên 10% từ dưới (để không che khung chat)
        self.video.pos_hint = {"x": 0, "y": 0.1}
        self.add_widget(self.video)
        
        # --- Chat Overlay Panel ---
        chat_panel = BoxLayout(orientation='vertical', size_hint=(1, 0.35), pos_hint={'x': 0, 'y': 0})
        # Tạo Label hiển thị chat, đặt vào ScrollView và lưu lại tham chiếu
        self.chat_display = Label(text="", markup=True, size_hint_y=None)
        self.chat_display.bind(texture_size=lambda instance, value: setattr(self.chat_display, 'height', value[1]))
        self.chat_scroll = ScrollView(size_hint=(1, 0.7))
        self.chat_scroll.add_widget(self.chat_display)
        chat_panel.add_widget(self.chat_scroll)
        
        # Input Panel gồm ô nhập và 3 nút: Gửi, Thêm, Clear
        input_panel = BoxLayout(size_hint=(1, 0.2))
        self.chat_input = TextInput(hint_text="Nhập tin nhắn...", multiline=False)
        self.chat_input.bind(on_text_validate=lambda instance: self.send_message())
        send_btn = Button(text="Gửi", size_hint=(0.3, 1))
        send_btn.bind(on_release=lambda instance: self.send_message())
        add_btn = Button(text="Thêm", size_hint=(0.3, 1))
        add_btn.bind(on_release=self.add_answer)
        clear_btn = Button(text="Clear", size_hint=(0.4, 1))
        clear_btn.bind(on_release=self.clear_history)
        input_panel.add_widget(self.chat_input)
        input_panel.add_widget(send_btn)
        input_panel.add_widget(add_btn)
        input_panel.add_widget(clear_btn)
        chat_panel.add_widget(input_panel)
        self.add_widget(chat_panel)
        
        # --- AI Selection Panel (ở góc trên bên phải) ---
        ai_panel = BoxLayout(orientation='vertical', size_hint=(0.15, 0.15),
                             pos_hint={'right': 1, 'top': 1}, spacing=5)
        ai1 = Button(text="THL")  # Tiểu Hồ Ly
        ai1.bind(on_release=lambda instance: self.select_ai("chat_history.xml", "video.mp4", "Tiểu Hồ Ly"))
        ai2 = Button(text="LDP")  # Lưu Duyệt Phi
        ai2.bind(on_release=lambda instance: self.select_ai("chat_historyLDP.xml", "video2.mp4", "Lưu Duyệt Phi"))
        ai_panel.add_widget(ai1)
        ai_panel.add_widget(ai2)
        self.add_widget(ai_panel)
        
        # --- Load video mặc định cho AI "Tiểu Hồ Ly" ---
        self.select_ai("chat_history.xml", "video.mp4", "Tiểu Hồ Ly")
    
    def select_ai(self, history_file, video_path, ai_name):
        self.active_history_file = history_file
        self.active_ai_name = ai_name
        abs_video = os.path.abspath(video_path)
        print("Loading video from:", abs_video)
        self.video.source = abs_video
        self.video.state = "play"
        
    def load_history(self):
        file_path = self.active_history_file
        if not os.path.exists(file_path):
            root = ET.Element("chatHistory")
            tree = ET.ElementTree(root)
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
            return pd.DataFrame(columns=["User", "Reply"])
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            entries = []
            for entry in root.findall("entry"):
                user_enc = entry.find("User").text if entry.find("User") is not None else ""
                reply_enc = entry.find("Reply").text if entry.find("Reply") is not None else ""
                user = decode_str(user_enc) if user_enc else ""
                reply = decode_str(reply_enc) if reply_enc else ""
                entries.append({"User": user, "Reply": reply})
            return pd.DataFrame(entries, columns=["User", "Reply"])
        except Exception:
            error = sys.exc_info()[1]
            print("Lỗi khi phát âm thanh 1:", error)
            return pd.DataFrame(columns=["User", "Reply"])
        
    def save_history(self, df):
        file_path = self.active_history_file
        root = ET.Element("chatHistory")
        for _, row in df.iterrows():
            entry = ET.SubElement(root, "entry")
            ET.SubElement(entry, "User").text = encode_str(str(row["User"]))
            ET.SubElement(entry, "Reply").text = encode_str(str(row["Reply"]))
        try:
            tree = ET.ElementTree(root)
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
        except Exception:
            print("Error saving XML")
    
    def send_message(self):
        user_input = self.chat_input.text.strip()
        if user_input:
            self.append_chat("Bạn", user_input)
            self.chat_input.text = ""
            self.last_question = user_input  # Lưu lại câu hỏi
            history = self.load_history()
            norm_input = normalize_text(user_input)
            match = history[history["User"].apply(lambda x: normalize_text(x)) == norm_input]
            if not match.empty:
                reply = match.sample(n=1).iloc[0]["Reply"]
                self.append_chat(self.active_ai_name, reply)
            else:
                self.show_teach_popup(user_input, history)
            Clock.schedule_once(lambda dt: setattr(self.chat_input, 'focus', True), 0.1)
    
    def add_answer(self, instance=None):
        question = self.last_question if self.last_question else self.chat_input.text.strip()
        if question:
            self.show_teach_popup(question, self.load_history())
            Clock.schedule_once(lambda dt: setattr(self.chat_input, 'focus', True), 0.1)
    
    def show_teach_popup(self, user_input, history):
        layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        answer_input = TextInput(hint_text="Nhập câu trả lời", multiline=False)
        layout.add_widget(answer_input)
        ok_btn = Button(text="OK", size_hint=(1, 0.3))
        layout.add_widget(ok_btn)
        popup = Popup(title="Dạy AI", content=layout, size_hint=(0.8, 0.4))
    
        def on_ok(instance):
            popup.dismiss()
            answer = answer_input.text.strip()
            if answer:
                new_row = {"User": user_input, "Reply": answer}
                new_df = pd.DataFrame([new_row])
                updated_history = pd.concat([history, new_df], ignore_index=True)
                self.save_history(updated_history)
                self.append_chat(self.active_ai_name, answer)
            else:
                self.append_chat(self.active_ai_name, "Xin lỗi, tôi không hiểu.")
            Clock.schedule_once(lambda dt: setattr(self.chat_input, 'focus', True), 0.1)
    
        ok_btn.bind(on_release=on_ok)
        popup.open()
    
    def append_chat(self, speaker, message):
        # Lấy nội dung hiện tại của chat_display
        current = self.chat_display.text if self.chat_display.text else ""
        new_line = "[b]{}:[/b] {}\n".format(speaker, message)
        full_text = current + new_line
        lines = full_text.strip().split("\n")
        max_lines = 4
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        # Cập nhật lại nội dung hiển thị và thêm xuống dòng cuối
        self.chat_display.text = "\n".join(lines) + "\n"
        # Nếu là AI, thì đọc câu trả lời
        if speaker == self.active_ai_name:
            speak_vietnamese(message)
        # Tự động cuộn xuống cuối sau 0.1 giây
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, 'scroll_y', 0), 0.1)
    
    def clear_history(self, instance=None):
        self.chat_display.text = ""

class ChatVideoAppKivy(App):
    def build(self):
        Window.clearcolor = (1, 1, 1, 1)
        return ChatVideoLayout()

if __name__ == '__main__':
    ChatVideoAppKivy().run()
