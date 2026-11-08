import tkinter as tk
from tkinter import filedialog, messagebox
import os

def select_folder():
    folder_path = filedialog.askdirectory()
    if folder_path:
        list_files(folder_path)
    

def list_files(folder_path):
    files = os.listdir(folder_path)
    for file in files:
        if os.path.isfile(os.path.join(folder_path, file)):
            file_path = os.path.join(folder_path, file)
            print(f"File: {file_path}")
            rename_file(file_path)

def rename_file(file_path):
    new_name = input(f"Enter new name for {file_path}: ")
    if new_name:
        new_file_path = os.path.join(os.path.dirname(file_path), new_name)
        os.rename(file_path, new_file_path)
        print(f"Renamed {file_path} to {new_file_path}")

# Create the main window
root = tk.Tk()
root.title("File Renamer")

# Create a button to select the folder
select_button = tk.Button(root, text="Select Folder", command=select_folder)
select_button.pack(pady=20)

# Start the GUI event loop
root.mainloop()