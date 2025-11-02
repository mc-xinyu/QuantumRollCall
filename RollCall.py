import sys
import random
import json
import os
import webbrowser
import urllib.request
import urllib.error
import zipfile
import threading
from PyQt5.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve, QUrl, pyqtSignal, QObject
from PyQt5.QtGui import QIcon, QPalette, QColor, QFont, QFontDatabase, QPixmap
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QStackedWidget, QFrame, QLabel, QFileDialog, QListWidgetItem,
                             QSpacerItem, QSizePolicy, QGraphicsDropShadowEffect,
                             QGraphicsOpacityEffect, QProgressDialog)

# Multimedia imports for sound playback (mp3)
try:
    from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
except Exception:
    QMediaPlayer = None
    QMediaContent = None

from qfluentwidgets import (NavigationInterface, NavigationItemPosition, NavigationWidget, MessageBox, InfoBar, InfoBarIcon,
                            isDarkTheme, setTheme, Theme, setThemeColor, FluentWindow,
                            PrimaryPushButton, InfoBarPosition, ScrollArea,
                            ComboBox, CheckBox, PushButton, LineEdit, ListWidget,
                            BodyLabel, TitleLabel, DisplayLabel, CaptionLabel,
                            TeachingTip, TeachingTipTailPosition, Dialog, FluentIcon,
                            SegmentedWidget, CardWidget, setFont, TransparentToolButton,
                            ExpandSettingCard, SettingCardGroup, HyperlinkCard,
                            ColorDialog, setCustomStyleSheet,
                            SwitchButton, SettingCard, Dialog, MessageBoxBase, IconWidget)


class DownloadSignals(QObject):
    """下载信号类，用于线程间通信"""
    progress_updated = pyqtSignal(int, int)  # 当前下载量, 总大小
    download_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)


class NameListManager:
    """名单管理器"""
    def __init__(self):
        # 默认名单改为空
        self.names = []
        self.used_names = set()

    def load_from_file(self, filename):
        """从文件加载名单"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.names = data.get('names', [])
                    self.used_names = set(data.get('used_names', []))
                return True
            return False
        except Exception:
            return False

    def save_to_file(self, filename):
        """保存名单到文件"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            data = {
                'names': self.names,
                'used_names': list(self.used_names)
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def add_name(self, name):
        """添加名字"""
        if name and name not in self.names:
            self.names.append(name)
            return True
        return False

    def remove_name(self, name):
        """删除名字"""
        if name in self.names:
            self.names.remove(name)
            if name in self.used_names:
                self.used_names.remove(name)
            return True
        return False

    def clear_names(self):
        """清空名单与已点名记录"""
        self.names.clear()
        self.used_names.clear()

    def reset_used_names(self):
        """重置已点名名单"""
        self.used_names.clear()

    def get_available_names(self):
        """获取可用名字"""
        return [name for name in self.names if name not in self.used_names]

    def get_random_name(self, avoid_repetition=True):
        """随机获取一个名字"""
        available_names = self.get_available_names() if avoid_repetition else self.names

        if not available_names:
            if avoid_repetition:
                # 如果开启了避免重复且没有可用名字，返回 None 表示需要重置
                return None
            else:
                return None

        if available_names:
            name = random.choice(available_names)
            return name
        return None

    def mark_name_as_used(self, name, avoid_repetition=True):
        """将名字标记为已使用"""
        if avoid_repetition and name:
            self.used_names.add(name)

    def check_and_reset_if_complete(self, avoid_repetition=True):
        """检查是否所有名字都已被点过，如果是则重置并返回True"""
        if avoid_repetition and len(self.used_names) >= len(self.names) and len(self.names) > 0:
            self.reset_used_names()
            return True
        return False


class Settings:
    """设置管理器"""
    def __init__(self):
        self.auto_save = True
        self.avoid_repetition = True
        self.check_update_on_startup = False  # 新增：启动时检查更新
        self.theme = Theme.AUTO
        self.version = "3.3.3"  # 当前版本

    def load_from_file(self, filename):
        """从文件加载设置"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.auto_save = data.get('auto_save', True)
                    self.avoid_repetition = data.get('avoid_repetition', True)
                    self.check_update_on_startup = data.get('check_update_on_startup', False)
                    theme_str = data.get('theme', 'AUTO')
                    self.theme = getattr(Theme, theme_str, Theme.AUTO)
                    self.version = data.get('version', "3.3.3")  # 加载版本
                return True
            return False
        except Exception:
            return False

    def save_to_file(self, filename):
        """保存设置到文件"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            data = {
                'auto_save': self.auto_save,
                'avoid_repetition': self.avoid_repetition,
                'check_update_on_startup': self.check_update_on_startup,
                'theme': self.theme.name,
                'version': self.version  # 保存版本
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def reset(self):
        """重置设置为默认值"""
        self.auto_save = True
        self.avoid_repetition = True
        self.check_update_on_startup = False
        self.theme = Theme.AUTO
        self.version = "3.3.3"  # 重置版本


