# Image Cache Handling — Family Health OS

## Problem

When users send images via the chat interface, the system inserts a `image_url` reference in the prompt.
However, this reference may:
1. Point to a file that doesn't exist yet (not yet written to disk)
2. Point to a previous image's cached path (stale)
3. Point to a path that was already garbage-collected

## Reproduction

```
User: [sends image A]
System prompt: image_url: /.../image_cache/img_A.jpg
Agent: calls vision_analyze(img_A.jpg) → OK

User: [sends image B]
System prompt: image_url: /.../image_cache/img_B.jpg  → Actually img_B.jpg doesn't exist yet!
Agent: calls vision_analyze(img_B.jpg) → Error: Invalid image source
```

## Root Cause

The system prompt generation is decoupled from the actual filesystem write.
The prompt may be constructed before the image cache is fully populated.

## Solution

### 1. Verify before calling

```python
import os

image_url = "/Users/.../image_cache/img_X.jpg"
if not os.path.exists(image_url):
    # Fallback: scan for the latest image
    cache_dir = "/Users/.../image_cache"
    jpg_files = sorted(
        [f for f in os.listdir(cache_dir) if f.endswith('.jpg')],
        key=lambda f: os.path.getmtime(os.path.join(cache_dir, f)),
        reverse=True
    )
    if jpg_files:
        image_url = os.path.join(cache_dir, jpg_files[0])
```

### 2. When handling multiple images in sequence

For each image the user sends:
1. Check if the system-provided `image_url` exists
2. If not, use the most recently modified `.jpg` in `image_cache/`
3. Call `vision_analyze` with the verified path
4. After processing, record the actual filename used in the exam record

### 3. For batch uploads (e.g., 5 CTPA slices)

```python
import os

cache_dir = "/Users/.../image_cache"
all_jpgs = sorted(
    [f for f in os.listdir(cache_dir) if f.endswith('.jpg')],
    key=lambda f: os.path.getmtime(os.path.join(cache_dir, f))
)

# Find the set of images uploaded in the current session
# (e.g., all files modified in the last 5 minutes)
from datetime import datetime, timedelta
now = datetime.now()
recent_files = [
    f for f in all_jpgs
    if datetime.fromtimestamp(os.path.getmtime(os.path.join(cache_dir, f))) > now - timedelta(minutes=5)
]

# Add all to the same exam record's images[]
```

## Verification

Always verify the image path before calling vision_analyze:
```
ls -la /path/to/image_cache/ | grep jpg | tail -5
```

## Related Pitfalls

- SKILL.md #22: "User description vs image content mismatch"
- SKILL.md #30: "System prompt image summary ≠ actual image"
- SKILL.md #29: "Batch image append to same exam record"
