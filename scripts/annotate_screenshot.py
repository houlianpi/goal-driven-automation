#!/usr/bin/env python3
"""
Add operation annotations to screenshots
"""
from PIL import Image, ImageDraw, ImageFont
import sys
import os

# Annotation configs for different action types
ANNOTATIONS = {
    "address_bar": {
        "box": (200, 45, 800, 85),  # x1, y1, x2, y2 (relative to 1200px width)
        "label": "Address Bar",
        "arrow_to": "top"
    },
    "new_tab": {
        "box": (750, 8, 850, 40),
        "label": "New Tab Button",
        "arrow_to": "top"
    },
    "type_url": {
        "box": (200, 45, 600, 85),
        "label": "Type: github.com",
        "arrow_to": "top"
    }
}

def annotate(img_path, action_type, output_path=None, custom_box=None, custom_label=None):
    """Add annotation to screenshot"""
    img = Image.open(img_path)
    draw = ImageDraw.Draw(img)
    
    # Get dimensions
    w, h = img.size
    scale = w / 1200  # Scale factor from 1200px base
    
    # Get annotation config
    if custom_box:
        box = tuple(int(x * scale) for x in custom_box)
        label = custom_label or action_type
    elif action_type in ANNOTATIONS:
        config = ANNOTATIONS[action_type]
        box = tuple(int(x * scale) for x in config["box"])
        label = config["label"]
    else:
        print(f"Unknown action type: {action_type}")
        return
    
    # Draw red box
    draw.rectangle(box, outline="#ff3333", width=3)
    
    # Draw label background
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(16 * scale))
    except:
        font = ImageFont.load_default()
    
    label_bbox = draw.textbbox((0, 0), label, font=font)
    label_w = label_bbox[2] - label_bbox[0]
    label_h = label_bbox[3] - label_bbox[1]
    
    label_x = box[0]
    label_y = box[1] - label_h - 10
    if label_y < 5:
        label_y = box[3] + 5
    
    # Draw label with background
    padding = 4
    draw.rectangle(
        (label_x - padding, label_y - padding, 
         label_x + label_w + padding, label_y + label_h + padding),
        fill="#ff3333"
    )
    draw.text((label_x, label_y), label, fill="white", font=font)
    
    # Save
    if output_path is None:
        base, ext = os.path.splitext(img_path)
        output_path = f"{base}_annotated{ext}"
    
    img.save(output_path)
    print(f"Annotated: {output_path}")
    return output_path

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: annotate_screenshot.py <image> <action_type> [output]")
        sys.exit(1)
    
    img_path = sys.argv[1]
    action_type = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    annotate(img_path, action_type, output_path)
