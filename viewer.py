#!/bin/python
"""
Minimal ASC viewer without menu.
- Symbols are loaded automatically from ./sym
- ASC file is loaded automatically from ./asc
"""

import os
import wx
from asc_viewer import AscCanvas

# =========================
# CONFIGURATION
# =========================

ASC_FILENAME = "transistor.asc"  # <-- nom du fichier dans ./asc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASC_DIR = os.path.join(BASE_DIR, "asc")
SYM_DIR = os.path.join(BASE_DIR, "sym")


class AscViewer(wx.Frame):
    def __init__(self):
        super().__init__(
            None,
            title="LTspice ASC Viewer",
            size=(800, 600),
        )

        # Status Bar
        self.statusbar = self.CreateStatusBar(1, wx.STB_DEFAULT_STYLE)

        # Canvas
        self.asc_canvas = AscCanvas(self)
        self.asc_canvas.Bind(wx.EVT_MOTION, self.on_motion)

        self._load_symbols()
        self._load_asc()

        self.Layout()

    def _load_symbols(self):
        if not os.path.isdir(SYM_DIR):
            raise RuntimeError(f"Symbol directory not found: {SYM_DIR}")

        self.asc_canvas.load_symbols([SYM_DIR])

    def _load_asc(self):
        asc_path = os.path.join(ASC_DIR, ASC_FILENAME)

        if not os.path.isfile(asc_path):
            raise RuntimeError(f"ASC file not found: {asc_path}")

        self.asc_canvas.load_asc(asc_path)

    def on_motion(self, event):
        net = self.asc_canvas.get_net_under_mouse(event)
        self.statusbar.SetStatusText(net.name if net else "")
        event.Skip()


if __name__ == "__main__":
    app = wx.App()
    frame = AscViewer()
    frame.Show()
    app.MainLoop()
