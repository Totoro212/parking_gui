import sys
import sqlite3
import cv2
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QGridLayout, QHBoxLayout,
    QLabel, QFileDialog, QDialog, QLineEdit, QMessageBox, QInputDialog, QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap

DB_FILE = "cameras.db"

def errors_func(text):
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Critical) 
    msg_box.setWindowTitle("Ошибка") 
    msg_box.setText(text) 
    msg_box.exec()
class CameraWindow(QWidget):
    def __init__(self, camera_name, video_path):
        super().__init__()
        self.setWindowTitle(f"Камера: {camera_name}")
        self.showMaximized()

        layout = QVBoxLayout(self)
        
        self.video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.video_label)
        self.setLayout(layout)

        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            errors_func("Ошибка открытия видео")
            return

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def update_frame(self):
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                bytes_per_line = ch * w
                q_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(q_image).scaled(
                    self.video_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.video_label.setPixmap(pixmap)
            else:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Зацикливаем видео

    def closeEvent(self, event):
        if self.cap.isOpened():
            self.cap.release()
        event.accept()

class CameraMonitorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Мониторинг парковок")
        self.setGeometry(100, 100, 900, 600)
        self.init_db()
        self.setup_ui()
        self.load_cameras()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        button_layout = QVBoxLayout()

        add_btn = QPushButton("--Добавить камеру--")
        add_btn.setFixedWidth(150)
        add_btn.clicked.connect(self.show_add_camera_dialog)
        button_layout.addWidget(add_btn)

        edit_btn = QPushButton("--Редактирвать камеру--")
        edit_btn.setFixedWidth(150)
        edit_btn.clicked.connect(self.edit_camera_dialog)
        button_layout.addWidget(edit_btn)

        delete_btn = QPushButton("--Удалить камеру--")
        delete_btn.setFixedWidth(150)
        delete_btn.clicked.connect(self.delete_camera_dialog)
        button_layout.addWidget(delete_btn)

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)

        grid_widget = QWidget()
        grid_widget.setLayout(self.grid_layout)

        main_layout.addLayout(button_layout) 
        main_layout.addWidget(grid_widget)   
        
        self.camera_boxes = {}
    def init_db(self):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cameras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    photo TEXT,
                    video TEXT
                )
            """)

    def load_cameras(self):
        with sqlite3.connect(DB_FILE) as conn:
            for camera_id, name, photo, video in conn.execute("SELECT id, name, photo, video FROM cameras").fetchall():
                self.add_parking_image(camera_id, name, photo, video)

    def add_parking_image(self, camera_id, name, photo, video):
        if not photo:
            return

        label = QLabel()
        pixmap = QPixmap(photo)

        if pixmap.isNull():
            errors_func("Ошибка загрузки изображения")
            return

        label.setPixmap(pixmap.scaled(300, 200, Qt.AspectRatioMode.KeepAspectRatio))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(300, 200)
        label.setToolTip(name)

        label.mousePressEvent = lambda event, n=name, v=video: self.open_camera(n, v)

        row, col = divmod(len(self.camera_boxes), 3)
        self.grid_layout.addWidget(label, row, col)
        self.camera_boxes[camera_id] = label

    def open_camera(self, name, video_path):
        if video_path:
            self.camera_window = CameraWindow(name, video_path)
            self.camera_window.show()

    
    def show_add_camera_dialog(self):
        dialog = AddCameraDialog(self)
        if dialog.exec():
            name, photo, video = dialog.get_camera_data()
            if name and photo and video:
                self.add_camera_to_db(name, photo, video)

    def edit_camera_dialog(self):
        with sqlite3.connect(DB_FILE) as conn:
            cameras = conn.execute("SELECT name FROM cameras").fetchall()

        camera_names = [camera[0] for camera in cameras]

        if not camera_names:
            errors_func("Нет доступных камер для редактирования")
            return

        selected_name, ok = QInputDialog.getItem(self, "Выбор камеры", "Выберите камеру для редактирования:", camera_names, 0, False)

        if ok and selected_name:
            dialog = EditCameraDialog(selected_name, self)
            if dialog.exec():
                self.update_camera_display()
        # Получаем список всех камер из базы данных
            with sqlite3.connect(DB_FILE) as conn:
                cameras = conn.execute("SELECT name FROM cameras").fetchall()

            camera_names = [camera[0] for camera in cameras]
            
            if not camera_names:
                errors_func("Нет доступных камер для редактирования")
                return

            # Показываем диалог для выбора камеры
            selected_name, ok = QInputDialog.getItem(self, "Выбор камеры", "Выберите камеру для редактирования:", camera_names, 0, False)
            
            if ok and selected_name:
                # Получаем старые данные камеры
                with sqlite3.connect(DB_FILE) as conn:
                    camera_data = conn.execute("SELECT * FROM cameras WHERE name = ?", (selected_name,)).fetchone()
                
                # Открываем диалоговое окно для изменения имени камеры
                new_name, ok = QInputDialog.getText(self, "Редактировать имя камеры", "Введите новое имя камеры:", text=camera_data[1])

                if ok and new_name:
                    # Обновляем имя камеры в базе данных
                    with sqlite3.connect(DB_FILE) as conn:
                        conn.execute("UPDATE cameras SET name = ? WHERE name = ?", (new_name, selected_name))
                    
                    # Обновляем отображение камер
                    self.update_camera_display()
                else:
                    QMessageBox.warning(self, "Ошибка", "Имя камеры не может быть пустым.")


    def update_camera_display(self):
        # Очистить текущий grid
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        self.camera_boxes.clear()

        # Получить камеры из базы данных
        with sqlite3.connect(DB_FILE) as conn:
            cameras = conn.execute("SELECT id, name, photo, video FROM cameras").fetchall()

        for idx, (camera_id, name, photo, video) in enumerate(cameras):
            if not photo or not os.path.exists(photo):
                continue  # пропустить, если нет фото

            pixmap = QPixmap(photo)
            if pixmap.isNull():
                continue  # если изображение не удалось загрузить

            label = QLabel()
            label.setPixmap(pixmap.scaled(300, 200, Qt.AspectRatioMode.KeepAspectRatio))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(300, 200)
            label.setToolTip(name)

            # Установим обработчик клика
            label.mousePressEvent = lambda event, n=name, v=video: self.open_camera(n, v)

            row, col = divmod(len(self.camera_boxes), 3)
            self.grid_layout.addWidget(label, row, col)
            self.camera_boxes[camera_id] = label

    def delete_camera_dialog(self):
        dialog = DeleteCameraDialog(self)
        if dialog.exec():
            self.update_camera_display()


    def add_camera_to_db(self, name, photo, video):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.execute(
                    "INSERT INTO cameras (name, photo, video) VALUES (?, ?, ?)",
                    (name, photo, video)
                )
                conn.commit()
                camera_id = cursor.lastrowid
            self.add_parking_image(camera_id, name, photo, video)
        except sqlite3.IntegrityError:
            errors_func("Камера с таким названием существует")

class AddCameraDialog(QDialog):
    """Диалог для добавления камеры."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить камеру")

        layout = QVBoxLayout(self)

        self.input_name = QLineEdit(self, placeholderText="Название парковки")
        layout.addWidget(self.input_name)

        self.btn_select_photo = QPushButton("Выбрать фото")
        self.btn_select_photo.clicked.connect(self.select_photo)
        layout.addWidget(self.btn_select_photo)

        self.photo_path_label = QLabel("Файл не выбран")
        layout.addWidget(self.photo_path_label)

        self.btn_select_video = QPushButton("Выбрать видео")
        self.btn_select_video.clicked.connect(self.select_video)
        layout.addWidget(self.btn_select_video)

        self.video_path_label = QLabel("Файл не выбран")
        layout.addWidget(self.video_path_label)

        self.add_button = QPushButton("Добавить")
        self.add_button.clicked.connect(self.add_camera)
        layout.addWidget(self.add_button)

        self.setLayout(layout)

        self.photo_path = ""
        self.video_path = ""

    def select_photo(self):
        """Выбирает фото."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбрать изображение", "", "Изображения (*.png *.jpg *.jpeg)")
        if file_path:
            self.photo_path = file_path
            self.photo_path_label.setText(file_path.split("/")[-1])

    def select_video(self):
        """Выбирает видео."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбрать видео", "", "Видео (*.mp4 *.avi *.mov)")
        if file_path:
            self.video_path = file_path
            self.video_path_label.setText(file_path.split("/")[-1])

    def add_camera(self):
        """Сохраняет камеру и закрывает диалог."""
        if self.input_name.text().strip() and self.photo_path and self.video_path:
            self.accept()  # Закрываем окно только если все данные есть

    def get_camera_data(self):
        """Возвращает введенные данные."""
        return self.input_name.text().strip(), self.photo_path, self.video_path
