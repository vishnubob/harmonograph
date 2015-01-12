#!/usr/bin/env python

import random
import math
import time
import os
import argparse

try:
    import pygame
except ImportError:
    msg = "Warning: no pygame module available"
    print msg

try:
    import silhouette
    units = silhouette.units
except ImportError:
    msg = "Warning: no silhouette module available"
    print msg
    from pint import UnitRegistry
    units = UnitRegistry()

units.define('pixel = point * 0.75 = pixels = px')

Defaults = {
    "center_x": None,
    "center_y": None,
    "width": "6in", 
    "height": "6in",
    "speed": 10,
    "pressure": 10,
    "resolution": 20,
    "threshold": 1,
    "steps": 30,
    "tsmin": 0,
    "tsmax": None,
    "mode": "svg",
}

def euclidean_distance(xy1, xy2):
    return math.sqrt((xy1[0] - xy2[0]) ** 2 + (xy1[1] - xy2[1]) ** 2)

class Pendulum(object):
    def __init__(self, frequency, amplitude, damping, phase=0):
        self.frequency = frequency
        self.amplitude = amplitude
        self.damping = damping
        self.phase = phase

    def __repr__(self):
        return "Pendulum(frequency=%s, amplitude=%s, damping=%s, phase=%s)" % (self.frequency, self.amplitude, self.damping, self.phase)

    def __call__(self, timestamp):
        val = self.amplitude * math.sin(timestamp * self.frequency + self.phase) * math.e ** (-self.damping * timestamp)
        return val

class Harmonograph(object):
    def __init__(self, xset, yset, center=True):
        self.xset = xset
        self.yset = yset
        self.center = center
        self.x_offset = int(sum([x.amplitude for x in self.xset])) + 50
        self.y_offset = int(sum([y.amplitude for y in self.yset])) + 50

    def calibrate(self, threshold=1):
        pos = self(0)
        ts = 1
        while True:
            resolution = math.pi / ts
            nextpos = self(resolution)
            distance = euclidean_distance(pos, nextpos)
            if distance < threshold:
                return math.pi / ts
            ts += 1

    def __call__(self, timestamp):
        x = sum([xpen(timestamp) for xpen in self.xset])
        y = sum([ypen(timestamp) for ypen in self.yset])
        if self.center:
            x += self.x_offset
            y += self.x_offset
        return (x, y)

    def __repr__(self):
        return "Harmonograph(\n    %s,\n    %s\n)" % (self.xset, self.yset)

class RandomRange(object):
    def __init__(self, center, tolerance):
        self.center = center
        self.tolerance = tolerance

    def __call__(self):
        return random.random() * (2 * self.tolerance) + (self.center - self.tolerance)

class HarmonographFactory(object):
    def build_harmonograph(self, frequency, amplitude, damp, phase):
        pens = [Pendulum(frequency(), amplitude(), damp(), phase()) for x in range(4)]
        return Harmonograph(pens[:2], pens[2:])

class FactoryAlpha(HarmonographFactory):
    def __call__(self):
        frequency = RandomRange(10, 0.5)
        damp = RandomRange(.001, .00049)
        phase = RandomRange(2 * math.pi, math.pi / 2.0)
        amplitude = RandomRange(200, 50)
        return self.build_harmonograph(frequency, amplitude, damp, phase)

class RandomWords(object):
    Words = None
    Dictonary = "/usr/share/dict/words"

    @classmethod
    def load(cls):
        if cls.Words == None:
            f = open(cls.Dictonary)
            cls.Words = f.readlines()

    @classmethod
    def __call__(cls):
        cls.load()
        return random.choice(cls.Words).strip().lower()

random_word = RandomWords.__call__

class DistanceStop(object):
    def __init__(self, steps, threshold):
        self.steps = steps
        self.threshold = threshold
        self.values = []
        self.last_pos = None

    def test(self, pos):
        if self.last_pos:
            distance = euclidean_distance(self.last_pos, pos)
            self.values.insert(0, distance)
            self.values = self.values[:self.steps]
        self.last_pos = pos
        if len(self.values) < self.steps:
            return False
        avg = sum(self.values) / float(len(self.values))
        return avg < self.threshold
        #return sum(self.values) < self.threshold

