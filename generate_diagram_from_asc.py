import argparse
import wx
import math
import glob, os
import rtreelib as rt
import asc_viewer.symbol as symbol_module
from asc_viewer.symbol import Symbol, window_types
from asc_viewer.symbol_instance import SymbolInstance
from PIL import Image, ImageOps
import numpy as np

# font sizes available in LTspice
font_size_factors = [0.625, 1, 1.5, 2, 2.5, 3.5, 5, 7]


class Net:
    """A net as used in LtSpice."""

    def __init__(self, name):
        self.name = name
        self.connections = []  # a list of (SymbolInstance, InstancePin, PinName) tuples
        self.type = None  # denotes spur type as string
        self.wires = set()


class Connection:
    """A connection between a net and an instance."""

    def __init__(self, instance, pin, pin_name):
        self.instance = instance
        self.pin = pin
        self.pin_name = pin_name


class WirePoint:
    """An endpoint of a wire."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.direction = (
            None  # direction for orientation of symbols attached to endpoints
        )
        self.wires = []
        self.net = None  # is set after DFS connects wires to nets


class Wire:
    """A wire as drawn in LtSpice."""

    def __init__(self, x0, y0, x1, y1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.net = None


class AscCanvas():
    """Headless LtSpice schematic loader capable of exporting to PNG.

    Arguments:
    symbol_paths -- optional list of path names where symbols are stored
    instance_name -- the instance name of this schematic, useful when the schematic is an instantiated subcircuit
    """

    def __init__(self, symbol_paths=None, instance_name=""):
        self.instance_name = instance_name
        self.symbols = {}
        self.filename = None

        self._ensure_app()
        self._patch_wx_clientdc()
        self._init_graphics_context()

        # create some graphics primitives for later use
        self.fonts = []
        self.black_pen = wx.Pen(wx.Colour(0, 0, 0), width=2, style=wx.PENSTYLE_SOLID)
        self.red_pen = wx.Pen(wx.Colour(255, 0, 0), width=2, style=wx.PENSTYLE_SOLID)
        for size in font_size_factors:
            font = self.create_font(size)
            self.fonts.append(font)
        font_size = 0.8
        self.black_font = self.create_font(font_size, wx.BLACK)
        self.blue_font = self.create_font(font_size, wx.BLUE)
        self.red_font = self.create_font(font_size, wx.RED)
        self.gray_font = self.create_font(font_size, wx.Colour(50, 50, 50, 50))

        self.reset()

        if symbol_paths:
            self.load_symbols(symbol_paths)

    def _patch_wx_clientdc(self):
        """Override wx.ClientDC with a MemoryDC to support headless usage."""

        class _HeadlessClientDC(wx.MemoryDC):
            def __init__(self, *args, **kwargs):
                super().__init__()
                self._bmp = wx.Bitmap(1, 1)
                self.SelectObject(self._bmp)

        wx.ClientDC = _HeadlessClientDC
        symbol_module.wx.ClientDC = _HeadlessClientDC

    def _ensure_app(self):
        """Create a minimal wx App so that GDI objects can be instantiated."""
        if wx.App.Get() is None:
            self._app = wx.App(False)
        else:
            self._app = wx.App.Get()

    def _init_graphics_context(self):
        """Prepare an off-screen graphics context for headless rendering."""
        self._scratch_bitmap = wx.Bitmap(1, 1)
        self.dc = wx.MemoryDC()
        self.dc.SelectObject(self._scratch_bitmap)
        self.gc = wx.GraphicsContext.Create(self.dc)

    def reset(self):
        self.wires = []
        self.wire_points = {}
        self.net_counter = 0  # for auto-labeling nets
        self.flags = {}  # off-schematic connectors or io pins
        self.texts = []
        self.rtree = rt.RTree()
        self.wire_lookup = rt.RTree()
        self.nets = {}  # name to net
        self.path = self.gc.CreatePath()
        self.symbol_instances = {}

    def reset_extent(self):
        self.x1 = float("inf")
        self.y1 = float("inf")
        self.x2 = float("-inf")
        self.y2 = float("-inf")

    def _update_bounds(self, x, y):
        self.x1 = min(self.x1, x)
        self.y1 = min(self.y1, y)
        self.x2 = max(self.x2, x)
        self.y2 = max(self.y2, y)

    def check_extent(self, xs, ys=None):
        if isinstance(xs, (list, tuple)) and isinstance(ys, (list, tuple)):
            for x, y in zip(xs, ys):
                self._update_bounds(x, y)
        elif isinstance(xs, (list, tuple)):
            for x in xs:
                self._update_bounds(x, ys if ys is not None else x)
        else:
            self._update_bounds(xs, ys if ys is not None else xs)

    def set_size(self, width, height):
        self.width = width
        self.height = height

    def Refresh(self):
        # No-op placeholder to keep interface compatible without GUI usage.
        pass

    def load_symbols(self, symbol_paths):
        """Loads symbols from a list of paths to asy files."""
        if isinstance(symbol_paths, str):
            symbol_paths = [symbol_paths]
        for path in symbol_paths:
            path = os.path.join(path, "*.asy")
            filenames = glob.glob(path)
            for f in filenames:
                name = os.path.basename(f)[:-4]
                self.symbols[name] = Symbol(self, f)

    def create_font(self, size, color=wx.BLACK):
        return self.gc.CreateFont(
            wx.Font(
                int(10 * size),
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_NORMAL,
            ),
            col=color,
        )

    def align_text(self, x, y, text, align, size, rotation, morig):
        """Aligns text for presentation. It takes formatting inputs from the asc file,
        i.e., rotation, alignment and matrix transformation and returns coordinates suitable
        for wx's DrawText function."""
        m = self.gc.CreateMatrix()
        m.Concat(morig)
        self.gc.SetFont(self.fonts[size])
        w, h, d, e = self.gc.GetFullTextExtent(text)
        if align[0] == "V":
            align = align[1:]
            m.Translate(x, y)
            m.Rotate(math.pi / 2 * 3)
            m.Translate(-x, -y)
            rotation += 270
        if align == "Right":
            x -= w
            y -= h / 2
        elif align == "Left":
            y -= h / 2
        elif align == "Top":
            x -= w / 2
        elif align == "Bottom":
            x -= w / 2
            y -= h
        elif align == "Center":
            x -= w / 2
            y -= h / 2
        m.Translate(x, y)

        # the only valid text directions are right or up
        if rotation % 360 == 180 or rotation % 360 == 90:
            m.Translate(w / 2, h / 2)
            m.Rotate(math.pi)
            m.Translate(-w / 2, -h / 2)
        x1, y1 = m.TransformPoint(0, 0)
        x2, y2 = m.TransformPoint(w, h)
        return min(x1, x2), min(y1, y2), max(y1, y2)

    def connect_wires(self, wire_point):
        """Connects wires to nets using recursion."""
        stack = [wire_point]
        while stack:
            wire_point = stack.pop()
            # check for a custom net name
            flag = self.flags.get((wire_point.x, wire_point.y))
            if flag:
                assert (
                    self.net_override is None or self.net_override == flag["net"]
                ), f"Conflicting net names are assigned: {self.net_override} and {flag['net']}"
                if self.net_override is None:
                    self.net_counter -= 1
                self.net_override = flag["net"]
                wire_point.net.name = flag["net"]

            for wire in wire_point.wires:
                wire.net = wire_point.net
                wire_point.net.wires.add(wire)
                if wire_point.x == wire.x0 and wire_point.y == wire.y0:
                    neighbor = self.wire_points.get((wire.x1, wire.y1))
                else:
                    neighbor = self.wire_points.get((wire.x0, wire.y0))
                if neighbor.net is None:
                    neighbor.net = wire_point.net
                    stack.append(neighbor)

    def load_asc(self, filename):
        """Loads an LtSpice schematic from the given filename."""
        instances = []
        self.filename = filename
        self.reset()
        self.reset_extent()
        f = open(filename, encoding="iso-8859-1")
        sheet_w, sheet_h = 0, 0
        for line in f:
            line = line.strip()
            if len(line) == 0:
                continue
            words = line.split(" ")
            if words[0] == "WIRE":
                wire = Wire(*[int(x) for x in words[1:]])
                self.check_extent([wire.x0, wire.x1], [wire.y0, wire.y1])
                self.wires.append(wire)

                # save endpoints and determine direction of wire ends that is used for some connector symbols and ground
                # default direction at wire end is down
                wire_point0 = self.wire_points.get((wire.x0, wire.y0))
                if wire_point0 is None:
                    wire_point0 = WirePoint(wire.x0, wire.y0)
                    self.wire_points[(wire.x0, wire.y0)] = wire_point0
                wire_point1 = self.wire_points.get((wire.x1, wire.y1))
                if wire_point1 is None:
                    wire_point1 = WirePoint(wire.x1, wire.y1)
                    self.wire_points[(wire.x1, wire.y1)] = wire_point1
                wire_point0.wires.append(wire)
                wire_point1.wires.append(wire)
                if wire.x0 == wire.x1:  # vertical
                    if wire.y0 < wire.y1:
                        wire_point0.direction = 2  # top
                    else:
                        wire_point1.direction = 2
                if wire.y0 == wire.y1:  # horizontal
                    if wire.x0 < wire.x1:
                        wire_point0.direction = 1  # left
                        wire_point1.direction = 3
                    else:
                        wire_point0.direction = 3  # right
                        wire_point1.direction = 1

                min_x, min_y = min(wire.x0, wire.x1), min(
                    wire.y0, wire.y1
                )  # rtree lib needs a well-formed rect
                max_x, max_y = max(wire.x0, wire.x1), max(wire.y0, wire.y1)
                rect = rt.Rect(min_x, min_y, max_x + 1, max_y + 1)
                self.wire_lookup.insert(wire, rect)
            elif words[0] == "TEXT":
                x = int(words[1])
                y = int(words[2])
                align = words[3]
                size = int(words[4])
                text = " ".join(words[5:])
                self.check_extent(x - 15, y - 15)

                x, y, y2 = self.align_text(
                    x, y, text, align, size, 0, self.gc.CreateMatrix()
                )
                t = dict(x=x, y=y, size=size, text=text)

                self.texts.append(t)
            elif words[0] == "SHEET":
                sheet_w, sheet_h = int(words[2]), int(words[3])
            elif words[0] == "FLAG":
                last_flag = dict(
                    x=int(words[1]), y=int(words[2]), net=words[3], type=None
                )
                self.check_extent(last_flag["x"], last_flag["y"])
                self.flags[(last_flag["x"], last_flag["y"])] = last_flag
            elif words[0] == "IOPIN":
                last_flag["type"] = words[3]
            elif words[0] == "SYMATTR":
                attr = " ".join(words[2:])
                if words[1] == "InstName" and self.instance_name != "":
                    attr = self.instance_name + "." + attr
                instances[-1].attrs[words[1]] = attr
            elif words[0] == "SYMBOL":
                instance = SymbolInstance(
                    self,
                    words[1],
                    int(words[2]),
                    int(words[3]),
                    words[4][0] == "M",
                    int(words[4][1:]),
                )
                instances.append(instance)
                self.check_extent(instance.x, instance.y)
                # load default attrs from symbol file
                symbol = self.symbols.get(words[1])
                assert symbol, f"Unknown symbol {words[1]}"
                symbol.load()
                instance.attrs = symbol.attrs.copy()
            elif words[0] == "WINDOW":
                x = int(words[2])
                y = int(words[3])
                window = dict(
                    type=window_types[words[1]],
                    x=x,
                    y=y,
                    align=words[4],
                    size=int(words[5]),
                )
                instances[-1].windows[window["type"]] = window

        # load symbol instances
        pin_positions = {}
        for instance in instances:
            s = self.symbols.get(instance.name)
            if s is None:
                print(f"Symbol not found {instance.name}")
                self.rtree.insert(
                    instance,
                    rt.Rect(
                        instance.x - 5, instance.y - 5, instance.x + 5, instance.y + 5
                    ),
                )
                continue
            s.load()
            instance.set_symbol(s)
            for pin in instance.pins:
                pin_positions[(pin.x, pin.y)] = (instance, pin)
            x1, y1 = instance.matrix.TransformPoint(s.x1, s.y1)
            x2, y2 = instance.matrix.TransformPoint(s.x2, s.y2)
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            self.rtree.insert(
                instance,
                rt.Rect(
                    instance.x + x1, instance.y + y1, instance.x + x2, instance.y + y2
                ),
            )
            self.symbol_instances[instance.attrs["InstName"]] = instance
            self.check_extent(
                [instance.x + s.x1, instance.x + s.x2],
                [instance.y + s.y1, instance.y + s.y2],
            )

        # connect wires to pins
        for wire_point in self.wire_points.values():
            if wire_point.net:
                continue
            self.net_counter += 1
            wire_point.net = Net(f"N{self.net_counter:03d}")
            self.nets[wire_point.net.name] = wire_point.net
            self.net_override = (
                None  # is set to net name if a user-assigned net name is found
            )
            self.connect_wires(wire_point)

        # calculate correct pin index from SpiceOrder

        # add instance connections to nets and label spur types
        for wire_point in self.wire_points.values():
            res = pin_positions.get((wire_point.x, wire_point.y))
            if res:
                instance, pin = res
                pin_name = str(pin.symbol_pin.index)
                connection = Connection(instance, pin, pin_name)
                wire_point.net.connections.append(connection)

        # add net flags to main rtree
        for flag in self.flags.values():
            x1 = flag["x"]
            y1 = flag["y"]
            x2 = x1 + 20
            y2 = y1 + 20
            net = self.nets.setdefault(flag["net"], Net(flag["net"]))
            self.rtree.insert(net, rt.Rect(x1, y1, x2, y2))

        if math.isinf(self.x1) or math.isinf(self.y1) or math.isinf(self.x2) or math.isinf(self.y2):
            self.x1 = 0
            self.y1 = 0
            self.x2 = sheet_w
            self.y2 = sheet_h

        self.x1 -= 10
        self.y1 -= 10
        self.x2 = max(self.x2, sheet_w)
        self.y2 = max(self.y2, sheet_h)
        self.set_size(self.x2 - self.x1, self.y2 - self.y1)
        self.Refresh()

        self.path = self.gc.CreatePath()

        for wire in self.wires:
            self.path.MoveToPoint(wire.x0, wire.y0)
            self.path.AddLineToPoint(wire.x1, wire.y1)

        for wire_point in self.wire_points.values():
            # add dots representing wire connection
            if len(wire_point.wires) > 2:
                self.path.AddRectangle(wire_point.x - 2, wire_point.y - 2, 4, 4)

        for flag in self.flags.values():
            x1, y1 = flag["x"], flag["y"]
            if flag["type"] == "In":
                path = self.gc.CreatePath()
                path.MoveToPoint(x1, y1)
                path.AddLineToPoint(x1 + 10, y1 + 10)
                path.AddLineToPoint(x1 + 10, y1 + 20)
                path.AddLineToPoint(x1 - 10, y1 + 20)
                path.AddLineToPoint(x1 - 10, y1 + 10)
                path.AddLineToPoint(x1, y1)
                wire_point = self.wire_points.get((x1, y1))
                if wire_point and len(wire_point.wires) == 1:
                    direction = wire_point.direction
                    if direction:
                        m = self.gc.CreateMatrix()
                        m.Translate(x1, y1)
                        m.Rotate(math.pi / 2 * direction)
                        m.Translate(-x1, -y1)
                        path.Transform(m)
                self.path.AddPath(path)
            elif flag["type"] == "Out":
                pass
            elif flag["type"] == "BiDir":
                pass
            elif flag["net"] == "0":
                path = self.gc.CreatePath()
                path.MoveToPoint(x1 - 10, y1)
                path.AddLineToPoint(x1 + 10, y1)
                path.MoveToPoint(x1 - 10, y1)
                path.AddLineToPoint(x1, y1 + 10)
                path.MoveToPoint(x1 + 10, y1)
                path.AddLineToPoint(x1, y1 + 10)
                self.path.AddPath(path)

    def export_to_png(self, filename, scale=1.0, padding=0, background_color=(255, 255, 255)):
        """Exports the current schematic view to a PNG file.

        Arguments:
        filename -- the output PNG filename
        scale -- scaling factor for the output image
        padding -- padding in pixels to add around the image (applied after scaling using PIL)
        """
        width = int((self.x2 - self.x1) * scale)
        height = int((self.y2 - self.y1) * scale)
        bmp = wx.Bitmap(width, height)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(wx.Colour(*background_color)))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        gc.Scale(scale, scale)
        gc.Translate(-self.x1, -self.y1)

        gc.SetPen(self.black_pen)
        gc.StrokePath(self.path)
        gc.SetFont(self.fonts[1])
        for flag in self.flags.values():
            if flag["net"] == "0":
                continue
            gc.DrawText(flag["net"], flag["x"], flag["y"])

        for instance in self.symbol_instances.values():
            instance.paint(gc)

        for text in self.texts:
            gc.SetFont(self.fonts[text["size"]])
            gc.DrawText(text["text"], text["x"], text["y"])

        dc.SelectObject(wx.NullBitmap)
        img = bmp.ConvertToImage()
        
        # Save to temporary location first
        temp_file = filename + ".tmp.png"
        img.SaveFile(temp_file, wx.BITMAP_TYPE_PNG)

        # Crop to content and add padding
        resized_image = self.crop_to_content_and_pad(
            temp_file,
            padding=padding,
            pad_color=background_color
        )

        # Save final image
        if filename:
            resized_image.save(filename)

        # Delete temporary file
        os.remove(temp_file)
        return img, filename

    
    def crop_to_content_and_pad(
        self,
        image_path,
        padding=20,
        bg_tolerance=10,
        pad_color=(255, 255, 255)
    ):
        """
        Crop an image tightly around its content and add padding.

        Parameters:
        - image_path: str, input image path
        - output_path: str or None
        - padding: int, pixels added around content
        - bg_tolerance: int, tolerance for background detection
        - pad_color: tuple, RGB padding color

        Returns:
        - PIL Image object
        """

        img = Image.open(image_path).convert("RGB")
        arr = np.array(img)

        # Estimate background color from corners
        corners = np.array([
            arr[0, 0],
            arr[0, -1],
            arr[-1, 0],
            arr[-1, -1]
        ])
        bg_color = np.mean(corners, axis=0)

        # Compute mask of non-background pixels
        diff = np.abs(arr - bg_color)
        mask = np.any(diff > bg_tolerance, axis=2)

        coords = np.column_stack(np.where(mask))

        if coords.size == 0:
            raise ValueError("No content detected")

        y_min, x_min = coords.min(axis=0)
        y_max, x_max = coords.max(axis=0)

        # Crop to content
        cropped = img.crop((x_min, y_min, x_max + 1, y_max + 1))

        # Add padding
        padded = ImageOps.expand(cropped, border=padding, fill=pad_color)

        return padded




