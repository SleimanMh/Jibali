// Render the illustrated scenes 01-05 (0-17 s, 408 frames at 24 fps) from jibali-motion.html.
// Usage:
//   node motion/render-motion.js video OUT.mp4
//   node motion/render-motion.js stills OUT_DIR 0.5 2 5.2 ...   (seconds)
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const FPS = 24, FRAMES = 408;
const page_url = "file://" + path.resolve(__dirname, "jibali-motion.html");

(async () => {
  const [mode, out, ...times] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.on("pageerror", e => { console.error("page error:", e.message); process.exitCode = 1; });
  await page.goto(page_url);
  await page.evaluate(() => window.ready);
  const canvas = await page.$("#c");
  const shot = async t => { await page.evaluate(t => window.render(t), t); return canvas.screenshot({ type: "png" }); };

  if (mode === "stills") {
    fs.mkdirSync(out, { recursive: true });
    for (const t of times) fs.writeFileSync(path.join(out, `t${t}.png`), await shot(parseFloat(t)));
  } else {
    const ff = spawn("ffmpeg", ["-v", "error", "-y", "-f", "image2pipe", "-c:v", "png", "-r", String(FPS), "-i", "-",
      "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
      "-c:v", "libx264", "-preset", "slow", "-crf", "14",
      "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
      "-an", out], { stdio: ["pipe", "inherit", "inherit"] });
    for (let i = 0; i < FRAMES; i++) {
      const buf = await shot(i / FPS);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
    }
    ff.stdin.end();
    await new Promise((res, rej) => ff.on("close", c => c === 0 ? res() : rej(new Error("ffmpeg " + c))));
  }
  await browser.close();
  console.log("done", out);
})();
