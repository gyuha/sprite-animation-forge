"""A stand-in for rife-ncnn-vulkan (tests only): ``-0 A -1 B -o OUT [-m DIR] [-s T] [-g ID]`` writes the blend of two images.
FAKE_RIFE_FAIL=1 exits 1 (a binary that is installed but broken); FAKE_RIFE_LOG=<file> appends the argv."""

import os
import sys

import numpy as np
from PIL import Image

args = sys.argv[1:]
if os.environ.get("FAKE_RIFE_LOG"):
    with open(os.environ["FAKE_RIFE_LOG"], "a") as f:
        f.write(" ".join(args) + "\n")
if os.environ.get("FAKE_RIFE_FAIL") == "1":
    print("vkCreateInstance failed", file=sys.stderr)
    sys.exit(1)
opts = dict(zip(args[::2], args[1::2]))
t = float(opts.get("-s", "0.5"))
a = np.asarray(Image.open(opts["-0"]).convert("RGB"), dtype=np.float64)
b = np.asarray(Image.open(opts["-1"]).convert("RGB"), dtype=np.float64)
Image.fromarray(np.rint(a * (1 - t) + b * t).astype(np.uint8), "RGB").save(opts["-o"])
