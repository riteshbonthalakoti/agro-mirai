// Local stand-in for the Vercel rewrites: serves this folder and forwards
// /admin/*, /v2/* and /health to the backend so the session cookie stays
// same-origin. Usage: BACKEND_URL=http://localhost:5001 node dev-server.mjs
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const backend = new URL(process.env.BACKEND_URL || "http://localhost:5000");
const port = Number(process.env.PORT || 3100);
const types = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".ico": "image/x-icon" };
const served = ["index.html", "style.css", "admin.js", "favicon.ico"];

http.createServer((req, res) => {
  if (/^\/(admin|v2|health)(\/|$|\?)/.test(req.url)) {
    const up = http.request(
      { host: backend.hostname, port: backend.port, path: req.url, method: req.method,
        headers: { ...req.headers, host: backend.host } },
      (r) => { res.writeHead(r.statusCode, r.headers); r.pipe(res); }
    );
    up.on("error", () => { res.writeHead(502); res.end("backend unreachable"); });
    req.pipe(up);
    return;
  }
  const p = req.url.split("?")[0];
  const name = p === "/" ? "index.html" : path.basename(p);
  if (!served.includes(name)) { res.writeHead(404); res.end("not found"); return; }
  res.writeHead(200, { "content-type": types[path.extname(name)] });
  fs.createReadStream(path.join(root, name)).pipe(res);
}).listen(port, () => console.log(`admin dashboard on http://localhost:${port} -> ${backend.href}`));
