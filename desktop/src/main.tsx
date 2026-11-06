import { createRoot } from 'react-dom/client';

function App() {
  return (
    <main>
      <h1>Respected Orchestrator</h1>
      <p>Masaüstü kabuğu çalışıyor. Motor bağlantısı sonraki görevde (B3-01.03).</p>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
