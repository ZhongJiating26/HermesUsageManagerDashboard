import { React } from './platform/react-host';
import { getHealth, type Health } from './services/api';
import { Dashboard } from './Dashboard';
import { configureSource } from './services/preview';

export function PluginApp() {
  const [health, setHealth] = React.useState<Health | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [attempt, setAttempt] = React.useState(0);

  React.useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setHealth(null);
    setError(null);
    getHealth(controller.signal).then((result) => {
      if (active) { configureSource(result.data_source); setHealth(result); }
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : '请求失败');
    });
    return () => { active = false; controller.abort(); };
  }, [attempt]);

  if (health) return <Dashboard live={health.data_source === 'live'} ready={health.capabilities.business_api && health.capabilities.storage === 'ready'} />;

  return <section className="hum-root" aria-label="用量管理连接状态">
    <aside className="hum-sidebar">
      <p className="hum-caption">Hermes Usage Manager</p>
      <span className="hum-selected">用量管理</span>
      <p>宿主连接状态</p>
    </aside>
    <main className="hum-content">
      <p className="hum-caption">原生 Dashboard 插件</p>
      <h1>用量管理 · 连接 Hermes</h1>
      <div className="hum-card" aria-live="polite">
        {!health && !error && <p role="status">正在请求 /health…</p>}
        {error && <p role="alert">连接失败：{error}</p>}
        <button type="button" onClick={() => setAttempt((current) => current + 1)}>重新检查</button>
      </div>
    </main>
  </section>;
}
