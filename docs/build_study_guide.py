"""Build docs/study_guide.html: the whole project explained, concept by concept and code chunk by code chunk.

Code is read from the source files when the guide is built, so it always matches the project.
Each chunk starts at an "anchor" line; if a source file changes so that an anchor is no longer
found, the build stops with an error instead of showing stale code.

    /opt/anaconda3/bin/python3 docs/build_study_guide.py
"""

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "study_guide.html"


# ====================================================================== code walkthrough content
# Each file: (path, language, intro, [(anchor, explanation), ...]). A chunk runs from its anchor
# line to the line before the next anchor.

FILES = [
("src/xbd.py", "python",
 "<p>The first file written. It knows how the raw xBD download is organised and how to read it: where the "
 "images and labels are, how a building outline is written, how to open the unusual 16-bit images, and how to "
 "draw a before/after pair. Every other file builds on it.</p>",
 [
  ('"""Helpers for reading', """
<p>A <b>docstring</b>: a text block in triple quotes at the top of a file or function. Python ignores it
when running; it is documentation for people. It shows the folder layout this file expects: for every tile
there is a <code>pre</code> image, a <code>post</code> image and a <code>.json</code> label file.</p>"""),
  ("import json", """
<p><b>Imports</b> load other people's code so we can use it.</p>
<ul>
<li><code>json</code> reads the label files, which are in JSON format (nested lists and dictionaries in text).</li>
<li><code>re</code> is "regular expressions", a mini-language for finding patterns in text. Used to pull numbers out of polygon text.</li>
<li><code>Path</code> handles file paths: <code>folder / "file.json"</code> joins them correctly on any computer.</li>
<li><code>matplotlib</code> draws pictures; <code>numpy</code> (as <code>np</code>) does fast maths on arrays of numbers; <code>pandas</code> (as <code>pd</code>) handles tables.</li>
<li><code>tifffile</code> reads TIFF images, including the 16-bit ones in xBD that Pillow (<code>PIL</code>) cannot open.</li>
</ul>"""),
  ("DAMAGE_CLASSES =", """
<p><b>Constants</b>, written in capitals by convention: values that never change. The five label names used
in xBD, and one colour per level (hex codes like <code>#d62728</code> = red), used in every picture in the project.</p>"""),
  ("_NUM_PAIR =", """
<p>A compiled regular expression that matches <b>two numbers separated by a space</b>, such as
<code>807.41 898.08</code>. Piece by piece: <code>-?</code> an optional minus sign, <code>\\d+</code> one or more digits,
<code>(?:\\.\\d+)?</code> an optional decimal part, <code>(?:[eE]-?\\d+)?</code> optional scientific notation like
<code>1e-5</code>, <code>\\s+</code> spaces. The two round-bracket groups capture x and y. The leading underscore
means "internal to this file".</p>"""),
  ("def parse_wkt_polygon", """
<p>xBD writes each building outline as <b>WKT</b> ("well-known text"), for example
<code>POLYGON ((807.4 898.1, 760.9 943.3, …))</code>. This function turns that text into a numpy array of shape
<code>(N, 2)</code>: N corner points, each with an x and a y.</p>
<ul>
<li>Line 39 keeps everything after the first <code>((</code>.</li>
<li>Line 40 keeps everything before the first <code>)</code>, i.e. only the outer ring (holes, if any, are ignored).</li>
<li>Line 41 finds every number pair with the regex and converts the text to <code>float</code> numbers.</li>
</ul>
<p>The same function works for pixel outlines (<code>xy</code>) and map outlines (<code>lng_lat</code>), because both are WKT.</p>"""),
  ("def polygon_area", """
<p>The <b>shoelace formula</b> for the area of a polygon from its corners: multiply each x by the next y, subtract
each y times the next x, add up, halve. <code>np.roll(y, 1)</code> shifts the array by one so "the next corner" lines
up. Used in notebook 01 to measure building sizes (median 654 square pixels).</p>"""),
  ("def find_pairs", """
<p>Lists every tile in a split folder (for example <code>data/xbd/tier1</code>) as one row of a table.</p>
<ul>
<li>Line 54 checks whether the images are <code>.tif</code> (the full release you downloaded) or <code>.png</code> (a smaller release). Added after the first version only looked for <code>.png</code>.</li>
<li>Line 56 finds every <code>*_post_disaster.json</code> label. <code>sorted</code> gives a fixed order, so runs are repeatable.</li>
<li>Line 57 cuts the tile id out of the file name, e.g. <code>hurricane-harvey_00000137</code>.</li>
<li>Line 58: <code>rsplit("_", 1)</code> splits at the last underscore, so the disaster is <code>hurricane-harvey</code>.</li>
<li>Lines 59–65 build a dictionary with the paths of the pre image, post image and label; line 66 turns the list into a pandas table.</li>
</ul>"""),
  ("def load_image", """
<p>The fix for the first real problem in the project. The GeoTIFF images store each colour value as a
<b>16-bit signed integer</b> (<code>int16</code>), although the values only go from 0 to 255. Pillow cannot open
3-channel 16-bit images, so:</p>
<ul>
<li>for <code>.tif</code>: read with <code>tifffile</code>, <code>np.clip</code> forces values into 0–255, and <code>astype(np.uint8)</code> converts to normal 8-bit colour;</li>
<li>for anything else: open with Pillow and force RGB.</li>
</ul>
<p>The result is always an array of shape <code>(1024, 1024, 3)</code>: height, width, and three colour channels (red, green, blue).</p>"""),
  ("def load_buildings", """
<p>Opens a label file and returns its buildings. In the JSON, <code>features["xy"]</code> holds outlines in
pixel coordinates, and each has <code>properties</code> such as <code>subtype</code> (the damage level) and
<code>uid</code> (a unique id). Non-buildings are skipped (line 87). If a building has no <code>subtype</code>
(pre-disaster labels have none), it is treated as <code>"un-classified"</code>.</p>"""),
  ("def load_metadata", """
<p>Returns the <code>metadata</code> block of a label file: satellite name, capture date, off-nadir angle (how
slanted the photo was), pixel size, and so on. Shown once in notebook 01.</p>"""),
  ("def building_table", """
<p>Loops over all tiles and all buildings and makes one big table with one row per building: tile, disaster,
damage level and area. This is what notebook 01 counts to get "162,787 buildings, 72% undamaged".
<code>itertuples()</code> walks through a pandas table row by row.</p>"""),
  ("def show_pair", """
<p>Draws a tile before and after, side by side, with every building outlined in its damage colour.</p>
<ul>
<li><code>plt.subplots(1, 2)</code> makes a figure with two panels.</li>
<li><code>imshow</code> draws an image; <code>MplPolygon</code> draws an outline; <code>add_patch</code> puts it on the panel.</li>
<li>Lines 123–127 also count buildings per level for the title.</li>
<li>Lines 134–136 add a colour legend at the bottom.</li>
</ul>"""),
 ]),

("src/preprocess.py", "python",
 "<p>Runs once, before any training. It converts the 130 GB of slow 16-bit GeoTIFFs into about 9 GB of JPEG "
 "images plus one <b>mask</b> per tile, a greyscale image where each pixel's number says what is there. Training "
 "then reads these small, fast files thousands of times.</p>",
 [
  ('"""Convert raw xBD', "<p>Docstring with the output layout and the two ways to run it: all splits, or only the ones you name.</p>"),
  ("import sys", """
<p><code>sys</code> gives access to the command-line arguments. <code>multiprocessing.Pool</code> runs work on
several CPU cores at once (your M1 Pro has 10). <code>cv2</code> is OpenCV, a fast image library used to write
JPEGs and draw filled polygons. The last line imports three helpers from <code>xbd.py</code>.</p>"""),
  ("RAW_ROOT =", """
<p>Settings: where raw data is, where to write, which splits exist, and the JPEG quality. Quality 95 was chosen
after a measurement: a PNG would be 1.8 MB per image (40 GB in total), JPEG 95 is 0.39 MB (8.6 GB), and
changes pixel values by only 1.46 out of 255 on average, which is invisible.</p>"""),
  ("# Pixel values in the mask", """
<p>The <b>mask encoding</b>: in each mask image, background pixels are 0 and building pixels hold the damage level,
1 to 4, or 5 for un-classified buildings. One mask therefore serves both models: the localization model only
asks "is it above 0?", the damage model uses the exact value.</p>"""),
  ("def make_mask", """
<p>Builds a mask for one tile.</p>
<ul>
<li>Line 40: start with a 1024 × 1024 array of zeros (all background). <code>uint8</code> = whole numbers 0–255, one byte each.</li>
<li>Line 42: polygon corners are decimal numbers; <code>np.round(...).astype(np.int32)</code> turns them into whole pixel positions, which OpenCV needs.</li>
<li>Line 43: <code>cv2.fillPoly</code> paints the inside of the polygon with the building's damage value.</li>
</ul>"""),
  ("def process_tile", """
<p>Converts one tile. For <code>pre</code> and <code>post</code>: read the TIFF with <code>load_image</code>, convert
the colour order with <code>cv2.cvtColor</code> (OpenCV stores colours as blue-green-red, the rest of Python uses
red-green-blue), and save as JPEG. Then make and save the mask as PNG (lossless, so the numbers stay exact).
The <code>if not ... exists()</code> checks skip finished files, so the script can be stopped and restarted.</p>"""),
  ("def process_split", """
<p>Converts a whole split in parallel.</p>
<ul>
<li>Lines 63–64 create the output folders (<code>parents=True</code> creates missing parent folders, <code>exist_ok=True</code> means "no error if it already exists").</li>
<li>Line 66 turns the table into a list of jobs, one per tile.</li>
<li>Line 67: <code>with Pool() as pool</code> starts one worker process per CPU core.</li>
<li>Line 68: <code>imap_unordered</code> hands the jobs out, 8 at a time (<code>chunksize</code>), and yields as each finishes; <code>enumerate(..., 1)</code> counts from 1 for the progress message.</li>
</ul>
<p>This converted the 933 <code>hold</code> tiles in 23 seconds.</p>"""),
  ("if __name__", """
<p>This block runs only when the file is started as a program (<code>python -m src.preprocess</code>), not when
another file imports it. <code>sys.argv[1:]</code> is the list of words typed after the command;
<code>or SPLITS</code> means "if none were typed, do all four".</p>"""),
 ]),

("src/dataset.py", "python",
 "<p>Feeds training examples to the localization model. PyTorch expects a <b>Dataset</b>: an object that says "
 "how many examples there are and returns example number <i>i</i> on request. PyTorch's <b>DataLoader</b> then "
 "asks for examples in random order, groups them into batches and does it in background processes.</p>",
 [
  ('"""PyTorch dataset', "<p>One-line docstring.</p>"),
  ("from pathlib import Path", "<p><code>torch</code> is PyTorch, the deep-learning library. <code>Dataset</code> is the base class our dataset extends.</p>"),
  ("# OpenCV's own thread pool", """
<p>One line that fixed a real bug. During the first speed test, training froze completely. PyTorch's DataLoader
starts helper processes to load images; OpenCV inside each of them started its own thread pool, and on macOS
this can <b>deadlock</b> (threads waiting for each other forever). <code>setNumThreads(0)</code> turns OpenCV's
threading off; the parallelism comes from the DataLoader's processes instead. After this line, the helpers
started in 8 seconds and training ran at full speed.</p>"""),
  ("IMAGENET_MEAN", """
<p>The average and spread of red, green and blue over the 1.2 million ImageNet photos the encoder was pretrained
on. Our images are normalised with the same numbers, so the pretrained network sees inputs in the range it is
used to.</p>"""),
  ("def read_rgb", "<p>Reads a JPEG with OpenCV and converts blue-green-red to red-green-blue.</p>"),
  ("def to_tensor", """
<p>Turns an image into what the network wants:</p>
<ul>
<li><code>/ 255.0</code>: pixel values 0–255 become 0–1;</li>
<li><code>- MEAN) / STD</code>: subtract the ImageNet average and divide by the spread, so values are centred around 0;</li>
<li><code>transpose(2, 0, 1)</code>: from (height, width, channels) to (channels, height, width), PyTorch's order;</li>
<li><code>torch.from_numpy</code>: wraps the numpy array as a PyTorch <b>tensor</b> (a multi-dimensional array that can live on the GPU and track gradients). <code>.copy()</code> makes the memory contiguous, which PyTorch requires after a transpose.</li>
</ul>"""),
  ("class BuildingDataset", """
<p>The dataset class and its constructor (<code>__init__</code>, run once when the object is created). It collects
the paths of all mask files in the given split folders. <code>max_tiles</code> is used only for small tests
(for example 8 tiles). <code>crop</code> and <code>augment</code> are stored for later.</p>"""),
  ("    def __len__", "<p>Tells PyTorch how many examples exist (2,799 for tier1). Needed so it can shuffle and count batches.</p>"),
  ("    def image_path", "<p>From a mask path like <code>.../masks/hurricane-harvey_00000137.png</code>, builds the matching image path <code>.../images/hurricane-harvey_00000137_pre.jpg</code>. <code>parent.parent</code> goes up two folders; <code>stem</code> is the file name without extension.</p>"),
  ("    def __getitem__", """
<p>Returns example number <code>i</code>. This runs about 2,800 times per epoch, inside the DataLoader's helper
processes. Line 52 reads the before image; line 53 reads the mask and turns it into <b>0/1</b>: <code>&gt; 0</code>
gives True for every building pixel whatever its damage level, and <code>astype(np.float32)</code> turns
True/False into 1.0/0.0.</p>"""),
  ("        if self.crop:", """
<p><b>Random crop.</b> Pick a random top-left corner (<code>y</code>, <code>x</code>) and cut a 512 × 512 square from
the 1024 × 1024 tile, the same square from image and mask. Each epoch therefore sees a different quarter of each
tile, and four times smaller inputs fit in memory with a batch of 8.</p>"""),
  ("        if self.augment:", """
<p><b>Augmentation</b>: random changes that create variety for free. A roof seen from above is equally valid
mirrored or rotated, so:</p>
<ul>
<li>50% chance: flip left–right (<code>[:, ::-1]</code> reverses the column order);</li>
<li>50% chance: flip upside down (<code>[::-1]</code> reverses the row order);</li>
<li>rotate by 0, 90, 180 or 270 degrees (<code>np.rot90(..., k)</code>).</li>
</ul>
<p>Image and mask always get the same change, so they stay aligned.</p>"""),
  ("        return to_tensor(image)", """
<p>Returns the pair (input, answer). The mask becomes a tensor and <code>[None]</code> adds a channel dimension:
shape <code>(1, 512, 512)</code>, matching the model's single output channel.</p>"""),
 ]),

("src/train.py", "python",
 "<p>Builds, trains and scores the first model, which finds buildings. Read the section <a href=\"#one-step\">One "
 "training step, traced</a> alongside this file.</p>",
 [
  ('"""Training and evaluation', "<p>Docstring: what the model is, how it is scored, and the command that runs it.</p>"),
  ("import csv", """
<p><code>segmentation_models_pytorch</code> (imported as <code>smp</code>) is a library of ready-made segmentation
networks: it saved writing a U-Net by hand. <code>torch.nn.functional</code> (as <code>F</code>) holds loss functions.
<code>DataLoader</code> batches examples. The last line imports our dataset.</p>"""),
  ("def build_model", """
<p>The whole model in one line: a <b>U-Net</b> whose encoder is a <b>ResNet-34</b> with weights pretrained on
ImageNet, taking 3 input channels (RGB) and producing 1 output channel (building score per pixel). It has
24,436,369 adjustable numbers (<b>parameters</b>), 21.3 million of them in the encoder. With
<code>pretrained=False</code> the architecture is built without downloading weights; that is used when loading our
own trained weights afterwards.</p>"""),
  ("def pick_device", """
<p>Chooses where the maths runs: an NVIDIA GPU (<code>cuda</code>) if present, else the Apple Silicon GPU
(<code>mps</code>, Metal Performance Shaders), else the CPU. On your Mac it returns <code>mps</code>.</p>"""),
  ("def dice_loss", """
<p><b>Dice loss</b> measures overlap between predicted and true building areas.</p>
<ul>
<li><code>sigmoid</code> turns raw scores (<b>logits</b>, any number) into probabilities 0–1.</li>
<li><code>inter</code>: sum of probability × truth = the "overlap"; <code>union</code>: total predicted + total true.</li>
<li><code>sum(dim=(1, 2, 3))</code> adds over channel, height and width, giving one number per image in the batch.</li>
<li>Dice = 2 × overlap / (predicted + true): 1 for perfect overlap. The loss is 1 − Dice, so smaller is better. <code>eps</code> avoids dividing by zero on crops without buildings.</li>
</ul>"""),
  ("def loss_fn", """
<p>The training loss is the sum of two parts. <b>Binary cross-entropy</b> scores every pixel on its own: it is
large when the model is confident and wrong. Because about 85% of pixels are background, it alone would let the
model under-predict small buildings; <b>Dice</b> compensates because it is a ratio of areas, not a count of pixels.</p>"""),
  ("@torch.no_grad()", """
<p>Scores the model on the validation split.</p>
<ul>
<li><code>@torch.no_grad()</code> tells PyTorch not to record gradients: faster and uses less memory, since we are not learning here.</li>
<li><code>model.eval()</code> switches layers such as batch normalisation to their fixed, test-time behaviour.</li>
<li>For each batch: probability above 0.5 means "building". Compare with the truth and count <b>true positives</b> (both say building), <b>false positives</b> (model says building, truth says no) and <b>false negatives</b> (missed buildings). <code>&amp;</code> is "and", <code>~</code> is "not"; <code>.item()</code> turns a one-number tensor into a Python number.</li>
<li>After all batches: precision, recall and F1, computed once over all pixels of all tiles, as the xView2 challenge does. <code>max(..., 1)</code> avoids dividing by zero.</li>
</ul>"""),
  ("def train_localization(", """
<p>The training function and its settings, each with a default. Training used these defaults:
tier1 for training, hold for validation, 30 epochs, batches of 8, learning rate 0.0003, 512-pixel crops.</p>"""),
  ("    data_root, out_dir = Path", """
<p>Setup: make sure the output folder exists, pick the device, and decide on <b>mixed precision</b>
(<code>use_amp</code>): on NVIDIA GPUs, half-size 16-bit numbers make training faster. It is off on your Mac
(<code>mps</code>), where everything runs in normal 32-bit precision.</p>"""),
  ("    train_ds = BuildingDataset", """
<p>Two datasets and their loaders.</p>
<ul>
<li>Training: random crops with augmentation; <code>shuffle=True</code> gives a new random order every epoch; <code>drop_last=True</code> drops the last incomplete batch (2,799 / 8 = 349 full batches); <code>persistent_workers</code> keeps the helper processes alive between epochs.</li>
<li>Validation: full 1024 × 1024 tiles, no augmentation, so the score is measured the same way every time; batch of 2 because full tiles use 4 times more memory.</li>
</ul>"""),
  ("    model = build_model(pretrained)", """
<p>The learning machinery.</p>
<ul>
<li><code>.to(device)</code> moves the model's parameters to the GPU.</li>
<li><b>AdamW</b> is the <b>optimizer</b>: the rule that updates each parameter after each batch. Adam adapts the step size of each parameter to how its gradients behave; the "W" adds <b>weight decay</b> (<code>1e-4</code>), a small pull of every weight towards zero that reduces overfitting.</li>
<li><b>CosineAnnealingLR</b> lowers the learning rate along half a cosine curve, from 0.0003 at the start to almost 0 after 30 epochs: big steps early, fine adjustments late. This is why the score jumped around in the first half and settled in the second.</li>
<li><code>GradScaler</code> belongs to mixed precision and does nothing on your Mac.</li>
</ul>"""),
  ("    start_epoch, best_f1", """
<p><b>Resuming.</b> If <code>last.pt</code> (a <b>checkpoint</b>, a saved copy) exists, load the model weights, the
optimizer's internal state, the learning-rate schedule and the epoch counter, and continue from the next epoch.
This is why rerunning the command after an interruption continues instead of starting over.</p>"""),
  ("    history_path =", """
<p>The <b>epoch loop</b>. One epoch is one pass over all training tiles. <code>range(start_epoch, epochs)</code> goes
from 0 (or the resume point) to 29.</p>"""),
  ("        model.train()", """
<p>The heart of training, run 349 times per epoch, once per batch:</p>
<ol>
<li><code>model.train()</code> switches layers to training behaviour.</li>
<li><code>.to(device)</code> sends the batch to the GPU.</li>
<li><code>zero_grad</code> clears the gradients left from the previous batch.</li>
<li><code>model(images)</code>: the <b>forward pass</b>, the model's prediction; <code>loss_fn</code> scores it.</li>
<li><code>.backward()</code>: <b>backpropagation</b>, which computes for each of the 24.4 million parameters how much the loss would change if that parameter changed (its <b>gradient</b>).</li>
<li><code>step(optimizer)</code>: AdamW nudges every parameter a little in the direction that lowers the loss.</li>
<li><code>loss.item()</code> is added up to report the average training loss.</li>
</ol>
<p>(<code>autocast</code> and <code>scaler</code> are mixed-precision helpers that do nothing on the Mac.)</p>"""),
  ("        scheduler.step()", "<p>After each epoch, lower the learning rate one step along the cosine curve.</p>"),
  ("        metrics = evaluate", """
<p>Score on the 933 validation tiles and print one line per epoch, such as
<code>epoch=27 train_loss=0.3174 f1=0.7918 precision=0.8185 recall=0.7668 ...</code>. <code>**metrics</code>
unpacks the dictionary's entries into the new one.</p>"""),
  ("        is_new_file", """
<p>Append the line to <code>history.csv</code>, writing column names first if the file is new. The progress display,
the notebooks and the report all read this file.</p>"""),
  ('        if metrics["f1"] > best_f1', """
<p>Two saves every epoch:</p>
<ul>
<li><code>best.pt</code>: only when the validation F1 beats the best so far. This is the model used later, from epoch 27 (F1 0.792).</li>
<li><code>last.pt</code>: always, with everything needed to resume.</li>
</ul>
<p><code>state_dict()</code> is a dictionary of all parameter tensors.</p>"""),
  ('    print(f"done', "<p>Final message after the last epoch.</p>"),
  ("if __name__", """
<p>The command-line interface. <code>argparse</code> reads options such as <code>--epochs 30</code> and passes them to
<code>train_localization</code>. Note <code>--workers</code> defaults to 4 here: the number of helper processes loading
images.</p>"""),
 ]),

("src/damage.py", "python",
 "<p>The second model: it compares the before and after images and labels every pixel's damage level. It has "
 "the same structure as <code>train.py</code>; this walkthrough focuses on what is different.</p>",
 [
  ('"""Phase 3: damage', "<p>Docstring with the classes and the xView2 scoring formula.</p>"),
  ("import csv", "<p>Same libraries as <code>train.py</code>, plus OpenCV and numpy. It reuses <code>read_rgb</code>, <code>to_tensor</code> and <code>pick_device</code> from the other files instead of copying them.</p>"),
  ("DAMAGE_NAMES =", """
<p><code>IGNORE = 255</code> is a special value: pixels of un-classified buildings get it, and the loss function is told
to skip them, since there is no correct answer to learn. <code>CLASS_WEIGHTS</code> are the default <b>class weights</b>
(v1): a mistake on a damaged pixel costs 3 times as much as on an undamaged one, and background costs half, because
damaged buildings are rare. v2 used <code>0.5, 1, 6, 3, 3</code> and v3 <code>0.5, 1, 4, 4, 3</code>, passed on the command line.</p>"""),
  ("class DamageDataset", "<p>Same as <code>BuildingDataset</code>: collects mask paths. <code>image_path</code> takes a phase, <code>\"pre\"</code> or <code>\"post\"</code>.</p>"),
  ("    def __getitem__", """
<p>Reads both images and the mask. The mask keeps its exact values 0–4, and line 62 replaces every 5
(un-classified) with 255 (ignore). The crop and augmentation are the same as before, applied identically to
<b>all three</b> arrays, otherwise before, after and labels would no longer line up.</p>"""),
  ("        x = torch.cat", """
<p><code>torch.cat</code> stacks the before image (3 channels) and the after image (3 channels) into one
<b>6-channel</b> input of shape <code>(6, 512, 512)</code>. The target becomes whole numbers (<code>int64</code>), which
cross-entropy needs for class labels.</p>"""),
  ("def build_model", """
<p>The same U-Net with a ResNet-34 encoder, but <code>in_channels=6</code> and <code>classes=5</code> (background +
4 damage levels). The pretrained first layer expects 3 channels; <code>smp</code> adapts it to 6 by reusing the
pretrained weights. The model has 24,446,357 parameters.</p>"""),
  ("def loss_fn", """
<p><b>Cross-entropy</b> for 5 classes: for every pixel, the model gives 5 scores; softmax turns them into
probabilities; the loss is high when the probability of the correct class is low. <code>weight=</code> applies the
class weights; <code>ignore_index=</code> skips un-classified pixels.</p>"""),
  ("def f1(", "<p>Precision, recall and F1 from counts, as in <code>train.py</code>, as a small reusable function.</p>"),
  ("def predict_classes", """
<p>Turns the 5 output scores per pixel into decisions, in two steps:</p>
<ul>
<li><code>argmax(1) &gt; 0</code>: the class with the highest score; if it is not background (0), the pixel is a building.</li>
<li><code>logits[:, 1:5].argmax(1) + 1</code>: the damage level among the four damage scores only, so every building pixel always gets a level even if background was a close second.</li>
</ul>"""),
  ("@torch.no_grad()", """
<p>The <b>xView2 scoring</b> on the validation split.</p>
<ul>
<li><code>loc</code> counts true positives, false positives and false negatives for building vs background (lines 113–116).</li>
<li><code>scored</code> marks pixels whose true level is 1–4; only these count for damage.</li>
<li>For each level <code>c</code>, count the three kinds of agreement (lines 118–122), giving a 4 × 3 table.</li>
<li>Line 126 is the <b>harmonic mean</b> of the four F1 values: 4 / (1/F1₁ + 1/F1₂ + 1/F1₃ + 1/F1₄). It is pulled down strongly by any weak class, which is why v2's near-zero major damage collapsed its score.</li>
<li>Line 127: score = 0.3 × localization F1 + 0.7 × damage F1.</li>
<li>Line 130 converts every value to a plain Python <code>float</code>. This fixed a real bug: numpy number types saved inside a checkpoint made <code>torch.load</code> refuse the file, so resuming would have crashed.</li>
</ul>"""),
  ("@torch.no_grad()", """
<p>The <b>building-level confusion matrix</b>, which is easier to explain than pixel scores. For each tile, it
finds every separate true building with <code>cv2.connectedComponents</code> (which labels each connected blob of
pixels with its own number). Inside each building it counts the true levels and the predicted levels with
<code>np.bincount</code>, takes the most common of each, and adds one to the matrix cell [true, predicted].</p>"""),
  ("def train_damage(", """
<p>The training function. Its body is the same as <code>train_localization</code> (datasets, loaders, AdamW, cosine
schedule, resume, epoch loop, history, best/last checkpoints), with three differences: the loss takes the class
weights, the best checkpoint is chosen by the xView2 <b>score</b> instead of F1, and the new
<code>init_from</code> option.</p>"""),
  ("    elif init_from:", """
<p><b>Starting from an existing model</b>, added for v3. When not resuming, the model's weights are replaced by those in
another checkpoint (v1's <code>best.pt</code>), so training continues from a model that already knows the task,
instead of from the ImageNet encoder alone. Together with the lower learning rate, this <b>fine-tunes</b> v1.</p>"""),
  ("if __name__", """
<p>Command-line options, including the three added for v2 and v3: <code>--class-weights</code> (exactly 5 numbers),
<code>--lr</code> and <code>--init-from</code>. The v3 command was:</p>
<pre class="cmd">python -m src.damage --out-dir runs/damage_v3 --train-splits tier1 tier3 --epochs 10 \\
    --lr 1e-4 --init-from runs/damage_resnet34/best.pt --class-weights 0.5 1 4 4 3</pre>"""),
 ]),

("src/predict.py", "python",
 "<p>Uses both trained models on new tiles and turns per-pixel predictions into buildings on a map.</p>",
 [
  ('"""Phase 4', "<p>Docstring listing the five steps applied to each tile.</p>"),
  ("import argparse", "<p><code>defaultdict(list)</code> is a dictionary that creates an empty list the first time a key is used: handy for grouping buildings by disaster. Buildings smaller than 30 pixels are ignored as noise.</p>"),
  ("def load_models", "<p>Builds both architectures without downloading weights, then loads our trained weights from the <code>best.pt</code> files. <code>.eval()</code> switches both to prediction mode.</p>"),
  ("@torch.no_grad()", """
<p>Runs both models on one tile at full size. <code>[None]</code> adds a batch dimension of 1.</p>
<ul>
<li>Localization: <code>sigmoid</code> gives a building probability per pixel; <code>[0, 0]</code> takes the first image and its only channel.</li>
<li>Damage: <code>[0, 1:5]</code> keeps the four damage scores; <code>softmax(dim=0)</code> turns them into four probabilities that add up to 1 for each pixel.</li>
</ul>"""),
  ("def extract_buildings", """
<p>From pixels to buildings.</p>
<ul>
<li>Line 56: probability above 0.5 = building pixel; <code>connectedComponents</code> gives each connected blob its own number (this is also why touching houses merge into one).</li>
<li>Line 62: average the four damage probabilities over the building's pixels; the highest is its level, and its value is reported as the <b>confidence</b>.</li>
<li>Line 63: <code>findContours</code> traces the blob's outline; line 64 keeps the largest and simplifies it with <code>approxPolyDP</code> (corners closer than 1 pixel to a straight line are dropped).</li>
</ul>"""),
  ("def georeference", """
<p>Converts pixel positions to longitude/latitude, the project's main finding in code. Each label file lists every
building twice: in pixels and in longitude/latitude. Lines 85–91 pair them up by building id.</p>
<p>Line 95 is an <b>affine transform</b> fitted by <b>least squares</b>: find the 6 numbers in <code>coef</code> so that
<code>[x, y, 1] @ coef ≈ [longitude, latitude]</code> for all corners at once. An affine transform can scale, shift,
rotate and shear, which covers how a map relates to a flat photo of a small area. The fit is exact to within
10 cm on every image.</p>
<p>Lines 97–101: tiles with no buildings fall back to the GeoTIFF tags, which are about 30 m off (see
<code>check_georef.py</code>). Lines 103–106 return a small function that applies the transform to any points.</p>"""),
  ("def geojson_polygon", "<p>Writes a ring of points in <b>GeoJSON</b>, the standard text format web maps read. The ring must end where it starts, so the first point is repeated. 7 decimals of a degree is about 1 cm.</p>"),
  ("def true_buildings", """
<p>For the expert-labelled buildings: their true level, and the level the model predicted inside the true outline
(a mask of the outline, then a vote with <code>bincount</code>). The dashboard uses this for "model vs. true labels".</p>"""),
  ("def export", "<p>The main loop: for each split and each hurricane tile, read the images, run both models, and get the tile's coordinate converter.</p>"),
  ("            predicted = extract_buildings", "<p>Each predicted building and each true building becomes one GeoJSON <b>feature</b> (a shape plus properties: source, tile, damage level, confidence), grouped by disaster.</p>"),
  ("            for phase, rgb in", """
<p>Saves small 512 × 512 copies of both images for the map, and a summary of the tile: its corners as
<code>[[south, west], [north, east]]</code> (the format Leaflet wants) and its building counts per level.</p>"""),
  ("    for disaster, feats in", "<p>Writes one GeoJSON file per hurricane and one <code>tiles.json</code> index. <code>separators=(\",\", \":\")</code> removes spaces to keep files smaller.</p>"),
  ("if __name__", "<p>Options: which splits to export (default hold and test) and which damage model to use (default v3).</p>"),
 ]),

("src/evaluate.py", "python",
 "<p>The final, one-time evaluation on the test split, which was never used for any decision.</p>",
 [
  ('"""Final evaluation', "<p>Docstring explaining why the test split exists: the hold split chose the best epochs, so its scores are slightly optimistic.</p>"),
  ("import argparse", "<p>Imports and the two damage models to compare: v1 and the final v3.</p>"),
  ("def load(", "<p>Builds a model with a given function and loads its best weights. Passing the function (<code>build</code>) as an argument lets one helper load both kinds of model.</p>"),
  ("def main(", "<p>Scores the localization model on all 933 test tiles with the same <code>evaluate</code> function used during training.</p>"),
  ("    damage_ds =", "<p>For v1 and v3: pixel scores, the building-level confusion matrix, and building accuracy (the diagonal of the matrix divided by its total). Everything is saved to <code>runs/test_results.json</code>.</p>"),
  ("if __name__", "<p>Runs on <code>test</code> by default.</p>"),
 ]),

("src/check_georef.py", "python",
 "<p>Checks the coordinate error across the whole dataset: for every image, how far apart the GeoTIFF tags and "
 "the label coordinates place the same buildings.</p>",
 [
  ('"""Compare the GeoTIFF', "<p>Docstring listing every measured column.</p>"),
  ("import json", "<p>Constants: metres per degree of latitude (about 110.6 km everywhere) and of longitude at the equator (111.3 km, shrinking with the cosine of latitude).</p>"),
  ("def check_image", "<p>For one label file: pair pixel outlines with longitude/latitude outlines by building id, as in <code>predict.py</code>. Images without buildings cannot be checked and return early.</p>"),
  ("    pixels, lnglats = np.vstack", """
<p><code>metres()</code> converts differences in degrees to metres: longitude differences are multiplied by
111,320 × cos(latitude), latitude differences by 110,574, and <code>hypot</code> gives the straight-line distance.
Then the same least-squares affine fit as in <code>predict.py</code>.</p>"""),
  ("    tif_path =", "<p>Reads the GeoTIFF tags (top-left corner and pixel size in degrees), places every building corner with them, and measures the distance to the label position in metres.</p>"),
  ("    row.update", """
<p>Records the results, including the key test: <code>label_ratio</code> (degrees of longitude per degree of latitude
for one pixel, from the labels), <code>tif_ratio</code> (always exactly 1.0) and <code>expected_ratio</code> = 1 / cos(latitude),
the ratio for pixels that are square on the ground. The labels match the expected ratio; the tags do not.</p>"""),
  ("def main", "<p>Checks all 22,068 label files in parallel (under a minute), saves <code>outputs/georef_check.csv</code>, and prints the summary and the table by disaster.</p>"),
 ]),

("src/validate_osm.py", "python",
 "<p>An independent check of the coordinate finding: compare xBD buildings with OpenStreetMap (OSM) buildings, "
 "which volunteers traced on other imagery.</p>",
 [
  ('"""Validate xBD', "<p>Docstring with the measured quantities.</p>"),
  ("import argparse", """
<p><code>requests</code> downloads data from the internet; <code>shapely</code> does geometry (is a point inside a polygon,
how far apart are two shapes). Seven disasters are sampled across latitudes, with Palu near the equator as a
control. The 100 m margin makes sure shifted buildings are still inside the downloaded area.</p>"""),
  ("def sample_tiles", "<p>Picks tiles with at least 30 buildings at random, but with a fixed <b>seed</b> (<code>Random(0)</code>), so the same tiles are chosen every run.</p>"),
  ("def xbd_buildings", "<p>Each building's outline placed two ways: from the label coordinates, and from the GeoTIFF tags.</p>"),
  ("def fetch_osm", """
<p>Downloads OSM buildings for a box through the <b>Overpass API</b>, a public query service. Results are cached in
<code>data/osm/</code> so each tile is downloaded once. The server is often busy, so it retries up to 6 times with
longer waits, and waits 2 seconds between requests to be polite. A tile that still fails is skipped, not crashed.</p>"""),
  ("def to_metres", "<p>Converts longitude/latitude to metres around the tile centre, so distances can be measured.</p>"),
  ("def score", "<p>For a set of building centres: the share that fall inside an OSM building (<b>hit rate</b>) and the median distance to the nearest OSM building. An <code>STRtree</code> is a spatial index that makes these searches fast.</p>"),
  ("def best_shift", "<p>Tries every shift of the label positions from −40 to +40 m in 2 m steps, and finds the one that puts the most centres inside OSM buildings. If the labels are right, the best shift should be small (a few metres, from OSM's own accuracy and roof lean).</p>"),
  ("def validate_tile", "<p>Puts it together for one tile: download OSM, build OSM polygons in metres, and score both placements.</p>"),
  ("def main", "<p>Runs all sampled tiles, saves <code>outputs/osm_validation.csv</code>, and prints the comparison overall, for well-covered tiles, and by disaster.</p>"),
 ]),

("src/progress.py", "python",
 "<p>The live progress display used during the overnight runs. It only reads files, so it cannot affect training.</p>",
 [
  ('"""Live training progress', "<p>Docstring with the command.</p>"),
  ("DAMAGE_COLUMNS", "<p>The runs to show: title, folder, program, which score decides \"best\", which columns to print, and how many epochs the run has.</p>"),
  ("def is_running", "<p>Asks the operating system whether a matching process exists, with the <code>pgrep</code> command.</p>"),
  ("def read_history", "<p>Reads a run's <code>history.csv</code> into a list of rows.</p>"),
  ("def show_run", "<p>Prints the status, a progress bar of <code>#</code> characters, the latest and best scores, and an estimated finish time from the average of the last 5 epochs.</p>"),
  ("def main", "<p>Clears the screen with a terminal control code, prints every run, waits 30 seconds, repeats. Ctrl+C raises <code>KeyboardInterrupt</code>, which ends the loop quietly.</p>"),
 ]),

("dashboard/index.html", "javascript",
 "<p>The map: one web page using <b>Leaflet</b>, an open-source map library. It reads the files written by "
 "<code>predict.py</code>. It needs a small web server (<code>python -m http.server</code>) because browsers do not "
 "let pages opened straight from disk load data files.</p>",
 [
  ("<!doctype html>", "<p>The page header: title, and Leaflet's stylesheet and script loaded from a public CDN (a server that hosts common libraries).</p>"),
  ("<style>", "<p>The page's CSS (styling). Colours are defined once as variables (<code>--bg</code>, <code>--destroyed</code>, …) and redefined for dark mode. The damage colours are the same as in every Python figure. The last rule stacks the sidebar under the map on narrow screens.</p>"),
  ("<body>", "<p>The page structure: a sidebar with the disaster menu, the prediction/labels switch, the before/after switch, the agreement score and the hardest-hit list, and an empty <code>div</code> where Leaflet draws the map.</p>"),
  ("<script>", "<p>Start of the JavaScript program.</p>"),
  ("const LEVELS", """
<p>The four damage levels; colours read from the CSS variables so they always match; readable disaster names; the
zoom level at which tile images appear (15). <code>state</code> holds what the user selected. <code>overlays</code> keeps the
tile images currently on the map; <code>cache</code> keeps downloaded GeoJSON so switching back is instant.</p>"""),
  ("const map = L.map", "<p>Creates the map. <code>preferCanvas: true</code> draws buildings on one canvas instead of thousands of separate elements, which keeps it smooth with over 10,000 buildings. Two base layers (Esri satellite, OpenStreetMap streets), a layer switcher and a scale bar.</p>"),
  ("function setSegment", "<p>Helpers for the button groups: highlight the chosen button, and run a function when one is clicked.</p>"),
  ("async function loadDisaster", "<p>Downloads one hurricane's GeoJSON the first time it is needed, showing \"Loading…\". <code>async</code>/<code>await</code> lets the page wait for the download without freezing.</p>"),
  ("function popupFor", "<p>The text shown when a building is clicked: predicted level and confidence, or for a labelled building, whether the model agreed.</p>"),
  ("function drawBuildings", "<p>Removes the old buildings layer and draws the buildings of the chosen source and checked levels, each coloured by level with a popup.</p>"),
  ("function drawLevelCounts", "<p>Rebuilds the checkboxes with counts and bars, and reconnects them so ticking a box redraws the map.</p>"),
  ("function drawAgreement", "<p>Share of labelled buildings where the model gave the same level.</p>"),
  ("function drawPriority", "<p>Ranks tiles by destroyed × 2 + major, keeps the top 10, and lets a click zoom to the tile and put its id in the address bar.</p>"),
  ("function drawTileOutlines", "<p>A thin white rectangle around every tile.</p>"),
  ("function updateImagery", "<p>Runs after every pan or zoom: when zoomed in far enough, adds the before or after image of each tile in view (placed by its corner coordinates) and removes the ones out of view, so only a few images are loaded at a time.</p>"),
  ("async function selectDisaster", "<p>Switching hurricane: load its buildings, draw everything, and zoom to fit its tiles.</p>"),
  ("async function init", "<p>Startup: read <code>tiles.json</code>, fill the menu, connect the controls, and open Harvey, or the tile named in the address, as in <code>#hurricane-harvey_00000198</code>.</p>"),
  ("init().catch", "<p>If startup fails (usually because <code>predict.py</code> was not run, or the page was opened without the server), show a message explaining what to do.</p>"),
 ]),
]


