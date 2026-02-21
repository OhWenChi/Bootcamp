# ssd1306.py  (save this file to the ESP32)
# MicroPython SSD1306 OLED driver (I2C) for 128x64
import framebuf

SET_CONTRAST = 0x81
SET_ENTIRE_ON = 0xA4
SET_NORM_INV = 0xA6
SET_DISP = 0xAE
SET_MEM_ADDR = 0x20
SET_COL_ADDR = 0x21
SET_PAGE_ADDR = 0x22
SET_DISP_START_LINE = 0x40
SET_SEG_REMAP = 0xA1
SET_MUX_RATIO = 0xA8
SET_COM_OUT_DIR = 0xC8
SET_DISP_OFFSET = 0xD3
SET_COM_PIN_CFG = 0xDA
SET_DISP_CLK_DIV = 0xD5
SET_PRECHARGE = 0xD9
SET_VCOM_DESEL = 0xDB
SET_CHARGE_PUMP = 0x8D


class SSD1306:
    def __init__(self, width, height, external_vcc=False):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        self.fb = framebuf.FrameBuffer(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        # Most 0.96" I2C OLEDs are internal charge-pump
        precharge = 0x22 if self.external_vcc else 0xF1
        chargepump = 0x10 if self.external_vcc else 0x14
        compins = 0x12 if self.height == 64 else 0x02

        for cmd in (
            SET_DISP | 0x00,
            SET_MEM_ADDR, 0x00,
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP,
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR,
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG, compins,
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, precharge,
            SET_VCOM_DESEL, 0x30,
            SET_CONTRAST, 0xFF,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_CHARGE_PUMP, chargepump,
            SET_DISP | 0x01,
        ):
            self.write_cmd(cmd)

        self.fill(0)
        self.show()

    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, contrast):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(contrast & 0xFF)

    def invert(self, invert):
        self.write_cmd(SET_NORM_INV | (invert & 1))

    def fill(self, col):
        self.fb.fill(col)

    def pixel(self, x, y, col):
        self.fb.pixel(x, y, col)

    def text(self, s, x, y, col=1):
        self.fb.text(s, x, y, col)

    def show(self):
        x0 = 0
        x1 = self.width - 1
        if self.width == 64:
            x0 += 32
            x1 += 32

        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(x0)
        self.write_cmd(x1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)

    # Implemented by subclass:
    def write_cmd(self, cmd):
        raise NotImplementedError

    def write_data(self, buf):
        raise NotImplementedError


class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C, external_vcc=False):
        self.i2c = i2c
        self.addr = addr
        super().__init__(width, height, external_vcc)

    def write_cmd(self, cmd):
        self.i2c.writeto(self.addr, bytearray([0x00, cmd & 0xFF]))

    def write_data(self, buf):
        # Co=0, D/C#=1 => 0x40 then data
        self.i2c.writeto(self.addr, b"\x40" + buf)