class HarmonographRender(object):
    DefaultUnit = "pixel"

    def __init__(self, factory, args):
        self.factory = factory
        self.args = args

    def _convert_unit(self, expr):
        val = units.parse_expression(expr)
        to_unit = units[self.DefaultUnit]
        return val.to(to_unit).magnitude

    @property
    def dimensions(self):
        x = self.args["width"]
        y = self.args["height"]
        (x, y) = (self._convert_unit(x), self._convert_unit(y))
        return map(int, (x, y))
    
    @property
    def center(self):
        x = self.args["center_x"]
        y = self.args["center_y"]
        if (x == None) or (y == None):
            (dx, dy) = self.dimensions
            return map(int, (dx / 2.0, dy / 2.0))
        (x, y) = (self._convert_unit(x), self._convert_unit(y))
        return map(int, (x, y))
    
    def reset(self):
        self.seed = self.args["seed"]
        if self.seed == None:
            random.seed()
            self.seed = random_word()
        random.seed(self.seed)
        self.engine = self.factory()

    def generate(self):
        print "Generating %s" % self.seed
        resolution = self.args["resolution"]
        threshold = self.args["threshold"]
        steps = self.args["steps"]
        resolution = self.engine.calibrate(resolution)
        step = 0
        dstep = DistanceStop(steps, threshold)
        running = True
        while running:
            ts = resolution * step + self.args["tsmin"]
            step += 1
            pos = self.engine(ts)
            yield pos
            if self.args["tsmax"] != None:
                running = ts < self.args["tsmax"]
            else:
                running = not dstep.test(pos)
        print "Generated %d points (resolution: %f, timestamp: %f)" % (step, resolution, ts)

    def scale_path(self, path):
        (dx, dy) = self.dimensions
        (cx, cy) = self.center
        (x_list, y_list) = zip(*path)
        x_min = min(x_list)
        x_max = max(x_list)
        y_min = min(y_list)
        y_max = max(y_list)
        x_scale = dx / (x_max - x_min)
        y_scale = dy / (y_max - y_min)
        x_offset = cx - (dx / 2.0)
        y_offset = cy - (dy / 2.0)
        x_list = [int((x - x_min) * x_scale + x_offset) for x in x_list]
        y_list = [int((y - y_min) * y_scale + y_offset) for y in y_list]
        return zip(x_list, y_list)

    def render(self):
        self.reset()
        path = self.generate()
        path = list(path)
        path = self.scale_path(path)
        return path

class SVG_Render(HarmonographRender):
    SVG_Template = \
"""<?xml version="1.0" encoding="utf-8" ?>
<svg width="%(width)s" height="%(height)s" version="1.2" xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events" xmlns:xlink="http://www.w3.org/1999/xlink">
    <defs />
    <path d="%(path)s" fill="white" stroke="black" stroke-width="0.1" />
</svg>
"""
    
    def render(self):
        path = super(SVG_Render, self).render()
        path = 'M ' + str.join(' L ', ["%d %d" % pos for pos in path])
        print "Saving %s" % self.seed
        self.save(path)
        self.view()

    def save(self, path):
        macros = {}
        (dx, dy) = self.dimensions
        macros["width"] = dx
        macros["height"] = dy
        macros["path"] = path
        svg = self.SVG_Template % macros
        svgfn = "%s.svg" % self.seed
        f = open(svgfn, 'w')
        f.write(svg)

    def view(self):
        svgfn = "%s.svg" % self.seed
        cmd = "open %s" % svgfn
        os.system(cmd)

class PygameRender(HarmonographRender):
    BackgroundColor = (0xff, 0xff, 0xff)
    ForegroundColor = (0, 0, 0)

    def render(self):
        dim = self.dimensions
        screen = pygame.display.set_mode(dim)
        pygame.display.set_caption('harmnograph')
        running = True
        while running:
            self.engine = self.factory()
            screen.fill(self.BackgroundColor)
            path = super(PygameRender, self).render()
            pygame.draw.aalines(screen, self.ForegroundColor, False, path)
            pygame.display.flip()
            eloop = True
            while eloop:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                        eloop = False
                        break
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        eloop = False
                        break

class SilhouetteRender(HarmonographRender):
    DefaultUnit = "steps"

    def init_cutter(self, pos):
        self.cutter = silhouette.Silhouette()
        self.cutter.connect()
        self.cutter.home()
        self.cutter.position = pos
        self.cutter.speed = self.args["speed"]
        self.cutter.pressure = self.args["pressure"]

    def render(self):
        path = super(SilhouetteRender, self).render()
        raw_input("Press enter to continue")
        self.init_cutter(path[0])
        self.cutter.draw(path)
        self.cutter.home()

def cli():
    parser = argparse.ArgumentParser(description='Harmonograph Generator')
    parser.add_argument('-x', '--center-x', type=str, help='X center (1.2in, 3mm, etc)')
    parser.add_argument('-y', '--center-y', type=str, help='Y center (1.2in, 3mm, etc)')
    parser.add_argument('-W', '--width', type=str, help='Width')
    parser.add_argument('-H', '--height', type=str, help='Height')
    parser.add_argument('-p', '--pressure', type=int, help='Pressure of pen (1-33)')
    parser.add_argument('--speed', type=int, help='Speed of pen (1-33)')
    parser.add_argument('-m', '--mode', type=str, help='Mode (svg, silhouete, pygame)')
    parser.add_argument('-s', '--seed', type=str, help='Seed')
    parser.add_argument('-r', '--resolution', type=float, help='resolution')
    parser.add_argument('-t', '--threshold', type=float, help='threshold')
    parser.add_argument('-S', '--steps', type=int, help='steps')
    parser.add_argument('--tsmin', type=float, help='timestamp start')
    parser.add_argument('--tsmax', type=float, help='timestamp max')
    parser.set_defaults(**Defaults)
    args = parser.parse_args()
    return args

def get_factory(args):
    factory = FactoryAlpha()
    return factory

def run(args):
    global pygame, silhouette
    factory = get_factory(args)
    if args["mode"] == "silhouette":
        mode = SilhouetteRender(factory, args)
    elif args["mode"] == "pygame":
        mode = PygameRender(factory, args)
    elif args["mode"] == "svg":
        mode = SVG_Render(factory, args)
    else:
        msg = "Unknown mode: %s" % args["mode"]
        raise RuntimeError(msg)
    mode.render()

if __name__ == '__main__':
    args = cli()
    args = args.__dict__.copy()
    run(args)