class MainWindow(FluentWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.name_manager = NameListManager()
        self.settings = Settings()

        # 配置文件路径
        self.config_dir = "config"
        self.name_list_path = os.path.join(self.config_dir, "name_list.json")
        self.settings_path = os.path.join(self.config_dir, "settings.json")

        # -------- Apply saved theme early to avoid startup flicker ----------
        # Load settings synchronously (very small I/O) and set theme before building UI.
        # This prevents the window briefly showing in the wrong (light) theme when the user configured dark.
        self.settings.load_from_file(self.settings_path)
        setTheme(self.settings.theme)
        # choose theme color consistent with apply_settings()
        if self.settings.theme == Theme.DARK:
            initial_theme_color = QColor("#6c8fff")
        elif self.settings.theme == Theme.LIGHT:
            initial_theme_color = QColor("#4a6bff")
        else:
            initial_theme_color = QColor("#6c8fff" if isDarkTheme() else "#4a6bff")
        setThemeColor(initial_theme_color)
        # -------------------------------------------------------------------

        # 启动时尽量不阻塞：先用一个安全的默认字体名，实际字体在延迟初始化中载入并应用
        self.custom_font_family = "Microsoft YaHei"

        # UI 先构建（主题已提前应用，避免闪烁）
        self.setup_ui()

        # 延迟完成启动工作（加载字体、图标、配置和名册，并应用设置）
        QTimer.singleShot(0, self.finish_startup)

    def finish_startup(self):
        """延后初始化：加载字体、图标、配置和名册，并应用设置"""
        loaded_font = self.load_custom_font()
        if loaded_font:
            self.custom_font_family = loaded_font
            QApplication.setFont(QFont(self.custom_font_family))
            if hasattr(self, 'roll_call_interface'):
                self.roll_call_interface.font_family = self.custom_font_family
                self.roll_call_interface.update_button_styles()
            if hasattr(self, 'settings_interface'):
                self.settings_interface.font_family = self.custom_font_family
                self.settings_interface.update_theme_style()
            if hasattr(self, 'timer_interface'):
                self.timer_interface.font_family = self.custom_font_family
                self.timer_interface.update_button_styles()
                self.timer_interface.update_digit_styles()

        # 仅使用 ico 作为图标（不再尝试 png）
        self.set_window_icon()

        # 加载数据（名单等）
        self.load_data()
        # Re-apply settings to ensure all UI reflects current settings values
        self.apply_settings()
        
        # 检查版本更新
        self.check_version_update()

        # 新增：启动时自动检查更新（静默，只在不是最新且联网正常时弹出对话框）
        if getattr(self.settings, 'check_update_on_startup', False):
            if hasattr(self, 'settings_interface'):
                QTimer.singleShot(400, self.settings_interface.silent_check_updates_on_startup)

    def check_version_update(self):
        """检查版本更新并显示更新对话框"""
        current_version = "3.3.3"  # 当前程序版本
        saved_version = self.settings.version  # 配置文件中保存的版本
        
        if saved_version != current_version:
            # 显示更新对话框
            self.show_update_dialog(saved_version, current_version)
            
            # 更新配置文件中的版本
            self.settings.version = current_version
            self.save_settings()

    def show_update_dialog(self, old_version, new_version):
        """显示更新对话框 - 使用带遮罩的对话框样式"""
        title = f"已更新到 {new_version}"
        content = "新版本内容：\n · 更新后展示更新内容对话框\n · 添加自动更新功能\n · 支持启动时自动检查更新"
        
        # 使用 MessageBox 创建带遮罩的对话框
        w = MessageBox(title, content, self)
        # 修改按钮文字为中文
        w.yesButton.setText('确定')
        w.cancelButton.setVisible(False)  # 隐藏取消按钮，只显示确定按钮
        w.exec()

    def load_custom_font(self):
        """加载自定义字体（延迟执行以减少启动阻塞）"""
        try:
            font_path = "assets/font.ttf"
            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    if font_families:
                        return font_families[0]
            return None
        except Exception:
            return None

    def set_window_icon(self):
        """设置窗口图标，只使用 assets/icon.ico"""
        try:
            ico_path = "assets/icon.ico"
            if os.path.exists(ico_path):
                icon = QIcon(ico_path)
                self.setWindowIcon(icon)
                if hasattr(QApplication, 'setWindowIcon'):
                    QApplication.setWindowIcon(icon)
        except Exception:
            pass

    def setup_ui(self):
        # 修改窗口标题为"量子点名系统"
        self.setWindowTitle("量子点名系统")
        self.resize(1000, 700)

        # 创建界面
        self.roll_call_interface = RollCallInterface(self, self.custom_font_family)
        # 新增计时器界面
        self.timer_interface = TimerInterface(self, self.custom_font_family)
        self.settings_interface = SettingsInterface(self, self.custom_font_family)

        # 添加到导航
        self.addSubInterface(self.roll_call_interface, FluentIcon.PEOPLE, '点名')
        self.addSubInterface(self.timer_interface, FluentIcon.DATE_TIME, '计时')
        self.addSubInterface(self.settings_interface, FluentIcon.SETTING, '设置', NavigationItemPosition.BOTTOM)

        # 设置初始界面
        self.stackedWidget.setCurrentWidget(self.roll_call_interface)
        self.navigationInterface.setCurrentItem(self.roll_call_interface.objectName())

    def add_name_to_list(self, name):
        """添加名字到名单"""
        if self.name_manager.add_name(name):
            if hasattr(self.settings_interface, 'refresh_name_list'):
                self.settings_interface.refresh_name_list()

            # 立即保存名单到文件（稍后调度以减少 UI 阻塞）
            QTimer.singleShot(0, self.save_name_list)

            InfoBar.success(
                title="成功",
                content=f"已添加: {name}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=1500,
                parent=self
            )
            return True
        else:
            InfoBar.warning(
                title="警告",
                content="名字已存在或为空",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=1500,
                parent=self
            )
            return False

    def remove_name_from_list(self, name):
        """从名单中删除名字"""
        if self.name_manager.remove_name(name):
            # 只刷新界面一次（设置界面会被刷新）
            if hasattr(self.settings_interface, 'refresh_name_list'):
                self.settings_interface.refresh_name_list()

            # 将保存延后（异步调度到事件循环），避免在删除时阻塞 UI 导致卡顿
            QTimer.singleShot(0, self.save_name_list)

            InfoBar.success(
                title="成功",
                content=f"已删除: {name}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=1500,
                parent=self
            )
            return True
        return False

    def clear_name_list(self):
        """清空整个名单"""
        # 如果正在点名，先停止
        if hasattr(self, 'roll_call_interface') and self.roll_call_interface.is_rolling:
            self.roll_call_interface.stop_roll_call()
        self.name_manager.clear_names()
        if hasattr(self.settings_interface, 'refresh_name_list'):
            self.settings_interface.refresh_name_list()

        # 立即保存名单到文件（延后调度）
        QTimer.singleShot(0, self.save_name_list)

        InfoBar.success(
            title="成功",
            content="名单已清空",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=1500,
            parent=self
        )
        return True

    def export_name_list(self):
        """导出名单"""
        filename, _ = QFileDialog.getSaveFileName(self, "导出名单", "name_list.json", "JSON Files (*.json)")
        if filename:
            if self.name_manager.save_to_file(filename):
                InfoBar.success(
                    title="成功",
                    content=f"名单已导出到 {filename}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    title="错误",
                    content="导出失败",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )

    def import_name_list(self):
        """导入名单"""
        filename, _ = QFileDialog.getOpenFileName(self, "导入名单", "", "JSON Files (*.json)")
        if filename:
            if self.name_manager.load_from_file(filename):
                if hasattr(self.settings_interface, 'refresh_name_list'):
                    self.settings_interface.refresh_name_list()

                # 导入后立即保存到默认位置（延后调度）
                QTimer.singleShot(0, self.save_name_list)

                InfoBar.success(
                    title="成功",
                    content="名单导入成功",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    title="错误",
                    content="导入失败",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )

    def export_settings(self):
        """导出设置"""
        filename, _ = QFileDialog.getSaveFileName(self, "导出设置", "settings.json", "JSON Files (*.json)")
        if filename:
            if self.settings.save_to_file(filename):
                InfoBar.success(
                    title="成功",
                    content=f"设置已导出到 {filename}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    title="错误",
                    content="导出失败",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )

    def import_settings(self):
        """导入设置"""
        filename, _ = QFileDialog.getOpenFileName(self, "导入设置", "", "JSON Files (*.json)")
        if filename:
            if self.settings.load_from_file(filename):
                self.apply_settings()
                # 导入设置后立即保存到默认位置
                self.save_settings()
                InfoBar.success(
                    title="成功",
                    content="设置导入成功",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )
            else:
                InfoBar.error(
                    title="错误",
                    content="导入失败",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=2000,
                    parent=self
                )

    def reset_settings(self):
        """重置设置"""
        self.settings.reset()
        self.apply_settings()
        # 重置设置后立即保存
        self.save_settings()
        InfoBar.success(
            title="成功",
            content="设置已重置",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=self
        )

    def apply_settings(self):
        """应用设置"""
        # Apply theme and theme color (this is safe to call multiple times)
        setTheme(self.settings.theme)
        if self.settings.theme == Theme.DARK:
            theme_color = QColor("#6c8fff")
        elif self.settings.theme == Theme.LIGHT:
            theme_color = QColor("#4a6bff")
        else:
            theme_color = QColor("#6c8fff" if isDarkTheme() else "#4a6bff")
        setThemeColor(theme_color)

        # 刷新设置界面
        if hasattr(self, 'settings_interface'):
            self.settings_interface.refresh_settings()
            self.settings_interface.update_theme_style()

        # 更新按钮样式
        if hasattr(self, 'roll_call_interface'):
            self.roll_call_interface.update_button_styles()
        if hasattr(self, 'timer_interface'):
            self.timer_interface.update_button_styles()
            self.timer_interface.update_digit_styles()

    def save_data(self):
        """保存数据"""
        self.save_name_list()
        self.save_settings()

    def save_name_list(self):
        """立即保存名单到文件"""
        self.name_manager.save_to_file(self.name_list_path)

    def save_settings(self):
        """立即保存设置到文件"""
        self.settings.save_to_file(self.settings_path)

    def load_data(self):
        """加载数据"""
        # 只加载名册文件 here; settings 已在构造早期加载以避免闪烁
        self.name_manager.load_from_file(self.name_list_path)
        if hasattr(self, 'settings_interface'):
            self.settings_interface.refresh_name_list()


class RollCallInterface(QWidget):
    """点名界面"""
    def __init__(self, parent=None, font_family="Microsoft YaHei"):
        super().__init__(parent)
        self.name_manager = parent.name_manager if parent else NameListManager()
        self.settings = parent.settings if parent else Settings()
        self.parent_window = parent
        self.font_family = font_family
        self.is_rolling = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_name)
        
        # 用于记录最后选中的名字
        self.last_selected_name = None

        self.setObjectName("RollCallInterface")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 40)

        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setAlignment(Qt.AlignCenter)

        self.title_label = QLabel("量子点名", self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setObjectName("title_label")
        title_layout.addWidget(self.title_label)

        layout.addWidget(title_container)

        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(20)

        self.hint_label = QLabel("被选中的是：", self)
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setObjectName("hint_label")
        center_layout.addWidget(self.hint_label)

        self.name_display = QLabel("准备点名", self)
        self.name_display.setAlignment(Qt.AlignCenter)
        self.name_display.setObjectName("name_display")
        center_layout.addWidget(self.name_display)

        layout.addWidget(center_container, 1)

        button_layout = QHBoxLayout()

        self.start_button = PrimaryPushButton("开始点名", self)
        self.start_button.setFixedSize(150, 50)
        self.start_button.clicked.connect(self.toggle_roll_call)

        self.reload_button = PushButton("重新加载", self)
        self.reload_button.setFixedSize(150, 50)
        self.reload_button.clicked.connect(self.reload_names)

        button_layout.addStretch(1)
        button_layout.addWidget(self.start_button)
        button_layout.addSpacing(30)
        button_layout.addWidget(self.reload_button)
        button_layout.addStretch(1)

        layout.addLayout(button_layout)

        self.update_button_styles()

    def update_button_styles(self):
        """更新按钮样式"""
        is_dark = isDarkTheme()

        title_color = "#6c8fff" if is_dark else "#4a6bff"
        hint_color = "white" if is_dark else "black"

        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-family: '{self.font_family}';
                font-size: 42px;
                font-weight: bold;
                color: {title_color};
                padding: 20px;
                margin: 0px;
                background: transparent;
            }}
        """)

        self.hint_label.setStyleSheet(f"""
            QLabel {{
                font-family: '{self.font_family}';
                font-size: 26px;
                font-weight: bold;
                color: {hint_color};
                margin: 0px;
                background: transparent;
            }}
        """)

        self.name_display.setStyleSheet(f"""
            QLabel {{
                font-family: '{self.font_family}';
                font-size: 64px;
                font-weight: bold;
                color: {title_color};
                padding: 60px 80px;
                background-color: rgba(255, 255, 255, 0.1);
                border: 3px solid {title_color};
                border-radius: 20px;
                margin: 0px;
            }}
        """)

        acrylic_style = """
            %s {
                background-color: rgba(128, 128, 128, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            %s:hover {
                background-color: rgba(128, 128, 128, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.4);
            }
            %s:pressed {
                background-color: rgba(128, 128, 128, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.5);
            }
        """

        start_button_style = acrylic_style % ("PrimaryPushButton", "PrimaryPushButton", "PrimaryPushButton") + """
            PrimaryPushButton {
                color: #4caf50;
            }
        """

        stop_button_style = acrylic_style % ("PrimaryPushButton", "PrimaryPushButton", "PrimaryPushButton") + """
            PrimaryPushButton {
                color: #d13438;
            }
        """

        reload_button_style = acrylic_style % ("PushButton", "PushButton", "PushButton") + """
            PushButton {
                color: #ff9800;
            }
        """

        if self.is_rolling:
            self.start_button.setText("暂停点名")
            self.start_button.setStyleSheet(stop_button_style)
        else:
            self.start_button.setText("开始点名")
            self.start_button.setStyleSheet(start_button_style)

        self.reload_button.setStyleSheet(reload_button_style)

    def toggle_roll_call(self):
        """切换点名状态"""
        if self.is_rolling:
            self.stop_roll_call()
        else:
            self.start_roll_call()

    def start_roll_call(self):
        """开始点名"""
        if not self.name_manager.names:
            InfoBar.warning(
                title="警告",
                content="名单为空，请先添加姓名",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )
            return

        self.is_rolling = True
        self.update_button_styles()
        self.timer.start(50)

    def stop_roll_call(self):
        """停止点名"""
        self.is_rolling = False
        self.update_button_styles()
        self.timer.stop()
        
        # 只有在停止点名时才将最后显示的名字标记为已使用
        if self.last_selected_name and self.settings.avoid_repetition:
            self.name_manager.mark_name_as_used(self.last_selected_name, self.settings.avoid_repetition)
            # 保存名单状态
            QTimer.singleShot(0, self.parent_window.save_name_list)
            
            # 检查是否所有名字都已被点过
            if self.name_manager.check_and_reset_if_complete(self.settings.avoid_repetition):
                # 所有名字都点过了，重置并显示提示
                self.name_display.setText("名单已重载")
                # 保存重置后的状态
                QTimer.singleShot(0, self.parent_window.save_name_list)

    def update_name(self):
        """更新显示的名字"""
        name = self.name_manager.get_random_name(self.settings.avoid_repetition)
        if name:
            self.name_display.setText(name)
            self.last_selected_name = name
        else:
            # 当没有可用名字时，显示准备点名
            self.name_display.setText("准备点名")
            self.last_selected_name = None

    def reload_names(self):
        """重新加载名单"""
        if self.is_rolling:
            self.stop_roll_call()

        self.name_manager.reset_used_names()
        self.name_display.setText("准备点名")
        self.last_selected_name = None

        # 显示重新加载成功的消息条
        self.show_reload_notification("名单已重载")
        
        # 保存重置后的状态
        QTimer.singleShot(0, self.parent_window.save_name_list)

    def show_reload_notification(self, message):
        """显示重新加载通知"""
        InfoBar.success(
            title="成功",
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=2000,
            parent=self
        )


class TimerInterface(QWidget):
    """计时/倒计时界面（实现倒计时页面）"""
    def __init__(self, parent=None, font_family="Microsoft YaHei"):
        super().__init__(parent)
        self.parent_window = parent
        self.font_family = font_family
        self.setObjectName("TimerInterface")

        # digits: [H_tens, H_ones, M_tens, M_ones, S_tens, S_ones]
        # 初始时间设为 5 分钟 => 00:05:00
        self.digits = [0, 0, 0, 5, 0, 0]
        # max per position: default; hour ones will be adjusted dynamically
        self.max_digit = [2, 9, 5, 9, 5, 9]

        self.is_running = False
        # 保存倒计时开始前的秒数快照（用于重置恢复）
        self._pre_start_seconds = None
        self._initial_seconds = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        # 用于淡出动画管理
        self._animations = []
        self._opacity_effects = []

        # 媒体播放器（按需初始化）
        self._player = None

        self._build_ui()
        # 确保 initial_seconds 与 digits 同步
        if self._initial_seconds is None:
            self._initial_seconds = self._digits_to_seconds(self.digits)
        # enforce hour constraints on startup
        self._enforce_hour_constraints()
        self.update_button_styles()
        self.update_digit_styles()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 40)
        layout.setSpacing(20)

        # segmented header similar to image (倒计时 / 计时器)
        try:
            sv = SegmentedWidget()
            sv.addSegment("倒计时")
            sv.addSegment("计时器")
            sv.setCurrentIndex(0)
            layout.addWidget(sv)
        except Exception:
            title = TitleLabel("倒计时", self)
            layout.addWidget(title)

        # digits area
        digits_container = QWidget()
        digits_layout = QHBoxLayout(digits_container)
        digits_layout.setAlignment(Qt.AlignCenter)
        digits_layout.setSpacing(24)

        # create six digit columns grouped as HH : MM : SS
        self.digit_labels = []
        self.plus_buttons = []
        self.minus_buttons = []
        self.colon_labels = []

        def make_digit_widget(pos):
            w = QWidget()
            l = QVBoxLayout(w)
            l.setContentsMargins(6, 6, 6, 6)
            l.setSpacing(6)

            plus = PushButton("+", self)
            plus.setFixedSize(56, 36)
            plus.clicked.connect(lambda _, p=pos: self._increment_digit(p))
            l.addWidget(plus, 0, Qt.AlignHCenter)

            lbl = QLabel("0", self)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(96, 140)
            l.addWidget(lbl, 0, Qt.AlignHCenter)

            minus = PushButton("-", self)
            minus.setFixedSize(56, 36)
            minus.clicked.connect(lambda _, p=pos: self._decrement_digit(p))
            l.addWidget(minus, 0, Qt.AlignHCenter)

            # 为 plus/minus 添加透明度效果，便于淡出动画
            for btn in (plus, minus):
                effect = QGraphicsOpacityEffect(btn)
                btn.setGraphicsEffect(effect)
                effect.setOpacity(1.0)
                self._opacity_effects.append(effect)

            self.digit_labels.append(lbl)
            self.plus_buttons.append(plus)
            self.minus_buttons.append(minus)

            return w

        # HH
        digits_layout.addWidget(make_digit_widget(0))
        digits_layout.addWidget(make_digit_widget(1))

        # colon
        colon1 = QLabel(":", self)
        colon1.setStyleSheet(f"QLabel {{ font-family: '{self.font_family}'; font-size: 40px; font-weight: bold; }}")
        # 添加透明度效果以便在主题切换时仍可控制样式（但不动画 colon）
        effect_col1 = QGraphicsOpacityEffect(colon1)
        colon1.setGraphicsEffect(effect_col1)
        effect_col1.setOpacity(1.0)
        self.colon_labels.append(colon1)
        digits_layout.addWidget(colon1)

        # MM
        digits_layout.addWidget(make_digit_widget(2))
        digits_layout.addWidget(make_digit_widget(3))

        colon2 = QLabel(":", self)
        colon2.setStyleSheet(f"QLabel {{ font-family: '{self.font_family}'; font-size: 40px; font-weight: bold; }}")
        effect_col2 = QGraphicsOpacityEffect(colon2)
        colon2.setGraphicsEffect(effect_col2)
        effect_col2.setOpacity(1.0)
        self.colon_labels.append(colon2)
        digits_layout.addWidget(colon2)

        # SS
        digits_layout.addWidget(make_digit_widget(4))
        digits_layout.addWidget(make_digit_widget(5))

        layout.addWidget(digits_container, 1)

        # start / reset buttons area
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)

        # 按钮顺序调整：开始计时放在左边，重置放在右边（满足你的要求）
        self.start_button = PrimaryPushButton("开始计时", self)
        self.start_button.setFixedSize(150, 50)
        self.start_button.clicked.connect(self.toggle)

        self.reset_button = PushButton("重置", self)
        self.reset_button.setFixedSize(150, 50)
        self.reset_button.clicked.connect(self.reset)

        # Start on the left, Reset on the right
        btn_layout.addWidget(self.start_button)
        btn_layout.addSpacing(30)
        btn_layout.addWidget(self.reset_button)
        btn_layout.addStretch(1)

        layout.addLayout(btn_layout)

        self.update_digit_display()

    def _enforce_hour_constraints(self):
        """如果小时十位为2，则小时个位最大为3；否则为9。并修正已有值超过上限的情况。"""
        if self.digits[0] == 2:
            self.max_digit[1] = 3
        else:
            self.max_digit[1] = 9
        # clamp the hour ones digit if necessary
        if self.digits[1] > self.max_digit[1]:
            self.digits[1] = self.max_digit[1]

    def update_digit_styles(self):
        """根据主题更新数字、按钮、冒号样式"""
        is_dark = isDarkTheme()

        title_color = "#6c8fff" if is_dark else "#4a6bff"
        digit_color = "white" if is_dark else "black"
        # plus/minus color - 使用与点名按钮边框一致的颜色，让它们在深浅色下都可见
        control_color = "white" if is_dark else "#666666"
        colon_color = digit_color

        for lbl in self.digit_labels:
            lbl.setStyleSheet(f"""
                QLabel {{
                    font-family: '{self.font_family}';
                    font-size: 72px;
                    font-weight: bold;
                    color: {digit_color};
                    padding: 10px;
                    background-color: rgba(255,255,255,0.04);
                    border: 2px solid {title_color};
                    border-radius: 8px;
                }}
            """)

        # plus/minus button style (small circular)
        for btn in self.plus_buttons + self.minus_buttons:
            btn.setStyleSheet(f"""
                PushButton {{
                    font-family: '{self.font_family}';
                    font-size: 20px;
                    color: {control_color};
                    border-radius: 18px;
                    border: 1px solid rgba(0,0,0,0.12);
                    background: rgba(255,255,255,0.02);
                }}
                PushButton:hover {{
                    background: rgba(255,255,255,0.04);
                }}
                PushButton:pressed {{
                    background: rgba(255,255,255,0.06);
                }}
            """)

        # 冒号也需随主题改变颜色
        for col in self.colon_labels:
            col.setStyleSheet(f"QLabel {{ font-family: '{self.font_family}'; font-size: 40px; font-weight: bold; color: {colon_color}; background: transparent; }}")

        # 更新开始/重置按钮颜色（重置按钮设为与"重新加载"相同的黄色）
        acrylic_style = """
            %s {
                background-color: rgba(128, 128, 128, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            %s:hover {
                background-color: rgba(128, 128, 128, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.4);
            }
            %s:pressed {
                background-color: rgba(128, 128, 128, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.5);
            }
        """
        start_style = acrylic_style % ("PrimaryPushButton", "PrimaryPushButton", "PrimaryPushButton") + """
            PrimaryPushButton {
                color: #4caf50;
            }
        """
        stop_style = acrylic_style % ("PrimaryPushButton", "PrimaryPushButton", "PrimaryPushButton") + """
            PrimaryPushButton {
                color: #d13438;
            }
        """
        reset_style = acrylic_style % ("PushButton", "PushButton", "PushButton") + """
            PushButton {
                color: #ff9800;
            }
        """

        if self.is_running:
            self.start_button.setText("暂停计时")
            self.start_button.setStyleSheet(stop_style)
        else:
            self.start_button.setText("开始计时")
            self.start_button.setStyleSheet(start_style)

        self.reset_button.setStyleSheet(reset_style)

    def update_button_styles(self):
        """更新按钮样式（与 update_digit_styles 合并）"""
        self.update_digit_styles()

    def _digits_to_seconds(self, digits):
        """将 digits 数组转换为总秒数"""
        h = digits[0] * 10 + digits[1]
        m = digits[2] * 10 + digits[3]
        s = digits[4] * 10 + digits[5]
        return h * 3600 + m * 60 + s

    def _seconds_to_digits(self, seconds):
        """将总秒数转换为 digits 数组"""
        seconds = max(0, seconds)
        h = seconds // 3600
        seconds %= 3600
        m = seconds // 60
        s = seconds % 60
        return [h // 10, h % 10, m // 10, m % 10, s // 10, s % 10]

    def update_digit_display(self):
        """根据 digits 数组更新数字显示"""
        for i, lbl in enumerate(self.digit_labels):
            lbl.setText(str(self.digits[i]))

    def _increment_digit(self, pos):
        if self.is_running:
            return
        self.digits[pos] += 1
        if self.digits[pos] > self.max_digit[pos]:
            self.digits[pos] = 0
        # 特殊处理：小时十位变化时，需要更新小时个位的上限
        if pos == 0:
            self._enforce_hour_constraints()
        self.update_digit_display()

    def _decrement_digit(self, pos):
        if self.is_running:
            return
        self.digits[pos] -= 1
        if self.digits[pos] < 0:
            self.digits[pos] = self.max_digit[pos]
        if pos == 0:
            self._enforce_hour_constraints()
        self.update_digit_display()

    def toggle(self):
        """切换计时器状态"""
        if self.is_running:
            self.stop()
        else:
            self.start()

    def start(self):
        """开始倒计时"""
        total_seconds = self._digits_to_seconds(self.digits)
        if total_seconds == 0:
            InfoBar.warning(
                title="警告",
                content="倒计时时间不能为0",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2000,
                parent=self
            )
            return

        # 保存当前 digits 对应的秒数（用于重置）
        self._pre_start_seconds = total_seconds
        self._initial_seconds = total_seconds

        self.is_running = True
        self.start_button.setText("暂停计时")
        self.update_button_styles()

        # 淡出加减按钮
        self._fade_out_controls()

        self.timer.start(1000)  # 1 second interval

    def stop(self):
        """暂停倒计时"""
        self.is_running = False
        self.start_button.setText("开始计时")
        self.update_button_styles()

        # 淡入加减按钮
        self._fade_in_controls()

        self.timer.stop()

    def reset(self):
        """重置倒计时"""
        self.stop()
        # 如果开始前有保存的秒数，则恢复；否则恢复为初始值
        if self._pre_start_seconds is not None:
            self.digits = self._seconds_to_digits(self._pre_start_seconds)
        elif self._initial_seconds is not None:
            self.digits = self._seconds_to_digits(self._initial_seconds)
        else:
            # 默认重置为 00:05:00
            self.digits = [0, 0, 0, 5, 0, 0]
        self._enforce_hour_constraints()
        self.update_digit_display()

    def _tick(self):
        """每秒触发一次，倒计时减一秒"""
        total_seconds = self._digits_to_seconds(self.digits)
        total_seconds -= 1
        if total_seconds < 0:
            self._timeout()
            return
        self.digits = self._seconds_to_digits(total_seconds)
        self.update_digit_display()

    def _timeout(self):
        """倒计时结束"""
        self.stop()
        # 播放提示音
        self._play_timeout_sound()
        # 显示提示
        InfoBar.success(
            title="完成",
            content="倒计时结束",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )

    def _play_timeout_sound(self):
        """播放提示音"""
        try:
            if QMediaPlayer is None:
                return
            if self._player is None:
                self._player = QMediaPlayer()
            sound_file = "assets/timeout.mp3"
            if os.path.exists(sound_file):
                url = QUrl.fromLocalFile(os.path.abspath(sound_file))
                self._player.setMedia(QMediaContent(url))
                self._player.play()
        except Exception:
            pass

    def _fade_out_controls(self):
        """淡出加减按钮"""
        self._clear_animations()
        for effect in self._opacity_effects:
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(300)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()
            self._animations.append(anim)

    def _fade_in_controls(self):
        """淡入加减按钮"""
        self._clear_animations()
        for effect in self._opacity_effects:
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(300)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()
            self._animations.append(anim)

    def _clear_animations(self):
        """清除动画"""
        for anim in self._animations:
            anim.stop()
        self._animations.clear()


class CustomSettingCard(CardWidget):
    """自定义设置卡片"""
    def __init__(self, icon, title, content, widget, parent=None, font_family="Microsoft YaHei"):
        super().__init__(parent)
        self.icon = icon
        self.title = title
        self.content = content
        self.widget = widget
        self.font_family = font_family

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)

        title_layout = QHBoxLayout()

        icon_widget = IconWidget(self.icon, self)
        icon_widget.setFixedSize(16, 16)
        title_layout.addWidget(icon_widget)

        title_layout.addSpacing(8)

        title_label = BodyLabel(self.title, self)
        title_label.setStyleSheet(f"BodyLabel {{ font-family: '{self.font_family}'; font-weight: bold; background: transparent; border: none; }}")
        title_layout.addWidget(title_label)

        title_layout.addStretch(1)

        layout.addLayout(title_layout)

        if self.content:
            content_label = CaptionLabel(self.content, self)
            content_label.setStyleSheet(f"CaptionLabel {{ font-family: '{self.font_family}'; color: gray; margin-top: 4px; background: transparent; border: none; }}")
            layout.addWidget(content_label)

        if self.widget:
            layout.addSpacing(12)
            layout.addWidget(self.widget)

        self.setStyleSheet("""
            QLabel, BodyLabel, TitleLabel, CaptionLabel {
                background: transparent;
                border: none;
            }
        """)


class SwitchSettingCard(SettingCard):
    """开关设置卡片"""
    def __init__(self, icon, title, content, config_name, parent=None, font_family="Microsoft YaHei"):
        super().__init__(icon, title, content, parent)
        self.config_name = config_name
        self.font_family = font_family
        self.switch = SwitchButton()
        
        # 更新字体
        self.titleLabel.setStyleSheet(f"QLabel {{ font-family: '{self.font_family}'; }}")
        self.contentLabel.setStyleSheet(f"QLabel {{ font-family: '{self.font_family}'; }}")
        
        # 添加开关到布局最右边
        self.hBoxLayout.addWidget(self.switch, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)


class SettingsInterface(ScrollArea):
    """设置界面 - 所有设置在一个页面"""
    def __init__(self, parent=None, font_family="Microsoft YaHei"):
        super().__init__(parent)
        self.parent_window = parent
        self.settings = parent.settings if parent else Settings()
        self.font_family = font_family
        self.setObjectName("SettingsInterface")
        self.setup_ui()
        # 延迟加载 logo 等资源，减少阻塞
        QTimer.singleShot(0, self.load_logo)
        self.update_theme_style()

        # 下载相关变量
        self.download_signals = DownloadSignals()
        self.download_signals.progress_updated.connect(self.on_download_progress)
        self.download_signals.download_finished.connect(self.on_download_finished)
        self.download_signals.error_occurred.connect(self.on_download_error)
        self.download_info_bar = None

    def setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        # 给容器设置对象名，避免对所有 QWidget 使用通配样式
        container.setObjectName("settings_container")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 20, 40, 40)
        layout.setSpacing(20)

        # 标题
        self.title_label = TitleLabel("系统设置", self)
        self.title_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.title_label)

        # 常规设置组
        self.general_label = BodyLabel("常规设置", self)
        layout.addWidget(self.general_label)

        # 自动保存设置 - 使用开关卡片
        self.auto_save_card = SwitchSettingCard(
            FluentIcon.SAVE,
            "自动保存设置",
            "自动保存所有更改到配置文件",
            "auto_save",
            self,
            self.font_family
        )
        self.auto_save_card.switch.setChecked(self.settings.auto_save)
        self.auto_save_card.switch.checkedChanged.connect(self.on_auto_save_changed)
        layout.addWidget(self.auto_save_card)

        # 避免重复点名 - 使用开关卡片
        self.avoid_repetition_card = SwitchSettingCard(
            FluentIcon.SYNC,
            "避免重复点名",
            "确保同一人不会被重复点到，直到所有名字都被点过",
            "avoid_repetition",
            self,
            self.font_family
        )
        self.avoid_repetition_card.switch.setChecked(self.settings.avoid_repetition)
        self.avoid_repetition_card.switch.checkedChanged.connect(self.on_avoid_repetition_changed)
        layout.addWidget(self.avoid_repetition_card)

        # 新增：启动时检查更新 - 使用开关卡片
        self.check_update_card = SwitchSettingCard(
            FluentIcon.UPDATE,
            "启动时检查更新",
            "开启后，软件启动时自动静默检查一次更新",
            "check_update_on_startup",
            self,
            self.font_family
        )
        self.check_update_card.switch.setChecked(self.settings.check_update_on_startup)
        self.check_update_card.switch.checkedChanged.connect(self.on_check_update_on_startup_changed)
        layout.addWidget(self.check_update_card)

        # 外观设置组
        self.appearance_label = BodyLabel("外观设置", self)
        layout.addWidget(self.appearance_label)

        # 主题设置 - 保持原有布局
        theme_widget = QWidget()
        theme_layout = QHBoxLayout(theme_widget)
        theme_layout.setContentsMargins(0, 0, 0, 0)

        theme_text = BodyLabel("主题:", self)
        self.theme_combo = ComboBox(self)
        self.theme_combo.addItems(["跟随系统", "浅色", "深色"])
        theme_map = {
            Theme.AUTO: "跟随系统",
            Theme.LIGHT: "浅色",
            Theme.DARK: "深色"
        }
        self.theme_combo.setCurrentText(theme_map.get(self.settings.theme, "跟随系统"))
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)

        theme_layout.addWidget(theme_text)
        theme_layout.addSpacing(10)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch(1)

        self.theme_card = CustomSettingCard(
            FluentIcon.BRUSH,
            "主题设置",
            "调整应用程序的整体外观",
            theme_widget,
            self,
            self.font_family
        )
        layout.addWidget(self.theme_card)

        # 名单管理组
        self.name_label = BodyLabel("名单管理", self)
        layout.addWidget(self.name_label)

        # 添加名字卡片 - 保持原有布局
        add_name_widget = QWidget()
        add_name_layout = QHBoxLayout(add_name_widget)
        add_name_layout.setContentsMargins(0, 0, 0, 0)

        self.name_input = LineEdit(self)
        self.name_input.setPlaceholderText("输入新名字...")
        self.name_input.setClearButtonEnabled(True)
        self.name_input.returnPressed.connect(self.add_name)

        self.add_name_btn = PushButton("添加", self)
        self.add_name_btn.setFixedWidth(80)
        self.add_name_btn.clicked.connect(self.add_name)

        add_name_layout.addWidget(self.name_input)
        add_name_layout.addSpacing(10)
        add_name_layout.addWidget(self.add_name_btn)

        self.add_name_card = CustomSettingCard(
            FluentIcon.ADD,
            "添加新名字",
            "向名单中添加新的名字",
            add_name_widget,
            self,
            self.font_family
        )
        layout.addWidget(self.add_name_card)

        # 名单列表卡片 - 保持原有布局
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self.name_list = ListWidget(self)
        self.name_list.setMinimumHeight(200)
        list_layout.addWidget(self.name_list)

        # 操作按钮 - 将"删除选中"改为"清空名单"
        operation_layout = QHBoxLayout()
        self.export_names_btn = PushButton(FluentIcon.SHARE, "导出名单", self)
        self.import_names_btn = PushButton(FluentIcon.DOWNLOAD, "导入名单", self)
        self.clear_names_btn = PushButton(FluentIcon.DELETE, "清空名单", self)

        self.export_names_btn.clicked.connect(self.parent_window.export_name_list)
        self.import_names_btn.clicked.connect(self.parent_window.import_name_list)
        # connect to local handler which will show confirmation overlay
        self.clear_names_btn.clicked.connect(self.on_clear_names_clicked)

        operation_layout.addWidget(self.export_names_btn)
        operation_layout.addWidget(self.import_names_btn)
        operation_layout.addWidget(self.clear_names_btn)

        list_layout.addLayout(operation_layout)

        self.list_card = CustomSettingCard(
            FluentIcon.PEOPLE,
            "当前名单",
            "查看和管理当前名单",
            list_widget,
            self,
            self.font_family
        )
        layout.addWidget(self.list_card)

        # 关于信息组
        self.about_label = BodyLabel("关于", self)
        layout.addWidget(self.about_label)

        about_widget = QWidget()
        about_layout = QVBoxLayout(about_widget)
        about_layout.setSpacing(15)

        # 占位 logo_label，实际 pixmap 延后加载以加快启动
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        self.logo_label.setStyleSheet("background: transparent; border: none;")
        about_layout.addWidget(self.logo_label)

        # 简化关于信息，只保留必要的描述
        about_title = BodyLabel("基于 PyQt-Fluent-Widgets 制作", self)
        about_layout.addWidget(about_title)

        self.about_card = CustomSettingCard(
            FluentIcon.INFO,
            "软件信息",
            "关于量子点名软件",
            about_widget,
            self,
            self.font_family
        )
        layout.addWidget(self.about_card)

        # 新增：检查更新卡片（位于软件信息卡片下），展示版本并提供"检查更新"按钮
        update_widget = QWidget()
        update_layout = QHBoxLayout(update_widget)
        update_layout.setContentsMargins(0, 0, 0, 0)

        # 右侧检查更新按钮（颜色会在 update_theme_style 中根据主题切换）
        self.check_update_btn = PushButton("检查更新", self)
        self.check_update_btn.setFixedSize(120, 40)
        self.check_update_btn.clicked.connect(self.on_check_updates_clicked)

        # 添加垂直方向的弹性空间，使按钮在卡片内垂直居中
        update_layout.addStretch(1)  # 顶部弹性空间
        update_layout.addWidget(self.check_update_btn, 0, Qt.AlignVCenter)  # 垂直居中
        update_layout.addStretch(1)  # 底部弹性空间

        # 软件版本改为 3.3.3
        self.update_check_card = CustomSettingCard(
            FluentIcon.UPDATE,
            "版本信息",
            f"© 版权所有 2025, mc_xinyu. 当前版本 {self.parent_window.settings.version}",  # 使用动态版本
            update_widget,
            self,
            self.font_family
        )
        layout.addWidget(self.update_check_card)

        # 设置操作卡片 - 添加图标，保持原有布局
        settings_operation_widget = QWidget()
        settings_operation_layout = QHBoxLayout(settings_operation_widget)
        settings_operation_layout.setContentsMargins(0, 0, 0, 0)

        self.export_settings_btn = PushButton(FluentIcon.SHARE, "导出设置", self)
        self.import_settings_btn = PushButton(FluentIcon.DOWNLOAD, "导入设置", self)
        self.reset_settings_btn = PushButton(FluentIcon.DELETE, "重置设置", self)

        self.export_settings_btn.clicked.connect(self.parent_window.export_settings)
        self.import_settings_btn.clicked.connect(self.parent_window.import_settings)
        # connect to local handler which will show confirmation overlay
        self.reset_settings_btn.clicked.connect(self.on_reset_settings_clicked)

        settings_operation_layout.addWidget(self.export_settings_btn)
        settings_operation_layout.addWidget(self.import_settings_btn)
        settings_operation_layout.addWidget(self.reset_settings_btn)

        self.settings_operation_card = CustomSettingCard(
            FluentIcon.SETTING,
            "设置管理",
            "导入导出应用程序设置",
            settings_operation_widget,
            self,
            self.font_family
        )
        layout.addWidget(self.settings_operation_card)

        layout.addStretch(1)

        self.setWidget(container)

        # 刷新显示
        self.refresh_settings()
        self.refresh_name_list()
        self.update_theme_style()

    def load_logo(self):
        """延迟加载 about 卡片的 logo（避免阻塞启动）"""
        try:
            if os.path.exists("assets/logo.png"):
                logo_pixmap = QPixmap("assets/logo.png")
                logo_pixmap = logo_pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.logo_label.setPixmap(logo_pixmap)
            else:
                pass
        except Exception:
            pass

    def update_theme_style(self):
        """更新设置界面主题样式"""
        is_dark = isDarkTheme()

        # 设置滚动区域背景和主容器背景
        container_bg = 'rgb(32, 32, 32)' if is_dark else 'rgb(243, 243, 243)'
        scroll_bg = container_bg

        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {scroll_bg};
                border: none;
            }}
            QScrollArea > QWidget > QWidget#settings_container {{
                background-color: {container_bg};
            }}
        """)

        # 主题色（用于复选框等控件）：暗色模式 #6c8fff，亮色模式 #4a6bff
        # 这里也用于"检查更新"按钮的背景色，满足你的要求
        section_color = "#6c8fff" if is_dark else "#4a6bff"
        # 设置全局主题色，方便 qfluentwidgets 的控件使用主色
        setThemeColor(QColor(section_color))

        # 更新容器背景和文字样式 - 使用更具体的选择器，
        # 并确保 CardWidget 内的文本（QLabel/BodyLabel/CaptionLabel）是透明背景
        container_style = f"""
            QWidget#settings_container {{
                background-color: {container_bg};
            }}
            /* 确保所有文字控件透明背景，避免出现方框 */
            CardWidget QLabel, CardWidget BodyLabel, CardWidget TitleLabel, CardWidget CaptionLabel, QLabel, BodyLabel, TitleLabel, CaptionLabel {{
                background: transparent;
                border: none;
            }}
            QComboBox {{
                background: transparent;
            }}
            QLineEdit {{
                background: transparent;
            }}
            QListWidget {{
                background: transparent;
            }}
            PushButton {{
                background: transparent;
            }}
            PrimaryPushButton {{
                background: transparent;
            }}
            CardWidget {{
                background: {'rgba(255, 255, 255, 0.05)' if is_dark else 'rgba(255, 255, 255, 0.9)'};
                border: 1px solid {'rgba(255, 255, 255, 0.1)' if is_dark else 'rgba(0, 0, 0, 0.1)'};
                border-radius: 8px;
            }}
        """
        # 应用样式到容器（setWidget 的 widget）
        if self.widget():
            self.widget().setStyleSheet(container_style)

        # 更新标题颜色
        title_color = "white" if is_dark else "black"

        self.title_label.setStyleSheet(f"""
            TitleLabel {{
                font-family: '{self.font_family}';
                color: {title_color};
                background: transparent;
                border: none;
            }}
        """)

        # 更新分组标题颜色
        section_labels = [self.general_label, self.appearance_label, self.name_label, self.about_label]
        for label in section_labels:
            label.setStyleSheet(f"""
                BodyLabel {{
                    font-family: '{self.font_family}';
                    font-size: 18px;
                    font-weight: bold;
                    color: {section_color};
                    margin-top: 10px;
                    margin-bottom: 5px;
                    background: transparent;
                    border: none;
                }}
            """)

        # Ensure the name list items reflect the new theme color
        # (call refresh_name_list to update per-item label color)
        self.refresh_name_list()

        # 为"检查更新"按钮应用主题色（背景色），文本颜色采用黑色以便与亮色背景对比
        if hasattr(self, 'check_update_btn') and self.check_update_btn:
            # 使用更明确的样式以覆盖之前的透明样式
            # 文本颜色可根据需要改为白色以提升可读性；此处保留黑色以匹配示例截图
            self.check_update_btn.setStyleSheet(f"""
                PushButton {{
                    background-color: {section_color};
                    color: #000000;
                    border: none;
                    border-radius: 8px;
                    padding: 6px 12px;
                    font-weight: bold;
                }}
                PushButton:hover {{
                    background-color: {section_color}cc;
                }}
                PushButton:pressed {{
                    background-color: {section_color}99;
                }}
            """)

    def on_auto_save_changed(self, is_checked):
        """自动保存设置改变"""
        self.settings.auto_save = is_checked
        # 自动保存设置改变时立即保存设置
        self.parent_window.save_settings()

    def on_avoid_repetition_changed(self, is_checked):
        """避免重复设置改变"""
        self.settings.avoid_repetition = is_checked
        # 避免重复设置改变时立即保存设置
        self.parent_window.save_settings()

    def on_check_update_on_startup_changed(self, is_checked):
        """启动时检查更新设置改变"""
        self.settings.check_update_on_startup = is_checked
        # 启动时检查更新设置改变时立即保存设置
        self.parent_window.save_settings()

    def on_theme_changed(self, theme_text):
        """主题设置改变"""
        theme_map = {
            "跟随系统": Theme.AUTO,
            "浅色": Theme.LIGHT,
            "深色": Theme.DARK
        }
        self.settings.theme = theme_map.get(theme_text, Theme.AUTO)
        # 立即应用主题并更新界面
        self.parent_window.apply_settings()
        # 主题设置改变时立即保存设置
        self.parent_window.save_settings()

    def add_name(self):
        """添加名字"""
        name = self.name_input.text().strip()
        if name:
            if self.parent_window.add_name_to_list(name):
                self.name_input.clear()

    def on_clear_names_clicked(self):
        """点击'清空名单'时使用内置对话框"""
        if not self.parent_window:
            return

        title = '确认清空名单'
        content = '是否确认清空名单？此操作不可撤销。'
        
        # 使用简单的 MessageBox，确保父窗口正确
        w = MessageBox(title, content, self.window())
        
        # 修改按钮文字为中文
        w.yesButton.setText('确定')
        w.cancelButton.setText('取消')
        
        if w.exec():
            # 用户点击了确定
            self.parent_window.clear_name_list()

    def on_reset_settings_clicked(self):
        """点击'重置设置'时使用内置对话框"""
        if not self.parent_window:
            return

        title = '确认重置设置'
        content = '是否确认重置所有设置为默认值？此操作不可撤销。'
        
        # 使用简单的 MessageBox，确保父窗口正确
        w = MessageBox(title, content, self.window())
        
        # 修改按钮文字为中文
        w.yesButton.setText('确定')
        w.cancelButton.setText('取消')
        
        if w.exec():
            # 用户点击了确定
            self.parent_window.reset_settings()

    def remove_selected_name(self):
        """已废弃：原来的删除选中功能不再用于 UI"""
        current_item = self.name_list.currentItem()
        if current_item:
            # 这里保留旧逻辑但不再调用本地刷新（主窗口会刷新）
            widget = self.name_list.itemWidget(current_item)
            if widget:
                # 尝试从 item widget 中找 label 文本
                label = widget.findChild(QLabel)
                if label:
                    name = label.text()
                    if self.parent_window.remove_name_from_list(name):
                        pass

    def refresh_name_list(self):
        """刷新名单列表"""
        # 禁止中间更新以减少绘制开销
        self.name_list.setUpdatesEnabled(False)
        self.name_list.blockSignals(True)

        # 保存当前滚动值（绝对值），稍后尽量恢复它
        scrollbar = self.name_list.verticalScrollBar()
        old_value = scrollbar.value() if scrollbar else 0

        self.name_list.clear()

        # Determine text color based on current theme
        text_color = "white" if isDarkTheme() else "black"

        # 确保使用与点名界面相同的名单管理器实例
        for name in self.parent_window.name_manager.names:
            # Create a custom widget for each list item with a delete button
            item = QListWidgetItem()
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(8, 4, 8, 4)
            row_layout.setSpacing(10)

            name_label = QLabel(name)
            # include color so it follows theme changes
            name_label.setStyleSheet(f"QLabel {{ font-family: '{self.font_family}'; color: {text_color}; background: transparent; border: none; }}")
            row_layout.addWidget(name_label)
            row_layout.addStretch(1)

            delete_btn = PushButton(FluentIcon.DELETE, "删除", self)
            delete_btn.setFixedHeight(28)
            delete_btn.setFixedWidth(80)
            # bind the current name to the slot to avoid late-binding issue
            delete_btn.clicked.connect(lambda _, n=name: self.on_delete_name_clicked(n))
            row_layout.addWidget(delete_btn)

            item.setSizeHint(row_widget.sizeHint())
            self.name_list.addItem(item)
            self.name_list.setItemWidget(item, row_widget)

        # 计算应恢复的滚动值：尽量保持原来的位置，超出范围时使用新的最大值
        if scrollbar:
            new_max = scrollbar.maximum()
            new_value = max(0, min(old_value, new_max))
            # 将恢复操作放到下一轮事件循环，确保布局/maximum 已稳定
            QTimer.singleShot(0, lambda val=new_value, sb=scrollbar: sb.setValue(val))

        # 恢复更新和信号
        self.name_list.blockSignals(False)
        self.name_list.setUpdatesEnabled(True)

    def on_delete_name_clicked(self, name):
        """处理单个名字的删除请求"""
        if not name:
            return
        # 仅调用主窗口的删除接口；主窗口会负责刷新界面和保存（已优化为异步保存）
        if self.parent_window:
            # 单条删除不再显示确认遮罩（只对清空/重置做确认）
            self.parent_window.remove_name_from_list(name)

    def refresh_settings(self):
        """刷新设置显示"""
        self.auto_save_card.switch.setChecked(self.settings.auto_save)
        self.avoid_repetition_card.switch.setChecked(self.settings.avoid_repetition)
        self.check_update_card.switch.setChecked(self.settings.check_update_on_startup)

        theme_map = {
            Theme.AUTO: "跟随系统",
            Theme.LIGHT: "浅色",
            Theme.DARK: "深色"
        }
        self.theme_combo.setCurrentText(theme_map.get(self.settings.theme, "跟随系统"))

    def on_check_updates_clicked(self):
        """检查更新按钮逻辑 - 从GitHub获取最新版本信息"""
        self._check_updates(silent=False)

    def silent_check_updates_on_startup(self):
        """启动时静默检查更新"""
        self._check_updates(silent=True)

    def _check_updates(self, silent=False):
        """检查更新核心逻辑"""
        try:
            # 从指定URL获取最新版本信息
            url = "https://ghproxy.net/https://raw.githubusercontent.com/mc-xinyu/QuantumRollCallUpdate/main/version.txt"
            with urllib.request.urlopen(url, timeout=10) as response:
                content = response.read().decode('utf-8').strip()
                lines = content.split('\n')
                
                if len(lines) >= 2:
                    latest_version = lines[0].strip()
                    download_url = lines[1].strip()
                    
                    current_version = self.parent_window.settings.version
                    
                    if latest_version != current_version:
                        if not silent:
                            # 显示更新对话框
                            title = "检查更新"
                            content = f"发现新版本 {latest_version}，是否立即更新？"
                            
                            w = MessageBox(title, content, self.window())
                            w.yesButton.setText('确定')
                            w.cancelButton.setText('取消')
                            
                            if w.exec():
                                # 用户点击确定，下载更新包
                                self.start_download_update(latest_version, download_url)
                        else:
                            # 启动静默检查时，发现新版本则弹出对话框（和手动一样）
                            title = "检查更新"
                            content = f"发现新版本 {latest_version}，是否立即更新？"
                            
                            w = MessageBox(title, content, self.window())
                            w.yesButton.setText('确定')
                            w.cancelButton.setText('取消')
                            
                            if w.exec():
                                # 用户点击确定，下载更新包
                                self.start_download_update(latest_version, download_url)
                    else:
                        if not silent:
                            InfoBar.success(
                                title="检查更新",
                                content="当前已是最新版本",
                                orient=Qt.Horizontal,
                                isClosable=True,
                                position=InfoBarPosition.TOP_RIGHT,
                                duration=2000,
                                parent=self
                            )
                        # silent: do nothing
                else:
                    raise ValueError("无法检查更新")
                    
        except Exception as e:
            if not silent:
                print(f"检查更新失败: {e}")
                InfoBar.error(
                    title="检查更新",
                    content="无法连接至更新服务器，请检查网络连接",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )
            # silent: do nothing

    def start_download_update(self, version, url):
        """开始下载更新（使用线程避免界面卡死）"""
        # 创建下载进度消息条
        self.download_info_bar = InfoBar(
            icon=InfoBarIcon.INFORMATION,
            title="更新",
            content="正在下载更新",
            orient=Qt.Horizontal,
            isClosable=False,
            position=InfoBarPosition.TOP,
            duration=-1,  # 永久显示
            parent=self
        )
        self.download_info_bar.show()
        
        # 在线程中执行下载
        download_thread = threading.Thread(
            target=self.download_update_thread,
            args=(version, url)
        )
        download_thread.daemon = True
        download_thread.start()

    def download_update_thread(self, version, url):
        """下载更新的线程函数"""
        try:
            # 创建downloads目录
            downloads_dir = "downloads"
            os.makedirs(downloads_dir, exist_ok=True)
            
            # 下载文件
            filename = os.path.join(downloads_dir, f"{version}.zip")
            
            def update_progress(block_num, block_size, total_size):
                """更新下载进度"""
                if total_size > 0:
                    downloaded = block_num * block_size
                    self.download_signals.progress_updated.emit(downloaded, total_size)
            
            # 下载文件
            urllib.request.urlretrieve(url, filename, update_progress)
            
            # 解压文件到 downloads/update 目录
            extract_path = os.path.join(downloads_dir, "update")
            os.makedirs(extract_path, exist_ok=True)
            
            with zipfile.ZipFile(filename, 'r') as zip_ref:
                # 获取压缩包中根目录的所有文件和文件夹
                for file_info in zip_ref.infolist():
                    # 提取根目录下的文件和文件夹（不包含子目录中的内容）
                    if '/' not in file_info.filename or file_info.filename.count('/') == 1:
                        # 如果是根目录的文件或一级子目录
                        zip_ref.extract(file_info, extract_path)
            
            # 下载完成
            self.download_signals.download_finished.emit()
            
        except Exception as e:
            error_msg = f"下载更新失败: {str(e)}"
            self.download_signals.error_occurred.emit(error_msg)

    def on_download_progress(self, downloaded, total_size):
        """更新下载进度"""
        if total_size > 0:
            progress = int(downloaded * 100 / total_size)
            if self.download_info_bar:
                self.download_info_bar.setContent(f"下载进度: {progress}%")
                
            # 如果下载完成
            if downloaded >= total_size:
                if self.download_info_bar:
                    self.download_info_bar.setContent("下载完成，正在解压...")

    def on_download_finished(self):
        """下载完成处理"""
        if self.download_info_bar:
            self.download_info_bar.close()
            self.download_info_bar = None
        
        # 查找并运行程序根目录的 Update.exe
        current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        update_exe_path = os.path.join(current_dir, "Update.exe")
        
        if os.path.exists(update_exe_path):
            try:
                import subprocess
                subprocess.Popen([update_exe_path])
                
                # 静默关闭程序，不显示任何消息条
                QTimer.singleShot(500, QApplication.quit)
            except Exception as e:
                InfoBar.error(
                    title="错误",
                    content=f"无法启动更新程序: {str(e)}",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self
                )
        else:
            InfoBar.error(
                title="警告",
                content="更新下载完成，未找到更新程序",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=self
            )

    def on_download_error(self, error_msg):
        """错误处理"""
        print(error_msg)
        if self.download_info_bar:
            self.download_info_bar.close()
            self.download_info_bar = None
            
        InfoBar.error(
            title="更新",
            content="无法下载更新文件，请检查网络连接",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=3000,
            parent=self
        )


if __name__ == '__main__':
    # 启用高DPI缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # 设置应用程序名称与版本 - 只保留应用程序名称
    app.setApplicationName("量子点名系统")
    app.setApplicationDisplayName("量子点名系统")

    # 设置进程名称
    try:
        from ctypes import windll
        windll.shell32.SetCurrentProcessExplicitAppUserModelID("量子点名系统")
    except Exception:
        pass

    # 仅使用 assets/icon.ico 作为应用图标（若不存在则不设置）
    try:
        ico_path = "assets/icon.ico"
        if os.path.exists(ico_path):
            app_icon = QIcon(ico_path)
        else:
            app_icon = QIcon()
        app.setWindowIcon(app_icon)
    except Exception:
        pass

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec_())