# ====================================================================== other sections

CONCEPTS = [
("Images are arrays of numbers",
 "<p>A colour image of 1024 × 1024 pixels is three grids of numbers, one each for red, green and blue, each from "
 "0 to 255. In code it is an <b>array</b> of shape <code>(1024, 1024, 3)</code>. A <b>tensor</b> is the same idea in "
 "PyTorch: a multi-dimensional array that can live on the GPU and remember how it was computed. A batch of 8 crops "
 "is a tensor of shape <code>(8, 3, 512, 512)</code>: 8 images, 3 colour channels, 512 rows, 512 columns.</p>"),
("Supervised learning",
 "<p>The model learns from examples where the answer is known: for every xBD tile, experts drew each building and "
 "gave it a damage level. Training shows the model an image, compares its answer with the expert answer, and "
 "adjusts the model to be a little less wrong. Repeat hundreds of thousands of times.</p>"),
("Segmentation",
 "<p>Most image models give one answer per image (\"cat\"). <b>Segmentation</b> gives one answer per pixel "
 "(\"building\", \"background\"). Both models here are segmentation models; buildings are found afterwards by "
 "grouping pixels.</p>"),
("Neural networks and parameters",
 "<p>A neural network is a long chain of simple calculations (multiply by a weight, add, apply a simple "
 "non-linear function), with millions of adjustable numbers called <b>parameters</b> or weights. Our models have "
 "about 24.4 million. Training means finding parameter values that make the outputs match the answers.</p>"),
("Convolution",
 "<p>Image networks use <b>convolutions</b>: a small grid of weights (for example 3 × 3) slides over the image and "
 "computes a weighted sum at each position. Early layers learn to detect edges and colours; deeper layers combine "
 "them into corners, roofs and building shapes.</p>"),
("U-Net: encoder and decoder",
 "<p>A <b>U-Net</b> has two halves. The <b>encoder</b> shrinks the image step by step (512 → 256 → … → 16 pixels "
 "wide) while learning more abstract features (\"roof texture here\"). The <b>decoder</b> expands back to full size "
 "to give an answer per pixel. <b>Skip connections</b> pass detail from each encoder level to the matching decoder "
 "level, so edges stay sharp. Drawn as a diagram, it looks like a U.</p>"),
("ResNet-34 and transfer learning",
 "<p>The encoder is a <b>ResNet-34</b>, a well-known 34-layer network whose \"residual\" shortcuts make deep "
 "networks trainable. Its weights were <b>pretrained</b> on ImageNet, 1.2 million everyday photos, so it already "
 "recognises edges, textures and shapes. Starting from that knowledge is called <b>transfer learning</b>; it needs "
 "far less data and time than starting from random weights.</p>"),
("Logits, sigmoid and softmax",
 "<p>A network's raw outputs are <b>logits</b>: any numbers, positive or negative. <b>Sigmoid</b> turns one logit into "
 "a probability between 0 and 1 (used for building vs background). <b>Softmax</b> turns several logits into "
 "probabilities that add up to 1 (used for the five damage classes).</p>"),
("Loss",
 "<p>The <b>loss</b> is one number that says how wrong the model is on a batch; training makes it smaller. "
 "<b>Cross-entropy</b> is large when the model gives a low probability to the correct answer. <b>Dice loss</b> "
 "measures overlap of areas. <b>Class weights</b> make mistakes on rare classes cost more.</p>"),
("Gradients, backpropagation and the optimizer",
 "<p>For each parameter, the <b>gradient</b> says how the loss changes if that parameter increases a little. "
 "<b>Backpropagation</b> computes all 24.4 million gradients efficiently, layer by layer from the output back to "
 "the input. The <b>optimizer</b> (here AdamW) then moves every parameter a small step against its gradient. The "
 "size of that step is the <b>learning rate</b> (0.0003, later 0.0001).</p>"),
("Batch, iteration, epoch",
 "<p>A <b>batch</b> is a group of examples processed together (8 crops). One <b>iteration</b> is one batch: forward, "
 "loss, backward, update. One <b>epoch</b> is one pass over all training tiles: 349 iterations for tier1, 1,146 for "
 "tier1 + tier3. Models v1 and the localization model trained for 30 epochs, v2 for 25, v3 for 10.</p>"),
("Augmentation and overfitting",
 "<p><b>Overfitting</b> is memorising the training examples instead of learning the general pattern; the model then "
 "does badly on new images. <b>Augmentation</b> (random crops, flips, rotations) and <b>weight decay</b> reduce it. "
 "The \"overfit tests\" in this project did the opposite on purpose: train on 8 tiles until memorised, just to prove "
 "the code can learn at all.</p>"),
("Training, validation and test splits",
 "<p>Data is split three ways. <b>Training</b> data (tier1, later tier3) is what the model learns from. "
 "<b>Validation</b> data (hold) is used to choose between options, such as the best epoch or v1 vs v3. <b>Test</b> "
 "data is used exactly once at the end; because nothing was chosen with it, its score is the honest estimate of "
 "performance on new data.</p>"),
("Precision, recall, F1",
 "<p><b>Precision</b>: of everything the model called a building, the share that really is. <b>Recall</b>: of all real "
 "buildings, the share the model found. <b>F1</b> = 2 × precision × recall / (precision + recall): high only when "
 "both are high. A model that calls everything a building has perfect recall and terrible precision, and a low F1.</p>"),
("The xView2 score and the harmonic mean",
 "<p>Score = 0.3 × localization F1 + 0.7 × damage F1. The damage F1 is the <b>harmonic mean</b> of the four "
 "per-level F1 values, which is dominated by the weakest: for example F1 values of 0.9, 0.9, 0.9 and 0.1 give a "
 "harmonic mean of only 0.3. This is why ignoring a rare damage level is heavily punished.</p>"),
("Confusion matrix",
 "<p>A table with true classes as rows and predicted classes as columns. Each cell counts how many buildings of "
 "that true level got that predicted level. The diagonal holds correct answers; everything else shows which "
 "mistakes are made, such as \"minor called major\".</p>"),
("Checkpoints",
 "<p>A <b>checkpoint</b> is a file with the model's parameters (and, for resuming, the optimizer state and epoch). "
 "<code>best.pt</code> is the epoch with the best validation score; <code>last.pt</code> is the latest, for resuming.</p>"),
("GPU, MPS and DataLoader workers",
 "<p>Neural networks are mostly large multiplications, which a GPU does in parallel. On Apple Silicon, PyTorch uses "
 "the GPU through <b>MPS</b>. While the GPU computes, <b>DataLoader workers</b> (separate processes) read and prepare "
 "the next images on the CPU, so the GPU never waits.</p>"),
("Georeferencing, WKT, GeoJSON, affine transforms",
 "<p><b>Georeferencing</b> means knowing where on Earth each pixel is. <b>WKT</b> and <b>GeoJSON</b> are text formats "
 "for shapes. An <b>affine transform</b> converts pixel (x, y) to (longitude, latitude) with six numbers: it can "
 "shift, scale, rotate and shear. A degree of longitude is about 111 km at the equator but only 96 km at Houston "
 "(30°N), because longitude lines meet at the poles; ignoring that is exactly the mistake in the GeoTIFF tags.</p>"),
]

