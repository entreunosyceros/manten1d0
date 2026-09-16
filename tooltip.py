import tkinter as tk


class ToolTip:
    """
    Clase para generar un tooltip en los botones creados.

    Uso:
        tooltip = ToolTip(widget, texto)

    Parámetros:
        widget (tkinter.Widget): El widget al que se asociará el tooltip.
        text (str): El texto que se mostrará en el tooltip.

    Métodos:
        show_tooltip(event=None):
            Muestra el tooltip cuando el cursor entra en el widget.
        hide_tooltip(event=None):
            Oculta el tooltip cuando el cursor sale del widget o se hace clic en él.
    """

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self._after_id = None
        self.widget.bind("<Enter>", self._programar, add="+")
        self.widget.bind("<Leave>", self._cancelar, add="+")
        self.widget.bind("<ButtonPress>", self._cancelar, add="+")
        self.widget.bind("<Destroy>", self._cancelar, add="+")

    def _programar(self, event=None):
        self._cancelar_espera()
        try:
            self._after_id = self.widget.after(400, self.show_tooltip)
        except tk.TclError:
            self._after_id = None

    def _cancelar(self, event=None):
        self._cancelar_espera()
        self.hide_tooltip()

    def _cancelar_espera(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def show_tooltip(self, event=None):
        self._after_id = None
        self.hide_tooltip()
        try:
            if not self.widget.winfo_exists():
                return
        except tk.TclError:
            return

        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        try:
            self.tooltip.attributes("-topmost", True)
        except tk.TclError:
            pass
        label = tk.Label(
            self.tooltip,
            text=self.text,
            bg="#ffffe0",
            relief="solid",
            borderwidth=1,
            justify=tk.LEFT,
            wraplength=360,
        )
        label.pack(ipadx=5, ipady=2)
        self.tooltip.bind("<Leave>", self._cancelar)
        self.tooltip.bind("<ButtonPress>", self._cancelar)

    def hide_tooltip(self, event=None):
        ventana = self.tooltip
        self.tooltip = None
        if ventana is None:
            return
        try:
            ventana.destroy()
        except tk.TclError:
            pass


def con_tooltip(widget, texto):
    """Asocia un tooltip descriptivo al widget y lo devuelve para poder encadenar pack/grid."""
    ToolTip(widget, texto)
    return widget
