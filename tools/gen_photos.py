#!/usr/bin/env python3
"""Generate site photos (theme-park key-visual style) via Vertex AI gemini-2.5-flash-image.

Usage:
  python3 tools/gen_photos.py [name ...]        # generate candidates _a/_b into tools/gen_out/ (skips existing)
  python3 tools/gen_photos.py --install name=variant ...   # e.g. cond-baby=a → static/img/photo/cond-baby-{480,800,1600}.webp

Auth: gcloud user token (project short-video-factory-492413). AI Studio key has no credit (402).
429 is common: the script waits and retries. Run progress lives in ~/workspace/company/kozure_photo_run.md
"""
import base64, json, pathlib, subprocess, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "gen_out"
PROJ = "short-video-factory-492413"
MODEL = "gemini-2.5-flash-image"

# Style learned from JUNGLIA / NESTA RESORT KOBE / 西武園ゆうえんち key visuals (2026-10-12).
BASE = ("Energetic Japanese theme-park / resort advertising photograph in the style of a key visual poster. "
        "Shot with a 24mm wide-angle lens very close to the subject, slight low angle, the child's face is large in the frame "
        "and looking straight into the camera. Vivid saturated colors, punchy contrast, bright commercial lighting with fill flash, "
        "crisp sharp focus, photorealistic, real Japanese kids in casual modern clothes (no kimono, no yukata). "
        "Parents may appear smaller and slightly blurred in the background, smiling. "
        "Absolutely no text, letters, kanji, signs or logos anywhere. No watermark. ")
JOY = "Exaggerated pure joy: mouth wide open laughing, eyes sparkling, dynamic motion. "
SOFT = "A big warm genuine smile, sparkling eyes, cheerful and lively but gentle. "

P = {
  # hero collage (installed 2026-10-12 as hero-hotel-*/hero-futon-play)
  # 条件から探す (tile 4:3)
  "cond-baby": ("4:3", SOFT + "A 10-month-old Japanese baby held up in a parent's arms very close to the camera, giggling with mouth open, "
      "reaching a chubby hand toward the lens, bright airy modern resort hotel room with a big window and blue sky behind."),
  "cond-babyfood": ("4:3", SOFT + "A 1-year-old Japanese baby in a white high chair at a bright hotel restaurant, face a little messy with baby food, "
      "laughing with mouth open as a parent's hand offers a small spoon, colorful little bowls of baby food on the tray."),
  "cond-cosleep": ("4:3", SOFT + "A 3-year-old Japanese toddler and a parent snuggled together under a fluffy white duvet on a big hotel bed, "
      "the toddler peeking out giggling at the camera, soft bright morning sunlight, cozy and playful."),
  "cond-crib": ("4:3", SOFT + "A 1-year-old Japanese baby standing in a white wooden baby crib in a bright hotel room, gripping the rail, "
      "huge gummy grin straight at the camera, parents' big bed blurred behind."),
  "cond-roommeal": ("4:3", JOY + "In a bright Japanese ryokan tatami room, a 5-year-old Japanese boy in casual clothes at a low table "
      "with a colorful children's meal tray (small dishes, shrimp tempura, rice ball) raising chopsticks in excitement toward the camera, "
      "his sister and parents laughing around the table."),
  "cond-privatebath": ("4:3", SOFT + "A 5-year-old Japanese girl wrapped fully in a big white bath towel with a small towel on her head, "
      "sitting on the wooden edge of a private open-air hinoki bath and dipping only her feet in the steaming water, laughing at the camera, "
      "green garden and blue sky behind. Fully covered, modest, family friendly."),
  "cond-kidsroom": ("4:3", JOY + "A 4-year-old Japanese boy jumping into a colorful ball pit in a bright hotel indoor kids' play room, "
      "balls flying around, his sister sliding down a small slide behind."),
  # 季節の特集 (wide 16:7 tile → generate 16:9)
  "season-newyear": ("16:9", JOY + "New Year's family trip: a 6-year-old Japanese girl in a warm winter coat and knit hat at a snowy hot spring town, "
      "holding a steaming fluffy mochi on a skewer close to the camera, cheeks rosy, crisp blue winter sky, parents behind. No shrine signs, no text."),
  "season-winter": ("16:9", JOY + "Winter holiday at a ski resort hotel: a 6-year-old Japanese boy in a bright red snowsuit sledding straight toward the camera, "
      "snow spraying up, his sister on a sled behind, deep blue sky and snowy mountains."),
}


def token():
    return subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()


def gen(prompt, ar, tok):
    url = f"https://aiplatform.googleapis.com/v1/projects/{PROJ}/locations/global/publishers/google/models/{MODEL}:generateContent"
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": ar}}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
    for part in d["candidates"][0]["content"]["parts"]:
        if "inlineData" in part:
            return base64.b64decode(part["inlineData"]["data"])
    raise RuntimeError("no image")


def generate(names):
    OUT.mkdir(parents=True, exist_ok=True)
    tok = token()
    todo = [(n, v) for n in names for v in "ab" if not (OUT / f"{n}_{v}.png").exists()]
    for n, v in todo:
        ar, p = P[n]
        for attempt in range(6):
            try:
                (OUT / f"{n}_{v}.png").write_bytes(gen(BASE + p, ar, tok))
                print("OK", n, v, flush=True)
                break
            except urllib.error.HTTPError as e:
                print("ERR", n, v, e.code, flush=True)
                time.sleep(30 if e.code in (429, 500, 503) else 5)
        else:
            print("FAIL", n, v, flush=True)


def install(pairs):
    from PIL import Image
    for pair in pairs:
        n, v = pair.split("=")
        im = Image.open(OUT / f"{n}_{v}.png").convert("RGB")
        for w in (480, 800, 1600):
            ww = min(w, im.width)
            im.resize((ww, round(im.height * ww / im.width)), Image.LANCZOS).save(
                ROOT / "static/img/photo" / f"{n}-{w}.webp", "WEBP", quality=78, method=6)
        print("installed", n, v)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--install":
        install(a[1:])
    else:
        generate(a or list(P))