TIMELINE = [
("Set up the project", "28 Sep",
 "Created the folders (<code>src</code>, <code>notebooks</code>, <code>data</code>, <code>outputs</code>), <code>README.md</code>, "
 "<code>requirements.txt</code> and <code>.gitignore</code>, wrote <code>src/xbd.py</code> and notebook 01, and tested both on a "
 "small fake dataset because the real one was not downloaded yet.", None),
("Downloaded and extracted xBD", "18 Oct",
 "You downloaded the full GeoTIFF release as 6 parts (55 GB). They were joined and unpacked in one pass, giving 130 GB "
 "in four folders: tier1 (2,799 pairs), tier3 (6,369), hold (933) and test (933).",
 "cat xview2_geotiff.tgz.part-a? | tar xzf - -C data/xbd --strip-components=1"),
("Fixed three surprises", "18 Oct",
 "The images were 16-bit, which Pillow cannot read, so <code>load_image</code> was added using <code>tifffile</code>. The "
 "training folder was called <code>tier1</code>, not <code>train</code>. And your default <code>python3</code> had changed to "
 "an install without Jupyter, so the project switched to Anaconda's Python at <code>/opt/anaconda3/bin/python3</code>.", None),
("Explored the data (notebook 01)", "18 Oct",
 "162,787 buildings in tier1 from 10 disasters: 72% no damage, 9% minor, 9% major, 8% destroyed. Harvey was mostly "
 "flooding (36% major, 1.7% destroyed). Median building 654 pixels. First git commit.",
 "python -m jupyter nbconvert --to notebook --execute --inplace 01_explore_xbd.ipynb"),
("Converted the data for training", "18 Oct",
 "Measured file sizes (PNG 1.8 MB, JPEG-95 0.39 MB per image), wrote <code>src/preprocess.py</code>, checked one mask "
 "by overlaying it on its image, and converted all four splits.", "python -m src.preprocess"),
("Wrote the localization training and proved it learns", "18 Oct",
 "Wrote <code>src/dataset.py</code> and <code>src/train.py</code>. A tiny test checked saving and resuming; an overfit test "
 "on 8 tiles raised F1 from 0.08 to 0.77, proving the code learns. (A Google Colab version was also prepared, then "
 "removed when you chose to train on the Mac.)", None),
("Fixed a training freeze", "18 Oct",
 "The first speed test froze: OpenCV threads deadlocked inside the DataLoader's worker processes. "
 "<code>cv2.setNumThreads(0)</code> fixed it. Measured speed: 0.86 seconds per batch, about 5 minutes of training "
 "per epoch.", None),
("Trained the localization model overnight", "18–19 Oct",
 "30 epochs at about 7 minutes each (including validation). The score jumped around early (0.78 at epoch 3, 0.49 at "
 "epoch 4) while the learning rate was high, then settled. Best: <b>F1 0.792 at epoch 27</b>.",
 "nohup caffeinate -i python -m src.train --epochs 30 > runs/loc_resnet34/train.log 2>&1 &"),
("Wrote the damage model and found a bug", "18 Oct",
 "Wrote <code>src/damage.py</code>. The overfit test showed it learns (score 0.14 → 0.54). The resume test crashed: numpy "
 "numbers in the checkpoint made <code>torch.load</code> refuse it. Fixed by converting metrics to plain floats.", None),
("Trained damage v1, chained automatically", "19 Oct",
 "A small script, <code>runs/overnight.sh</code>, waited for the localization run to finish and then started the damage "
 "model. Best: <b>score 0.575 at epoch 26</b>, but minor damage F1 only 0.22.",
 "python -m src.damage --epochs 30"),
("Built the map and found the coordinate error", "19 Oct",
 "Wrote <code>src/predict.py</code> and <code>dashboard/index.html</code>. Placing buildings with the GeoTIFF tags put them "
 "tens of metres off; fitting an affine transform from the label coordinates fixed it. Exported 804 hurricane tiles "
 "and checked alignment with screenshots.", "python -m src.predict"),
("Tried to fix minor damage: v2 failed", "19–20 Oct",
 "Added tier3 (9,168 tiles) and doubled the minor weight (0.5, 1, 6, 3, 3), 25 epochs at about 20 minutes each. "
 "Minor improved (0.22 → 0.40) but major collapsed (0.59 → 0.08): <b>score 0.402</b>. Lesson: weights trade "
 "neighbouring classes off against each other.",
 "python -m src.damage --out-dir runs/damage_v2 --train-splits tier1 tier3 --epochs 25 --class-weights 0.5 1 6 3 3"),
("v3: balanced weights, fine-tuned from v1", "20 Oct",
 "Started from v1's trained weights, equal weights for minor and major (4, 4), learning rate 0.0001, 10 epochs, "
 "3.3 hours. <b>Score 0.711</b>, with minor 0.45, major 0.69, destroyed 0.80.",
 "python -m src.damage --out-dir runs/damage_v3 --train-splits tier1 tier3 --epochs 10 --lr 1e-4 --init-from runs/damage_resnet34/best.pt --class-weights 0.5 1 4 4 3"),
("Wrote the report and slides", "19–21 Oct",
 "<code>docs/build_report.py</code> builds the Word report from the results and code, so numbers never need copying by "
 "hand. The presentation was built as a slide deck.", "python docs/build_report.py"),
("Final evaluation on the test split", "21 Oct",
 "Ran once at the end: localization F1 <b>0.788</b>, v1 score 0.584, v3 score <b>0.702</b>, 80.8% of buildings at the "
 "right level. Every number within about 0.01 of validation.", "python -m src.evaluate"),
("Pushed to GitHub", "21 Oct", "Merged GitHub's placeholder README and pushed everything except data and models.", "git push -u origin main"),
("Checked the coordinate error everywhere", "21 Oct",
 "<code>src/check_georef.py</code> checked all 22,068 images: median offset 30 m, up to 84 m, growing with latitude. "
 "A side-by-side figure on an independent Esri basemap confirmed the labels are right.", "python -m src.check_georef"),
("Started the OpenStreetMap validation", "21 Oct",
 "<code>src/validate_osm.py</code> compares xBD buildings with OSM buildings on 105 tiles across 7 disasters.",
 "python -m src.validate_osm --per-disaster 15"),
]

