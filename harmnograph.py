#!/usr/bin/env python

import random
import math
import time
import os

background_colour = (0, 0, 0)
(width, height) = (500, 500)

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
    def __init__(self, factory):
        self.factory = factory

    def reset(self, seed=None):
        if seed == None:
            random.seed()
            self.seed = random_word()
        random.seed(self.seed)
        self.engine = self.factory()

    def generate(self, resolution=20, threshold=1, steps=30):
        resolution = self.engine.calibrate(resolution)
        step = 0
        dstep = DistanceStop(steps, threshold)
        print "Generating %s" % self.seed
        while True:
            ts = resolution * step
            step += 1
            pos = self.engine(ts)
            if dstep.test(pos):
                print "Generated %d points" % step
                raise StopIteration
            yield pos

    def render(self, seed=None, *args, **kw):
        self.reset(seed)
        return self.generate(*args, **kw)

class SVG_Render(HarmonographRender):
    SVG_Template = \
"""<?xml version="1.0" encoding="utf-8" ?>
<svg baseProfile="tiny" height="100%%" version="1.2" width="100%%" xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events" xmlns:xlink="http://www.w3.org/1999/xlink"><defs />
    <path d="%s" fill="white" stroke="black" stroke-width="0.1" />
</svg>
"""
    
    def render(self, *args, **kw):
        path = super(SVG_Render, self).render(*args, **kw)
        path = 'M ' + str.join(' L ', ["%d %d" % pos for pos in path])
        print "Saving %s" % self.seed
        self.save(path)
        self.view()

    def save(self, path):
        svg = self.SVG_Template % path
        svgfn = "%s.svg" % self.seed
        f = open(svgfn, 'w')
        f.write(svg)

    def view(self):
        svgfn = "%s.svg" % self.seed
        cmd = "open %s" % svgfn
        os.system(cmd)

class PygameRender(object):
    BackgroundColor = (0, 0, 0)

    def __init__(self, factory):
        self.factory = factory
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption('harmnograph')

    def reset(self):
        self.pixel_hash = {}
        self.engine = self.factory()
        self.lastpos = None
        self.timestamp = 0
        self.screen.fill(self.BackgroundColor)

    def run(self):
        self.reset()
        self.running = True
        step = self.engine.calibrate()
        while self.running:
            pos = self.engine(self.timestamp)
            #self.timestamp += .01
            self.timestamp += step
            if pos not in self.pixel_hash:
                self.pixel_hash[pos] = 0
            if self.lastpos and pos != self.lastpos:
                self.pixel_hash[pos] += 1
                color = [self.pixel_hash[pos] * 50] * 3
                self.screen.set_at(pos, color)
                #pygame.draw.line(self.screen, color, self.lastpos, pos)
                pygame.display.flip()
            self.lastpos = pos

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self.reset()

factory = FactoryAlpha()
if 0:
    import pygame
    pr = PygameRender(factory)
    pr.run()
if 1:
    pr = SVG_Render(factory)
    pr.render()
