import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],build:{rollupOptions:{output:{manualChunks:{charts:['echarts/core','echarts/charts','echarts/components','echarts/renderers']}}}},server:{port:5173,proxy:{'/api':{target:'http://127.0.0.1:8000'},'/ws':{target:'ws://127.0.0.1:8000',ws:true}}}});