QUESTIONS = [
("Why are there two models instead of one?",
 "Finding buildings and judging damage are different tasks. Buildings are clearest in the before image, before any "
 "damage; damage needs both images. Splitting them keeps each model's job simple. (In practice the damage model also "
 "found buildings slightly better, F1 0.82 vs 0.79, because it sees both images.)"),
("Why train on 512 × 512 crops if tiles are 1024 × 1024?",
 "Four times less memory per example, so a batch of 8 fits on the laptop GPU, and each epoch sees a different random "
 "quarter of each tile, which acts as extra variety."),
("Why normalise with the ImageNet mean and standard deviation?",
 "The encoder's pretrained weights were learned on images normalised that way. Feeding differently scaled numbers "
 "would make its learned features less useful at the start."),
("Why add Dice loss to cross-entropy for the localization model?",
 "About 85% of pixels are background. Cross-entropy counts pixels, so small buildings contribute little. Dice is a "
 "ratio of overlapping areas, so a missed small building matters as much as a large stretch of background."),
("Why did v2 fail?",
 "Minor and major damage are the two levels the model confuses most. With minor weighted 6 and major 3, calling an "
 "uncertain building \"minor\" became the cheaper mistake, so the model almost stopped predicting major. The "
 "harmonic mean then pulled the score down."),
("Why did v3 work?",
 "Equal weights for minor and major meant neither was the safer guess; starting from v1 kept what v1 already knew "
 "about major damage; the lower learning rate refined rather than overwrote it; and tier3 tripled the data. v3 "
 "changed all of these at once, so the gain cannot be attributed to one change."),
("Why is v3's building accuracy not higher than v1's, if its score is much higher?",
 "v3 finds far more minor-damage buildings, but also calls about 11–14% of undamaged buildings minor. Undamaged "
 "buildings are the large majority, so plain accuracy stays about the same, while the score, which weights all four "
 "levels equally, rises sharply."),
("Why is the test score the one to report?",
 "The hold split was used to choose epochs and versions, so its scores are slightly optimistic. The test split was "
 "never used for any decision, so it is the honest estimate of performance on new data."),
("How do we know the label coordinates are right and the GeoTIFF tags wrong?",
 "Three independent pieces of evidence: the tags use exactly the same degrees for longitude and latitude, which is "
 "only correct at the equator; the error grows with latitude exactly as that mistake predicts (1 m at Palu, 49 m in "
 "Portugal); and on an independent Esri basemap the label placement lines up while the tag placement shows every "
 "building doubled. The OpenStreetMap comparison adds a fourth."),
("What would you improve next?",
 "A Siamese network (one shared encoder for before and after), splitting touching buildings (watershed), ensembles "
 "and test-time augmentation, and fine-tuning on data from the affected region."),
]

