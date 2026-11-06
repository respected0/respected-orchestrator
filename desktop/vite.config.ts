import { defineConfig } from 'vite';

export default defineConfig({ server: { watch: { ignored: ['**/src-tauri/target/**', '**/src-tauri/gen/**'] } } });
