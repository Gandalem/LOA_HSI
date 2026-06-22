import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import esbuild from 'esbuild';

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = join(__dirname, '..');
const distDir = join(rootDir, 'dist');
const assetsDir = join(distDir, 'assets');
const apiBase = process.env.VITE_API_BASE || '/api';

rmSync(distDir, { recursive: true, force: true });
mkdirSync(assetsDir, { recursive: true });

await esbuild.build({
  entryPoints: [join(rootDir, 'src', 'main.jsx')],
  outfile: join(assetsDir, 'app.js'),
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: ['es2020'],
  jsx: 'transform',
  loader: {
    '.js': 'js',
    '.jsx': 'jsx',
    '.css': 'css',
  },
  define: {
    'import.meta.env.VITE_API_BASE': JSON.stringify(apiBase),
  },
  minify: true,
  sourcemap: false,
  legalComments: 'none',
});

const sourceHtml = readFileSync(join(rootDir, 'index.html'), 'utf8');
const builtHtml = sourceHtml.replace(
  /<script\s+type="module"\s+src="\/src\/main\.jsx"><\/script>/,
  '<link rel="stylesheet" href="/assets/app.css" />\n    <script type="module" src="/assets/app.js"></script>',
);

writeFileSync(join(distDir, 'index.html'), builtHtml, 'utf8');