ONE_STEP = """
<p>What happens in one iteration of the localization model, with the actual shapes:</p>
<ol>
<li><b>Load.</b> The DataLoader asks the dataset for 8 random tiles. Each is cropped to 512 × 512, flipped or rotated at
random, and normalised. Stacked together: images <code>(8, 3, 512, 512)</code>, masks <code>(8, 1, 512, 512)</code> of 0s and 1s.</li>
<li><b>Move.</b> Both tensors are copied to the GPU (<code>.to("mps")</code>).</li>
<li><b>Forward pass.</b> The encoder shrinks each crop through 5 levels down to 16 × 16 × 512 features; the decoder
expands back to 512 × 512 using the skip connections. Output: logits <code>(8, 1, 512, 512)</code>, one score per pixel.</li>
<li><b>Loss.</b> Binary cross-entropy compares all 2,097,152 pixel scores (8 × 512 × 512) with the mask; Dice compares
predicted and true areas per image. Their sum is one number, for example 0.7.</li>
<li><b>Backward pass.</b> <code>loss.backward()</code> computes a gradient for each of the 24,436,369 parameters.</li>
<li><b>Update.</b> AdamW moves each parameter a tiny step (scaled by the learning rate, 0.0003) to lower the loss.</li>
<li><b>Repeat.</b> 349 times is one epoch (about 5 minutes); then validation on 933 full tiles (about 1.5 minutes); then
save checkpoints; then the next epoch, with a slightly lower learning rate.</li>
</ol>
<p>The damage model is the same except the input is <code>(8, 6, 512, 512)</code> (before and after stacked), the output is
<code>(8, 5, 512, 512)</code> (five class scores per pixel), the target is <code>(8, 512, 512)</code> whole numbers 0–4 (or 255 to
ignore), and the loss is weighted cross-entropy.</p>
"""