class EditCameraDialog(QDialog):
    def __init__(self, camera_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактировать камеру")
        self.setModal(True)
        self.camera_name = camera_name

        self.init_ui()
        self.load_camera_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.input_name = QLineEdit(self)
        layout.addWidget(QLabel("Новое имя камеры:"))
        layout.addWidget(self.input_name)

        self.btn_select_photo = QPushButton("Выбрать фото")
        self.btn_select_photo.clicked.connect(self.select_photo)
        layout.addWidget(self.btn_select_photo)

        self.photo_path_label = QLabel("Файл не выбран")
        layout.addWidget(self.photo_path_label)

        self.btn_select_video = QPushButton("Выбрать видео")
        self.btn_select_video.clicked.connect(self.select_video)
        layout.addWidget(self.btn_select_video)

        self.video_path_label = QLabel("Файл не выбран")
        layout.addWidget(self.video_path_label)

        self.save_button = QPushButton("Сохранить изменения")
        self.save_button.clicked.connect(self.save_changes)
        layout.addWidget(self.save_button)

    def load_camera_data(self):
        with sqlite3.connect(DB_FILE) as conn:
            result = conn.execute("SELECT name, photo, video FROM cameras WHERE name = ?", (self.camera_name,)).fetchone()

        if result:
            name, photo, video = result
            self.input_name.setText(name)
            self.photo_path_label.setText(photo if photo else "Файл не выбран")
            self.video_path_label.setText(video if video else "Файл не выбран")

    def select_photo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбрать фото", "", "Изображения (*.jpg *.jpeg *.png)")
        if file_path:
            self.photo_path_label.setText(file_path)

    def select_video(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выбрать видео", "", "Видео (*.mp4 *.avi *.mov)")
        if file_path:
            self.video_path_label.setText(file_path)

    def save_changes(self):
        new_name = self.input_name.text().strip()
        new_photo = self.photo_path_label.text() if self.photo_path_label.text() != "Файл не выбран" else None
        new_video = self.video_path_label.text() if self.video_path_label.text() != "Файл не выбран" else None

        if not new_name:
            QMessageBox.warning(self, "Ошибка", "Имя камеры не может быть пустым.")
            return

        with sqlite3.connect(DB_FILE) as conn:
            try:
                conn.execute("UPDATE cameras SET name = ?, photo = ?, video = ? WHERE name = ?", 
                            (new_name, new_photo, new_video, self.camera_name))
                conn.commit()
                QMessageBox.information(self, "Успех", "Камера успешно обновлена.")
                self.accept()
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Ошибка", "Камера с таким именем уже существует.")
class DeleteCameraDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Удалить камеру")
        self.setFixedSize(300, 150)

        layout = QVBoxLayout(self)

        with sqlite3.connect(DB_FILE) as conn:
            cameras = conn.execute("SELECT name FROM cameras").fetchall()

        self.camera_names = [c[0] for c in cameras]

        if not self.camera_names:
            QMessageBox.warning(self, "Ошибка", "Нет доступных камер для удаления.")
            self.close()
            return

        self.combo = QComboBox()
        self.combo.addItems(self.camera_names)
        layout.addWidget(QLabel("Выберите камеру для удаления:"))
        layout.addWidget(self.combo)

        btn_layout = QHBoxLayout()
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self.delete_camera)
        btn_layout.addWidget(self.delete_btn)

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def delete_camera(self):
        selected_name = self.combo.currentText()
        if selected_name:
            confirm = QMessageBox.question(
                self,
                "Подтверждение",
                f"Вы уверены, что хотите удалить камеру '{selected_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if confirm == QMessageBox.StandardButton.Yes:
                with sqlite3.connect(DB_FILE) as conn:
                    conn.execute("DELETE FROM cameras WHERE name = ?", (selected_name,))
                self.accept()  # Закрыть диалог с успехом


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CameraMonitorApp()
    window.show()
    sys.exit(app.exec())
