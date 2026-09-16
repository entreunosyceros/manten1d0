import os
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog


def carpeta_notas():
    """Carpeta fija de notas del usuario: Documentos/Manten1d0/Notas."""
    documentos = os.path.expanduser("~/Documentos")
    if not os.path.isdir(documentos):
        documentos = os.path.expanduser("~/Documents")
    if not os.path.isdir(documentos):
        documentos = os.path.expanduser("~")
    ruta = os.path.join(documentos, "Manten1d0", "Notas")
    os.makedirs(ruta, exist_ok=True)
    return ruta


def listar_notas(limite=12):
    carpeta = carpeta_notas()
    notas = []
    try:
        nombres = os.listdir(carpeta)
    except OSError:
        return []
    for nombre in nombres:
        if not nombre.lower().endswith((".txt", ".md")):
            continue
        ruta = os.path.join(carpeta, nombre)
        if os.path.isfile(ruta):
            notas.append((os.path.getmtime(ruta), ruta, nombre))
    notas.sort(reverse=True)
    return notas[:limite]


def nombre_nota_nuevo():
    return datetime.now().strftime("nota-%Y-%m-%d-%H%M.txt")


class EditorTextos:
    def __init__(self, root, ruta_inicial=None):
        self.root = root
        self.root.title("Editor de Texto")
        self.root.geometry("800x600")
        self.ruta_archivo = ruta_inicial

        self.create_menu()
        self.create_text_area()
        self.create_status_bar()
        self.create_context_menu()
        if ruta_inicial:
            self._cargar_ruta(ruta_inicial)
        else:
            self.update_word_and_char_count()
            self.update_line_numbers()
        self._actualizar_titulo()

    def create_menu(self):
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Nuevo", command=self.new_file)
        file_menu.add_command(label="Abrir", command=self.open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Guardar", command=self.save_file)
        file_menu.add_command(label="Guardar como...", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.exit_program)
        menu_bar.add_cascade(label="Archivo", menu=file_menu)

        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Buscar", command=self.search_text)
        edit_menu.add_separator()
        edit_menu.add_command(label="Deshacer", command=self.undo)
        edit_menu.add_command(label="Rehacer", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Copiar (Ctrl+C)", command=self.copy_text)
        edit_menu.add_command(label="Pegar (Ctrl+V)", command=self.paste_text)
        menu_bar.add_cascade(label="Opciones", menu=edit_menu)

    def create_text_area(self):
        frame = tk.Frame(self.root)
        frame.pack(fill="both", expand=True)

        self.line_numbers = tk.Label(frame, width=4, bg="lightgrey", anchor='nw')
        self.line_numbers.pack(side="left", fill="y")

        self.text_area = tk.Text(frame, wrap="word", undo=True)
        self.text_area.pack(side="left", fill="both", expand=True)

        self.scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.text_area.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.text_area.config(yscrollcommand=self.scrollbar.set)

        self.text_area.bind("<Key>", self.update_line_numbers)
        self.text_area.bind("<KeyRelease>", self.update_word_and_char_count)
        self.text_area.bind("<Button-3>", self.show_context_menu)
        self.root.bind("<Control-s>", lambda _e: self.save_file())

    def create_status_bar(self):
        self.status_bar = tk.Label(self.root, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.update_word_and_char_count()

    def create_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copiar", command=self.copy_text)
        self.context_menu.add_command(label="Pegar", command=self.paste_text)
        self.context_menu.add_command(label="Deshacer", command=self.undo)
        self.context_menu.add_command(label="Rehacer", command=self.redo)
        self.context_menu.add_command(label="Buscar", command=self.search_text)

    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def update_line_numbers(self, event=None):
        lines = self.text_area.get("1.0", "end-1c").split('\n')
        line_numbers_text = "\n".join(str(i + 1) for i in range(len(lines)))
        self.line_numbers.config(text=line_numbers_text)

    def update_word_and_char_count(self, event=None):
        text = self.text_area.get("1.0", "end-1c")
        words = len(text.split())
        characters = len(text)
        carpeta = carpeta_notas()
        self.status_bar.config(
            text=f"Palabras: {words}  Caracteres: {characters}  |  Notas: {carpeta}"
        )

    def _actualizar_titulo(self):
        nombre = os.path.basename(self.ruta_archivo) if self.ruta_archivo else "Nota nueva"
        self.root.title(f"Editor de Texto — {nombre}")

    def _cargar_ruta(self, ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as file:
                content = file.read()
        except OSError as error:
            messagebox.showerror("Notas", f"No se pudo abrir la nota:\n{error}", parent=self.root)
            return
        self.text_area.delete(1.0, "end")
        self.text_area.insert("end", content)
        self.ruta_archivo = ruta
        self.update_line_numbers()
        self.update_word_and_char_count()
        self._actualizar_titulo()

    def _escribir(self, ruta):
        with open(ruta, "w", encoding="utf-8") as file:
            file.write(self.text_area.get(1.0, "end-1c"))
        self.ruta_archivo = ruta
        self._actualizar_titulo()
        messagebox.showinfo("Notas", f"Guardada en:\n{ruta}", parent=self.root)

    def new_file(self):
        self.text_area.delete(1.0, "end")
        self.ruta_archivo = None
        self.update_line_numbers()
        self.update_word_and_char_count()
        self._actualizar_titulo()

    def open_file(self):
        file_path = filedialog.askopenfilename(
            parent=self.root,
            initialdir=carpeta_notas(),
            filetypes=[("Text files", "*.txt"), ("Markdown files", "*.md")],
        )
        if file_path:
            self._cargar_ruta(file_path)

    def save_file(self):
        if self.ruta_archivo:
            try:
                self._escribir(self.ruta_archivo)
            except OSError as error:
                messagebox.showerror("Notas", f"No se pudo guardar:\n{error}", parent=self.root)
            return
        self.save_file_as(os.path.join(carpeta_notas(), nombre_nota_nuevo()))

    def save_file_as(self, inicial=None):
        file_path = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".txt",
            initialdir=carpeta_notas(),
            initialfile=os.path.basename(inicial) if inicial else nombre_nota_nuevo(),
            filetypes=[("Text files", "*.txt"), ("Markdown files", "*.md")],
        )
        if file_path:
            try:
                self._escribir(file_path)
            except OSError as error:
                messagebox.showerror("Notas", f"No se pudo guardar:\n{error}", parent=self.root)

    def exit_program(self):
        if messagebox.askokcancel("Salir", "¿Estás seguro de que quieres salir?", parent=self.root):
            self.root.destroy()

    def copy_text(self):
        self.text_area.event_generate("<<Copy>>")

    def paste_text(self):
        self.text_area.event_generate("<<Paste>>")

    def undo(self):
        self.text_area.edit_undo()

    def redo(self):
        self.text_area.edit_redo()

    def search_text(self):
        search_query = simpledialog.askstring("Buscar", "Escribe el texto a buscar:", parent=self.root)
        if search_query:
            start_pos = '1.0'
            while True:
                start_pos = self.text_area.search(search_query, start_pos, stopindex=tk.END)
                if not start_pos:
                    break
                end_pos = f"{start_pos}+{len(search_query)}c"
                self.text_area.tag_add("highlight", start_pos, end_pos)
                start_pos = end_pos
            self.text_area.tag_config("highlight", background="yellow", foreground="black")


def main():
    root = tk.Tk()
    EditorTextos(root)
    root.mainloop()

if __name__ == "__main__":
    main()