RESULTS = [
("Localization F1 (finding buildings)", "0.792", "0.788"),
("Damage score, v1", "0.575", "0.584"),
("Damage score, v2", "0.402", "—"),
("Damage score, v3 (final)", "0.711", "0.702"),
("v3: buildings at the right level", "77.7%", "80.8%"),
("v3 F1: no / minor / major / destroyed", "0.91 / 0.45 / 0.69 / 0.80", "0.93 / 0.42 / 0.69 / 0.82"),
]


# ====================================================================== rendering

def chunks(path, anchors):
    lines = (ROOT / path).read_text().splitlines()
    starts = []
    search_from = 0
    for anchor in anchors:
        for i in range(search_from, len(lines)):
            if lines[i].startswith(anchor):
                starts.append(i)
                search_from = i + 1
                break
        else:
            raise SystemExit(f"{path}: anchor not found after line {search_from}: {anchor!r}")
    ends = starts[1:] + [len(lines)]
    for start, end in zip(starts, ends):
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        yield start + 1, lines[start:end]


def slug(text):
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def render():
    toc_files = []
    file_sections = []
    for path, lang, intro, parts in FILES:
        anchors = [a for a, _ in parts]
        sid = slug(path)
        toc_files.append(f'<li><a href="#{sid}">{html.escape(path)}</a></li>')
        blocks = []
        for (first, code_lines), (_, explanation) in zip(chunks(path, anchors), parts):
            last = first + len(code_lines) - 1
            # every "line N" / "lines N–M" in an explanation must point inside the chunk it explains
            for a, b in re.findall(r"[Ll]ines? (\d+)(?:–(\d+))?", explanation):
                for n in filter(None, (a, b)):
                    if not first <= int(n) <= last:
                        raise SystemExit(f"{path}: explanation cites line {n}, but the chunk is lines {first}–{last}")
            numbers = "\n".join(str(first + k) for k in range(len(code_lines)))
            code = html.escape("\n".join(code_lines))
            label = f"lines {first}–{first + len(code_lines) - 1}" if len(code_lines) > 1 else f"line {first}"
            code_html = (f'<div class="code"><pre class="ln" aria-hidden="true">{numbers}</pre>'
                         f'<pre class="src"><code class="language-{lang}">{code}</code></pre></div>')
            if len(code_lines) > 45:
                code_html = f'<details class="long"><summary>Show {label} ({len(code_lines)} lines)</summary>{code_html}</details>'
            blocks.append(f'<div class="chunk"><div class="chunk-code"><p class="where">{label}</p>{code_html}</div>'
                          f'<div class="chunk-text">{explanation}</div></div>')
        lines = len((ROOT / path).read_text().splitlines())
        file_sections.append(f'<section class="file" id="{sid}"><h3><code>{html.escape(path)}</code>'
                             f'<span class="meta">{lines} lines</span></h3>{intro}{"".join(blocks)}</section>')

    concepts = "".join(f'<div class="concept"><h3>{html.escape(t)}</h3>{body}</div>' for t, body in CONCEPTS)
    timeline = "".join(
        f'<li><div class="t-head"><span class="t-date">{date}</span><h3>{html.escape(title)}</h3></div><p>{body}</p>'
        + (f'<pre class="cmd">{html.escape(cmd)}</pre>' if cmd else "") + "</li>"
        for title, date, body, cmd in TIMELINE)
    results = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in RESULTS)
    questions = "".join(f"<details class=\"q\"><summary>{html.escape(q)}</summary><p>{html.escape(a)}</p></details>"
                        for q, a in QUESTIONS)

    page = TEMPLATE.replace("{{TOC_FILES}}", "".join(toc_files)).replace("{{CONCEPTS}}", concepts) \
        .replace("{{TIMELINE}}", timeline).replace("{{ONE_STEP}}", ONE_STEP).replace("{{FILES}}", "".join(file_sections)) \
        .replace("{{RESULTS}}", results).replace("{{QUESTIONS}}", questions)
    OUT.write_text(page)
    print(f"wrote {OUT} ({len(page) / 1024:.0f} KB, {sum(len(p) for *_, p in FILES)} code chunks)")


