import os
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox
import time
import sys

def show_error_message(title, message):
    """显示错误弹窗"""
    try:
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        root.attributes("-topmost", True)  # 确保窗口在最前面
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        pass

def kill_process_by_name(process_name):
    """强制结束指定进程名的进程"""
    try:
        killed = False
        
        if sys.platform == "win32":
            # Windows系统使用taskkill命令
            try:
                result = subprocess.run(
                    ["taskkill", "/f", "/im", process_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 or "成功" in result.stdout or "SUCCESS" in result.stdout:
                    killed = True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        else:
            # Linux/macOS系统使用pkill命令
            try:
                result = subprocess.run(
                    ["pkill", "-f", process_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    killed = True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        # 等待进程完全结束
        if killed:
            time.sleep(2)
            
        return True
        
    except Exception as e:
        show_error_message("进程结束错误", f"结束进程 {process_name} 时出错: {str(e)}")
        return False

def copy_and_replace_files(source_dir, target_dir):
    """复制并替换文件，但保留目标目录中的不同名文件"""
    try:
        # 确保源目录存在
        if not os.path.exists(source_dir):
            show_error_message("目录错误", f"更新目录不存在: {source_dir}")
            return False
        
        # 确保目标目录存在
        os.makedirs(target_dir, exist_ok=True)
        
        copied_count = 0
        error_count = 0
        
        def copy_item(source_path, relative_path):
            """递归复制项目"""
            nonlocal copied_count, error_count
            
            target_path = os.path.join(target_dir, relative_path)
            
            try:
                if os.path.isdir(source_path):
                    # 如果是目录，确保目标目录存在，然后递归复制内容
                    os.makedirs(target_path, exist_ok=True)
                    
                    # 递归复制子目录和文件
                    for item_name in os.listdir(source_path):
                        item_source_path = os.path.join(source_path, item_name)
                        item_relative_path = os.path.join(relative_path, item_name)
                        copy_item(item_source_path, item_relative_path)
                        
                else:
                    # 如果是文件，复制并替换
                    shutil.copy2(source_path, target_path)
                    copied_count += 1
                    
            except PermissionError as e:
                error_count += 1
                show_error_message("权限错误", f"复制文件 {relative_path} 时权限不足: {str(e)}")
                return False
            except Exception as e:
                error_count += 1
                show_error_message("文件复制错误", f"复制文件 {relative_path} 时出错: {str(e)}")
                return False
            
            return True
        
        # 开始复制过程
        for item_name in os.listdir(source_dir):
            source_path = os.path.join(source_dir, item_name)
            if not copy_item(source_path, item_name):
                return False
        
        return copied_count > 0 or error_count == 0
        
    except Exception as e:
        show_error_message("文件复制错误", f"复制文件时发生错误: {str(e)}")
        return False

def move_and_replace_files(source_dir, target_dir):
    """移动并替换文件，但保留目标目录中的不同名文件"""
    try:
        # 先复制文件到目标目录
        if not copy_and_replace_files(source_dir, target_dir):
            return False
        
        # 复制成功后，删除源目录中的文件
        try:
            if os.path.exists(source_dir):
                for item_name in os.listdir(source_dir):
                    item_path = os.path.join(source_dir, item_name)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
        except Exception:
            # 清理失败不影响主要功能，继续执行
            pass
        
        return True
        
    except Exception as e:
        show_error_message("文件移动错误", f"移动文件时发生错误: {str(e)}")
        return False

def start_program_background(program_path):
    """在后台启动程序"""
    try:
        if not os.path.exists(program_path):
            show_error_message("程序启动错误", f"程序文件不存在: {program_path}")
            return False
        
        # 在后台启动程序
        startupinfo = None
        creationflags = 0
        
        if sys.platform == "win32":
            # Windows系统隐藏控制台窗口
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW
            
            subprocess.Popen(
                [program_path],
                startupinfo=startupinfo,
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False
            )
        else:
            # Linux/macOS系统在后台启动
            subprocess.Popen(
                [program_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        
        return True
        
    except Exception as e:
        show_error_message("程序启动错误", f"启动程序时出错: {str(e)}")
        return False

def cleanup_empty_directories(dir_path):
    """清理空目录"""
    try:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            # 检查目录是否为空
            if not os.listdir(dir_path):
                os.rmdir(dir_path)
    except Exception:
        pass

def main():
    """主更新程序"""
    try:
        # 获取当前程序所在目录
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe文件
            current_dir = os.path.dirname(sys.executable)
        else:
            # 如果是Python脚本
            current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 定义路径
        downloads_dir = os.path.join(current_dir, "downloads")
        update_dir = os.path.join(downloads_dir, "update", "RollCall-Main")
        target_dir = current_dir
        rollcall_exe = os.path.join(current_dir, "RollCall.exe")
        
        # 1. 结束 RollCall.exe 进程
        if not kill_process_by_name("RollCall.exe"):
            # 即使结束进程失败也继续，可能进程本来就没运行
            pass
        
        # 等待确保进程完全结束
        time.sleep(1)
        
        # 2. 移动更新文件（只替换同名文件，保留不同名文件）
        if os.path.exists(update_dir):
            if not move_and_replace_files(update_dir, target_dir):
                return False
            
            # 清理空目录
            cleanup_empty_directories(update_dir)
            cleanup_empty_directories(os.path.join(downloads_dir, "update"))
            cleanup_empty_directories(downloads_dir)
        
        # 3. 启动新的 RollCall.exe
        if not start_program_background(rollcall_exe):
            return False
        
        return True
        
    except Exception as e:
        show_error_message("更新错误", f"更新过程中发生未知错误: {str(e)}")
        return False

if __name__ == "__main__":
    # 在Windows上隐藏控制台窗口
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass
    
    # 运行主程序
    success = main()
    
    # 程序完成后退出
    sys.exit(0 if success else 1)