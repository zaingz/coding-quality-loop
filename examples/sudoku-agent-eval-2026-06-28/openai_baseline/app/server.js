// Minimal static file server (no dependencies) for local play.
// ES modules require an http origin, so open the app via this server
// rather than the file:// protocol.
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const port = process.env.PORT ? Number(process.env.PORT) : 8080;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};

const server = http.createServer(async (req, res) => {
  try {
    const urlPath = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const relative = urlPath === '/' ? 'index.html' : urlPath.replace(/^\/+/, '');
    const filePath = normalize(join(root, relative));

    if (!filePath.startsWith(root)) {
      res.writeHead(403).end('Forbidden');
      return;
    }

    const data = await readFile(filePath);
    res.writeHead(200, { 'Content-Type': MIME[extname(filePath)] ?? 'application/octet-stream' });
    res.end(data);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' }).end('Not found');
  }
});

server.listen(port, () => {
  console.log(`Sudoku running at http://localhost:${port}`);
});