TEMPLATE = r"""<title>Hurricane Damage Mapper Study Guide</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,650&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<style>
/* Layout: a single reading column; code chunks go two-up (code | explanation) on wide screens. */
:root {
  --bg: #f4f6f7; --surface: #ffffff; --ink: #18222c; --muted: #55626e; --line: #d8dee3;
  --accent: #b4521a; --link: #1d5c9c; --code-bg: #eef2f4; --code-ink: #1d2833;
  --hl-key: #8a3ea8; --hl-str: #2c7a39; --hl-num: #b4521a; --hl-com: #6c7884; --hl-fn: #1d5c9c;
  --display: "Newsreader", Georgia, serif; --body: "Source Sans 3", "Segoe UI", Arial, sans-serif;
  --mono: "JetBrains Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #11171c; --surface: #182027; --ink: #e2e8ed; --muted: #9eabb6; --line: #2b3640;
  --accent: #f0955a; --link: #7db4ec; --code-bg: #141b21; --code-ink: #dbe3ea;
  --hl-key: #d29ef0; --hl-str: #8fd19a; --hl-num: #f0b07a; --hl-com: #7f8d99; --hl-fn: #8cc3f5; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #11171c; --surface: #182027; --ink: #e2e8ed; --muted: #9eabb6; --line: #2b3640;
  --accent: #f0955a; --link: #7db4ec; --code-bg: #141b21; --code-ink: #dbe3ea;
  --hl-key: #d29ef0; --hl-str: #8fd19a; --hl-num: #f0b07a; --hl-com: #7f8d99; --hl-fn: #8cc3f5; color-scheme: dark }
body { background: var(--bg); color: var(--ink); font: 17px/1.6 var(--body);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.wrap { max-width: 1180px; margin: 0 auto; padding-block: 48px 96px; display: flex; flex-direction: column; gap: 56px; }
h1, h2, h3 { font-family: var(--display); font-weight: 650; line-height: 1.15; text-wrap: balance; margin: 0; }
h1 { font-size: clamp(34px, 5vw, 52px); }
h2 { font-size: clamp(26px, 3.4vw, 34px); padding-top: 8px; border-top: 2px solid var(--ink); }
h3 { font-size: 22px; }
p, li { max-width: 68ch; }
a { color: var(--link); }
code { font-family: var(--mono); font-size: 0.86em; background: var(--code-bg); color: var(--code-ink); padding: 1px 5px; border-radius: 4px; }
.lede { font-size: 20px; color: var(--muted); max-width: 62ch; }
.eyebrow { font: 600 13px/1.4 var(--body); letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); margin: 0; max-width: none; }
header { display: flex; flex-direction: column; gap: 14px; }
.section { display: flex; flex-direction: column; gap: 20px; }
nav.toc { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 8px 32px; background: var(--surface);
  border: 1px solid var(--line); border-radius: 10px; padding: 20px 24px; }
nav.toc ol, nav.toc ul { margin: 6px 0 0; padding-left: 20px; }
nav.toc li { margin: 2px 0; }
.howto { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
.howto div { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 16px 18px; }
.howto b { display: block; font-family: var(--display); font-size: 19px; margin-bottom: 4px; }
pre.mermaid { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 20px; overflow-x: auto; text-align: center; }
.concepts { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.concept { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px; min-width: 0; }
.concept h3 { font-size: 19px; margin-bottom: 6px; }
.concept p { margin: 0; }
ol.timeline { list-style: none; counter-reset: step; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 18px; }
ol.timeline > li { counter-increment: step; position: relative; padding-left: 52px; min-width: 0; }
ol.timeline > li::before { content: counter(step); position: absolute; left: 0; top: 0; width: 34px; height: 34px; border-radius: 50%;
  background: var(--ink); color: var(--bg); font: 600 15px/34px var(--body); text-align: center; font-variant-numeric: tabular-nums; }
.t-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }
.t-head h3 { font-size: 20px; }
.t-date { font: 600 13px var(--body); color: var(--accent); letter-spacing: 0.04em; }
ol.timeline p { margin: 6px 0; }
pre.cmd { font: 13.5px/1.5 var(--mono); background: var(--code-bg); color: var(--code-ink); padding: 10px 14px; border-radius: 8px;
  overflow-x: auto; margin: 6px 0 0; white-space: pre; }
.file { display: flex; flex-direction: column; gap: 18px; padding-top: 8px; }
.file h3 { display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px; font-size: 24px; }
.file h3 code { background: none; padding: 0; font-size: 22px; color: var(--ink); }
.meta { font: 600 13px var(--body); color: var(--muted); }
.chunk { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 20px 28px; padding: 16px 0; border-top: 1px solid var(--line); }
.chunk-code, .chunk-text { min-width: 0; }
.chunk-text p:first-child { margin-top: 0; }
.chunk-text ul, .chunk-text ol { padding-left: 20px; }
.where { font: 600 12px var(--body); letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); margin: 0 0 6px; }
.code { display: flex; background: var(--code-bg); border-radius: 8px; overflow-x: auto; }
.code pre { margin: 0; padding: 12px 0; font: 13px/1.55 var(--mono); }
pre.ln { color: var(--muted); text-align: right; padding-left: 12px; padding-right: 12px; border-right: 1px solid var(--line); user-select: none; flex: none; opacity: 0.8; }
pre.src { padding-left: 14px; padding-right: 16px; color: var(--code-ink); flex: 1; }
pre.src code { background: none; padding: 0; font-size: inherit; color: inherit; }
details.long > summary { cursor: pointer; font: 600 14px var(--body); color: var(--link); padding: 8px 0; }
.hljs-keyword, .hljs-built_in, .hljs-literal, .hljs-meta { color: var(--hl-key); }
.hljs-string, .hljs-attr, .hljs-template-variable { color: var(--hl-str); }
.hljs-number { color: var(--hl-num); }
.hljs-comment, .hljs-doctag { color: var(--hl-com); font-style: italic; }
.hljs-title, .hljs-title.function_, .hljs-name, .hljs-selector-tag { color: var(--hl-fn); }
table.results { border-collapse: collapse; width: 100%; max-width: 760px; font-variant-numeric: tabular-nums; }
.table-wrap { overflow-x: auto; }
table.results th, table.results td { text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--line); }
table.results th { font: 600 13px var(--body); letter-spacing: 0.05em; text-transform: uppercase; color: var(--muted); }
table.results td:not(:first-child) { white-space: nowrap; }
details.q { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 14px 18px; }
details.q summary { cursor: pointer; font-weight: 600; }
details.q p { margin: 10px 0 0; }
:focus-visible { outline: 2px solid var(--link); outline-offset: 2px; }
@media (max-width: 860px) { .chunk { grid-template-columns: minmax(0, 1fr); } body { font-size: 16px; } }
</style>

<div class="wrap">
<header>
  <p class="eyebrow">Hurricane Damage Mapper · Master’s project · Lamar University</p>
  <h1>Study guide: the whole project, step by step</h1>
  <p class="lede">Every concept, every step that was run, and every code file chunk by chunk with line numbers, so you can explain any part of the project in your own words.</p>
</header>

<section class="section">
  <div class="howto">
    <div><b>New to deep learning?</b>Read “Concepts” first. Each card explains one idea with this project’s own numbers.</div>
    <div><b>Want the story?</b>“What was done, in order” lists every step from download to final test, with the commands.</div>
    <div><b>Preparing for questions?</b>Read the code walkthrough with the file open in VS Code, then try “Test yourself”.</div>
  </div>
  <nav class="toc" aria-label="Contents">
    <div><strong>Contents</strong>
      <ol>
        <li><a href="#picture">The project in one picture</a></li>
        <li><a href="#concepts">Concepts</a></li>
        <li><a href="#timeline">What was done, in order</a></li>
        <li><a href="#one-step">One training step, traced</a></li>
        <li><a href="#code">The code, file by file</a></li>
        <li><a href="#results">The results</a></li>
        <li><a href="#quiz">Test yourself</a></li>
      </ol>
    </div>
    <div><strong>Code files</strong><ul>{{TOC_FILES}}</ul></div>
  </nav>
</section>

<section class="section" id="picture">
  <h2>The project in one picture</h2>
  <p>Raw satellite data goes through two trained models; their predictions become buildings on a map. The file that does each step is named in the box.</p>
<pre class="mermaid">
flowchart LR
  A["Raw xBD: GeoTIFF images and JSON labels (130 GB)"] --> B["preprocess.py: JPEG images and masks (9 GB)"]
  B --> C["train.py: model 1 finds buildings"]
  B --> D["damage.py: model 2 classifies damage"]
  C --> E["predict.py: buildings, damage, map coordinates"]
  D --> E
  E --> F["dashboard/index.html: interactive map"]
  C --> G["evaluate.py: final test scores"]
  D --> G
</pre>
</section>

<section class="section" id="concepts">
  <h2>Concepts</h2>
  <p>The ideas the code relies on, in the order they build on each other.</p>
  <div class="concepts">{{CONCEPTS}}</div>
</section>

<section class="section" id="timeline">
  <h2>What was done, in order</h2>
  <p>Every major step of the project, with the command that ran it. Commands use <code>python</code> as short for Anaconda’s <code>/opt/anaconda3/bin/python3</code> and run from the project folder.</p>
  <ol class="timeline">{{TIMELINE}}</ol>
</section>

<section class="section" id="one-step">
  <h2>One training step, traced</h2>
  {{ONE_STEP}}
</section>

<section class="section" id="code">
  <h2>The code, file by file</h2>
  <p>Each file’s code is shown in chunks, with the real line numbers on the left and an explanation on the right. The code is read from the project when this guide is built, so it is always current. Long chunks are folded; click to open them.</p>
  {{FILES}}
  <section class="file">
    <h3>Other files</h3>
    <ul>
      <li><code>notebooks/01_explore_xbd.ipynb</code>: counts, damage distribution, building sizes and before/after examples, using <code>xbd.py</code>.</li>
      <li><code>notebooks/02_building_localization.ipynb</code> and <code>03_damage_classification.ipynb</code>: training curves, predictions and the confusion matrix, read from <code>runs/</code>.</li>
      <li><code>docs/build_report.py</code>: builds the Word report from the results and source code. <code>docs/build_study_guide.py</code>: builds this guide.</li>
      <li><code>runs/overnight.sh</code> (not in git): waited for the localization run to end, then started damage v1.</li>
    </ul>
  </section>
</section>

<section class="section" id="results">
  <h2>The results</h2>
  <p>Validation (hold) chose epochs and versions; test was used once at the end and is the number to report.</p>
  <div class="table-wrap"><table class="results">
    <thead><tr><th>Measure</th><th>Validation</th><th>Test</th></tr></thead>
    <tbody>{{RESULTS}}</tbody>
  </table></div>
</section>

<section class="section" id="quiz">
  <h2>Test yourself</h2>
  <p>Questions a committee is likely to ask. Answer out loud first, then open the answer.</p>
  {{QUESTIONS}}
</section>
</div>

<script>
if (window.hljs) document.querySelectorAll("pre.src code").forEach(el => hljs.highlightElement(el));
</script>
"""

if __name__ == "__main__":
    render()
