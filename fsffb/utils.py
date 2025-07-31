#
# This program is largely based on the TelemFFB distribution (https://github.com/walmis/TelemFFB).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

"""
Utilities Module

This module contains various helper functions and classes used throughout the application.
"""

import math

def clamp(value, min_val, max_val):
    """Clamps a value between a minimum and maximum."""
    return max(min_val, min(value, max_val))

def scale(value, in_min_max, out_min_max):
    """Scales a value from one range to another."""
    in_min, in_max = in_min_max
    out_min, out_max = out_min_max
    
    # Avoid division by zero
    if in_max == in_min:
        return out_min
        
    # Scale the value
    scaled = (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    return scaled
    
def scale_clamp(value, in_min_max, out_min_max):
    """Scales a value and clamps it to the output range."""
    scaled_val = scale(value, in_min_max, out_min_max)
    return clamp(scaled_val, *out_min_max)

def mix(a, b, ratio):
    """Linearly interpolates between two values."""
    return a * (1.0 - ratio) + b * ratio

def expocurve(x, k):
    """
    Applies an exponential curve to a value.
    - k > 0 bends the curve up (more sensitive at the start)
    - k < 0 bends the curve down (less sensitive at the start)
    """
    new_value = 0
    expo_a = 5.5  # Alpha controls the "bendiness"
    if k >= 0:
        new_value = (1 - k) * x + k * (1 - math.exp(-expo_a * x)) / (1 - math.exp(-expo_a))
    else:
        new_value = (1 + k) * x + (-k) * (math.exp(expo_a * (x - 1)) - math.exp(-expo_a)) / (1 - math.exp(-expo_a))
    return new_value

class Vector:
    """A simple 3D vector class."""
    def __init__(self, data):
        self.data = list(data)
        self.x, self.y, self.z = self.data

    def __sub__(self, other):
        return Vector([self.x - other.x, self.y - other.y, self.z - other.z])

    def rotY(self, angle):
        x = self.x * math.cos(angle) + self.z * math.sin(angle)
        z = -self.x * math.sin(angle) + self.z * math.cos(angle)
        return Vector([x, self.y, z])

    def rotX(self, angle):
        y = self.y * math.cos(angle) - self.z * math.sin(angle)
        z = self.y * math.sin(angle) + self.z * math.cos(angle)
        return Vector([self.x, y, z])

    def rotZ(self, angle):
        x = self.x * math.cos(angle) - self.y * math.sin(angle)
        y = self.x * math.sin(angle) + self.y * math.cos(angle)
        return Vector([x, y, self.z])
        
    def __iter__(self):
        return iter(self.data)

class Vector2D:
    """A simple 2D vector class."""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        
    def magnitude(self):
        return math.sqrt(self.x**2 + self.y**2)

    def normalize(self):
        mag = self.magnitude()
        if mag == 0:
            return Vector2D(0, 0)
        return Vector2D(self.x / mag, self.y / mag)

    def to_polar(self):
        magnitude = self.magnitude()
        angle = math.atan2(self.y, self.x)
        return magnitude, angle

class LowPassFilter:
    """A simple low-pass filter."""
    def __init__(self, time_constant):
        self.time_constant = time_constant
        self.filtered_value = 0.0

    def process(self, input_value, dt):
        """Update the filter with a new value and time delta."""
        if self.time_constant <= 0:
            self.filtered_value = input_value
            return self.filtered_value

        # alpha = dt / (time_constant + dt)
        alpha = dt / (self.time_constant + dt)
        self.filtered_value = alpha * input_value + (1 - alpha) * self.filtered_value
        return self.filtered_value 