ASC_FILENAME = "curvetrace.asc"  # <-- nom du fichier dans ./asc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASC_DIR = os.path.join(BASE_DIR, "asc")
SYM_DIR = os.path.join(BASE_DIR, "sym")


def export_schematic(asc_path, sym_dir, output_path, scale=1.0, padding=40, background_color=(255, 255, 255)):
    asc_exporter = AscCanvas([sym_dir])
    asc_exporter.load_asc(asc_path)
    asc_exporter.export_to_png(output_path, scale=scale, padding=padding, background_color=background_color)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export LTspice ASC schematic to PNG without GUI")
    parser.add_argument(
        "--asc",
        default=os.path.join(ASC_DIR, ASC_FILENAME),
        help="Path to the ASC schematic file (defaults to ./asc/transistor.asc)",
    )
    parser.add_argument(
        "--sym-dir",
        default=SYM_DIR,
        help="Directory containing LTspice symbol (.asy) files (defaults to ./sym)",
    )
    parser.add_argument(
        "--output",
        default="exported_schematic.png",
        help="Output PNG filename",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=2.0,
        help="Scale factor for the exported image",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=40,
        help="Padding in pixels around the schematic to center it in the image",
    )

    args = parser.parse_args()

    if not os.path.isdir(args.sym_dir):
        raise RuntimeError(f"Symbol directory not found: {args.sym_dir}")

    asc_path = args.asc
    if not os.path.isabs(asc_path):
        asc_path = os.path.join(BASE_DIR, asc_path)
    if not os.path.isfile(asc_path):
        raise RuntimeError(f"ASC file not found: {asc_path}")

    export_schematic(asc_path, args.sym_dir, args.output, scale=args.scale, padding=args.padding)

